---
type: project-prd-rfc
status: accepted
created: 2026-05-21
approved: 2026-05-21
approved-by: Life Index Developer
title: gbrain absorption — 6 candidates + 2 carrier modules
slug: gbrain-absorption
phases: 6
parallel_max: 4
estimated_wall_clock: 5-10 days
related:
  - .strategy/cli/2026-05-20-gbrain-absorption-roadmap.md
  - .strategy/cli/2026-05-20-gbrain-life-index-comparison-archive.md
  - docs/PROJECT_WORKFLOW.md
  - docs/RFC_WORKFLOW.md
  - docs/rfc/RFC-2026-05-19-foundation-freeze.md (implemented)
  - docs/rfc/RFC-2026-05-20-foundation-module-interface.md (accepted)
  - docs/rfc/RFC-2026-05-21-phase-2-governance-architecture.md (accepted)
---

# gbrain absorption — 6 candidates + 2 carrier modules

> **本文档同时是 PRD（项目需求文档）与 substantive gate RFC**。按 `docs/PROJECT_WORKFLOW.md` 走 4-Milestone 流程；本身作为 M1 主交付物，land 时按 `CHARTER.md` §5 substantive gate 走（rationale / 反对 addressed / 影响清单 / ack #1 齐备）。

## §1 Rationale

### §1.1 项目背景

2026-05-20 完成 gbrain (https://github.com/garrytan/gbrain) 与 Life Index 多维对比研究（见 `.strategy/cli/2026-05-20-gbrain-life-index-comparison-archive.md`），输出 6 个借鉴候选 + 抽象路线（见 `.strategy/cli/2026-05-20-gbrain-absorption-roadmap.md`）。

2026-05-21 Foundation Freeze v1 退出（commit `bc16707`），Phase-2 通道打开。本项目是 Phase-2 第一个实质性产品工作。

### §1.2 为什么现在做

Life Index 当前局部弱于 gbrain 的能力：

- **检索质量评估面单薄**：缺 graph ablation / source-tier eval
- **后台维护循环缺失**：CHARTER §1 反复强调 audit / freshness 但无自动化 nightly/weekly
- **关系图谱无自动候选**：Entity Graph 完全靠人工治理，缺低风险的"候选边"探针
- **检索模式单一**：search/smart-search 接口缺 default/recall/deep 分档语义
- **趋势分析缺失**：既有日志字段未被结构化提取为 typed observations

借鉴 gbrain 的对应能力，可在 **不破坏 CHARTER §1.1-§1.10 invariants**、**不引入外部 DB 依赖**、**不默认开启 LLM** 的前提下，把 CLI 检索/治理面提升到与 gbrain 评估架构对齐的水平。

### §1.3 为什么一次性扫 6 项

3 选 1（详见 §8 反对 addressed §8.1）：

- 一次性扫降低**研究上下文丢失风险**：现在 2026-05-21 离研究新鲜度最高，分散到未来按需拉动会迫使每次重新加载 gbrain 上下文
- 6 项之间**有相互验证关系**（#1 eval 验证 #2 + #4 maintenance smoke 调 #1 + #3），分开做反而损失协同
- **6 worktree 并行**实际 wall clock 与单 phase 差异不大（5-10 天），不显著拖慢 Phase-2 启动

## §2 目标 & 非目标

### §2.1 目标（必须做）

1. 实现 6 个 gbrain 借鉴候选，每个落到 §3 表中指定的层级
2. 创建 2 个载体模块 `tools/recall/` 与 `tools/trajectory/`，作为 #5/#6 的真实消费者
3. 通过 #1 ablation eval 量化 #2 source-tier 对 P@5/R@5/MRR@5 的影响
4. 整套 CHARTER §1.1-§1.10 invariants 守住（详 §4 影响清单）
5. CHANGELOG `[Unreleased]` 补齐 6 + 2 user-facing 条目
6. 项目完成后，"gbrain 题材"声明闭合（lock），后续 gbrain 衍生改动必须起新 RFC

### §2.2 非目标（不做 / 禁止做）

- **不引入 Postgres / PGLite 或任何外部 DB 依赖**（gbrain 用 PGLite，Life Index 保持 SQLite + 向量索引文件 + Markdown 文件）
- **不引入默认路径 LLM 调用**（CHARTER §1.5 / §1.9 —— deep mode 在 #5 必须显式 opt-in）
- **不引入 dream synthesis / LLM 抽取 facts/takes**（CHARTER §1.5 / §1.9 / 隐私边界）
- **不自动写 production Entity Graph**（#3 candidate edges 只出报告，不落 `entity_graph.yaml`）
- **不扩 L1 frontmatter / journal schema**（#6 typed observations 只读既有字段，CHARTER §1.8）
- **不引入 reranker 外部依赖（如 ZeroEntropy）**（保持本地 SQLite + sqlite-vec）
- **不实现 #4 maintenance 的自动修复**（dry-run / report-only，CHARTER §1.10 用户保留决策权）
- **不锁 L2 surface 演进**（lock 范围仅限 gbrain 题材，与 §1.10 / §5 流程并存）

### §2.3 Lock 定义（项目完成后生效）

- AGENTS.md / CHANGELOG 加注："gbrain absorption closed by `docs/projects/gbrain-absorption/PRD.md` (2026-05-2X implemented)"
- 后续 gbrain 衍生改动（拉新候选、改本期决策）必须起新 RFC，不能 silent 改本期产物
- 非 gbrain 衍生的 L2 演进**不受限**（按 CHARTER §1.10 / §5 既有流程走）

## §3 Scope：6 候选 × 落点 × 消费者 + 2 载体模块

| # | gbrain 候选 | 落点 | 实际消费者 | 文件/surface |
|---|---|---|---|---|
| 1 | Graph ablation eval | cross-cutting eval | 项目内 #2 验证 + #4 smoke 调用 | `tools/eval/ablation/` + `entity-graph-eval` CLI |
| 2 | Source-tier / evidence-tier boost | L2 (search ranking) | #1 eval 作 target；future modules 拉 | `tools/search_journals/ranking.py` 加 tier weights + `search_constants.py` 参数 |
| 3 | Candidate edges 报告 | cross-cutting eval (report-only) | 用户人工 review；#4 maintenance 引用 | `entity --candidate-edges` CLI 子命令 |
| 4 | Maintenance cycle | cross-cutting maintenance | 用户 nightly/weekly 跑 | `maintenance` CLI 命令 (新 L2 命令) |
| 5 | Search modes (default/recall/deep) | `tools/recall/` 模块 | recall 模块本身 | `tools/recall/` (新 L3 模块) |
| 6 | Facts/trajectory 窄版 | `tools/trajectory/` 模块 | trajectory 模块本身 | `tools/trajectory/` (新 L3 模块) |

### §3.1 载体模块边界

**`tools/recall/`** (Phase E 产物):
- 通过 subprocess 调用 L2 `search` / `smart-search`（同 `on_this_day` 模式）
- 暴露 `recall --mode={default|recall|deep}` CLI
- `default` = 仅 FTS 关键词（最快、最确定性）
- `recall` = 既有 hybrid（FTS + semantic + RRF）
- `deep` = `recall` + LLM query expansion **必须显式 `--use-llm`**，否则降级到 `recall`
- 失败可降级，三模式输出可审计差异
- **零 L2 改动**（不动 search / smart-search 命令本体）

**`tools/trajectory/`** (Phase F 产物):
- 通过 subprocess 调用 L2 `search` / `aggregate` / `analyze`
- 暴露 `trajectory --field={weight|sleep|mood|location|project} --range={...}` CLI
- 只读既有 L1 字段（frontmatter / journal 正文标记）
- 输出 typed observation JSON：`{type, value, time, evidence_paths[]}`
- **零 L1 schema 写**（不扩 frontmatter / journal 标准字段）
- evidence_paths 全可追溯

## §4 影响清单

### §4.1 文件改动汇总

| 文件 | 改动类型 |
|---|---|
| `tools/eval/ablation/` | 新建（Phase A）|
| `tools/eval/ablation/__main__.py` | 新建 CLI 入口 `entity-graph-eval` |
| `tools/search_journals/ranking.py` | 加 tier weights（Phase B）|
| `tools/search_journals/search_constants.py` | 加 tier 参数（Phase B）|
| `tools/entity/__main__.py` | 加 `--candidate-edges` flag（Phase C）|
| `tools/maintenance/` | 新建（Phase D，新 L2 命令）|
| `tools/recall/` | 新建（Phase E）|
| `tools/trajectory/` | 新建（Phase F）|
| `tests/contract/test_ablation_eval_contract.py` | 新建 |
| `tests/contract/test_source_tier_contract.py` | 新建 |
| `tests/contract/test_candidate_edges_contract.py` | 新建 |
| `tests/contract/test_maintenance_contract.py` | 新建 |
| `tests/contract/test_recall_contract.py` | 新建 |
| `tests/contract/test_trajectory_contract.py` | 新建 |
| `tests/contract/test_layer_invariants.py` | 扩展（验 6+2 surface 守 §1.5）|
| `docs/API.md` | 加 `entity-graph-eval` / `maintenance` / `recall` / `trajectory` 文档 + schema_version |
| `docs/ARCHITECTURE.md` | 加 ranking tier 说明 + 4 新 surface 说明 |
| `CHANGELOG.md` `[Unreleased]` | 加 6+2 user-facing 条目 |
| `AGENTS.md` | 加 "gbrain absorption closed" 注；版本 v3.5 → v3.6 |

### §4.2 Invariant 影响 check

| invariant | 影响 | 处置 |
|---|---|---|
| §1.1 数据主权 | 无 | — |
| §1.5 L2 不持 LLM | 守住：default 路径全部 0 LLM；`recall --mode=deep` 与既有 `smart-search --use-llm` 同形态 opt-in | 测试断言 |
| §1.7 三条底线 | 无 | — |
| §1.8 高迁移成本 schema | 守住：#6 typed observation 只读既有字段，不扩写 L1 | 测试断言 |
| §1.9 Agent-Native Module | 守住：recall / trajectory / maintenance default 无 LLM；可 opt-in | 测试断言 |
| §1.10 Module-Foundation 边界 | #2 source-tier 是 L2 promotion，但本期同时有 #1 eval 作真实消费者；其余 L3 候选放载体模块本地 | §4.3 详 |
| §5 修订流程 | 本 PRD-RFC 走 substantive gate，无 invariant amendment | — |

### §4.3 §1.10 ≥2 模块复用门 处置

CHARTER §1.10 要求 L2 原语升格需 "≥2 模块需要或清晰架构理由"。本期 #2 source-tier 进 L2 search ranking，理由：

- **#1 ablation eval** 是即时消费者（用 source-tier 作 eval target，量化 graph + tier 组合效果）
- **#4 maintenance cycle** 的 smoke check 会调 #1 eval，间接复用 #2
- **#5 recall 模块**的 `recall` 与 `deep` 两档自然受益于 ranking tier weights（多模块复用）
- 清晰架构理由：tier weighting 是确定性 ranking 策略，与 ranking 调用方解耦，本质上是 L2 自然延伸

满足 §1.10 "≥2 消费者 + 清晰架构理由" 双重门。

### §4.4 与既有 RFC 兼容性

| RFC | 状态 | 本期影响 |
|---|---|---|
| RFC-2026-05-15 模块开发者契约 | accepted | 本期 2 载体模块遵守此契约 |
| RFC-2026-05-19 Foundation Freeze v1 | implemented | 已退出，本期是 Phase-2 工作，不冲突 |
| RFC-2026-05-20 foundation-module-interface | accepted | 本期 #2 L2 promotion 走此 RFC §3 「原语升格」流程 |
| RFC-2026-05-20 governance-scope-correction | accepted | 本 PRD-RFC 自身走此 RFC 定义的 substantive gate |
| RFC-2026-05-20 inheritor-as-product-object | accepted | 不冲突 |
| RFC-2026-05-21 phase-2-governance-architecture | accepted | 本期是其首次实战验证 |

**无冲突**。

## §5 Phase 拆分（× 派发纪律 3 门 × 每 Phase）

### Phase A — `gbrain-A` — Graph ablation eval

- **可证伪退出**：`python -m tools.eval.ablation --queries=tests/fixtures/eval/ablation_queries.json --output=stdout` 输出 JSON 含 `entity_graph={true,false}` × `semantic={true,false}` × `hybrid={true,false}` 8 种组合的 P@5/R@5/MRR@5；契约测试 `test_ablation_eval_contract.py` 通过
- **真实消费者**：#2 source-tier（Phase B）跑后用本 eval 验证 lift；#4 maintenance（Phase D）smoke 调用
- **有界自主**：可写 `tools/eval/ablation/` + `tests/contract/test_ablation_eval_contract.py` + `tests/fixtures/eval/ablation_queries.json`；可读 `tools/search_journals/` / `tools/entity/` / `tools/lib/`；**不动** L2 search / smart-search 源码

### Phase B — `gbrain-B` — Source-tier boost

- **可证伪退出**：`search` 启用 tier weights（参数在 `search_constants.py`）；`test_source_tier_contract.py` 通过；Phase A eval 跑后 `tier=on` vs `tier=off` 的 P@5 delta documented（正/负/null 均接受，要写入 `.strategy/cli/2026-05-2X-source-tier-eval-result.md`）
- **真实消费者**：#1 eval（即时验证）；future modules（如 memoir / evidence pack）
- **有界自主**：可写 `tools/search_journals/ranking.py` / `search_constants.py` / `tests/contract/test_source_tier_contract.py`；可读 `tools/eval/ablation/`；**不动** smart-search planner / entity 命令
- **依赖**：Phase A 必须 merged 才能跑 eval

### Phase C — `gbrain-C` — Candidate edges 报告

- **可证伪退出**：`entity --candidate-edges --output=json` 输出 `[{type, source, target, evidence_paths, confidence, suggested_action}]`；零 `entity_graph.yaml` 写入断言通过；`test_candidate_edges_contract.py` 通过
- **真实消费者**：用户人工 review；Phase D maintenance 引用
- **有界自主**：可写 `tools/entity/__main__.py` 加 `--candidate-edges` 分支 + `tools/entity/candidate_edges.py` + `tests/contract/test_candidate_edges_contract.py`；可读全仓库；**不动** Entity Graph 现有写入逻辑

### Phase D — `gbrain-D` — Maintenance cycle

- **可证伪退出**：`maintenance --dry-run` 输出 6 类检查报告（index freshness / entity audit / orphan related_entries / search eval smoke / backup verification / candidate edges 数量）；零 production 写入断言通过；`test_maintenance_contract.py` 通过
- **真实消费者**：用户 nightly/weekly 跑；CI cron（如启用）
- **有界自主**：可写 `tools/maintenance/` + `tests/contract/test_maintenance_contract.py`；可读 `tools/eval/ablation/` / `tools/entity/` / `tools/build_index/` / `tools/backup/`；**不动** 被调用模块的源
- **依赖**：Phase A + Phase C 必须 merged

### Phase E — `gbrain-E` — Recall 模块 + #5 search modes

- **可证伪退出**：`recall --mode=default|recall|deep` 通过 subprocess 调 L2；`test_recall_contract.py` ≥ 9 通过（3 modes × 3 case：basic / no_results / opt-in 边界）；deep 模式无 `--use-llm` 时降级到 recall；零默认 LLM 断言通过
- **真实消费者**：recall 模块本身（Step 3 真模块的 v1）
- **有界自主**：可写 `tools/recall/` + `tests/contract/test_recall_contract.py`；可读 L2 search / smart-search CLI 文档；**不动** L2 search / smart-search 本体

### Phase F — `gbrain-F` — Trajectory 模块 + #6 facts/trajectory

- **可证伪退出**：`trajectory --field={weight|sleep|mood|location|project} --range=...` 输出 typed observation JSON 含 `evidence_paths`；零 L1 schema 写断言通过；`test_trajectory_contract.py` 通过（每 field 至少 1 测）
- **真实消费者**：trajectory 模块本身（Step 3 真模块的 v1）
- **有界自主**：可写 `tools/trajectory/` + `tests/contract/test_trajectory_contract.py`；可读 L2 search / aggregate / analyze CLI 文档；**不动** L1 frontmatter / journal 写入

## §6 依赖图 + Worktree 拓扑

```
gbrain-A (#1 ablation eval)   ──┐
                                 ├─ merge ─> gbrain-B (#2 source-tier)
gbrain-C (#3 candidate edges) ──┤
                                 ├─ merge ─> gbrain-D (#4 maintenance)
gbrain-E (#5 + tools/recall/) ──── 独立
gbrain-F (#6 + tools/trajectory/) 独立
```

**Worktree 拓扑**：

| Worktree | 分支 | Phase | 并行波次 |
|---|---|---|---|
| `gbrain-A` | `claude/gbrain-A` | #1 ablation eval | 1（同时启 A/C/E/F）|
| `gbrain-C` | `claude/gbrain-C` | #3 candidate edges | 1 |
| `gbrain-E` | `claude/gbrain-E` | #5 + recall | 1 |
| `gbrain-F` | `claude/gbrain-F` | #6 + trajectory | 1 |
| `gbrain-B` | `claude/gbrain-B` | #2 source-tier | 2（after A）|
| `gbrain-D` | `claude/gbrain-D` | #4 maintenance | 2（after A + C）|

**主控 Agent** 在 main 上做 PR 验收（M3 并行线 1），不占独立 worktree。

**估计 wall clock**：5-10 天（瓶颈是 Phase F，预计 L 规模 >3 天）。

## §7 完成定义（可证伪）

Item 2 完成 **当且仅当** 下列全部 ✅：

1. 6 个 phase（A-F）各自的"可证伪退出"标准全部 PASS
2. 所有契约测试（6 个新 + layer invariant 扩展）整体绿，整套 contract+integration 通过
3. `entity-graph-eval` 跑过，输出 `tier=on` vs `tier=off` 的 lift 报告（数值 documented，不强制为正）
4. Gold Set 回归 ≥ 基线（CHARTER §4.5）
5. CHANGELOG `[Unreleased]` 含 6 个候选 + 2 模块 user-facing 条目
6. AGENTS.md v3.6 含 "gbrain absorption closed" 注 + 本 PRD-RFC 路径
7. 本 PRD-RFC frontmatter `status: implemented`
8. atomic governance commits 已 push origin/main

## §8 反对意见 addressed（substantive gate item）

### §8.1 「为何一次性扫 6 项？为何不按现有 roadmap 等真实模块拉动？」

`.strategy/cli/2026-05-20-gbrain-absorption-roadmap.md` §3 写「Freeze 期不实施，等真实模块拉动」。本 PRD 在 Freeze 退出后做，不与 roadmap §3 直接冲突；本期通过**同时创建 2 个载体模块**（recall + trajectory）解决"无真实消费者"问题：

- #2 source-tier 由 #1 eval 即时消费（不需等未来模块）
- #5 search modes 由 `tools/recall/` 消费（本期同时创建）
- #6 facts/trajectory 由 `tools/trajectory/` 消费（本期同时创建）
- #1 / #3 / #4 是 cross-cutting eval/maintenance，独立成立无需 L3 消费者

故实际**不 bypass** 真实消费者门，而是**同时创建消费者**。

### §8.2 「6 phase 并行会不会引入 merge 冲突？」

phase 间文件域**几乎不重叠**：

- A 写 `tools/eval/ablation/`
- B 写 `tools/search_journals/ranking.py` + `search_constants.py`
- C 写 `tools/entity/__main__.py` (加 flag 分支) + `tools/entity/candidate_edges.py`
- D 写 `tools/maintenance/`
- E 写 `tools/recall/`
- F 写 `tools/trajectory/`

唯一交集是：
- `docs/API.md`（多 phase 加文档）→ 按 phase 顺序 merge，每 phase merge 时 rebase
- `CHANGELOG.md` `[Unreleased]`（多 phase 加条目）→ 同上
- `tests/contract/test_layer_invariants.py`（扩展断言）→ 由先 merge 的 phase 完成扩展，后续 phase rebase

可控。

### §8.3 「`tools/recall/` 与 `smart-search` 重复 / overlap？」

不重复：

- `smart-search` 是 **L2 命令**（直接 plan + execute search，带 opt-in LLM expansion）
- `tools/recall/` 是 **L3 模块**（通过 subprocess 调 L2，提供 mode 切换抽象）
- 类似 `tools/on_this_day/` 与 `search` 的关系 —— L3 消费 L2

未来可能将 `recall` mode 抽象升格为 L2（如多模块需要），届时按 §1.10 走升格流程。本期不预设此升格。

### §8.4 「PRD-RFC 合二为一是否合规？」

`docs/PROJECT_WORKFLOW.md` "PRD vs RFC 关系" §明文允许："小型任务：单个 RFC = PRD（合二为一）"。

本期严格来说是中-大型项目（6 phase），但只需**单一 substantive gate**（整体 scope 已经 brainstorming 阶段决议；phase 内部不需要再起子 RFC），合二为一形态合规且降低治理开销。

如执行中（M2/M3）出现需要 substantive 决策的子问题，按 PROJECT_WORKFLOW M3 §异常 escalate 走 —— 回 M1 起子 RFC 或修本 PRD。

### §8.5 「`maintenance` 命令是新 L2，CHARTER §1.10 怎么过？」

`maintenance` 命令本质是 **既有命令的 dry-run 编排器**：调 `entity --audit` / `build-index --check` / `search` eval smoke / `backup --verify`。它的 "新 L2" 性质是 surface 上的 —— 实现是组合 L2，不引入新原语。

从 §1.10 视角：
- 不是 "新原语"，是 "L2 命令编排"
- 类比：既有 `generate-index` 命令也是组合多个 L2 步骤
- 真实消费者：用户的 nightly/weekly 健康巡检

满足 §1.10。

### §8.6 「`recall` 的 `deep` 模式 LLM opt-in，会不会破 §1.5？」

§1.5 禁的是 **L2 默认路径** LLM。`recall` 是 L3 模块，且 `deep` 必须显式 `--use-llm`（与既有 `smart-search --use-llm` 同形态），不破 §1.5。

测试断言：`recall --mode=deep` 不带 `--use-llm` 时降级到 `recall` mode，零 LLM 调用 trace。

## §9 后续动作锚点

- **本期 M1 ack #1 后**：进 M2（任务编排）—— 主控 Agent 检出 6 worktree + 生成 6 份 Phase TDD brief
- **本期 M4 ack #2 后**：本 PRD-RFC status → implemented；AGENTS.md 加注；CHANGELOG 同步；"gbrain 题材锁定"声明
- **Step 3 启动时**：`tools/recall/` 与 `tools/trajectory/` 作为已存在的 v1 模块，由 Step 3 真模块（memoir / health-trend / GUI）按需扩 v2
- **6 个月后 retrospective**（2026-11-21 前后）：评估 #2 source-tier lift 数据是否符合预期、6 个 phase 是否有事后发现的隐藏冲突

## §10 Ack #1

- [x] ack #1 by Life Index Developer (2026-05-21)
- approved: 2026-05-21
- approved-by: Life Index Developer
