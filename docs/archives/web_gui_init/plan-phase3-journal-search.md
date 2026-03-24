# Phase 3: Journal View + Search — Thin Index

**Goal:** Split Journal View and Search into independently executable docs while preserving shared contracts.

**Shared contracts:** [`shared-contracts.md`](shared-contracts.md)

## What changed

原始超长版本已保留为：

- [plan-phase3-journal-search-legacy-full.md](plan-phase3-journal-search-legacy-full.md)

新的推荐执行入口：

- Task 9 → [plan-phase3a-journal-view.md](plan-phase3a-journal-view.md)
- Task 10 → [plan-phase3b-search.md](plan-phase3b-search.md)

## Dependency Summary

- Task 9 depends on Phase 1 scaffold
- Task 10 depends on Phase 1 scaffold
- Edit flow later depends on Task 9’s journal route contract

## Contracts to preserve

Contract definitions live in [`shared-contracts.md`](shared-contracts.md). This phase only highlights the parts it depends on:

- route input uses `journal_route_path`
- parse journal body from `_body`
- search payloads must normalize raw paths before rendering links
- empty result ≠ tool failure

## When to use the legacy full doc

- 需要完整 TDD steps
- 需要对照旧的 Journal/Search acceptance criteria
- 需要复制大段示例代码时

## Recommended execution order

1. `plan-phase3a-journal-view.md`
2. `plan-phase3b-search.md`
3. 如需完整细节，再参考 `plan-phase3-journal-search-legacy-full.md`
