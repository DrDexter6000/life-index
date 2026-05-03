# Gold Set 审计与净化报告 (Round 18 Phase 1.0)

> 审计日期: 2026-04-21
> 原始 query 数: 151
> 净化后 active: 104 | 跳过 (Phase 3): 29 | 删除: 18

---

## 执行摘要

按 Opus 4.7 指令，在启动 Phase 2-B 前完成 Gold Set 净化。净化后建立 **104 条干净 active 基线**（≥100），满足准入门槛。

**净后基线指标:**

| 指标 | 值 |
|------|-----|
| Active queries | 104 |
| Skipped (D/E) | 29 |
| Pass rate | **71.2%** (74/104) |
| MRR@5 | **0.4516** |
| Recall@5 | **0.7222** |
| Recall@10 | **0.7778** |
| Precision@5 | **0.3699** |
| NDCG@5 | **0.4956** |

**M2 硬指标状态:**
- ✅ Recall@5 ≥ 0.45 (实际 0.7222)
- ✅ time_range fail rate ≤ 35% (实际 33.3%, 7/21)
- ❌ complex_query fail rate ≤ 35% (实际 **41.2%**, 14/34) → **Phase 2-B 目标**

---

## 净化操作记录

### 1. 删除 A 类 — 数据完整性 bug (18 条)

`must_contain_title` 指向的日志标题根本不在 live DB 中。任何搜索代码优化都无法修复。

**删除列表:**

| ID | Query |
|----|-------|
| GQ01 | 想念我的女儿 |
| GQ02 | 重庆过生日 |
| GQ03 | 数字灵魂 |
| GQ04 | 边缘计算 |
| GQ05 | 乐乐 |
| GQ06 | 小英雄 |
| GQ08 | 想念小英雄 |
| GQ13 | Google Stitch |
| GQ14 | integration testing |
| GQ15 | dynamic loading |
| GQ16 | deployment |
| GQ17 | AI 算力 |
| GQ18 | my daughter 乐乐 |
| GQ19 | OpenClaw deployment |
| GQ21 | Life Index |
| GQ22 | OpenClaw |
| GQ23 | LobsterAI |
| GQ24 | AI算力投资策略 |

### 2. 跳过 D/E 类 — Pipeline/Tokenizer 依赖 (29 条)

这些 query 依赖尚未启用的语义搜索管道或中文分词器，在 Phase 2 强行测试会产生虚假失败信号。标记 `skip_until_phase: 3`。

**D 类 (Tokenizer 假设, 5 条):**
GQ138, GQ139, GQ140, GQ141, GQ142

**E 类 (Semantic Pipeline 假设, 24 条):**
GQ20, GQ37–GQ49, GQ116–GQ123, GQ151, GQ154

---

## Category 级失败分析 (净后基线)

| Category | Total | Fail | Fail Rate | Status | 失败 IDs |
|----------|-------|------|-----------|--------|----------|
| time_range | 21 | 7 | **33.3%** | ✅ PASS | GQ51, GQ52, GQ55, GQ57, GQ61, GQ090, GQ092 |
| complex_query | 34 | 14 | **41.2%** | ❌ FAIL | GQ62, GQ63, GQ64, GQ65, GQ68, GQ69, GQ70, GQ095, GQ096, GQ097, GQ098, GQ105, GQ106, GQ107 |
| entity_expansion | 20 | 2 | 10.0% | ✅ PASS | GQ25, GQ34 |
| edge_case | 19 | 5 | 26.3% | ✅ PASS | GQ77, GQ80, GQ81, GQ82, GQ127 |
| noise_rejection | 7 | 2 | 28.6% | ✅ PASS | GQ10, GQ11 |
| high_frequency | 3 | 0 | 0.0% | ✅ PASS | — |

### time_range (7 失败)

已满足 ≤35% 门槛。剩余失败多为语义漂移或 ground truth 过严：
- `GQ51/GQ090/GQ092`: 月份查询，预期日志不在该月份
- `GQ52`: "春天的记录" 预期不匹配
- `GQ55/GQ61`: 含"最近"相对时间，ground truth 漂移
- `GQ57`: "四月初的国际新闻" 结果不足

### complex_query (14 失败) — Phase 2-B 主攻

**主题过滤失效 (7 条):**
`GQ095–GQ098`, `GQ105–GQ107` — "work/think/life/create 相关的日志" 搜索未正确按 topic 过滤。

**时空组合失效 (4 条):**
`GQ63–GQ65`, `GQ68` — 时间范围 + 关键词/地点组合查询未返回预期结果。

**语义扩展不足 (3 条):**
`GQ62`, `GQ69`, `GQ70` — 需要更灵活的实体/关系扩展。

---

## 代码变更

1. **`tools/eval/golden_queries.yaml`**: 删除 18 条 A 类，为 29 条 D/E 类添加 `skip_until_phase: 3`
2. **`tools/eval/run_eval.py`**: 新增 `phase` 参数，eval runner 自动跳过 `skip_until_phase > current_phase` 的 query

---

## 准入结论

✅ **Gold Set 净化完成，满足 ≥100 条 active 基线要求。**

下一步：**Phase 2-B — 将 complex_query 失败率从 41.2% 降至 ≤35%**（需修复 3+ 条，目标 ≤11/34 失败）。
