# Phase 4a: LLM Provider + Write Service — Thin Index

**Goal:** Separate provider logic, write orchestration, and writing template content into focused docs.

**Shared contracts:** [`shared-contracts.md`](shared-contracts.md)

## What changed

原始超长版本已保留为：

- [plan-phase4a-llm-write-service-legacy-full.md](plan-phase4a-llm-write-service-legacy-full.md)

新的推荐执行入口：

- Provider → [plan-phase4a1-llm-provider.md](plan-phase4a1-llm-provider.md)
- Write service → [plan-phase4a2-write-service.md](plan-phase4a2-write-service.md)
- Writing templates → [plan-phase4a3-writing-templates.md](plan-phase4a3-writing-templates.md)

## Dependency Summary

- depends on Phase 1 scaffold
- unblocks Phase 4b write route/template

## Contracts to preserve

Contract definitions live in [`shared-contracts.md`](shared-contracts.md). This phase only highlights the parts it depends on:

- `date` is the real tool-level hard requirement
- `content` / `title` / `topic` / `abstract` are workflow-filled at Web layer
- `journal_path` returned from write flow may be absolute and must later normalize to `journal_route_path`

## When to use the legacy full doc

- 需要完整 TDD steps
- 需要旧版 code blocks / acceptance criteria

## Recommended execution order

1. `plan-phase4a1-llm-provider.md`
2. `plan-phase4a2-write-service.md`
3. `plan-phase4a3-writing-templates.md`
4. 如需完整细节，再参考 `plan-phase4a-llm-write-service-legacy-full.md`
