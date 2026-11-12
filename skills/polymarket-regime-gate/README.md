# polymarket-regime-gate

Reusable Polymarket 5-min Up/Down regime gate for dual-sided 0.48/0.48 preorders.

## What this package contains
- skills/polymarket-regime-gate/SKILL.md  (this contract)
- config.yaml                              (frozen thresholds + strategy)
- scripts/classify.py                      (offline classifier)
- scripts/record.py                        (read-only snapshot recorder)
- examples/                                (3 snapshots, one per label)

## Quick start

# 1. Install deps
pip install requests pyyaml

# 2. Run the classifier on a bundled example
python3 skills/polymarket-regime-gate/scripts/classify.py \
  skills/polymarket-regime-gate/examples/goldilocks.json

# 3. To record your own snapshots (read-only public APIs):
python3 skills/polymarket-regime-gate/scripts/record.py \
  --auto-slug --output-dir data/snapshots/

## Supported markets and threshold overrides
This package is calibrated for the **BTC 5-minute** Up/Down market only. The frozen thresholds (spread_max 0.02, mid_distance_max 0.05, recent_trade_count_min 3, locked_mid_min 0.30) are **not directly transferable** to ETH or to other time windows — recalibrate before applying them elsewhere.

You can override thresholds per-run on the CLI without editing config.yaml. Priority: **CLI > config.yaml > defaults**. From inside the skill package directory (`skills/polymarket-regime-gate/`):

# Override a threshold for one classification (e.g., loosen the mid-distance gate)
python3 classify.py snapshot.json --mid-distance-max 0.10

# Parameterized recording: asset and window only affect --auto-slug slug naming/windowing
python3 record.py --auto-slug --asset eth --window-minutes 5

## What "GO" means
GO is not a profit guarantee. It means: current regime satisfies the strict goldilocks definition (narrow spread, mid near 0.5, recent trade activity ≥ 3 in the last 60 seconds). The evaluation found goldilocks in 3.5% of the 399-snapshot design set (18.9% among the 53 active snapshots). The gate's primary value is avoiding the 31.8% of snapshots where a naive dual-sided strategy would lose one leg (resolved_pending 27.8% + locked_two_sided 4.0%). See artifacts/evaluation_report_v2.md in the parent repo for the full evaluation.

## Limitations
- Fill simulation is conservative (next snapshot only, 20s gap).
- Single-day design set; goldilocks rate may shift on other days.
- Settlement uses Chainlink 30s TWAP; order-book features are a proxy.

## Attribution and openJiuwen link
Built on the WorkSwarm / JiuwenSwarm environment.
Link: https://github.com/openJiuwen-ai/jiuwenswarm

## License
(Leave as TODO for now — will fill in when publishing to GitHub.)