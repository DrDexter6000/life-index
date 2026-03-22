# Phase 3a: Journal View — Split Subplan

**Parent plan:** [`plan-phase3-journal-search.md`](plan-phase3-journal-search.md)  
**Owns:** Task 9 (`web/services/journal.py` + `web/routes/journal.py` + `journal.html`)  
**Why this split exists:** Journal 阅读链路与 Search 链路职责不同，应单独执行与 review。

**Shared contracts:** [`shared-contracts.md`](shared-contracts.md)

## Scope

- journal path validation
- `get_journal(relative_path)` / route / template
- Markdown 渲染
- 附件展示
- 编辑入口链接

不包含：

- 搜索表单与搜索结果页
- Search service 的参数映射

## Contracts You Must Preserve

See [`shared-contracts.md`](shared-contracts.md) for canonical definitions.

- route 参数始终是 `journal_route_path`
- 使用 `_body` 而不是 `body`
- 路径穿越防护以 `JOURNALS_DIR` 为边界
- journal view 不重新定义底层 path contract

## Files

- `web/services/journal.py`
- `web/routes/journal.py`
- `web/templates/journal.html`
- `tests/unit/test_web_journal_search.py` 中 Task 9 相关部分

## Dependencies

- Depends on: Phase 1 scaffold
- Unblocks: Edit flow (`plan-phase4c-edit.md`)

## Verification

- `/journal/{journal_route_path}` works
- traversal → 404
- attachment rewriting works
- edit button points to `/journal/{journal_route_path}/edit`
