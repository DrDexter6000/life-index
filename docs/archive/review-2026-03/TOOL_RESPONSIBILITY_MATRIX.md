# Tool Responsibility Matrix

> **Document role**: Define explicit responsibility boundaries for key Life Index tools during Phase 1 review work
> **Audience**: Project Owner, reviewers, implementers, and future agents
> **SSOT relationship**: This document is review-scoped execution guidance. Runtime interface truth remains in `docs/API.md`, `SKILL.md`, `docs/ARCHITECTURE.md`, and code.
> **Scope for this first cut**: `write_journal`, `edit_journal`, `query_weather`, `search_journals`
> **状态**: 部分采纳 — 核心 caller-facing ownership 已上提到 `docs/API.md`、`SKILL.md`、`references/WEATHER_FLOW.md`；本文件保留矩阵式 review reasoning 与剩余开放问题

---

## 1. Boundary rule for this matrix

Use this matrix to answer five questions for each tool:

1. What does the tool clearly own?
2. What does the tool clearly not own?
3. What must the caller provide or handle?
4. What failure semantics are already visible?
5. Where are the ambiguous or risky boundaries?

This matrix must not redefine tool parameters or overwrite existing workflow SSOT. When in doubt:

- `docs/API.md` owns interface truth
- `SKILL.md` owns skill-facing workflow truth
- `docs/ARCHITECTURE.md` owns architecture principle truth

---

## 2. `write_journal`

### Owns

- Create a journal file in the date-based journal tree under `~/Documents/Life-Index/`
- Perform atomic write via temp file + replace flow
- Generate file sequence numbers and protect write operations with file locking
- Process attachments referenced in content or passed explicitly
- Trigger location normalization and internal weather lookup before final write
- Update downstream indexes after successful write preparation
- Return structured write results, including `needs_confirmation` when follow-up confirmation is required

### Does not own

- Final confirmation conversation with the user
- High-level semantic interpretation of the user’s natural-language intent
- Independent weather implementation logic (delegates to weather helper / weather tool path)
- Post-write correction workflow when user says the auto-filled weather/location is wrong

### Caller obligations

- Provide the required structured payload expected by the tool contract
- Read and handle `needs_confirmation` rather than stopping at `success: true`
- Supply or derive required semantic metadata at the agent layer when the workflow expects it
- If the user rejects auto-filled weather/location, continue with follow-up correction flow instead of assuming write flow is finished

### Failure semantics visible today

- Core write path is treated as critical and protected by atomic write behavior
- Weather enrichment is part of the current write flow, but the conversation-level confirmation remains caller-owned
- Index update behavior is coupled to the write path, which creates an open question about blocking vs non-blocking semantics

### Evidence

- `tools/write_journal/core.py`: journal path generation, atomic write, locking, index update, confirmation result
- `tools/write_journal/weather.py`: internal weather query wrapper and delegation path
- `SKILL.md`: agent-side required fields and write workflow expectations
- `references/WEATHER_FLOW.md`: explicit requirement that the caller must inspect `needs_confirmation`

### Boundary risks / open questions

- `write_journal` may drift into a “super entrypoint” if more decision logic is pushed down into the tool
- Write success, weather enrichment, and index success are still too tightly grouped conceptually
- Caller responsibility for confirmation is documented, but not enforced structurally beyond the response payload

---

## 3. `edit_journal`

### Owns

- Modify existing journal files
- Update frontmatter fields and/or journal body
- Support dry-run preview for edits
- Reconcile affected indexes after metadata-changing edits
- Synchronize vector index updates when relevant fields change

### Does not own

- Automatic weather refresh when location changes
- Standalone weather querying
- Intent interpretation about whether location/weather should be changed together

### Caller obligations

- Select the correct journal target before invoking the tool
- If a location change implies weather refresh, call `query_weather` first and then pass both values into `edit_journal`
- Decide whether the edit is a metadata edit, append operation, or full replacement before calling

### Failure semantics visible today

- Edit path owns file mutation and index synchronization for the edited journal
- Caller remains responsible for any pre-edit enrichment or multi-tool orchestration

### Evidence

- `tools/edit_journal/__init__.py`: edit operations, dry-run, index rebalance, vector sync
- `tools/edit_journal/__main__.py`: explicit edit options, no built-in weather fetch path
- `references/WEATHER_FLOW.md`: explicit statement that `tools.edit_journal` does not auto-query weather

### Boundary risks / open questions

- Location edit without weather refresh is currently too easy to invoke incorrectly
- The correct weather-edit sequence lives mostly as documentation knowledge rather than self-explanatory interface behavior

---

## 4. `query_weather`

### Owns

- Resolve a location into coordinates
- Query weather data from the upstream weather service
- Return weather information in a lightweight structured/output format suitable for callers
- Support simple date-based weather lookup behavior exposed by the CLI contract

### Does not own

- Persisting weather into a journal
- Location normalization for write flow business logic
- Fallback persistence when weather API access fails
- Any journal-editing behavior

### Caller obligations

- Supply the location/date inputs expected by the weather tool
- Decide what to do with the returned weather data
- If weather lookup fails but journal consistency still matters, use an alternate strategy and then write/edit via the appropriate journal tool

### Failure semantics visible today

- The tool is a capability provider, not a recovery orchestrator
- Recovery after weather failure is caller-owned

### Evidence

- `tools/query_weather/__main__.py`: geocoding, weather lookup, formatting responsibilities
- `references/WEATHER_FLOW.md`: fallback responsibility assigned to the agent/caller
- `tools/write_journal/weather.py`: current internal use of weather capability inside write flow

### Boundary risks / open questions

- The system currently has two user-visible mental models: direct weather lookup vs embedded weather enrichment inside write flow
- The project still needs a clearer contract for when weather is optional enrichment vs operationally required context

---

## 5. `search_journals`

### Owns

- Execute the dual-pipeline search architecture
- Run keyword-oriented retrieval flow (index / metadata / content layers)
- Run semantic retrieval flow
- Merge results with hybrid ranking / fusion logic
- Accept structured filters for topic, project, tags, mood, people, date, location, weather, and search level controls

### Does not own

- Rebuilding indexes from scratch
- Deciding the user’s true search intent from vague natural language on its own
- Final answer formatting and interpretation for the user

### Caller obligations

- Translate user intent into query text and optional filters
- Decide whether the user wants exact keyword retrieval, broader conceptual retrieval, or both
- Interpret the returned results into a user-facing answer

### Failure semantics visible today

- Search owns retrieval execution, not product-level interpretation
- Search quality depends on the existence and health of the underlying index layers

### Evidence

- `tools/search_journals/core.py`: dual-pipeline execution and hybrid result combination
- `tools/search_journals/__main__.py`: filter and level interface exposed at CLI level
- `SKILL.md`: caller-side responsibility for parsing query intent

### Boundary risks / open questions

- User-facing intent parsing and retrieval execution are still split across agent knowledge and tool capability
- There is still room for confusion between “search result quality” and “agent answer quality”

---

## 6. Cross-tool boundary observations

### A. Weather handling is intentionally asymmetric today

- `write_journal` includes weather enrichment behavior in its current flow
- `edit_journal` explicitly does not auto-refresh weather
- `query_weather` provides capability, but not orchestration

This asymmetry is not necessarily wrong, but it must be documented clearly because it is not obvious to a new caller.

### B. Confirmation is caller-owned, not tool-owned

The tool can signal that confirmation is needed, but it does not own the conversational loop. That is a core Agent-vs-Tool boundary and should remain explicit.

### C. Search returns retrieval results, not product meaning

`search_journals` should remain a retrieval engine. The agent or caller should continue to own result framing, summarization, and user-facing interpretation.

---

## 7. What this matrix does not decide yet

This document does **not** yet settle:

- whether index updates should be synchronous-required, best-effort, or repairable in the final contract
- whether weather/location coordination should be strengthened through warnings or API changes
- whether some current tool asymmetries should remain as-is or be smoothed out later

Those decisions belong to the next Phase 1 artifacts:

- `docs/review/execution/CANONICAL_WORKFLOWS.md`
- `docs/review/execution/WRITE_FAILURE_SEMANTICS.md`
- `docs/review/execution/WEATHER_EDIT_BOUNDARY.md`
