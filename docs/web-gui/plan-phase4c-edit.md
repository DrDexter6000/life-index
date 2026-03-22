# Phase 4c: Edit Service + Route + Template — Thin Index

**Goal:** Split edit diff/weather logic from edit route/template UI while preserving E0504 and CSRF contracts.

**Shared contracts:** [`shared-contracts.md`](shared-contracts.md)

## What changed

原始超长版本已保留为：

- [plan-phase4c-edit-legacy-full.md](plan-phase4c-edit-legacy-full.md)

新的推荐执行入口：

- Edit service → [plan-phase4c1-edit-service.md](plan-phase4c1-edit-service.md)
- Edit route + template → [plan-phase4c2-edit-route-template.md](plan-phase4c2-edit-route-template.md)

## Dependency Summary

- depends on Task 9 journal view contract
- depends on Phase 4b CSRF/write-route contract

## Contracts to preserve

Contract definitions live in [`shared-contracts.md`](shared-contracts.md). This phase only highlights the parts it depends on:

- content diff uses `_body`
- location/weather coupling must satisfy E0504 semantics
- route path uses `journal_route_path`
- CSRF matches write route (`csrf_token` cookie + hidden field)

## When to use the legacy full doc

- 需要完整 route/service/template code blocks
- 需要完整 checklist / acceptance criteria

## Recommended execution order

1. `plan-phase4c1-edit-service.md`
2. `plan-phase4c2-edit-route-template.md`
3. 如需完整细节，再参考 `plan-phase4c-edit-legacy-full.md`

## Current implementation status

- ✅ edit diff service foundation 已实现（基于 `_body` 比较正文）
- ✅ `GET /journal/{journal_path}/edit` 已实现
- ✅ `POST /journal/{journal_path}/edit` 已实现
- ✅ edit 页 route-level CSRF 已实现
- ✅ edit form prefill 已实现
- ✅ edit 成功后会 redirect 回 journal 页面并显示 success banner
- ✅ `/api/weather` 已实现
- ✅ edit 页 location / weather 联动已实现
- ✅ location 变更时前端会清空旧 weather，并在缺失 weather 时阻止提交
