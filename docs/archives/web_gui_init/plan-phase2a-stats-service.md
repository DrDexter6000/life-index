# Phase 2a: Stats Service — Split Subplan

**Parent plan:** [`plan-phase2-dashboard.md`](plan-phase2-dashboard.md)  
**Owns:** Task 7 (`web/services/stats.py`)  
**Why this split exists:** 将 Dashboard 的数据聚合与页面渲染分离，降低单文档认知负担。

**Shared contracts:** [`shared-contracts.md`](shared-contracts.md)

## Scope

本子计划只负责：

- `web/services/stats.py`
- `tests/unit/test_web_dashboard.py` 中与 stats 聚合直接相关的测试
- `journal_route_path` 所需的 Dashboard 结果整形

本子计划不负责：

- `web/routes/dashboard.py`
- `web/templates/dashboard.html`
- ECharts 初始化与模板交互细节

## Contracts You Must Preserve

See [`shared-contracts.md`](shared-contracts.md) for canonical definitions.

- 使用 `tools.lib.metadata_cache.get_all_cached_metadata()` 作为元数据主入口
- 读取正文时使用 `parse_journal_file(...)["_body"]`
- 输入路径通常是绝对 `file_path`
- 输出到模板层的日志链接字段必须是 `journal_route_path`
- 不直接定义新的 path contract；统一服从 `implementation-plan.md` 中的 Web Path Normalization Rule

## Files

- Create/Modify: `web/services/stats.py`
- Test: `tests/unit/test_web_dashboard.py`

## Dependencies

- Depends on: Phase 1 scaffold
- Must finish before: `plan-phase2b-dashboard-route-template.md`

## Execution Notes

- 详细 TDD 步骤仍以父文档 `plan-phase2-dashboard.md` 的 **Task 7** 为准
- 如果后续继续精拆，应把 Task 7 的完整 step-by-step 内容迁移到本文件，再把父文档降级为 index

## Verification

- stats 单测通过
- 空数据 / 缺失字段 / on-this-day / streak / word-count 均覆盖
- 模板消费字段中不再泄露原始 `file_path` 作为路由链接
