# Round 7 Execution Audit — v1.6.5 Entity Graph Evolution

> **审计日期**：2026-04-14
> **归档校准日期**：2026-04-14
> **审计范围**：Round 7 PRD 全部 3 Phase、12 Task 的实际代码 / 测试 / 文档一致性
> **审计方法**：直接源码读取 + 关键测试执行 + Explore / Oracle 交叉复核
> **最终结论**：**Round 7 已完成，可关闭**

---

## 一、总评

| 维度 | 评级 | 说明 |
|------|------|------|
| Entity CLI 工具链 (`tools/entity/`) | ✅ 完成 | review / merge / delete / stats / check / csv-xlsx review aid 均有实代码、测试、CLI 入口 |
| Search 热路径集成 | ✅ 完成 | `entity_runtime` 已接入 `search_journals/core.py`，search 输出包含 `entity_hints` |
| Write 热路径集成 | ✅ 完成 | `entity_candidates` 已接入 `write_journal/core.py`，write 输出包含 `entity_candidates` |
| Phase 3 维护增强 | ✅ 完成 | `entity --stats` / `--check` / relation normalization / CSV-Excel export-import 全部可用 |
| 文档一致性 | ⚠️ 已校准 | 初版审计存在 grep 误判；本归档版已与当前代码和 SSOT 文档对齐 |
| 测试状态 | ✅ 全绿 | `pytest tests/unit/` 全量通过，4 个 Unix-only skip，0 fail |

**一句话结论**：Round 7 的 Entity Graph Evolution 已实质完成。Entity CLI 子系统、search/write 热路径、维护增强与相关测试都已落地，当前已可作为完成轮次归档。

---

## 二、关键勘误

### 勘误 1：热路径“未接入”是误判

初版审计曾误判以下两项未完成：

- `entity_runtime -> search_journals`
- `entity_candidates -> write_journal`

误判根因：当时 grep 只检查了绝对导入 `from tools.lib.xxx`，遗漏了项目实际大量使用的相对导入 `from ..lib.xxx`。

经直接读取源码确认：

- `tools/search_journals/core.py`
  - 导入 `entity_runtime`
  - 初始化并输出 `entity_hints`
  - 通过 `resolve_query_entities()` 与 `expand_query_with_entity_graph()` 使用 runtime view
- `tools/write_journal/core.py`
  - 导入 `extract_entity_candidates`
  - 在 enrich 阶段调用并写入 `result["entity_candidates"]`

因此，Round 7 的两条核心热路径集成**实际已完成**。

### 勘误 2：`timing.py` 不是死代码

初版审计曾把 `timing.py` 判为“无消费者”。复核后确认：

- `write_journal/core.py` 直接导入并使用 `Timer`
- `search_journals` / `build_index` 的观测层主要使用 `trace.py`

所以更准确的表述是：

- `timing.py` = **write_journal 专用性能计时工具**
- `trace.py` = **search / build / write 的 step-based observability 基础设施**

---

## 三、Phase 逐项审计

### Phase 1 — Entity Graph Serving Layer + Search Integration (P0)

| TDD 勾选声明 | 实际状态 | 证据 |
|---|---|---|
| Entity runtime view 支持 reverse lookup 与 controlled phrase patterns | ✅ 已完成 | `entity_runtime.py` 143 行，`build_runtime_view()` + `EntityRuntimeView` dataclass，phrase registry 已落地 |
| Search 对 alias / role / relationship phrase 的展开覆盖 | ✅ 已完成 | `search_journals/core.py` 的 expansion 逻辑使用 runtime view + phrase patterns |
| Search JSON 响应包含 `entity_hints` / suggestion 字段 | ✅ 已完成 | `search_journals/core.py` 初始化并填充 `entity_hints`，`test_search_entity_hints.py` 覆盖验证 |
| `entity_cache.py` cache-first helper 已实现 | ✅ 已完成（实现层） | `entity_cache.py` 提供 `is_cache_fresh()` + `resolve_entity_cached()` |
| `entity_cache.py` 是当前 search/write 主热路径的一部分 | ⚠️ 否 | 当前主热路径以 `entity_runtime` 为主；`entity_cache` helper 已落地，但未被 search/write 直接导入 |
| Phase 1 regression tests + benchmark tests 全绿 | ✅ 已完成 | Phase 1 相关测试存在且当前全量 unit 回归通过 |

**Phase 1 判定**：完成。需要特别说明的是，Phase 1 的战略目标已经实现，但“cache activation”的最终形态是 **cache-first helper 已实现、runtime view 成为主 serving path**，而不是所有 read path 都直接调用 `entity_cache.py`。

---

### Phase 2 — Write-Time Candidates + Pure CLI Review Closure (P1)

| TDD 勾选声明 | 实际状态 | 证据 |
|---|---|---|
| `write_journal` 返回 `entity_candidates`，覆盖 frontmatter + body mention | ✅ 已完成 | `write_journal/core.py` 直接导入并调用 `extract_entity_candidates()` |
| candidate layer 被正式定义，不依赖额外 GUI 或外部工具 | ✅ 已完成 | `entity_candidates.py` 已落地，write 输出直接暴露结果 |
| `life-index entity review` 提供 pure CLI 完整审订闭环 | ✅ 已完成 | `entity/review.py` 风险优先排序 + preview-then-commit |
| review queue 按风险优先排序 | ✅ 已完成 | 高 / 中 / 低风险分层清晰 |
| 高风险项默认支持合并 / alias / 分离 / 手动编辑 / 跳过 | ✅ 已完成 | review action applicator 已落地 |
| 所有图谱写回采用 preview-then-commit | ✅ 已完成 | review workflow 先生成 preview，再确认写回 |
| `life-index entity --merge` 可合并实体 | ✅ 已完成 | entity CLI 子命令可用 |
| `life-index entity --delete` 可安全删除 | ✅ 已完成 | entity CLI 子命令可用 |
| Phase 2 相关 docs 已同步 | ✅ 已完成 | 当前 API / strategy / roadmap / audit 已完成本轮校准 |
| 全量 `pytest` 无回归 | ✅ 已完成 | 当前 unit 回归全绿 |

**Phase 2 判定**：完成。

---

### Phase 3 — Maintenance Enhancements + CSV/Excel Review Aid (P2)

| TDD 勾选声明 | 实际状态 | 证据 |
|---|---|---|
| `entity --stats` 输出覆盖率 / 引用 / 共现 | ✅ 已完成 | `stats.py` 已实现 |
| `entity --check` 输出快速 integrity report | ✅ 已完成 | `check.py` 已实现 |
| relation normalization helper 已落地 | ✅ 已完成 | `entity_relations.py` 已实现 |
| CSV / Excel export-import 已定义并落地 | ✅ 已完成 | `review_io.py` 已实现，xlsx 缺依赖时 graceful degrade |
| 本地 HTML 页面保持后续增强定位 | ✅ 已完成 | 未提前膨胀 scope |
| Phase 3 docs 已同步 | ✅ 已完成 | 当前归档文档已校准 |
| 全量 `pytest` 无回归 | ✅ 已完成 | 当前 unit 回归全绿 |

**Phase 3 判定**：完成。

---

## 四、测试与质量结论

### 当前验证结果

| 范围 | 结果 |
|------|------|
| `pytest tests/unit/` | ✅ 全绿，4 个 Unix-only skip |
| `test_search_entity_hints.py` | ✅ 通过 |
| `test_entity_search_expansion_v2.py` | ✅ 通过 |
| `test_entity_candidates_on_write.py` | ✅ 通过 |
| `test_metadata_cache.py::TestCachePerformance::test_cache_faster_than_parsing` | ✅ 已修复并稳定通过 |

### 质量判断

- **代码质量**：高。Round 7 不是“模块空壳”，而是有真实实现、真实调用、真实测试的完整交付。
- **接口质量**：高。`entity_hints` 与 `entity_candidates` 都已进入调用方可消费的 JSON contract。
- **架构质量**：高。`entity_graph.yaml` 仍然是 SSOT；runtime view、cache helper、candidate layer 都是派生层，没有破坏项目的 local-first / human-readable 原则。

### 非阻塞遗留项

- `errors.py` 仍是**部分集成**，不是 Round 7 blocker
- `entity_cache.py` 已实现但不是当前主热路径；这是**实现路径差异**，不是 Round 7 未完成

---

## 五、归档前修正（已完成）

本次归档校准已经完成以下修正：

1. 清除了“search/write 热路径未接入”的旧误判
2. 修正了 `timing.py` / `trace.py` / `entity_runtime.py` 等模块的文档登记
3. 修正了 Round 7 优化计划中把已完成工作当作待执行工作的残留内容
4. 修正了顶层 `.strategy/strategy.md`、`.strategy/ROADMAP.md`、`.strategy/cli/TDD.md` 的阶段状态漂移
5. 修正了 `docs/API.md` 中未体现 Round 7 输出字段的接口示例

---

## 六、最终判定

| 项目 | 结论 |
|------|------|
| Round 7 是否完成 | **是** |
| Round 7 质量评级 | **高** |
| 是否存在阻止归档的缺口 | **否** |
| 是否可以进入下一轮（Round 8 Prep） | **是** |

**最终结论**：Round 7 已完成，质量高，可以关闭并归档。后续工作应进入 Round 8 准备或新一轮维护计划，而不是继续把 Round 7 当作未完成轮次处理。

---

*本文件为 Round 7 最终归档版审计报告。所有结论以当前代码、测试与已校准的 SSOT 文档为依据。*
