#!/usr/bin/env python3
"""
Polymarket 5 分钟 Up/Down 订单簿记录器（只读）。

只调用三个公开只读 API，不认证、不放置任何订单：
  1. Gamma:    GET https://gamma-api.polymarket.com/markets?slug=<slug>&limit=1
               -> 解析 market 对象；clobTokenIds 是 JSON 编码字符串，需 json.loads 解析，
                  取出 Up 与 Down 两个 token id；同时取 conditionId、question、slug。
  2. CLOB:     GET https://clob.polymarket.com/book?token_id=<token_id>（Up 与 Down 各一次）
  3. Data API: GET https://data-api.polymarket.com/v2/trades?condition=<conditionId>&limit=100

Data API 适配说明：
  - v1（/trades?market=...）已退役，返回 410 {"error":"Data API v1 has been retired",...}。
  - v2 使用 /v2/trades，且查询参数名是 condition（不是 market；v2 错误提示原样：
    "'market' is not a query param on this API: filter by condition id with 'condition'"）。
  - v2 返回 {"data":[...],"pagination":...}；v2 将 v1 时代的 asset 字段更名为 token_id。
    因此对每条 trade 保留原始字段（token_id/side/size/price/timestamp/...）并额外写入
    asset = token_id，以满足任务规格的 schema 校验（asset/side/size/price/timestamp）。

每次轮询保存一个 JSON 文件到 <output_dir>/<slug>_<epoch>.json（默认 data/snapshots/），
文件键：recorded_at_utc / recorded_at_epoch / market{slug,conditionId,question,up_token_id,down_token_id}
        / book_up / book_down / trades_recent。

CLI: --slug | --auto-slug --output-dir --interval --duration --once

--auto-slug 模式（与 --slug 二选一）：
  - 每次轮询实时计算当前 5 分钟窗口：epoch = floor(now_utc/300)*300，
    slug = f"btc-updown-5m-{epoch}"。
  - 窗口切换（slug 变化）时重新拉取该市场的 Gamma 元数据并打印日志
    [window] switched to <new_slug> at <time>；同一窗口内缓存不重复拉取。
  - 若某窗口 slug 在 Gamma 查不到（防御性处理），原样报告响应并以非零码退出。
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

import requests

GAMMA_BASE = "https://gamma-api.polymarket.com"
CLOB_BASE = "https://clob.polymarket.com"
DATA_API_BASE = "https://data-api.polymarket.com"

REQUEST_TIMEOUT = 30

MAX_ATTEMPTS = 3
RETRY_SLEEP = 2.0

REQUIRED_TOP_KEYS = ("recorded_at_utc", "recorded_at_epoch", "market", "book_up", "book_down", "trades_recent")
REQUIRED_MARKET_KEYS = ("slug", "conditionId", "question", "up_token_id", "down_token_id")
REQUIRED_TRADE_KEYS = ("asset", "side", "size", "price", "timestamp")


class RecordingError(Exception):
    """网络韧性失败：fetch_json 重试耗尽后抛出，携带 URL 与最后一次异常。"""

    def __init__(self, url, last_exc):
        self.url = url
        self.last_exc = last_exc
        super().__init__(f"RecordingError: {url} 重试 {MAX_ATTEMPTS} 次仍失败: "
                         f"{last_exc.__class__.__name__}: {last_exc}")


def fetch_json(url, params):
    """GET 请求并返回 JSON。

    网络韧性（PATCH 1）：最多 MAX_ATTEMPTS(3) 次尝试，尝试间 sleep RETRY_SLEEP(2s)；
    仅捕获连接类异常 (ConnectTimeout, ReadTimeout, ConnectionError)；每次失败打
    [retry] 日志；第 3 次失败后抛 RecordingError（携带 URL 与最后一次异常）。
    HTTP 错误（raise_for_status）与 JSON 解析错误不属于捕获范围，原样向上抛。
    REQUEST_TIMEOUT 不变。
    """
    last_exc = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except (requests.exceptions.ConnectTimeout,
                requests.exceptions.ReadTimeout,
                requests.exceptions.ConnectionError) as exc:
            last_exc = exc
            print(f"[retry] {url} attempt {attempt}/{MAX_ATTEMPTS} failed: {exc.__class__.__name__}")
            if attempt < MAX_ATTEMPTS:
                time.sleep(RETRY_SLEEP)
    raise RecordingError(url, last_exc)


def get_market(slug):
    """Gamma: 按 slug 取唯一 market，解析 Up/Down 两个 token id。"""
    data = fetch_json(f"{GAMMA_BASE}/markets", {"slug": slug, "limit": 1})
    if not isinstance(data, list) or len(data) != 1:
        raise RuntimeError(f"Gamma /markets?slug={slug!r}&limit=1 未返回恰好 1 个 market: {data!r}")
    m = data[0]
    clob_token_ids = json.loads(m["clobTokenIds"])  # clobTokenIds 是 JSON 编码字符串
    if len(clob_token_ids) != 2:
        raise RuntimeError(f"clobTokenIds 应含 2 个 token id，实际 {len(clob_token_ids)} 个: {clob_token_ids!r}")
    return {
        "slug": m["slug"],
        "conditionId": m["conditionId"],
        "question": m["question"],
        "up_token_id": clob_token_ids[0],
        "down_token_id": clob_token_ids[1],
    }


def get_book(token_id):
    """CLOB: 单个 token 的订单簿（含 bids/asks 列表）。"""
    return fetch_json(f"{CLOB_BASE}/book", {"token_id": token_id})


def get_trades(condition_id, limit=100):
    """Data API v2: 取该 condition 最近的成交记录，并归一化 asset=token_id。"""
    data = fetch_json(f"{DATA_API_BASE}/v2/trades", {"condition": condition_id, "limit": limit})
    if not isinstance(data, dict) or "data" not in data:
        raise RuntimeError(f"Data API v2 /trades 返回结构异常: {data!r}")
    trades = []
    for t in data["data"]:
        t = dict(t)  # 拷贝，避免改动原始对象
        if "asset" not in t and "token_id" in t:
            # v2 将 v1 的 asset 更名为 token_id；补齐 asset 以通过规格 schema 校验
            t["asset"] = t["token_id"]
        trades.append(t)
    return trades


def validate_snapshot(snapshot):
    """最小 schema 校验：必需键存在；book 的 bids/asks 是列表；trade 有 asset/side/size/price/timestamp。"""
    missing = [k for k in REQUIRED_TOP_KEYS if k not in snapshot]
    if missing:
        raise ValueError(f"SchemaError: snapshot 缺少必需键 {missing}")
    market = snapshot["market"]
    missing = [k for k in REQUIRED_MARKET_KEYS if k not in market]
    if missing:
        raise ValueError(f"SchemaError: market 缺少必需键 {missing}")
    for key in ("book_up", "book_down"):
        book = snapshot[key]
        for side in ("bids", "asks"):
            if not isinstance(book.get(side), list):
                raise ValueError(f"SchemaError: {key}.{side} 不是列表: {book.get(side)!r}")
    for i, trade in enumerate(snapshot["trades_recent"]):
        missing = [k for k in REQUIRED_TRADE_KEYS if k not in trade]
        if missing:
            raise ValueError(f"SchemaError: trades_recent[{i}] 缺少必需键 {missing}; trade={trade!r}")


def build_snapshot(market, book_up, book_down, trades):
    now_epoch = int(time.time())
    return {
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "recorded_at_epoch": now_epoch,
        "market": market,
        "book_up": book_up,
        "book_down": book_down,
        "trades_recent": trades,
    }


def save_snapshot(snapshot, output_dir, slug):
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f"{slug}_{snapshot['recorded_at_epoch']}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2, ensure_ascii=False)
    return path


def main():
    parser = argparse.ArgumentParser(description="Polymarket 5 分钟 Up/Down 订单簿记录器（只读）")
    parser.add_argument("--slug", default=None, help="Gamma 市场 slug（与 --auto-slug 二选一）")
    parser.add_argument("--auto-slug", action="store_true",
                        help="自动按当前窗口计算 slug：epoch=floor(now_utc/window_sec)*window_sec，"
                             "slug=<asset>-updown-<window-minutes>m-<epoch>；窗口切换时重新拉取 Gamma 元数据并打印切换日志")
    parser.add_argument("--asset", default="btc", choices=["btc", "eth", "sol"],
                        help="资产代号（默认 btc），仅用于 --auto-slug 的 slug 前缀")
    parser.add_argument("--window-minutes", type=int, default=5, choices=[5, 15],
                        help="窗口长度分钟（默认 5），仅用于 --auto-slug 的窗口计算")
    parser.add_argument("--output-dir", default="data/snapshots", help="快照输出目录（默认 data/snapshots）")
    parser.add_argument("--interval", type=float, default=20.0, help="轮询间隔秒（默认 20）")
    parser.add_argument("--duration", type=float, default=None, help="总运行时长秒（默认不限，Ctrl-C 停止）")
    parser.add_argument("--once", action="store_true", help="只采集一次后退出")
    args = parser.parse_args()

    if args.auto_slug and args.slug:
        parser.error("--slug 与 --auto-slug 互斥，请二选一")
    if not args.auto_slug and not args.slug:
        parser.error("必须提供 --slug 或 --auto-slug 之一")

    def resolve_window():
        """返回当前应记录的 (slug, window_epoch)。--auto-slug 时按 --window-minutes 实时计算窗口。"""
        if args.auto_slug:
            window_sec = args.window_minutes * 60
            now_epoch = int(time.time())
            window_epoch = (now_epoch // window_sec) * window_sec  # floor(now_utc/window_sec)*window_sec
            return f"{args.asset}-updown-{args.window_minutes}m-{window_epoch}", window_epoch
        return args.slug, None

    market = None
    current_slug = None
    consecutive_failures = 0
    skipped = 0
    saved = 0

    start = time.time()
    poll_no = 0
    while True:
        poll_no += 1
        try:
            slug, _ = resolve_window()
            if slug != current_slug:
                # 窗口切换：重新拉取该市场的 Gamma 元数据；同一窗口内（slug 未变）走缓存
                print(f"[window] switched to {slug} at {datetime.now(timezone.utc).isoformat()}")
                market = get_market(slug)  # slug 查不到时抛出含原样响应的 RuntimeError
                current_slug = slug
                print(f"[init] slug={market['slug']!r} conditionId={market['conditionId']!r}")
                print(f"[init] up_token_id={market['up_token_id']!r}")
                print(f"[init] down_token_id={market['down_token_id']!r}")
            print(f"[poll {poll_no}] {datetime.now(timezone.utc).isoformat()}")
            book_up = get_book(market["up_token_id"])
            book_down = get_book(market["down_token_id"])
            trades = get_trades(market["conditionId"])
            snapshot = build_snapshot(market, book_up, book_down, trades)
            validate_snapshot(snapshot)  # 校验失败时 raise，错误原样向上抛
            path = save_snapshot(snapshot, args.output_dir, current_slug)
            print(f"[saved] {path}")
            saved += 1
            consecutive_failures = 0  # 成功一轮，清零连败计数
            if args.once:
                print("[done] --once：单次快照已保存")
                return 0
        except RecordingError as e:
            # 网络韧性（PATCH 2）：单轮失败不退出，打 [skip] 日志并计数
            skipped += 1
            consecutive_failures += 1
            print(f"[skip] poll failed at {datetime.now(timezone.utc).isoformat()}: {e}")
            if consecutive_failures >= 5:
                # 仅当连续 5 轮失败才退出进程
                print(f"[fatal] consecutive_failures={consecutive_failures} >= 5，退出")
                return 1
            if args.once:
                # --once 语义：失败也退出，但明确报告未保存（不假装成功）
                print(f"[done] --once：本轮失败（{e.__class__.__name__}），未保存快照")
                return 1

        if args.duration is not None and (time.time() - start) >= args.duration:
            print(f"[done] duration={args.duration}s polls={poll_no} skipped={skipped} saved={saved}")
            return 0
        time.sleep(args.interval)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("[interrupted] Ctrl-C")
        sys.exit(130)
    except RuntimeError as e:
        # 防御性处理：例如 --auto-slug 下某窗口 slug 在 Gamma 查不到，原样报告响应并停下
        print(f"[fatal] {e}")
        sys.exit(1)
