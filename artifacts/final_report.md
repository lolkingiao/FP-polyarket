# Polymarket 5-Minute Up/Down Dual-Sided Preorder Gate
## A regime classification workflow using WorkSwarm

### 1. The Finance Problem (0.5 page)

The user is a trader who currently places dual 0.48/0.48 BUY orders on both sides of Polymarket 5-minute BTC Up/Down markets [source: artifacts/evaluation_report_v2.md §1]. The strategy works only when both legs fill: total cost 0.96, settlement pays 1.00, net +0.04 per snapshot [source: artifacts/evaluation_report_v2.md §1]. It fails in two ways. In quiet markets the legs do not fill and the capital idles — 51.1% of the design set has zero trades inside the last 60 seconds [source: artifacts/round1_design_analysis_v3.md §0]. In trending markets only one leg fills, tying up 0.48 in a position that resolves against the trader [source: artifacts/evaluation_report_v2.md §1, §3].

Properly framed, this is execution-risk-aware parity monitoring, not arbitrage: a midquote sum below 1.00 is not executable profit — fill risk decides the outcome [source: artifacts/evaluation_report_v2.md §1, §3]. What was missing was a method to decide ex ante whether placing the dual order is appropriate in the current market state [source: artifacts/evaluation_report_v2.md §4].

### 2. Data and Method (0.75 page)

**Data.** 399 snapshots over 34 windows of 5-minute BTC Up/Down markets on Polymarket, recorded on 2026-11-11 UTC across two user-defined recording segments A and B; one DNS failure was gracefully skipped by the recorder's resilience patch [source: artifacts/round1_design_analysis.md §0, §1, 附录A (all timestamps 2026-11-11T…Z); data/snapshots/round1_design_resume.log ([skip] at 2026-11-11T12:26:19Z); artifacts/evaluation_report_v2.md §1]. The recorder (scripts/record.py) is read-only: it polls three public endpoints — Gamma /markets, CLOB /book, Data API v2 /trades — and writes one JSON snapshot per 20 s [source: artifacts/round1_design_analysis.md §6 (Data API /v2/trades?limit=100); scripts/record.py].

**Method.** Five-way regime classification with four frozen thresholds [source: artifacts/round1_design_analysis_v3.md §0; skills/polymarket-regime-gate/SKILL.md]:

    goldilocks       = spread < 0.02 ∧ mid_dist < 0.05 ∧ recent ≥ 3 ∧ not one_sided
    quiet            = spread < 0.02 ∧ recent < 3 ∧ not one_sided
    resolved_pending = one_sided
    locked_two_sided = spread < 0.02 ∧ mid_dist ≥ 0.30 ∧ recent ≥ 3 ∧ not one_sided
    unclassified     = else

Decision mapping: goldilocks → GO; quiet → WAIT; resolved_pending / locked_two_sided / unclassified → NO-GO [source: skills/polymarket-regime-gate/SKILL.md, §What it does; artifacts/evaluation_report_v2.md §1].

### 3. WorkSwarm Use — Evidence (0.75 page)

**a. Recorder development.** The recorder's docstring explicitly documents all three API mismatches found in real execution: Data API v1 retired (HTTP 410), v2 uses `condition` not `market`, and v2 renames `asset`→`token_id` [source: scripts/record.py docstring + round1_design_analysis.md §6].

**b. Network resilience.** A pre-patch ConnectTimeout terminated the recorder (see data/snapshots/round1_design_2h.log traceback). After the patch, a DNS failure at 2026-11-11T12:26:19Z was gracefully handled by the [skip] handler (see data/snapshots/round1_design_resume.log) [source: _2h.log traceback + _resume.log [skip] line].

(see evidence/S2.png)

**c. Agent Check.** classify.py was verified on 3 known snapshots and then on the full 399-snapshot batch: 0/399 label mismatch, 0/399 decision mismatch, fully diagonal confusion matrix, 12.36 s total runtime [source: artifacts/classify_reconciliation.md §a–§e].

(see evidence/S1.png)

**d. Config discrepancy.** WorkSwarm detected a stale config.yaml on disk, backed it up to /tmp/config.yaml.pre_task_a.bak, smoke-tested that config changes propagate (spread_max 0.02→0.01 flipped a quiet snapshot to unclassified/NO-GO), and stopped for human arbitration before overwriting [source: backup /tmp/config.yaml.pre_task_a.bak; smoke-test executed on 2026-11-12 (workflow record); final human ruling: Option 3, merge and restore].

(see evidence/S3.png)

**e. What WorkSwarm did NOT do.** It did not invent volatility numbers, did not claim "verified" without actually running, and abstained on ambiguous API errors instead of guessing [source: round1_design_analysis_v3.md §6 + classify_reconciliation.md].

Required screenshots (placeholders to be pasted later):
- S1: classify.py full-399 reconciliation output showing 0 mismatch
- S2: [skip] log line + [done] summary from round1_design_resume.log
- S3: SKILL.md structure after TASK D
- S4: GitHub commit page after TASK G

### 4. Evaluation (0.75 page)

Baseline vs Gate arithmetic, per snapshot [source: artifacts/evaluation_report_v2.md §2]:

    Baseline (always dual):  0.035 × 0.04 − (0.040 + 0.278) × 0.48 + 0.511 × 0 + 0.135 × 0 = 0.0014 − 0.1526 = −0.1512
    Gate (goldilocks only):  0.035 × 0.04 + 0.965 × 0 = +0.0014

The gate flips the per-snapshot expectation from negative to barely positive; its primary value is loss avoidance, not profit generation [source: artifacts/evaluation_report_v2.md §2 table caption, Conclusion].

**What the gate buys.** It avoids the 31.8% of snapshots where a naive dual-sided strategy loses one leg — resolved_pending 27.8% + locked_two_sided 4.0% [source: artifacts/evaluation_report_v2.md §3; round1_design_analysis_v3.md §3].

**What the gate cannot do.** Strict goldilocks appears in only 3.5% of the batch (14/399) and 18.9% among the 53 active snapshots; the gate therefore waits most of the time [source: artifacts/round1_active_moments_analysis.md §5; artifacts/evaluation_report_v2.md §4].

**Headline finding.** Dual-sided preordering is viable only inside a narrow regime window that the gate can identify. This is a NEGATIVE result in the sense that it does not claim profitability — it claims loss avoidance [source: artifacts/evaluation_report_v2.md §4, Conclusion].

### 5. Reusable Contribution (0.5 page)

Package: `skills/polymarket-regime-gate/` (public GitHub). Contents: SKILL.md, README.md, config.yaml (frozen thresholds + strategy), scripts/classify.py, scripts/record.py, and examples/ with 3 snapshots — one per label (goldilocks / quiet / resolved_pending) [source: skills/polymarket-regime-gate/README.md, §What this package contains].

Quick start [source: skills/polymarket-regime-gate/README.md, §Quick start]:

    python3 skills/polymarket-regime-gate/scripts/classify.py \
      skills/polymarket-regime-gate/examples/goldilocks.json

(see evidence/S4.png)

Link: https://github.com/openJiuwen-ai/jiuwenswarm

Attribution: the package reuses the course's JiuwenSwarm environment; the classifier and the recorder are original work; the three example snapshots come from the user's own recorded data [source: skills/polymarket-regime-gate/README.md, §Attribution and openJiuwen link].

### 6. Limitations and Future Work (0.5 page)

- Fill simulation is conservative: each snapshot checks only the next snapshot's best_ask (20 s gap), not the full price path [source: artifacts/evaluation_report_v2.md §5.1].
- Single-day design set; regime shares and rates may shift on other days [source: artifacts/evaluation_report_v2.md §5.2].
- Settlement uses Chainlink 30s TWAP; order-book features are a proxy [source: artifacts/evaluation_report_v2.md §5.3].
- Future work: 15-minute markets, order-book microstructure for fill probability, TWAP-aware regime detection [source: user outlook].

### References

- artifacts/evaluation_report_v2.md
- artifacts/round1_design_analysis.md
- artifacts/round1_design_analysis_v3.md
- artifacts/round1_active_moments_analysis.md
- artifacts/classify_reconciliation.md
- skills/polymarket-regime-gate/ (SKILL.md, README.md, config.yaml, scripts/, examples/)
- data/snapshots/round1_design_resume.log