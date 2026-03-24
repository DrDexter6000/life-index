# Phase 4b1: Write Route — Split Subplan

**Parent plan:** [`plan-phase4b-write-route-template.md`](plan-phase4b-write-route-template.md)  
**Owns:** Task 11b 中 `web/routes/write.py` 部分  
**Why this split exists:** route orchestration、CSRF、upload handling 属于后端职责，应该与模板解耦。

**Shared contracts:** [`shared-contracts.md`](shared-contracts.md)

## Scope

- `GET /write`
- `POST /write`
- CSRF double-submit cookie contract
- upload temp-file handling
- redirect to normalized `journal_route_path`

## Contracts You Must Preserve

See [`shared-contracts.md`](shared-contracts.md) for canonical definitions.

- hidden field name: `csrf_token`
- cookie name: `csrf_token`
- `journal_path` → normalize → `journal_route_path`
- route 不直接做 journal 持久化写入

## Dependencies

- Depends on: `plan-phase4a1-llm-provider.md`, `plan-phase4a2-write-service.md`
- Pairs with: `plan-phase4b2-write-template.md`

## Verification

- GET sets CSRF cookie
- POST validates cookie/form token match
- success → 303 redirect
- failure → preserves user input

## Current implementation status

- ✅ 已实现 `GET /write`
- ✅ 已实现 `POST /write`
- ✅ 已实现 upload temp-file handling
- ✅ 已实现 multipart 本地附件 → `source_path` bridge
- ✅ 已实现 URL 附件下载 → 本地临时文件 → `source_path` bridge
- ✅ 已实现阻塞型/非阻塞型 URL 下载失败分流
- ✅ 已实现成功路径 warning query-param transport
