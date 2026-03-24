# Phase 4b: Write Route + Template — Thin Index

**Goal:** Keep write orchestration and write UI separate while preserving one CSRF and redirect contract.

**Shared contracts:** [`shared-contracts.md`](shared-contracts.md)

## What changed

原始超长版本已保留为：

- [plan-phase4b-write-route-template-legacy-full.md](plan-phase4b-write-route-template-legacy-full.md)

新的推荐执行入口：

- Write route → [plan-phase4b1-write-route.md](plan-phase4b1-write-route.md)
- Write template → [plan-phase4b2-write-template.md](plan-phase4b2-write-template.md)

## Dependency Summary

- depends on Phase 4a outputs
- unblocks Phase 4c and Phase 5

## Contracts to preserve

Contract definitions live in [`shared-contracts.md`](shared-contracts.md). This phase only highlights the parts it depends on:

- CSRF uses `csrf_token` cookie + hidden `csrf_token` field
- route normalizes returned `journal_path` into `journal_route_path`
- template stays compatible with route contract

## When to use the legacy full doc

- 需要完整测试代码示例
- 需要旧版完整 POST/GET acceptance criteria

## Recommended execution order

1. `plan-phase4b1-write-route.md`
2. `plan-phase4b2-write-template.md`
3. 如需完整细节，再参考 `plan-phase4b-write-route-template-legacy-full.md`

## Current implementation status

- ✅ `GET /write` / `POST /write` 已实现
- ✅ route-level CSRF（double-submit cookie）已实现
- ✅ 写入成功会 303 跳转到规范化后的 `journal_route_path`
- ✅ 写入失败会保留用户输入并回显错误
- ✅ 本地上传附件已接入 temp-file staging
- ✅ URL 附件已支持下载到本地临时文件后再桥接到底层 `write_journal`
- ✅ URL 下载失败已区分阻塞型（如 Content-Type rejected）与非阻塞型（跳过并继续写入）
- ✅ 成功写入但部分 URL 附件跳过时，journal 页面会显示 warning banner
