#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
classify.py — Polymarket 5 分钟 Up/Down 快照体制分类器（离线、只读）

用法: python3 scripts/classify.py <snapshot.json 路径> [--spread-max F] [--mid-distance-max F] [--recent-min N] [--locked-mid-min F]
      CLI 阈值覆盖优先级: CLI 参数 > config.yaml > 默认值。
成功: stdout 输出一行 JSON（label / decision / 四个测量值），退出码 0
失败: stderr 输出错误信息，退出码非 0

硬边界: 全程离线，只读传入的快照 JSON，不请求任何 API；不修改任何文件。

冻结分类条件（判定顺序即优先级，先命中先返回，一字不改）:
  1. resolved_pending := (one_sided == true)
  2. quiet          := (spread_max < 0.02) AND (recent_count < 3) AND NOT one_sided
  3. goldilocks     := (spread_max < 0.02) AND (mid_distance_from_half < 0.05)
                       AND (recent_count >= 3) AND (one_sided == false)
  4. locked_two_sided := (spread_max < 0.02) AND (mid_distance_from_half >= 0.30)
                       AND (recent_count >= 3) AND NOT one_sided
  5. unclassified   := 其余一切（else 兜底）

决策映射: goldilocks -> GO | quiet -> WAIT | resolved_pending -> NO-GO
          locked_two_sided -> NO-GO | unclassified -> NO-GO

四个测量值口径（与 v3 分析一致，见 /tmp/round1_rows_v3.json 与
artifacts/round1_design_analysis_v3.md，本文件为权威注释）:
  - spread_max = max(spread_up, spread_down)；每个 token 簿 spread = best_ask - best_bid (float)。
    CLOB 陷阱: bids 数组升序、asks 数组降序 → best_bid 取 max(bids[].price)、
    best_ask 取 min(asks[].price)。CLOB 口径下若某侧最佳价为 None（同侧无价）则该侧 spread 为 None；
    spread_max 仅在 up/down 两侧 spread 均非 None 时取 max，否则为 None（v3 口径，全量 399 行对账一致）。
  - mid_distance_from_half = max(|up_mid - 0.5|, |down_mid - 0.5|)，其中
    up_mid = (best_bid_up + best_ask_up) / 2（该侧两侧均有价才定义，否则 None），down_mid 同理；
    均取非 None 的 mid 计算，无任何 mid 时 None（v3 口径: 更偏离 0.5 的一侧，全量对账一致）。
  - recent_count = trades_recent 中满足 trade.timestamp >= recorded_at_epoch - 60 的条数
    （trade.timestamp 为 unix 秒）。
  - one_sided = (book_up.bids 空 OR book_up.asks 空) OR (book_down.bids 空 OR book_down.asks 空)，
    从簿面推导而非读字段；若快照内存在 one_sided 字段则交叉核对，两者不一致时报错。
"""

import argparse
import json
import os
import sys

try:
    import yaml
except ImportError:
    yaml = None

DECISION_MAP = {
    "goldilocks": "GO",
    "quiet": "WAIT",
    "resolved_pending": "NO-GO",
    "locked_two_sided": "NO-GO",
    "unclassified": "NO-GO",
}

# 冻结默认阈值（config.yaml 缺失 / yaml 模块不可用 / 解析失败时的回退值，与用户给定值一致）
DEFAULT_THRESHOLDS = {
    "spread_max": 0.02,
    "mid_distance_max": 0.05,
    "recent_trade_count_min": 3,
    "locked_mid_min": 0.30,
}


def _load_thresholds():
    """从 config.yaml 加载 thresholds 四项，映射到分类阈值。

    定位优先级: <脚本所在目录上一级>/config.yaml（skill 包 config 优先） ->
                repo_root/config.yaml -> CWD/config.yaml -> 默认阈值。
    文件缺失、yaml 不可用或解析失败时回退默认值（不报错退出，stderr 打一行提示）。
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(script_dir)  # scripts/ 的上一级
    # 定位优先级: script_dir/../config.yaml（skill 包 config 优先） ->
    #             repo_root/config.yaml -> CWD/config.yaml -> DEFAULT_THRESHOLDS
    candidates = [
        os.path.join(script_dir, "..", "config.yaml"),  # skill 包 config 优先
        os.path.join(repo_root, "config.yaml"),
        os.path.join(os.getcwd(), "config.yaml"),
    ]
    for path in candidates:
        if not os.path.exists(path):
            continue
        if yaml is None:
            print(f"Warning: PyYAML 不可用，无法解析 {path}，使用默认阈值", file=sys.stderr)
            return dict(DEFAULT_THRESHOLDS)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            th = (data or {}).get("thresholds") or {}
            return {k: th.get(k, v) for k, v in DEFAULT_THRESHOLDS.items()}
        except Exception as e:
            print(f"Warning: 加载 config.yaml 失败（{path}）: {e}，使用默认阈值", file=sys.stderr)
            return dict(DEFAULT_THRESHOLDS)
    return dict(DEFAULT_THRESHOLDS)


_TH = _load_thresholds()

SPREAD_THRESHOLD = _TH["spread_max"]          # config.yaml thresholds.spread_max
MID_NEAR_THRESHOLD = _TH["mid_distance_max"]  # config.yaml thresholds.mid_distance_max
MID_FAR_THRESHOLD = _TH["locked_mid_min"]     # config.yaml thresholds.locked_mid_min
QUIET_RECENT_LIMIT = _TH["recent_trade_count_min"]  # config.yaml thresholds.recent_trade_count_min


class ClassifyError(Exception):
    """分类器输入错误（文件读不到 / JSON 解析失败 / 缺关键字段）。"""


def _side_best(book, side):
    """返回一侧簿的最佳买/卖价。bids 升序、asks 降序 → best_bid=max、best_ask=min。"""
    items = book.get(side)
    if not isinstance(items, list):
        raise ClassifyError(f"SchemaError: book.{side} 不是列表: {items!r}")
    if not items:
        return None
    return float(max(x["price"] for x in items)) if side == "bids" \
        else float(min(x["price"] for x in items))


def _spread(best_bid, best_ask):
    """单侧簿 spread；任一侧无价则为 None（不定义）。"""
    if best_bid is None or best_ask is None:
        return None
    return best_ask - best_bid


def _one_sided_from_book(book):
    """簿面单边判定：bids 空或 asks 空即该侧单边。"""
    return not book.get("bids") or not book.get("asks")


def measure(snapshot):
    """从快照计算四个测量值（口径见模块 docstring）。"""
    missing = [k for k in ("recorded_at_epoch", "book_up", "book_down", "trades_recent") if k not in snapshot]
    if missing:
        raise ClassifyError(f"SchemaError: snapshot 缺少必需键 {missing}")

    recorded_epoch = snapshot["recorded_at_epoch"]
    bu, bd = snapshot["book_up"], snapshot["book_down"]

    # one_sided: 从簿面推导；若快照内有该字段则交叉核对
    derived_os = _one_sided_from_book(bu) or _one_sided_from_book(bd)
    stored_os = snapshot.get("one_sided")
    if stored_os is not None and bool(stored_os) != derived_os:
        raise ClassifyError(
            f"one_sided 不一致: 簿面推导={derived_os}, 快照字段={stored_os}"
        )

    # 单侧 spread 与 mid
    bbu, bau = _side_best(bu, "bids"), _side_best(bu, "asks")
    bbd, bad = _side_best(bd, "bids"), _side_best(bd, "asks")
    spread_up = _spread(bbu, bau)
    spread_down = _spread(bbd, bad)
    spread_max = None if (spread_up is None or spread_down is None) else max(spread_up, spread_down)

    up_mid = None if (bbu is None or bau is None) else (bbu + bau) / 2.0
    down_mid = None if (bbd is None or bad is None) else (bbd + bad) / 2.0
    dists = [abs(m - 0.5) for m in (up_mid, down_mid) if m is not None]
    mid_distance_from_half = max(dists) if dists else None

    trades = snapshot["trades_recent"]
    if not isinstance(trades, list):
        raise ClassifyError(f"SchemaError: trades_recent 不是列表: {trades!r}")
    recent_count = sum(1 for t in trades if isinstance(t, dict) and t.get("timestamp") >= recorded_epoch - 60)

    return {
        "spread_max": spread_max,
        "mid_distance_from_half": mid_distance_from_half,
        "recent_count": recent_count,
        "one_sided": derived_os,
    }


def classify(m, th=None):
    """按冻结分类条件判定标签（顺序即优先级）。spread/mid 为 None 时不满足任何 < 阈值比较。

    th: 可选阈值 dict（CLI 覆盖后的最终阈值）；缺省用模块级 _TH（config.yaml > 默认值）。
    """
    if th is None:
        th = _TH
    sm, md, rc, os_ = m["spread_max"], m["mid_distance_from_half"], m["recent_count"], m["one_sided"]
    spread_t = th["spread_max"]
    mid_near_t = th["mid_distance_max"]
    mid_far_t = th["locked_mid_min"]
    recent_t = th["recent_trade_count_min"]
    if os_:
        return "resolved_pending"
    if sm is not None and sm < spread_t and rc < recent_t:
        return "quiet"
    if sm is not None and sm < spread_t and md is not None and md < mid_near_t and rc >= recent_t:
        return "goldilocks"
    if sm is not None and sm < spread_t and md is not None and md >= mid_far_t and rc >= recent_t:
        return "locked_two_sided"
    return "unclassified"


def main(argv):
    parser = argparse.ArgumentParser(
        description="Polymarket 5 分钟 Up/Down 快照体制分类器（离线、只读）")
    parser.add_argument("snapshot", help="快照 JSON 路径")
    parser.add_argument("--spread-max", type=float, default=None,
                        help="覆盖 thresholds.spread_max（CLI > config.yaml > 默认值）")
    parser.add_argument("--mid-distance-max", type=float, default=None,
                        help="覆盖 thresholds.mid_distance_max（CLI > config.yaml > 默认值）")
    parser.add_argument("--recent-min", type=int, default=None,
                        help="覆盖 thresholds.recent_trade_count_min（CLI > config.yaml > 默认值）")
    parser.add_argument("--locked-mid-min", type=float, default=None,
                        help="覆盖 thresholds.locked_mid_min（CLI > config.yaml > 默认值）")
    args = parser.parse_args(argv[1:])

    # 最终阈值: CLI 覆盖项优先于 _TH（_TH 本身 = config.yaml > 默认值）
    th = dict(_TH)
    for key, cli_val in (
        ("spread_max", args.spread_max),
        ("mid_distance_max", args.mid_distance_max),
        ("recent_trade_count_min", args.recent_min),
        ("locked_mid_min", args.locked_mid_min),
    ):
        if cli_val is not None:
            th[key] = cli_val

    path = args.snapshot
    try:
        with open(path, "r", encoding="utf-8") as f:
            snapshot = json.load(f)
    except FileNotFoundError:
        print(f"Error: 文件不存在: {path}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as e:
        print(f"Error: JSON 解析失败: {path}: {e}", file=sys.stderr)
        return 1
    except OSError as e:
        print(f"Error: 读取失败: {path}: {e}", file=sys.stderr)
        return 1

    try:
        m = measure(snapshot)
    except ClassifyError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    label = classify(m, th)
    out = {
        "label": label,
        "decision": DECISION_MAP[label],
        "spread_max": m["spread_max"],
        "mid_distance_from_half": m["mid_distance_from_half"],
        "recent_count": m["recent_count"],
        "one_sided": m["one_sided"],
    }
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))