# Phase 4c1: Edit Service — Split Subplan

**Parent plan:** [`plan-phase4c-edit.md`](plan-phase4c-edit.md)  
**Owns:** Task 12 中 `web/services/edit.py` 部分  
**Why this split exists:** diff computation 与 edit route/template 分离后更容易验证 E0504 语义。

**Shared contracts:** [`shared-contracts.md`](shared-contracts.md)

## Scope

- `compute_edit_diff()`
- `query_weather_for_location()`
- location/weather coupling support

## Contracts You Must Preserve

See [`shared-contracts.md`](shared-contracts.md) for canonical definitions.

- content compare uses `_body`
- location changed ⇒ weather must accompany mutation
- service 不直接渲染模板

## Dependencies

- Depends on: Phase 3 journal view contract
- Feeds into: `plan-phase4c2-edit-route-template.md`

## Verification

- unchanged fields omitted
- E0504 support path is explicit
- weather auto-query failure handled as documented
