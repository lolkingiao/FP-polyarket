# classify.py 399 全量对账报告（vs v3 标签）

- 日期：2026-11-12（本地）
- 数据源：`data/snapshots/round1_design/`（399 个快照，只读）
- 分类器：`scripts/classify.py`（冻结阈值分类器，离线，未做任何修改）
- v3 基准：`/tmp/round1_rows_v3.json`（v3_label 字段）
- 可复核中间数据：`/tmp/round1_classify_399.json`（399 个快照的 classify.py 完整 stdout 单行 JSON）
- 执行：对每个快照独立运行 `python3 scripts/classify.py <path>`，采集 stdout（单行 JSON）后统一对账。

---

## a. label mismatch 总数

**0 / 399**（目标 0）✅

| 项 | 值 |
|---|---|
| classify.py label vs v3_label 不一致 | **0** |

无逐条列表（mismatch 为 0）。

---

## b. decision mismatch 总数

**0 / 399**（目标 0）✅

decision 由 classify.py 输出（label→decision 映射），与"由 v3 label 按冻结映射推导的决策"比对：goldilocks→GO、quiet→WAIT、resolved_pending→NO-GO、locked_two_sided→NO-GO、unclassified→NO-GO。不一致 0 条。

---

## c. 5x5 混淆矩阵（v3_label × classify.py label）

| v3 \ classify | goldilocks | quiet | resolved_pending | locked_two_sided | unclassified | 行合计 |
|---|---|---|---|---|---|---|
| goldilocks | **14** | 0 | 0 | 0 | 0 | 14 |
| quiet | 0 | **204** | 0 | 0 | 0 | 204 |
| resolved_pending | 0 | 0 | **111** | 0 | 0 | 111 |
| locked_two_sided | 0 | 0 | 0 | **16** | 0 | 16 |
| unclassified | 0 | 0 | 0 | 0 | **54** | 54 |
| 列合计 | 14 | 204 | 111 | 16 | 54 | 399 |

完全对角：每个快照的 classify.py label 与 v3_label 一致，无一错分。

---

## d. classify.py 各 label 计数（须与 v3 一致）

| label | classify.py | v3 | 一致 |
|---|---|---|---|
| quiet | 204 | 204 | ✅ |
| resolved_pending | 111 | 111 | ✅ |
| unclassified | 54 | 54 | ✅ |
| goldilocks | 14 | 14 | ✅ |
| locked_two_sided | 16 | 16 | ✅ |
| 合计 | 399 | 399 | ✅ |

---

## e. 399 个分类总耗时

**12.36 秒**（399 次独立子进程调用，单进程约 31ms/快照；含 Python 解释器启动开销）。

---

## 特别核查：locked_two_sided 的 recent_count 性质

v3 判定顺序中 quiet 先于 locked_two_sided：`quiet = spread<0.02 AND recent_count<3 AND NOT one_sided` 会先吃掉 recent_count<3 的双边窄盘快照，因此 **locked_two_sided 隐含要求 recent_count>=3**。核查结果：

- v3 侧 16 个 locked_two_sided：**min recent_count = 35，全部 ≥ 3** ✅
- classify.py 侧 16 个 locked_two_sided：**min recent_count = 35，全部 ≥ 3** ✅
- 两侧 locked 快照集合完全一致（16/16 同一批文件）✅

**结论：无逻辑 bug**。locked_two_sided 分支的 recent_count≥3 性质在 classify.py 中成立（由 quiet 优先级在判定顺序上天然保证：第 2 条 quiet 先命中 recent<3 的双边盘，第 4 条 locked 只在 recent≥3 时可达）。本报告未修改 classify.py。

---

## 结论

classify.py 在 399 全量快照上与 v3 分析标签**完全一致**：0 label mismatch、0 decision mismatch、混淆矩阵全对角、各标签计数与 v3 吻合，locked 性质核查通过。无需任何修复。