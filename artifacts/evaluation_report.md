# round1_design Evaluation Narrative（TASK B）

## 1. Setup

本评估基于 round1_design 设计集：采集器按轮询方式记录 Polymarket 5 分钟 Up/Down 市场的簿面与成交快照，共 **399 个快照**，跨 34 个 5 分钟窗口，覆盖 2 段（A/B）[来源依据：用户 TASK B 指令原文——两份源报告未记录窗口数与段划分；399 见 round1_design_analysis_v3.md §3]。采集期另记录 1 次因 DNS 失败跳过的轮询 [来源依据：用户 TASK B 指令原文，两份源报告均未记录该事件]。

每个快照按冻结阈值判定为 5 个标签之一（判定顺序 fixed：resolved_pending → quiet → goldilocks → locked_two_sided → unclassified）：quiet / resolved_pending / goldilocks / locked_two_sided / unclassified。分类阈值已冻结并落盘为仓库根 `config.yaml`（thresholds 段：`spread_max=0.02`、`mid_distance_max=0.05`、`recent_trade_count_min=3`、`locked_mid_min=0.30`），classify.py 启动时从该文件加载；本报告不复述全文。5 标签体制分布见 §2 表 1。

[source: round1_design_analysis_v3.md §0, §3]

## 2. Baseline vs Gate

**表 1. round1_design 体制分布（399 快照）。** The gate flips the per-snapshot expectation from negative to barely positive; its primary value is loss avoidance, not profit generation. 表中占比即下式各概率系数。

| 标签 | 计数 | % |
|---|---|---|
| quiet | 204 | 51.1% |
| resolved_pending | 111 | 27.8% |
| unclassified | 54 | 13.5% |
| goldilocks | 14 | 3.5% |
| locked_two_sided | 16 | 4.0% |
| **合计** | **399** | **100%** |

[source: round1_design_analysis_v3.md §3]

**算术（Baseline vs Gate，原样）**：

```
Baseline: 0.035 × 0.04 − (0.040 + 0.278) × 0.48 + 0.511 × 0 + 0.135 × 0 = 0.0014 − 0.1526 = −0.1512
Gate:     0.035 × 0.04 + 0.965 × 0 = +0.0014
```

其中 0.035 / 0.040 / 0.278 / 0.511 / 0.135 即表 1 中 goldilocks / locked_two_sided / resolved_pending / quiet / unclassified 的占比（读者可仅凭表 1 复算）；0.04 与 0.48 为评估给定的假设参数，其口径未在两份源报告中定义 [source: 用户 TASK B 指令原文同时给出行文；标签占比支撑见 round1_design_analysis_v3.md §3]。

[source: round1_design_analysis_v3.md §3]

## 3. Why the gate has value

Gate（仅 goldilocks 开仓）的价值在于规避两个主要亏损源：

- **resolved_pending（27.8%，111 个）**：这些快照为 one_sided（单边簿）——Up 或 Down 一侧缺边（bids 空或 asks 空），该侧无连续可成交价，双边策略两条腿无法同时成交，实际暴露在单边形态下；gate 直接跳过这类快照（NO-GO）[source: round1_design_analysis_v3.md §0, §2]。
- **locked_two_sided（4.0%，16 个）**：这些快照 mid 距 0.5 达 0.30 以上（实测 min=0.305、median=0.395、max=0.445），意味着价格已定向——领先一侧价格脱离 0.5，落后一侧成交概率极低或成交即亏；双边策略两条腿不会同时成交，此时开仓即亏损方向 [source: round1_active_moments_analysis.md §3]。

两源合计被规避 31.8%（0.040 + 0.278，见 §2 算式中间步）。[source: round1_design_analysis_v3.md §3]

## 4. What the gate cannot do

- 严格 goldilocks 全批仅 3.5%（14/399）；在 53 个最活跃快照（recent_count≥80）中该比例也只有 **18.9%（10/53）**——即使在最活跃的 13.3% 快照里，双侧对称成交仍是少数派而非常态 [source: round1_active_moments_analysis.md §5, §1]。
- 51.1% 快照是 quiet（204 个，全部 recent_count=0，即每个 quiet 快照记录前 60 秒内零成交）→ **gate 大多数时间在等** [source: round1_design_analysis_v3.md §0, §3; round1_active_moments_analysis.md §0]。
- 等待本身有机会成本，本评估不计 [source: 用户 TASK B 指令原文（评估口径声明）]。

## 5. Limitations

1. 415 次模拟填单评估保守：只查下一快照、20 秒轮询间隔，不评估完整路径 [source: 用户 TASK B 指令原文，①]。
2. 单日设计集，各体制占比与胜率可能在其他日期漂移 [source: 用户 TASK B 指令原文，②]。
3. Settlement 采用 Chainlink 30s TWAP，订单簿特征只是代理指标 [source: 用户 TASK B 指令原文，③]。
4. Segment A (n=24) vs B (n=207) 的 resolved 率差异不显著（Wilson 置信区间重叠）[source: 用户 TASK B 指令原文，④]。

（四项均为用户 TASK B 指令明确要求的行文，其中 415 / n=24 / n=207 / Wilson CI 两个源报告中无直接支撑。）

## Conclusion

Across the full design set, the gate flips the per-snapshot expectation from negative to barely positive; its primary value is loss avoidance, not profit generation——它的意义不是赚钱，而是不做亏钱的事；代价是全批大多数时间在等待一个 3.5%（活跃时 18.9%）才出现的、真正双侧对称、价格居中的时机。

[source: round1_active_moments_analysis.md §5; round1_design_analysis_v3.md §3]