# polymarket-regime-gate

Scope: decides GO / WAIT / NO-GO for dual-sided 0.48/0.48 preorders on Polymarket 5-minute BTC Up/Down markets, based on order-book regime classification.

## What it does
Classifies one snapshot into exactly one of five regimes using four frozen thresholds, then maps regime to a decision:
  goldilocks       → GO
  quiet            → WAIT
  resolved_pending → NO-GO
  locked_two_sided → NO-GO
  unclassified     → NO-GO

## Inputs
- A single snapshot JSON produced by scripts/record.py, with keys: recorded_at_epoch, market, book_up, book_down, trades_recent.
- The 4 thresholds in config.yaml (read at load time).
- Optional: config.yaml override to change thresholds.
- Optional: CLI flags (--spread-max, --mid-distance-max, --recent-min, --locked-mid-min) override config.yaml thresholds; priority: CLI > config.yaml > defaults.

## Outputs
- One line of JSON to stdout: label, decision, spread_max, mid_distance_from_half, recent_count, one_sided.
- Exit code 0 on success, 1 on schema error or file error, 2 on usage error.

## Procedure
1. Load thresholds from config.yaml (fallback to defaults if absent).
2. Compute four measurements from the snapshot.
3. Apply the five-way classification (priority order matters).
4. Emit JSON with label + decision + measurements.

## Checks
- Self-test on the three examples in examples/:
    python3 scripts/classify.py examples/goldilocks.json
    → label=goldilocks, decision=GO
    python3 scripts/classify.py examples/quiet.json
    → label=quiet, decision=WAIT
    python3 scripts/classify.py examples/resolved_pending.json
    → label=resolved_pending, decision=NO-GO
- All three must pass on a fresh load; if any fails, the skill is not correctly packaged.

## Failure handling
- Missing file / bad JSON → stderr message, exit 1.
- Missing required key → ClassifyError, exit 1.
- If one_sided field in the snapshot disagrees with the derived one_sided → ClassifyError, exit 1.
- If config.yaml is missing → fall back to defaults, print one stderr warning, do NOT exit.

## Limitations
- "Fill simulation is conservative: checks next snapshot only, not full path."
- "Settlement uses Chainlink 30s TWAP; order-book features are a proxy."
- "Single-day design set; goldilocks rate may shift on other days."

## Reused work / attribution
- Snapshot schema: produced by scripts/record.py in this same package.
- Threshold values: frozen on 2026-11-11 after design-set analysis on 399 snapshots.
- See README.md for the full evaluation and source data reference.