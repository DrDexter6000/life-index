# Phase 4a1: LLM Provider — Split Subplan

**Parent plan:** [`plan-phase4a-llm-write-service.md`](plan-phase4a-llm-write-service.md)  
**Owns:** Task 11a 中 `web/services/llm_provider.py` 部分  
**Why this split exists:** Provider abstraction 与 write orchestration 是不同风险面。

**Shared contracts:** [`shared-contracts.md`](shared-contracts.md)

## Scope

- `LLMProvider` ABC
- `HostAgentProvider` stub / availability contract
- `APIKeyProvider`
- `get_provider()` priority logic

## Contracts You Must Preserve

- HostAgentProvider 在 MVP 中仍可 unavailable
- APIKeyProvider 使用 OpenAI-compatible 接口
- provider layer 不负责 journal write

## Dependencies

- Depends on: Phase 1 scaffold
- Feeds into: `plan-phase4a2-write-service.md`

## Verification

- availability detection works
- extraction contract returns partial metadata dict
- provider fallback order documented and tested
