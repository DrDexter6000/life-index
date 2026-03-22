# Phase 4a3: Writing Templates — Split Subplan

**Parent plan:** [`plan-phase4a-llm-write-service.md`](plan-phase4a-llm-write-service.md)  
**Owns:** Task 11a 中 `web/templates/writing_templates.json` 部分  
**Why this split exists:** 模板内容属于内容设计，不应淹没在 provider / service 实现细节里。

**Shared contracts:** [`shared-contracts.md`](shared-contracts.md)

## Scope

- `web/templates/writing_templates.json`
- 模板 schema
- 7 个预设模板内容

## Contracts You Must Preserve

- 模板不覆盖已有用户输入
- 模板只预填，不承担最终 metadata truth
- topic/tags/content skeleton 必须兼容 write form

## Verification

- JSON schema consistent
- template ids stable
- blank template remains default
