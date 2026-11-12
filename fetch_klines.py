#!/usr/bin/env python3
"""fetch_klines.py — 从 Binance 拉 BTC 1 分钟 K 线，覆盖 round1_design 快照的时间范围。"""
import csv, json, glob, time
from pathlib import Path
import requests

SNAPSHOT_DIR = Path("data/snapshots/round1_design")
OUT = SNAPSHOT_DIR / "btc_klines_1m.csv"
BINANCE = "https://api.binance.com/api/v3/klines"

# 1. 收集所有 recorded_at_epoch
epochs = []
for f in glob.glob(str(SNAPSHOT_DIR / "btc-updown-5m-*.json")):
    try:
        d = json.loads(Path(f).read_text())
        epochs.append(int(d["recorded_at_epoch"]))
    except Exception:
        pass

if not epochs:
    raise SystemExit("No snapshots found.")

start = min(epochs) - 60
end = max(epochs) + 60
start_ms = start * 1000
end_ms = end * 1000
print(f"Fetching BTC 1m klines from {start} to {end} ({end-start} seconds)...")

# 2. 分页拉（Binance 单次最多 1000 根）
rows = []
cur = start_ms
while cur < end_ms:
    params = {"symbol": "BTCUSDT", "interval": "1m", "startTime": cur, "endTime": end_ms, "limit": 1000}
    r = requests.get(BINANCE, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    if not data:
        break
    rows.extend(data)
    cur = data[-1][0] + 60000  # 下一分钟
    time.sleep(0.3)  # 避免限流
    if len(data) < 1000:
        break

# 3. 写 CSV
with OUT.open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["open_time_ms", "open_time_utc", "open", "high", "low", "close", "volume"])
    for row in rows:
        open_ms = int(row[0])
        utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(open_ms/1000))
        w.writerow([open_ms, utc, row[1], row[2], row[3], row[4], row[5]])

print(f"Wrote {len(rows)} rows to {OUT}")