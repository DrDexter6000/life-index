# ADR-025: Phase 1-D Baseline 从 v3 迁移到 v4

> **状态**: 已决（Decided）
> **决策日期**: 2026-05-04
> **来源**: Round 19 Phase 1-D Mode A 子任务 M-1 — Baseline Provenance 调查
> **决策者**: 主审（Opus 4.7）裁决；用户 2026-05-04 双 ack 授权 + 4 项推荐 ack
> **承载文档**: [`.kimi-learnings/round-19-phase1d/exchange no.7.md`](../../.kimi-learnings/round-19-phase1d/exchange%20no.7.md)
> **替代 ADR**: 无（v3 baseline 自身未被 ADR 命名为不变量；本 ADR 是首次显式 governance 这一对象）
> **影响范围**: Round 19 Phase 1-D 全部 task 的绿测试阈值、phase exit 起点参考、retrospective 量化记录

---

## 1. 决策上下文

### 1.1 起源

Round 19 Phase 1-C Track B 收尾（commit `a9fb32e`，2026-05-03）将 v3 baseline (`tests/eval/baselines/round-19-phase1c-baseline-v3.json`，MRR@5=0.6093，frozen 2026-05-02) 引为 Phase 1-D plan §3/§4 的绿测试阈值与 phase exit 起点。

Phase 1-D plan v2（2026-05-03 主审起草）写明：
- §3.C1a.4 / §3.C1b.4 全量绿测试阈值 「M1 MRR@5 ≥ 0.6093（不低于 v3）, M2 Recall@5 ≥ 0.9140」
- §3.R1.4 红测试 baseline 「M1 = 0.6093」
- §4.1 phase exit 表 「v3 实测 0.6093 → 目标 ≥ 0.65」

但在 plan 起草到 F1 task 启动之间，main 上累积了下列 commits：

| Commit | 性质 | 影响 |
|--------|------|------|
| `a9fb32e` | feat(search) — Track B 中文时间表达式解析 + query_preprocessor + noise gate | code-only 漂移 -0.0096（详见 `tools/dev/v4-regression-analysis.md`） |
| `9cb9666` | feat(entity): Block 4 Pilot 7 篇日志 entity 标注 | 真实 metadata 数据漂移（影响 entity_expansion / complex_query 的 ranking 候选集） |
| `7a9aed4` | refactor(pilot): AI entities 重分类 person/ai_assistant + stats 修正 | 真实 metadata 数据修订（同上） |
| `32fad4b` | feat(eval): F1 deterministic eval anchor injection（Phase 1-D F1） | code 改动；同时修复 `month/cn_month` typo，让之前 UnboundLocalError 的"今年X月/去年X月"分支能跑但排名靠后 |

→ Plan §3 起草时未盘点这些 commits 对 0.6093 阈值的影响，**plan defect**（[exchange no.7] §「遇见问题」问题 1）。

### 1.2 触发证据

F1 lightweight audit 主审漏 perf 维度（[feedback_search_audit_dimensions]），未对比 baseline 数值。C1-a/b lightweight audit 暴露 2 条红信号：
1. M1 MRR@5 = 0.5687（HEAD post-C1）< plan §3.C1a.4 阈值 0.6093，差 -0.0406
2. anti-test queries 缺失（plan §3.C1a §4「必须做」）

Kimi 自决 reframe red→non-red（"regression 来自 a9fb32e，与 C1 改动无关"）触方法论 05 盲点 1 + 触发器 1（≥1 红 → 升级 Mode A）。

主审升级 Mode A 自接 M-1，得三项核心结论：
1. v3 阈值已过期；不再是 Phase 1-D 的合法 reference
2. Kimi 简报数字真实（独立 eval 复现 MRR@5=0.5687, Recall@5=0.8280 完全一致）
3. 0.5687 - 0.5559 = +0.0128，C1-a/b 相对 F1 baseline **是改善而非退化**

---

## 2. 决策内容

### 2.1 主裁决

废弃 v3 (`round-19-phase1c-baseline-v3.json`) 作为 Phase 1-D 阈值参考，**冻结 v4** (`round-19-phase1d-baseline-v4.json`) 作为新阈值锚点。

### 2.2 v4 baseline 规范

| 字段 | 值 |
|------|-----|
| baseline_id | `round-19-phase1d-baseline-v4` |
| 文件路径 | `tests/eval/baselines/round-19-phase1d-baseline-v4.json` |
| source_commit | `32fad4b`（F1 deterministic eval anchor injection） |
| eval_anchor (`LIFE_INDEX_TIME_ANCHOR`) | `2026-05-04` |
| total_queries | 104 |
| MRR@5 | **0.5559** |
| Recall@5 | **0.7957** |
| Precision@5 | 0.4628 |
| nDCG@5 | 0.5932 |
| Failures | 22 |
| frozen_at | 2026-05-04 |
| frozen_by | 主审（Opus 4.7）under Mode A 子任务 M-1 |
| Push commit | `077b552`（chore(baseline): freeze v4 baseline for Phase 1-D） |

### 2.3 阈值迁移规则

Phase 1-D plan §3 / §4 中 0.6093 / 0.9140 的所有引用，按下列规则迁移：

| 旧引用 | 新引用 |
|-------|-------|
| 「不低于 0.6093」 防退化阈值 | 「不低于 v4 baseline 0.5559」+「不引入新 regression vs F1 32fad4b」 |
| 「不低于 0.9140」 Recall 防退化阈值 | 「不低于 v4 baseline 0.7957」 |
| Phase exit 「目标 ≥ 0.65 / ≥ 0.92」 | **不变**（最终目标，由用户 phase 启动 ack 锁定，与 baseline 改锚无关） |
| §1.1 Phase 1-C 历史表 (0.6093 / 0.9140) | **保留**（历史记录，标 deprecated） |

### 2.4 v3 文件命运

`tests/eval/baselines/round-19-phase1c-baseline-v3.json` 与 `tests/eval/baselines/round-19-phase1c-baseline-v4.json` 仍保留在仓库中（不删除），用于：
- 历史溯源
- `tools/dev/d2_runner.py` / `tools/dev/recall_diff_runner.py` 的回归对比工具仍引用 v3
- ADR / retrospective 引用证据保全

但**不再用作任何 plan 或绿测试的阈值依据**。任何工具或 plan 文档新增的阈值引用必须指向 v4。

---

## 3. 决策替代方案与拒绝理由

### Option A: 回滚 a9fb32e + 9cb9666 + 7a9aed4 重建 v3 状态

**拒绝**。回滚意味着丢弃：
- Pilot 7 篇日志 entity 标注（ADR-024 v1 schema 冻结的实证基础）
- AI entities 类目重分类（用户 2026-05-03 ack 的修订）

代价远大于"维持 v3 阈值不变"的收益。

### Option B: 重锚定到 v4（**采纳 ✅**）

接受 baseline 演化的事实，在 governance 层（ADR + plan 修订 + exchange）显式记录迁移决策与依据。代价：3 个 governance commit + 用户 3 次 push ack。

### Option C: 仅改 plan 阈值，不写 ADR、不 freeze v4 file

**拒绝**。会留下"幽灵阈值"债务——后续 retrospective 或新 phase 起草者无法独立溯源 baseline 演化路径，违反 [methodology/06-audit-gate-policy.md] 「governance 改动其错误代价不是 git revert 能挽回」原则。

---

## 4. 决策影响

### 4.1 对 Phase 1-D 进行中 task 的影响

| Task | 当前状态 | v4 迁移后影响 |
|------|---------|---------------|
| **F1** (32fad4b 已上 main) | 已 push | 重审：0.5559 即 v4 自身，无 regression 概念可言；F1 spot-check + 主审独立 eval 复现 ✅ |
| **C1-a/b** (8db7b61 在 feature 分支) | 待重审 | 0.5687 vs v4 0.5559 = **+0.0128 改善**，**PASS** prerequisite metric；仍需补 anti-test queries（plan §3.C1a §4）才完整 PASS |
| **R1** | 未启动 | 红测试 baseline 改用 0.5559；目标 ≥ 0.65 不变 |
| **A1** | 未启动 | month-part 语义 task 不直接受 baseline 数值影响 |

### 4.2 对历史 retrospective 的影响

Round 19 Phase 1-C close report 已记录 v3 = 0.6093 状态，是当时事实，不需要改写。Round 19 Phase 1-D close report（待写）应交叉引用本 ADR + exchange no.7 + v3→v4 数值变化解释。

### 4.3 对工具脚本的影响

`tools/dev/d2_runner.py` / `tools/dev/recall_diff_runner.py` 当前 hardcode v3 路径用作"diff against pre-Track-B"工具——**不修改**（用途明确：对比 Track B 漂移）。任何**新建**的 baseline-diff 工具必须默认指向 v4。

---

## 5. 后续动作

- [x] (1) Freeze v4 baseline JSON — commit `077b552` 已推 main 2026-05-04
- [ ] (2) Plan §3 修订 + 提交本 ADR + 入轨 exchange no.7 — governance bundle，本次 push
- [ ] (3) 本 ADR 录入 `docs/adr/INDEX.md`
- [ ] (4) F1 (32fad4b) 重审 verdict（已 push，无新 push 动作）
- [ ] (5) Brief Kimi 通过 exchange no.9 补 anti-test queries 到 `tools/eval/golden_queries.yaml`（artifact）
- [ ] (6) C1-a/b (8db7b61) + anti-test 重审 + push（artifact）
- [ ] (7) Phase 1-D close report 引用本 ADR

---

## 6. 教训沉淀（待 phase 收尾合入 retrospective）

| 教训 | 来源 | 拟沉淀位置 |
|------|------|---------|
| 主审 lightweight audit checklist 必须显式 perf 维度对比 baseline 数值 | F1 audit 漏判 | [methodology/02-mode-a-checkpoint-driven.md] audit rigor 段 |
| 主审写 prompt 给 executor 前必须 grep plan 对应 §——不可凭记忆 | M-1 期间一次 prompt 草稿把 C1-a/b 描述错为「类别守门器/类别均衡」（用户未采纳） | [methodology/02-mode-a-checkpoint-driven.md] audit rigor 段 |
| Plan §3 显式阈值若引用历史 baseline，必须在起草时盘点 baseline-后 commits 对该阈值的影响 | 本 ADR 即是 plan defect 的纠偏 | [methodology/04-tdd-plan-template.md] §「绿测试阈值标定」段 |

---

## 7. 溯源

- 触发: Phase 1-D F1 audit 漏 perf + C1 audit 触发 ≥1 红 → Mode A 升级
- 根因调查: `tools/dev/v4-regression-analysis.md`（2026-05-03 主审写）
- 主审 exchange: `.kimi-learnings/round-19-phase1d/exchange no.7.md`
- v4 freeze commit: `077b552`
- 用户 ack: 2026-05-04（双 ack：动 M-1 / 写 exchange）+ 4 项推荐 ack
- 方法论引用: [02-mode-a-checkpoint-driven.md] / [05-signals-and-escalation.md] 触发器 1 + 盲点 1 / [06-audit-gate-policy.md] Gate B / [feedback_search_audit_dimensions]
