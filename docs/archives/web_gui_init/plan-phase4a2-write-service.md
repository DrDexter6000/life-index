# Phase 4a2: Write Service — Split Subplan

**Parent plan:** [`plan-phase4a-llm-write-service.md`](plan-phase4a-llm-write-service.md)  
**Owns:** Task 11a 中 `web/services/write.py` 部分  
**Why this split exists:** 写入编排是核心业务，应该从 provider 细节和模板预设中解耦。

**Shared contracts:** [`shared-contracts.md`](shared-contracts.md)

## Scope

- `prepare_journal_data()`
- `write_journal_web()`
- workflow fallback rules

## Contracts You Must Preserve

See [`shared-contracts.md`](shared-contracts.md) for canonical definitions.

- `date` 是底层工具硬要求
- `content` / `title` / `topic` / `abstract` 在 Web workflow 中补齐
- `write_journal()` 返回的 `journal_path` 可能是绝对路径
- route 层后续必须把 `journal_path` 归一化为 `journal_route_path`

## Dependencies

- Depends on: `plan-phase4a1-llm-provider.md`
- Feeds into: `plan-phase4b1-write-route.md`

## Verification

- no-LLM fallback works
- user input wins over LLM output
- write delegation via thread/executor is documented and tested
