# Phase 2b: Dashboard Route + Template — Split Subplan

**Parent plan:** [`plan-phase2-dashboard.md`](plan-phase2-dashboard.md)  
**Owns:** Task 8 (`web/routes/dashboard.py` + `web/templates/dashboard.html`)  
**Why this split exists:** 将 Dashboard UI 渲染与 stats 聚合分离，减少跨层跳转。

**Shared contracts:** [`shared-contracts.md`](shared-contracts.md)

## Scope

本子计划只负责：

- `web/routes/dashboard.py`
- `web/templates/dashboard.html`
- 由 route 将 stats service 结果喂给模板

本子计划不负责：

- stats 聚合算法本身
- 额外的数据契约设计

## Contracts You Must Preserve

See [`shared-contracts.md`](shared-contracts.md) for canonical definitions.

- 只消费 `web/services/stats.py` 的输出
- 所有 journal 链接使用 `journal_route_path`
- Route 不做新的 journal/metadata 持久化逻辑
- 图表组件的降级行为必须与 design-spec 对齐

## Files

- Create/Modify: `web/routes/dashboard.py`
- Create/Modify: `web/templates/dashboard.html`
- Reuse: `web/templates/base.html`

## Dependencies

- Depends on: `plan-phase2a-stats-service.md`

## Execution Notes

- 详细 TDD 步骤仍以父文档 `plan-phase2-dashboard.md` 的 **Task 8** 为准
- 后续若继续精拆，父文档应仅保留 Phase Scope / prerequisites / checklist / split navigation

## Verification

- `/` 可正常渲染
- 所有 Dashboard journal link 指向 `/journal/{journal_route_path}`
- HTMX / Alpine / ECharts 相关模板引用不破坏 base layout
