# round1_design 逐快照分析报告 v3（quiet 定义修正为 recent_count<3）

- 前置：基于 v1（`artifacts/round1_design_analysis.md`）与 v2（`artifacts/round1_design_analysis_v2.md`）已验收报告。本 v3 **唯一变更**为 quiet 定义（用户指令）；其余分析结论直接引用 v2，不重算。
- 数据源：`data/snapshots/round1_design/`（只读）；全部 399 个快照 JSON 实际重读以计算 recent_count（未只依赖 v2 中间数据）。未触碰 artifacts/t1、artifacts/t2、data/t2；未修改 record.py；未写 classifier；未 git；阈值 0.02/0.05/0.30/0.20 仍为 placeholder。
- 可复核中间数据：`/tmp/round1_rows_v3.json`（399 行，含 recent_count/len_trades/v3_label 与 v2 既有字段）。

---

## 0. quiet 定义修正（唯一变更）

**v2 定义（已弃用）**：`quiet = (spread < 0.02) AND (len(trades_recent)<5 或截断时 age>60)`。用户指出 age>60 代理过松（len==100 时最老交易 232–275s 旧几乎恒真），quiet 虚高。

**v3 定义（本次采用）**：
- `recent_count = trades_recent 中满足 trade.timestamp >= recorded_at_epoch − 60 的条数`（timestamp 为 unix 秒，已核实）；
- `quiet = (spread_max < 0.02) AND (recent_count < 3)`；
- 不再使用 len<5 或 age>60 代理，399 个快照统一按 recent_count 口径实际重算。

**标签判定顺序不变**（每快照恰好一个）：`resolved_pending（one_sided=true）→ quiet → goldilocks（需 NOT quiet）→ locked_two_sided → unclassified`。quiet 与 goldilocks 重叠默认仍 quiet 优先（见 §4）。

**FINDING 3A（对用户预期的如实回应）**：新口径下 quiet **不降反升**——v2 43.6%（174）→ v3 51.1%（204）。原因是本批 5 分钟市场交易极其稀疏：**323/399（81.0%）快照在记录前 60s 内交易数为 0**（recent_count=0）。quiet 偏高主要由市场本身"60s 内基本无交易"决定，而非 age>60 代理的松紧。若期望 quiet 占比下降，需重新讨论 quiet 的语义（如 0 交易快照是否应单独分类），本轮只报告事实，不冻结方案。

---

## 1. 截断统计（必须项 1）

| 类别 | 快照数 | 占比 |
|---|---|---|
| len(trades_recent) < 100（未截断） | 97 | 24.3% |
| len(trades_recent) == 100（截断） | 302 | 75.7% |

即约 3/4 快照的 trades_recent 受 data-api limit=100 截断，仅有最近 100 条交易。

---

## 2. recent_count 直方图（必须项 2）

- 范围：min=0，max=100，median=0。
- 分桶：**等宽 5 bin 覆盖 0–100 全范围**，[0,20)/[20,40)/[40,60)/[60,80)/[80,101)（末 bin 右开含 100）。

| bin | 计数 |
|---|---|
| [0, 20) | **326** |
| [20, 40) | 4 |
| [40, 60) | 9 |
| [60, 80) | 7 |
| [80, 101) | 53 |

分布呈**极端双峰**：81.7% 落在 [0,20)（其中 recent_count=0 有 323 个、=1/=2 各 0 个），13.3% 落在 [80,101)（交易活跃且截断），中间带极稀疏。这意味着对绝大多数快照，"最近 60s 内交易 <3 笔"几乎恒真（0 笔）。

**recent_count<3 的快照共 323 个（81.0%）**，但其最终标签分布不全是 quiet：其中 111 个 one_sided（→ resolved_pending，判定优先）、8 个 spread_max≥0.02（→ unclassified）、**204 个成为 quiet**。即 recent<3 是 quiet 的必要条件之一，quiet 251.1% 占比由"最近 60s 无交易 + 价差窄 + 双边盘"共同决定。

---

## 3. 新标签分布与 v2 对比（必须项 3）

**v3 全批次标签分布（399 快照）**：

| 标签 | v3 计数 | v3 % | v2 计数 | v2 % | 变化 |
|---|---|---|---|---|---|
| quiet | 204 | 51.1% | 174 | 43.6% | **+30（+7.5pp）** |
| resolved_pending | 111 | 27.8% | 111 | 27.8% | 0 |
| goldilocks | 14 | 3.5% | 17 | 4.3% | −3 |
| locked_two_sided | 16 | 4.0% | 28 | 7.0% | −12 |
| unclassified | 54 | 13.5% | 69 | 17.3% | −15 |
| 合计 | 399 | 100% | 399 | 100% | — |

**关键变化**：quiet 从 43.6% 升至 **51.1%**（不降反升，见 §0 FINDING 3A）；goldilocks/locked/unclassified 均小幅下降（被更宽的 quiet 吸收）。resolved_pending 不受影响（判定在 quiet 之前且不涉及 recent_count）。

其余分析结论（FINDING 1 timing、FINDING 2 构成、FIX 1 unclassified 深挖、FIX 2 窗口聚合、A/B 波动率交叉验证、M 段勘误）引用 v2，不受本次 quiet 定义修正影响，不重算。

---

## 4. v2 重叠 15 个快照的新归属（必须项 4）

v2 中"满足 goldilocks 数值条件但同时 trade_slow 被 quiet 优先抢走"的重叠快照共 15 个，在新更严规则（recent_count<3）下的归属：

| 新归属 | 数量 | 说明 |
|---|---|---|
| 仍为 quiet | **12** | 全部 recent_count=0（60s 内无任何交易） |
| 回到 goldilocks | **3** | recent_count=64/65/84（交易活跃，不再满足 quiet） |
| 其他标签 | 0 | 全部落在 quiet 或 goldilocks |

3 个回 goldilocks 的快照：1794390000_1794390020.json（recent=84）、1794400800_1794400858.json（recent=65）、1794401400_1794401405.json（recent=64）。

其余 12 个（recent=0）：1794389100_1794389245、1794391500_1794391667、1794391500_1794391688、1794391800_1794391856、1794393300_1794393431、1794398400_1794398414、1794399000_1794399187、1794401700_1794401720、1794402300_1794402327、1794402600_1794402640、1794402900_1794403057、1794403200_1794403286。

---

## 5. 新旧 quiet 迁移（补充）

**v2 quiet（174 个）在 v3 的归属**：

| v3 归属 | 数量 |
|---|---|
| quiet（保持） | 155 |
| unclassified | 10 |
| locked_two_sided | 6 |
| goldilocks | 3 |
| 合计 | 174 |

**v3 quiet（204 个）的来源（原 v2 标签）**：

| 原 v2 标签 | 数量 |
|---|---|
| quiet | 155 |
| unclassified | 25 |
| locked_two_sided | 18 |
| goldilocks | 6 |
| 合计 | 204 |

说明：v3 净增 30 个 quiet = 新增 49 − 移出 19。移出的 19 个（10 unclassified + 6 locked + 3 goldilocks）在 v3 下 recent_count≥3（60s 内确有交易）但 spread<0.02，转入对应标签；新增的 49 个主要是 v2 中 len∈[5,100) 未截断却不满足 age>60 代理的快照——v3 统一 recent_count 口径后，这些"60s 内交易<3 笔"的快照被正确识别为 quiet。

---

## 6. 待确认项与可复核性

**待确认项**：
1. **quiet 语义**：323/399（81%）快照 recent_count=0（recent<3 共 323 个）——若 quiet 意图是"有微量交易"，0 交易快照是否应与 quiet 区分（如单独归入 unclassified 或新增 no_trade 标签）？本轮只分析、不冻结。
2. **quiet∩goldilocks 数值重叠（口径更新）**：v3 下同时满足 quiet 数值条件（spread<0.02 ∧ recent<3 ∧ 非 one_sided）与 goldilocks 数值条件（mid<0.05）的快照共 **18 个**（全部 recent=0、mid∈[0.005,0.045]），默认 quiet 优先全归 quiet。这与 v2 的 15 个重叠是两个不同集合：v2 的 15 个中 12 个 v3 仍 quiet、3 个回 goldilocks（见 §4）；v3 的 18 个含 v2 不同标签迁入的新 quiet。若按"goldilocks 优先"裁决，则 v3 goldilocks=32、quiet=186。此口径供用户裁决确认。

**可复核中间数据**：`/tmp/round1_rows_v3.json`（399 行，字段含 v2 全字段 + recent_count/len_trades/v3_label）；v2 中间数据 `/tmp/round1_rows_v2.json`；v1 中间数据 `/tmp/round1_rows.json`。