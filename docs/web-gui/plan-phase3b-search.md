# Phase 3b: Search — Split Subplan

**Parent plan:** [`plan-phase3-journal-search.md`](plan-phase3-journal-search.md)  
**Owns:** Task 10 (`web/services/search.py` + `web/routes/search.py` + templates)  
**Why this split exists:** Search 有自己的参数映射、HTMX 局部渲染和结果整形，不应与 Journal View 混写。

**Shared contracts:** [`shared-contracts.md`](shared-contracts.md)

## Scope

- `web/services/search.py`
- `web/routes/search.py`
- `web/templates/search.html`
- `web/templates/partials/search_results.html`

## Contracts You Must Preserve

See [`shared-contracts.md`](shared-contracts.md) for canonical definitions.

- 原始搜索结果 `path` 不可直接用于前端路由
- 输出给模板的 link 字段必须是 `journal_route_path`
- 空结果与执行失败必须区分
- HTMX partial 与 full-page 渲染分离

## Dependencies

- Depends on: Phase 1 scaffold
- Can coexist with: `plan-phase3a-journal-view.md`

## Verification

- `/search` full page works
- HX-Request partial works
- search result links use normalized route path
- filters map cleanly to `hierarchical_search()`
