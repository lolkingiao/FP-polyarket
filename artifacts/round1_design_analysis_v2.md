# round1_design 逐快照分析报告 v2（quiet 重定义 + unclassified 深挖 + 窗口聚合 + A/B 波动率交叉验证）

- 前置：基于已验收 v1（`artifacts/round1_design_analysis.md`，全量中间数据 `/tmp/round1_rows.json`）与 v2 中间数据（`/tmp/round1_rows_v2.json`、399 行）产出本报告。
- 数据源：`data/snapshots/round1_design/`（只读）；交叉验证仅使用用户指定的 `data/snapshots/round1_design/btc_klines_1m.csv`（249 行 1 分钟 K 线，09:18–13:26Z）。未触碰 artifacts/t1、artifacts/t2、data/t2；未修改 record.py；未写 classifier；未 git；阈值 0.02/0.05/0.30/0.20 仍为 placeholder。
- 口径变更提示：v2 引入 quiet 标签并弃用 thin，因此 v1 与 v2 的标签计数**不可直接比较**（v2 的 goldilocks=17 与 v1 的 32 差异即来自 quiet 优先判定，见 FINDING 3）。

---

## 0. M 段纠正（对背景假设的显式勘误）

v1 已记录：背景所述"两段间约 110 分钟缺口"**不成立**。实测 10:05–10:59Z 存在连续 M 段（11 个窗口、157 个快照），每窗口 13–15 个快照、跨度约 290s。本报告继续按 4 段划分：T（<09:30Z，11）、A（09:30–10:04Z，24）、M（10:05–10:59Z，157）、B（11:55–13:25Z，207），并保留 A/B 对比。此勘误在 v2 中显式记录，后续分析均基于此。

---

## 1. FINDING 1（头条，保留）：goldilocks 集中在开窗后前 60s，而非临近到期

复用 v1 §4 结论（v2 标签下 goldilocks 子集变化，但 timing 结论稳健，见下）：

- 34 个窗口中有 20 个出现过 goldilocks（v1 口径）；32 个 v1-goldilocks 快照的 seconds_before_endDate：min=112，median=257，max=296，全部在 endDate 前。
- 按窗口生命周期分桶：240–300s：20（62.5%）；180–240s：5；120–180s：5；60–120s：2；**0–60s：0**。
- 各窗口首个 goldilocks 的 sbe：min=113，median=266，max=296。

**结论：goldilocks 不集中在窗口前 60–90s，而是集中在窗口前 240–300s（即开窗后前 0–60s）；窗口最后 60s 内无任何 goldilocks。这是对"临近到期出现可交易窄价差"假设的反转。**

v2 口径核验：v2 goldilocks 17 个（被 quiet 抢走 15 个重叠），其 sbe 分布仍集中在 240–300s 桶（17 个中 11 个落在 240–300s，其余落在 120–240s），无 0–60s 案例，结论不变。

---

## 2. FINDING 2（goldilocks=8%）："92% 长什么样"构成分解（不松阈值）

v1 口径 goldilocks = 32/399 = 8.0%，其余 367 个 = 92.0%。按 **v2 新标签方案**分解这 367 个（注意：v2 下 15 个原 goldilocks 因 quiet 优先被划出，故 v2 全局非 goldilocks 为 382 = 95.7%，此处同时给出两口径）：

**92% 构成（367 个，v1 goldilocks 之外，按 v2 标签）**：

| 构成 | 计数 | 占 92% | 占全部 |
|---|---|---|---|
| quiet | 159 | 43.3% | 39.8% |
| resolved_pending | 111 | 30.2% | 27.8% |
| unclassified | 69 | 18.8% | 17.3% |
| locked_two_sided | 28 | 7.6% | 7.0% |
| 合计 | 367 | 100% | 92.0% |

**v2 全局非 goldilocks 构成（382 = 95.7%）**：quiet 174 (45.5%)、resolved_pending 111 (29.1%)、unclassified 69 (18.1%)、locked_two_sided 28 (7.3%)。

**解读**：92% 里近半（quiet）是"窄价差但交易稀少"的快照，其次三成是已单边化（resolved_pending），近两成落在缝隙区间（unclassified），仅 7.6% 是双边 tight 且偏离 0.5（locked_two_sided）。若 regime gate 只认 goldilocks，约 92% 时段无法进入该状态；quiet 与 resolved_pending 占了 73%，这两类应作为 gate 的主要分支候选。

---

## 3. FINDING 3：thin 弃用，重定义 quiet（交易活跃度）

**thin（spread≥0.20）在全批次 399 个快照中 0 例**（v1 已验证），5 分钟 Up/Down 市场价差恒窄（绝大多数 1 分），弃用 thin 标签。

**quiet 定义**：`quiet = (spread < 0.02) AND (trade_slow)`，其中：
- 未受 limit=100 截断时：`trade_slow = (len(trades_recent) < 5)`；
- 受截断时（len == 100）：改用时间戳跨度代理 `age = recorded_at_epoch − min(trade.timestamp)`，`age > 60` → 视为交易少（quiet 前提满足）。

**timestamp 单位核实**：对快照内 trade 的 `timestamp` 字段抽样验证为 unix 秒（int），与 `recorded_at_epoch` 同单位（实测差值 232–275s，合理），代理计算有效。

**新标签方案（每快照恰好一个，判定顺序显式）**：
1. `resolved_pending`：one_sided = true（最高优先级）
2. `quiet`：spread < 0.02 AND trade_slow（**默认 quiet 优先于 goldilocks/locked**）
3. `goldilocks`：spread < 0.02 AND mid_distance_from_half < 0.05 AND NOT quiet
4. `locked_two_sided`：spread < 0.02 AND mid_distance_from_half ≥ 0.30 AND NOT quiet
5. `unclassified`：其余（含缝隙区间）

**重叠处理（待确认标注）**：quiet 与 goldilocks 数值条件可重叠（spread<0.02 且 trade_slow 且 mid<0.05）。默认按判定顺序 quiet 优先，即 goldilocks 需 NOT quiet。**重叠快照数量 = 15**（满足 goldilocks 数值条件但同时 trade_slow），全部为 v1 goldilocks 被划入 quiet。此口径标为**待确认**：若用户裁决 goldilocks 优先，则 v2 goldilocks = 32、quiet = 159（15 个回到 goldilocks）。

**v2 全批次标签分布（399 快照）**：

| 标签 | 计数 | 百分比 |
|---|---|---|
| quiet | 174 | 43.6% |
| resolved_pending | 111 | 27.8% |
| unclassified | 69 | 17.3% |
| goldilocks | 17 | 4.3% |
| locked_two_sided | 28 | 7.0% |

**分 T/A/M/B 段分布（v2 口径）**：

| 段 | n | quiet | resolved_pending | unclassified | goldilocks | locked_two_sided |
|---|---|---|---|---|---|---|
| T | 11 | 2 (18.2%) | 3 (27.3%) | 1 (9.1%) | 2 (18.2%) | 3 (27.3%) |
| A | 24 | 9 (37.5%) | 11 (45.8%) | 2 (8.3%) | 0 (0.0%) | 2 (8.3%) |
| M | 157 | 62 (39.5%) | 46 (29.3%) | 29 (18.5%) | 10 (6.4%) | 10 (6.4%) |
| B | 207 | 101 (48.8%) | 51 (24.6%) | 37 (17.9%) | 5 (2.4%) | 13 (6.3%) |

A vs B（v2）：A 段 goldilocks 0 个、resolved_pending 45.8%；B 段 goldilocks 5 个（2.4%）、resolved_pending 24.6%、quiet 48.8%。B 段更"quiet 主导"，A 段更"单边化主导"。

---

## 4. FIX 1：unclassified 深挖（缝隙区间 bin 分布）

**v2 下 unclassified = 69 个**（v1 的 122 个缝隙区间中有 53 个因 trade_slow 划入 quiet，去向：69 留 unclassified + 53 进 quiet，合计 122 自洽）。

69 个 unclassified 的构成（spread 为 max(up,down) 口径）：

| 带 | 定义 | 计数 | 占 unclassified |
|---|---|---|---|
| **transition 带** | spread < 0.02 且 mid ∈ [0.05, 0.30) | **52** | **75.4%** |
| in-between-liquidity 带 | spread ∈ [0.02, 0.20) | 17 | 24.6% |
| 兜底（两带之外） | — | 0 | 0% |

**in-between-liquidity 带（spread∈[0.02,0.20)，5 个等宽 bin）**：

| bin | 计数 |
|---|---|
| [0.02, 0.056) | **14** |
| [0.056, 0.092) | 3 |
| [0.092, 0.128) | 0 |
| [0.128, 0.164) | 0 |
| [0.164, 0.20) | 0 |

**transition 带（mid∈[0.05,0.30)，5 个等宽 bin）**：

| bin | 计数 |
|---|---|
| [0.05, 0.10) | 11 |
| [0.10, 0.15) | 11 |
| [0.15, 0.20) | 12 |
| [0.20, 0.25) | 9 |
| [0.25, 0.30) | 9 |

**结论**：
- **unclassified 主要落在 transition 带（52/69 = 75.4%）**，即"价差已收窄（<0.02）但 mid 尚未收敛到 0.5 附近（∈[0.05,0.30)）"的中间状态。
- in-between-liquidity 带仅 17 个且**高度集中在首 bin**（[0.02,0.056) 占 14/17，代表如 1794389100_1794389203.json spread=0.02、1794392700_1794392800.json spread=0.02），即价差刚越过 0.02 的边界案例，真正 spread≥0.056 的快照全批次仅 3 个。
- transition 带 mid 分布近似均匀（9–12/每 bin），无单点聚集。
- **含义（只分析、不冻结）**：若后续要减少 unclassified，优先考虑为 transition 带定义独立标签（mid∈[0.05,0.30) 且 spread<0.02），而非收紧 goldilocks 定义（后者仅影响 15 个重叠且方向相反）；本轮不冻结任何方案。

---

## 5. FIX 2：窗口级聚合（34 窗口，v2 标签口径）

每窗口一行：window_epoch、段、快照数、median spread（max(up,down) 口径，双侧非空快照的中位数；无则 null）、median mid_distance_from_half（非 null 中位数；全 null 标 null）、goldilocks 计数、resolved_pending 计数。

| window_epoch | 段 | n | med_spread | med_mid | gold | resolved | 短评 |
|---|---|---|---|---|---|---|---|
| 1794388500 | T | 3 | null | null | 0 | 3 | 无gold+resolved过半（全单边） |
| 1794389100 | T | 8 | 0.010 | 0.105 | 2 | 0 | - |
| 1794389700 | A | 8 | 0.010 | 0.285 | 0 | 4 | 无gold+resolved过半 |
| 1794390000 | A | 12 | 0.010 | 0.305 | 0 | 3 | 无gold |
| 1794391200 | A | 4 | null | null | 0 | 4 | 无gold+resolved过半（全单边） |
| 1794391500 | M | 15 | 0.010 | 0.065 | 4 | 3 | goldilocks 最密集窗口 |
| 1794391800 | M | 14 | 0.010 | 0.265 | 0 | 3 | 无gold |
| 1794392100 | M | 15 | 0.010 | 0.195 | 0 | 5 | 无gold |
| 1794392400 | M | 14 | 0.010 | 0.395 | 0 | 6 | 无gold，resolved 偏高 |
| 1794392700 | M | 14 | 0.010 | 0.425 | 0 | 6 | 无gold，resolved 偏高 |
| 1794393000 | M | 14 | 0.010 | 0.435 | 0 | 2 | 无gold |
| 1794393300 | M | 15 | 0.010 | 0.305 | 1 | 4 | - |
| 1794393600 | M | 14 | 0.010 | 0.375 | 0 | 3 | 无gold |
| 1794393900 | M | 14 | 0.010 | 0.395 | 2 | 5 | - |
| 1794394200 | M | 15 | 0.010 | 0.175 | 2 | 6 | - |
| 1794394500 | M | 13 | 0.010 | 0.425 | 1 | 3 | - |
| 1794398100 | B | 13 | 0.010 | 0.185 | 1 | 4 | - |
| 1794398400 | B | 14 | 0.010 | 0.375 | 0 | 2 | 无gold |
| 1794398700 | B | 15 | 0.010 | 0.435 | 0 | 1 | 无gold |
| 1794399000 | B | 14 | 0.010 | 0.195 | 0 | 3 | 无gold |
| 1794399300 | B | 6 | 0.010 | 0.315 | 0 | 0 | - |
| 1794399600 | B | 2 | 0.030 | 0.170 | 0 | 1 | 无gold+resolved过半；spread 偏高（唯一 med_spread>0.01 窗口） |
| 1794400200 | B | 2 | 0.010 | 0.485 | 0 | 1 | 无gold+resolved过半 |
| 1794400500 | B | 9 | 0.010 | 0.499 | 0 | 7 | 无gold+resolved 高（7/9）；med_mid 最高 |
| 1794400800 | B | 14 | 0.010 | 0.385 | 1 | 3 | - |
| 1794401100 | B | 14 | 0.010 | 0.445 | 1 | 6 | - |
| 1794401400 | B | 15 | 0.010 | 0.290 | 0 | 4 | 无gold |
| 1794401700 | B | 14 | 0.010 | 0.455 | 0 | 4 | 无gold |
| 1794402000 | B | 14 | 0.010 | 0.455 | 1 | 5 | - |
| 1794402300 | B | 15 | 0.010 | 0.295 | 1 | 5 | - |
| 1794402600 | B | 14 | 0.010 | 0.180 | 0 | 3 | 无gold |
| 1794402900 | B | 14 | 0.010 | 0.205 | 0 | 0 | 无gold且无resolved（全 quiet/unclassified） |
| 1794403200 | B | 15 | 0.010 | 0.185 | 0 | 2 | 无gold |
| 1794403500 | B | 3 | 0.010 | 0.285 | 0 | 0 | - |

**异常窗口短评**：
- **1794388500 / 1794391200（T/A）**：med_spread=null、resolved 全满——窗口内快照全部单边化（无双侧 book），T 段 09:15 窗口为测试运行、A 段 10:00 窗口为补丁前崩溃点附近，符合"补丁前簿记更差"。
- **1794389700（A 段首个窗口）**：resolved 4/8 = 50%，med_mid 0.285，无 goldilocks。
- **1794391500（M 段首个窗口）**：goldilocks 4 个（全批次单窗口最多），med_mid 0.065 最低——开窗初期 mid 贴近 0.5 且流动性充足。
- **1794400500（B）**：resolved 7/9、med_mid 0.499（最高，mid 已锁定到一侧）——临近期权到期单边化+价格锁定。
- **1794402900（B）**：gold=0 且 resolved=0，14 个快照全部为 quiet/unclassified——全窗口"窄价差但交易稀少"，无单边化也无可交易 goldilocks。
- **1794399600（B）**：唯一 med_spread=0.030 的窗口（n=2，样本极小），其余 33 窗口 med_spread 均为 0.010。

---

## 6. A vs B resolved_pending 差异解释（btc_klines_1m.csv 交叉验证）

问题：A 段 resolved_pending 45.8%（11/24）vs B 段 24.6%（51/207）。是样本量（A 仅 24）还是 A 段处于 BTC 高波动期？

**波动率口径**：1 分钟已实现波动率代理 = |ln(close_t / close_{t-1})|（close-to-close 对数收益绝对值），对 `btc_klines_1m.csv` 相邻分钟收盘价计算；Segment A 取 open_time ∈ [09:30, 10:05)Z、Segment B 取 open_time ∈ [11:55, 13:26)Z。

| 时段 | 分钟数 | 中位数 | min | p25 | p75 | max |
|---|---|---|---|---|---|---|
| Segment A (09:30–10:05Z) | 35 | **0.000217** | 0.000019 | 0.000138 | 0.000494 | 0.001132 |
| Segment B (11:55–13:26Z) | 91 | **0.000324** | 0.000000 | 0.000135 | 0.000541 | 0.001326 |
| 全时段参考 (09:18–13:26Z) | 248 | 0.000255 | 0.000000 | 0.000124 | 0.000480 | 0.001339 |

**结论**：
1. **"A 段高波动"假设不成立**：A 段 1 分钟波动率中位数（0.000217）**低于** B 段（0.000324）。A 段 resolved_pending 更高但 BTC 波动更低——单边化与波动率无正相关（至少在本批次两段内），方向相反。
2. **样本量视角**：resolved_pending 比例 Wilson 95% CI——A 段 11/24=45.8% → CI (27.9%, 64.9%)；B 段 51/207=24.6% → CI (19.3%, 30.9%)。A 的 CI 极宽（n=24），**与 B 的 CI 存在重叠区（27.9%–30.9%）**，差异在统计上**不显著**（无法排除抽样波动）。
3. 综合判断：A vs B 的 resolved_pending 差异**更可能源于样本量小（A 仅 24 快照，且集中于 3 个窗口，其中 10:00 窗口 4 个快照全部单边化）**，而非 BTC 高波动期所致。补丁前段（A）簿记状态较差是事实，但 45.8% 这个点估计不宜作为稳定结论；需要更多补丁前样本才能确认。

---

## 附录 A：可复核性

- v2 全量逐快照数据（399 行，含 v2_label/trade_slow/age/spread_max）：`/tmp/round1_rows_v2.json`。
- v1 全量数据：`/tmp/round1_rows.json`；v1 报告：`artifacts/round1_design_analysis.md`。
- K 线交叉验证数据：`data/snapshots/round1_design/btc_klines_1m.csv`（249 行，09:18–13:26Z）。
- 计算均为一次性只读脚本（未落盘为 classifier、未修改 record.py、未 git）；阈值 0.02/0.05/0.30/0.20 仍为 placeholder，未冻结。
- 待确认项：quiet 与 goldilocks 重叠 15 个的归属（默认 quiet 优先）；transition 带是否引入独立标签（本轮只分析）。