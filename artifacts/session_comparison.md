# Session Comparison: Original 399 vs Round2 Session A / Session B

*Generated: 2026-11-15. Read-only analysis; `config.yaml` / `classify.py` NOT modified.*

## 0. Data coverage and cleaning

- Source: `data/snapshots/round2_dual_session/` — **11,589 JSON snapshots** (≈1.0 GB), 0 parse failures.
- Schema identical to round1; measurements computed by **reusing `scripts/classify.py` `measure()` + `classify()`** (same frozen logic as `round1_design_analysis_v3.md`), thresholds from `config.yaml` (`spread_max=0.02`, `mid_distance_max=0.05`, `recent_trade_count_min=3`, `locked_mid_min=0.30`).
- Actual coverage: **2026-11-13 11:40Z → 2026-11-14 18:00Z** (two calendar days).

**Honest discrepancy note:** the crash gap is *not* 16:00–22:00 UTC as stated in the task brief. Hourly counts show a real gap of **~18:00Z (11-13) → 05:00Z (11-14) ≈ 11 h** (hour-18 has only 3 snapshots on each day). Additionally, `2026-11-14 hour 14` has only **369** snapshots (vs ~610 for neighbouring hours) — a ~40% sampling shortfall within that hour; results below are insensitive to it (verified per-day).

**Grouping rule:** by UTC hour of `recorded_at_utc`; hours with <100 snapshots dropped (hour 18 on both days — crash points).

| Dataset | UTC hours | n snapshots | days included |
|---|---|---|---|
| Original 399 baseline | — (round1_design) | 399 | 2026-11-11 |
| Session A | 06–10 | 2,452 | 11-14 only (11-13 data starts at 11:40Z) |
| Session B | 12–16 | 4,640 | 11-13 + 11-14 |

## 1. Regime share comparison (Task 2.1)

Percent of snapshots per label, same five-way classifier, same thresholds.

| Label | Original 399 (n=399) | Session A (n=2,452) | Session B (n=4,640) |
|---|---|---|---|
| goldilocks | **3.5%** (14) | 3.2% (79) | **2.0%** (93) |
| quiet | 51.1% (204) | 57.2% (1,402) | 50.4% (2,337) |
| resolved_pending | 27.8% (111) | 19.2% (470) | 20.0% (930) |
| locked_two_sided | 4.0% (16) | 4.5% (110) | 2.7% (126) |
| unclassified | 13.5% (54) | 15.9% (391) | 24.9% (1,154) |

## 2. Distribution comparison (Task 2.2–2.3)

| Metric | Original 399 | Session A | Session B |
|---|---|---|---|
| median `spread_max` | 0.0100 | 0.0100 | 0.0100 |
| share with `spread_max` < 0.02 | 94.1% (271/288) | 92.3% (1,829/1,982) | **80.7%** (2,995/3,710) |
| median `recent_count` | 0 | 0 | 0 |
| mean `recent_count` | 15.91 | 10.73 | 10.89 |
| share with `recent_count` ≥ 3 | 19.0% (76/399) | 19.2% (472/2,452) | 18.4% (856/4,640) |
| avg `mid_distance_from_half` (not one_sided) | 0.2763 | 0.2475 | 0.2489 |

Per-hour detail (round2, full day; hours with n≥100):

| hour | n | goldilocks | quiet | median rc |
|---|---|---|---|---|
| 05 | 612 | 2.8% | 46.2% | 0 |
| 06 | 613 | 3.3% | 58.7% | 0 |
| 07 | 613 | 4.2% | 53.2% | 0 |
| 08 | 613 | 2.4% | 61.5% | 0 |
| 09 | 613 | 2.9% | 55.3% | 0 |
| 10 | 617 | 2.1% | 62.6% | 0 |
| 11 | 820 | 2.3% | 58.2% | 0 |
| 12 | 1,226 | 2.6% | 56.0% | 0 |
| 13 | 1,214 | 1.9% | 54.8% | 0 |
| 14 | 975 | 1.5% | 45.4% | 0 |
| 15 | 1,225 | 1.9% | 44.3% | 0 |
| 16 | 1,223 | 1.4% | 48.1% | 0 |
| 17 | 1,219 | 1.3% | 42.5% | 0 |
| 18 | 6 | (n<100, ignored) | | |

## 3. Critical findings (Task 3)

### Q1. Does the goldilocks rate *increase* in Session B vs the 399 baseline?

**No — it significantly *decreases*.** Two-proportion z-test: Session B 2.0% (93/4640) vs baseline 3.5% (14/399) → **z = 2.00, p = 0.0455** (significant at α=0.05, direction: lower). Session A 3.2% vs baseline is not significant (z = 0.30, p = 0.24).

The expectation "Europe-US overlap is more liquid → more goldilocks" is **not supported**. The regime share shift in Session B is towards *unclassified* (24.9% vs 13.5% baseline), driven mainly by wider spreads (only 80.7% of Session B snapshots have `spread_max` < 0.02 vs 94.1% baseline).

### Q2. Is `recent_count` significantly higher in Session B than in Session A?

**No.** Mann–Whitney U on `recent_count`: U = 5,723,030, **z = 0.61, p = 0.46** — not significant. Both sessions have median 0 and near-identical means (10.89 vs 10.73). Session B vs baseline is also not significant (p = 0.38). At the 5 s sampling interval both sessions are dominated by zero-trade-in-60s snapshots (~55–58% quiet).

### Q3. Are the original thresholds *too strict* for Session B?

**The `recent_trade_count_min` is not too strict — raising it would be wrong.** The task-brief hypothesis ("if 90% of Session B has recent_count > 10, threshold should be 10") is **not supported by the data**: only **17.6%** of Session B snapshots have `recent_count ≥ 10` (and 18.4% have ≥ 3). Raising the recent threshold to 10 would cut goldilocks from 93 → 89 (2.0% → 1.9%), i.e. it would *tighten*, not loosen.

The binding constraint in Session B is **`spread_max`**, not `recent_count`. Sensitivity (Session B, only one knob changed):

| Candidate threshold change | goldilocks count | goldilocks rate |
|---|---|---|
| current (0.02 / 0.05 / 3 / 0.30) | 93 | 2.0% |
| `--recent-min 0` (drop recent gate) | 286 | 6.2% |
| `--recent-min 10` | 89 | 1.9% |
| `--spread-max 0.03` | 104 | 2.2% |
| `--mid-distance-max 0.10` | 199 | 4.3% |
| `--spread-max 0.03 --mid-distance-max 0.10` | 227 | 4.9% |

## 4. Proposal: time-of-day dynamic thresholds

**Recommended — keep recent gate as-is, optionally relax `mid_distance_max` for Session B hours:**

1. **`recent_trade_count_min`: keep 3 (do NOT raise).** No evidence of higher recent activity in either session; the gate's job (only trade in active windows) is preserved. Raising to 10 contradicts the data.
2. **`spread_max`: keep 0.02.** Median spread is identical (0.0100) across all three datasets; the wider Session B tail (p95 = 0.04 vs 0.02) argues *against* loosening — 0.02 already filters out the riskier wide-spread tail.
3. **`mid_distance_max`: the only lever with material headroom — Session B hours (12–16 UTC): 0.05 → 0.10.** Doubles the GO candidates (93 → 199, 2.0% → 4.3%) while staying below the `locked_mid_min` 0.30 far gate. Optional; should be validated out-of-sample before freezing.
4. **`locked_mid_min`: keep 0.30** (no signal for change).

**Verdict:** the original thresholds are *not* too strict for Session B — the sessions are statistically indistinguishable on activity, and the goldilocks shortage is structural (mid far from 0.5 in ~90% of non-one-sided snapshots, same as baseline). Time-of-day dynamic thresholds are **not clearly justified by this data**; if one knob is to move for Session B, it is `mid_distance_max`, with out-of-sample validation required.

## 5. Method notes

- Classifier reuse: `scripts/classify.py` `measure()`/`classify()` imported directly → identical definitions to `round1_design_analysis_v3.md` (spread_max = max of both sides; mid_distance_from_half = more-deviant side; recent_count = 60 s window; one_sided from book, cross-checked).
- Baseline 399 recount matches prior reconciliation exactly: 14 goldilocks / 204 quiet / 111 resolved / 16 locked / 54 unclassified (0 mismatch vs `artifacts/classify_reconciliation.md`).
- No files in `round1_design/` were modified; no `config.yaml`/`classify.py` changes; no git.
