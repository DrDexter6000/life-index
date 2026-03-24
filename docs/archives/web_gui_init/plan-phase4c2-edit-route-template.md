# Phase 4c2: Edit Route + Template — Split Subplan

**Parent plan:** [`plan-phase4c-edit.md`](plan-phase4c-edit.md)  
**Owns:** Task 12 中 `web/routes/edit.py` + `web/templates/edit.html` 部分  
**Why this split exists:** 编辑页的 route、CSRF、weather API、template 交互不应和 diff service 混写。

**Shared contracts:** [`shared-contracts.md`](shared-contracts.md)

## Scope

- `GET /journal/{path}/edit`
- `POST /journal/{path}/edit`
- `GET /api/weather`
- `web/templates/edit.html`

## Contracts You Must Preserve

See [`shared-contracts.md`](shared-contracts.md) for canonical definitions.

- route path input is `journal_route_path`
- CSRF contract matches write route (`csrf_token` cookie + hidden field)
- path validation is allowed minimal route responsibility
- route delegates mutation to edit service / `tools.edit_journal`

## Dependencies

- Depends on: `plan-phase4c1-edit-service.md`, `plan-phase3a-journal-view.md`, `plan-phase4b1-write-route.md`

## Verification

- edit form prefill works
- weather API contract works
- success redirects back to journal route path
- failure preserves edit state
