# Phase 2: Dashboard — Thin Index

**Goal:** Dashboard renders all 8 components with real data while keeping implementation docs navigable.

**Shared contracts:** [`shared-contracts.md`](shared-contracts.md)

## What changed

原始超长版本已保留为：

- [plan-phase2-dashboard-legacy-full.md](plan-phase2-dashboard-legacy-full.md)

新的推荐执行入口：

- Task 7 → [plan-phase2a-stats-service.md](plan-phase2a-stats-service.md)
- Task 8 → [plan-phase2b-dashboard-route-template.md](plan-phase2b-dashboard-route-template.md)

## Dependency Summary

- Task 7 depends on Phase 1 scaffold
- Task 8 depends on Task 7 + `base.html`

## Contracts to preserve

Contract definitions live in [`shared-contracts.md`](shared-contracts.md). This phase only highlights the parts it depends on:

- use `_body` for word count reads
- normalize raw file paths into `journal_route_path`
- route/template must not link with raw `file_path`

## When to use the legacy full doc

使用下列场景再打开 legacy full：

- 需要完整逐步 TDD 步骤
- 需要原始 acceptance criteria 逐条核对
- 需要对照旧版 checklist / embedded code blocks

## Recommended execution order

1. `plan-phase2a-stats-service.md`
2. `plan-phase2b-dashboard-route-template.md`
3. 如需详细 step-by-step，再回看 `plan-phase2-dashboard-legacy-full.md`
