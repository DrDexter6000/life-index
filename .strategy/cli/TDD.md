# v1.6.5 Round 7 — Entity Graph Evolution TDD 总纲

> **起草日期**：2026-04-13
> **状态**：Round 7 已完成并归档关闭；下一轮参考 `Round_8_TDD_prep.md`
> **前置阅读**：`.strategy/cli/Round_7_PRD.md`
> **触发原因**：Entity Graph 专项审视确认其应升格为 CLI 下一阶段核心基础设施项目
> **范围**：Phase 1（Serving Layer + Search）+ Phase 2（Write + Pure CLI Review Closure）+ Phase 3（Maintenance Enhancements + CSV/Excel Review Aid）

---

## 战略定位

本轮目标是：**把 Entity Graph 从“静态实体登记表”升级成一个 active serving layer——真正参与搜索扩展、关键词建议、写入候选、图谱维护与未来 GUI 契约承接。**

不做图数据库。不做 GraphRAG。不做复杂 NLP。不引入后台进程。不把图谱写入逻辑变成黑箱自动化。

### Round 7 PRD 核心决策（本轮 authority）

| # | 决策 | 选择 | 理由 |
|---|------|------|------|
| A | Entity Graph 战略定位 | 升格为 CLI 核心基础设施项目 | 同时支撑 Layer 1 与未来 Layer 3 |
| B | Storage | YAML SSOT + 派生 cache / runtime view | 保持本地优先、人可读与轻量级 |
| C | Search 接入 | resolution + expansion + suggestion 三层 | 既增强召回，也返回机器可读 hints |
| D | Write 接入 | 输出 entity_candidates，并进入 candidate layer | 避免图谱污染 |
| E | Review 模型 | `entity review` 作为 review hub，默认 preview-then-commit | 让 pure CLI workflow 完整成立 |
| F | Manual Edit | Agent 对话式编辑为主，结构化表单为辅 | 适应文化语义歧义与人类表达习惯 |
| G | External review surfaces | CSV / Excel 优先，本地 HTML 页其次，且都不是前提 | 允许增强，但不改变 CLI-first 原则 |
| H | Phase 3 范围 | stats/check + relation normalization + CSV/Excel | 维护增强与批量人工校对留在 Round 7，但不挤压 pure CLI review 主线 |
| I | Graph DB / 大型 NLP | 全部不做 | 过度工程化，偏离项目边界 |

### 改进原则

- 不引入图数据库、不引入新后台进程
- SSOT 仍是 `entity_graph.yaml`
- 所有 serving layer 都是派生视图，可重建、可丢弃
- **CLI / Layer 1 优先**：pure CLI workflow 必须先闭环；CSV / Excel / HTML 只做增强，不做前提
- **每个测试必须包含真实 assert**，assert 对象必须是运行时输出
- **每个 Task 完成后立即 commit**，commit message 引用 Task 编号
- 向后兼容：新增 suggestion / candidate 字段不破坏现有 CLI 消费者
- **兼容期定义**：旧字段（如 `new_entities_detected`）在新字段上线后保留至少 1 个 minor version；如未来进入移除窗口，应先在输出中增加 `deprecated: true` 或等价标记，再在后续 minor version 移除

---

## TDD 文件拆分

| 文件 | 范围 | 预估任务数 | 优先级 |
|------|------|-----------|--------|
| **[Phase_1_TDD.md](./Phase_1_TDD.md)** | Entity Graph Serving Layer：runtime view + cache activation + search expansion/suggestion | Task 1 — Task 5 | P0 |
| **[Phase_2_TDD.md](./Phase_2_TDD.md)** | Write-time candidates + candidate layer + entity review hub + merge/delete + preview writeback | Task 6 — Task 8 | P1 |
| **[Phase_3_TDD.md](./Phase_3_TDD.md)** | stats/check + relation normalization + CSV/Excel review aid | Task 9 — Task 12 | P2 |

---

## 全局依赖图

```text
Phase 1 — Entity Graph Serving Layer + Search (P0)
══════════════════════════════════════════════════

Task 1 (runtime view: reverse index + pattern registry)
    │
    ├──▶ Task 2 (entity_cache activation)
    │        │
    │        └──▶ Task 3 (search expansion v2)
    │                   │
    │                   └──▶ Task 4 (search suggestion output contract)
    │
    └──▶ Task 5 (Phase 1 regression + benchmark)


Phase 2 — Write + Pure CLI Review Closure (P1)
════════════════════════════════════════════════════════════════

Task 6 (write-time entity candidates from frontmatter/body)
    │
    └──▶ Task 7 (entity review hub)
                │
                └──▶ Task 8 (entity --merge / --delete)

Phase 3 — Maintenance Enhancements + CSV/Excel Review Aid (P2)
══════════════════════════════════════════════════════════════

Task 9 (`entity --stats` / `entity --check`)
Task 10 (relationship vocabulary normalization helpers)
Task 11 (CSV / Excel export-import)
Task 12 (Phase 3 docs + regression sync)
```

**Phase 间依赖**：

- Phase 1 是 Phase 2 的前置基础，因为 write/search/maintenance 都要共享 runtime view 与 cache 能力
- Task 7 `entity review` 是 Phase 2 的 workflow anchor；merge/delete 应围绕 review hub 组织
- Phase 3 建立在 Phase 2 完成之后，属于维护增强与批量人工校对辅助
- CSV / Excel 审订表优先于本地 HTML 页面，但两者都建立在 Task 7 完成之后

---

## 新增错误码分配

| 模块 | 码段 | 用途 |
|------|------|------|
| Entity Runtime | E1000 — E1049 | runtime view / cache / pattern registry |
| Entity Maintenance | E1050 — E1099 | merge / delete / stats / check |
| Suggestion Contract | E1100 — E1129 | suggestion / candidate contract |

**具体错误码在各 Phase TDD 中定义。**

---

## 完成标志

本轮完成时，以下条件必须全部满足：

### Phase 1 完成标志 ✅ (2026-04-13)

- [x] Entity runtime view 支持 reverse lookup 与 controlled phrase patterns
- [x] `entity_cache.py` 实际接入 resolve/read 路径
- [x] Search 对 alias / role / relationship phrase 的展开覆盖不再局限于单一 hardcoded case
- [x] Search JSON 响应包含 `entity_hints` / suggestion 字段
- [x] Phase 1 regression tests + benchmark tests 全绿

### Phase 2 完成标志 ✅ (2026-04-13)

- [x] `write_journal` 返回 `entity_candidates`，覆盖 frontmatter + body mention
- [x] candidate layer 被正式定义，并不依赖额外 GUI 或外部工具即可工作
- [x] `life-index entity review` 提供 pure CLI 的完整 HITL review workflow
- [x] review queue 按风险优先排序：高风险重复/冲突 → 关系候选 → 新实体候选
- [x] 高风险项默认支持：合并 / 改为 alias / 保留分离 / 手动编辑 / 跳过
- [x] 所有图谱写回采用 preview-then-commit，而非逐条即时落盘
- [x] `life-index entity --merge` 可合并实体并保留 alias / relationship / refs
- [x] `life-index entity --delete` 可安全删除并报告/清理引用
- [x] Phase 2 相关 docs 已同步
- [x] 全量 `pytest` 无回归

### Phase 3 完成标志 ✅ (2026-04-14)

- [x] `life-index entity --stats` 输出覆盖率 / 引用 / 共现结构化统计
- [x] `life-index entity --check` 输出快速 integrity report
- [x] relation normalization helper 已落地
- [x] CSV / Excel export-import 被定义并落地为优先增强能力
- [x] 本地 HTML 页面仍保持后续增强定位
- [x] Phase 3 相关 docs 已同步
- [x] 全量 `pytest` 无回归

---

*本文件承接 Round 7 PRD，将 Entity Graph Evolution 需求转化为三阶段可执行 TDD 计划。*
