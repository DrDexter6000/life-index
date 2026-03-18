# Canonical Workflows

> **Document role**: Define the canonical workflow specification for the core Life Index user journeys during Phase 1 review work
> **Audience**: Project Owner, reviewers, implementers, and future agents
> **SSOT relationship**: This document is review-scoped execution guidance. Runtime workflow truth remains in `SKILL.md`, interface truth remains in `docs/API.md`, and architecture truth remains in `docs/ARCHITECTURE.md`.
> **Scope for this first cut**: Write journal, search journals, edit journal
> **状态**: 已采纳 — 核心workflow指导已上提到 `SKILL.md`
> **采纳日期**: 2026-03-18
> **后续维护**: 本文档保留作为历史记录和详细参考，运行时指导以 `SKILL.md` 为准

---

## 1. Workflow rule for this document

Each workflow in this file must answer four questions:

1. What is the happy path?
2. When is clarification required?
3. When is confirmation required?
4. What is the failure path?

This document does **not** redefine formal parameters or replace `SKILL.md`. It narrows the operational contract so future work can proceed from a shared model.

---

## 2. Workflow A — Write Journal

### Intent

The user wants to record a new life event, reflection, memory, or experience as a new journal entry.

### Happy path

1. User expresses intent to record a journal entry in natural language.
2. Agent determines that the request is a new-entry workflow rather than search or edit.
3. Agent extracts or prepares the required structured fields expected by the write flow.
4. Agent decides whether the current input is sufficient or whether clarification is required first.
5. Agent calls `write_journal` with the structured payload.
6. Tool performs deterministic write responsibilities:
   - validate the input it owns
   - prepare journal path / sequence
   - perform atomic write behavior
   - run current write-side enrichment/index responsibilities that already belong to the tool path
7. Tool returns structured result.
8. If the tool returns `needs_confirmation`, the agent enters the confirmation path before ending the conversation.
9. If the user confirms, the write workflow is complete.

### Clarification path

Clarification is required before tool invocation when the agent cannot confidently derive the minimum required write payload or cannot safely choose the correct write intent.

Typical clarification triggers:

- the user intent is ambiguous between writing and editing
- the journal content is too incomplete to produce the required write payload
- critical structured fields cannot be responsibly inferred
- the user’s instruction implies a correction to an existing entry rather than a new entry

Clarification rule:

- The agent should clarify **before** calling `write_journal`
- The tool should not become the place where missing user intent is guessed conversationally

### Confirmation path

Confirmation is required **after** tool execution when the tool explicitly signals that confirmation is needed.

Current canonical rule:

- `success: true` does **not** automatically mean the conversation is complete
- if `needs_confirmation` is present/true, the agent must surface the confirmation request to the user
- if the user accepts, the workflow completes
- if the user rejects or corrects weather/location-related auto-filled values, the agent transitions into the correction flow rather than ending the session

### Failure path

Failure in the write workflow can happen at several levels:

#### A. Pre-tool failure

- The agent cannot determine whether the request is truly a write request
- The agent cannot safely prepare the required structured payload

Required action:

- clarify intent or missing fields before calling the tool

#### B. Tool execution failure

- The tool reports a failure in write execution
- The tool cannot complete a core deterministic step it owns

Required action:

- do not pretend the journal was saved
- surface the failure accurately
- determine whether retry, correction, or fallback is appropriate based on tool output and caller context

#### C. Post-write correction failure

- The write succeeded but the user rejects the auto-filled enrichment data
- A follow-up correction flow is needed but cannot be completed immediately

Required action:

- preserve the distinction between “journal write succeeded” and “enrichment still needs correction”
- do not collapse the two into a single success/fail message

### Boundary summary

#### Agent owns

- intent recognition
- semantic extraction / interpretation
- clarification questions
- user-facing confirmation loop
- post-write correction orchestration

#### Tool owns

- deterministic write execution
- file mutation and atomicity
- current built-in write-side indexing / enrichment behavior already implemented in code
- structured result signaling

---

## 3. Workflow B — Search Journals

### Intent

The user wants to find previous journal entries, memories, patterns, or related passages.

### Happy path

1. User expresses a find/search/retrieve intent.
2. Agent recognizes this as a retrieval workflow.
3. Agent interprets the query and extracts any optional filters or search framing.
4. Agent decides whether the request is:
   - exact / keyword oriented
   - broad / conceptual
   - mixed
5. Agent calls `search_journals` with the query and any relevant filters.
6. Tool performs deterministic retrieval responsibilities:
   - execute keyword-oriented search layers
   - execute semantic retrieval path as configured
   - merge/rank results through the implemented search pipeline
7. Tool returns search results.
8. Agent interprets and presents the results in a user-appropriate way.

### Clarification path

Clarification is required before tool invocation when the search request is too underspecified to produce a meaningful retrieval request.

Typical clarification triggers:

- the user asks for “that one entry” without enough identifying detail
- the user intent could mean either “search entries” or “summarize my history”
- the user’s request implies a filter dimension that is still too vague to apply meaningfully

Clarification rule:

- the agent should clarify user intent, search scope, or retrieval framing before calling the tool when ambiguity would materially affect search usefulness

### Confirmation path

Search does **not** normally require a post-tool confirmation loop.

However, the agent may confirm follow-up intent when:

- the user wants refinement after seeing initial results
- the user appears to be asking for a second operation such as edit, summarize, or compare after retrieval

### Failure path

#### A. Pre-tool failure

- the agent cannot determine what the user is asking to retrieve

Required action:

- ask a targeted clarification question rather than guessing a low-quality query

#### B. Tool execution failure

- retrieval tool returns failure or cannot use part of the search stack

Required action:

- do not present tool failure as “no results” unless that is explicitly what the tool indicates
- distinguish between retrieval failure and empty result set whenever possible

#### C. Empty result path

- the tool runs successfully but returns no useful matches

Required action:

- present the empty result truthfully
- optionally guide the user toward reformulation, narrower filters, or broader search framing

### Boundary summary

#### Agent owns

- search-intent recognition
- query interpretation
- deciding what the user really wants from the results
- result framing, explanation, and next-step suggestion

#### Tool owns

- deterministic retrieval execution
- multi-layer search mechanics
- search result ranking / fusion already implemented in the retrieval layer

---

## 4. Workflow C — Edit Journal

### Intent

The user wants to modify an existing journal entry, either by changing metadata, adjusting content, or fixing a previously recorded value.

### Happy path

1. User expresses intent to correct, update, append to, or modify an existing journal.
2. Agent recognizes that the request is an edit workflow rather than a new write workflow.
3. Agent identifies the target journal entry.
4. Agent determines the edit type:
   - metadata field update
   - content append
   - content replace
   - combined change
5. If the edit has coupling implications (for example, location + weather), the agent resolves those obligations before tool invocation.
6. Agent calls `edit_journal` with the correct edit payload.
7. Tool performs deterministic edit responsibilities:
   - load the journal
   - apply the requested mutation
   - write back the result
   - update affected indexes already owned by the edit path
8. Tool returns the edit result.
9. Agent reports completion or follow-up outcome to the user.

### Clarification path

Clarification is required before tool invocation when the target journal or the intended mutation is unclear.

Typical clarification triggers:

- the user references an entry without enough identifying detail
- it is unclear whether the user wants append vs replace behavior
- the request sounds like a new memory to record, not an edit
- the request changes a coupled field but does not specify whether related values should also be updated

Clarification rule:

- the agent must clarify journal target and mutation intent before calling the edit tool when ambiguity could modify the wrong entry or apply the wrong change type

### Confirmation path

Edit does not normally require the same post-write confirmation loop used in write flow.

However, confirmation may still be appropriate when:

- the edit request is destructive or replacing body content
- the user’s intent is ambiguous enough that a final confirmation protects against accidental overwrite

This confirmation remains agent-owned, not tool-owned.

### Failure path

#### A. Pre-tool failure

- the target journal cannot be identified confidently
- a required coupled value (such as refreshed weather after location change) is still unresolved

Required action:

- clarify or gather required context first

#### B. Tool execution failure

- the edit tool cannot apply the requested mutation or synchronize owned side effects

Required action:

- do not claim the edit succeeded
- distinguish between “target not found,” “mutation rejected,” and “edit failed after selection” whenever the tool output allows it

#### C. Coupled-field failure

- a multi-tool prerequisite such as weather refresh fails before edit completion

Required action:

- do not silently apply a partial semantic correction without explaining the state
- preserve the distinction between journal edit status and enrichment completeness

### Boundary summary

#### Agent owns

- target identification
- deciding whether the request is edit vs write
- clarification about mutation type
- orchestration of coupled-field preconditions such as weather refresh
- optional destructive-action confirmation

#### Tool owns

- deterministic mutation of an existing journal
- index synchronization that belongs to the edit path
- dry-run style preview behavior where supported by the tool contract

---

## 5. Cross-workflow operational rules

### A. Write vs Edit separation

- New memory or new event capture should enter the write workflow
- Correction or modification of an existing journal should enter the edit workflow
- If the user intent could be either, the agent must clarify instead of guessing

### B. Agent vs Tool separation

- Agent owns meaning, clarification, confirmation, and multi-step orchestration
- Tool owns deterministic execution and structured result signaling

### C. Search is retrieval, not interpretation

- `search_journals` retrieves results
- the agent decides how to explain or use them in the conversation

### D. Weather handling is asymmetric today

- Write flow currently includes weather enrichment behavior in the tool path
- Edit flow does not auto-refresh weather on location change
- This asymmetry is accepted for now, but must remain explicit until a later Phase 1 artifact resolves whether it should change

---

## 6. What this workflow spec does not settle yet

This document does **not** yet settle:

- whether write-side index updates are synchronous-required, best-effort, or repairable in the final contract
- whether edit flow should eventually surface stronger warnings for location-weather coupling
- whether some current asymmetries should be normalized in code or remain documentation-level behavior

Those decisions belong to the next Phase 1 artifacts:

- `docs/review/execution/WRITE_FAILURE_SEMANTICS.md`
- `docs/review/execution/WEATHER_EDIT_BOUNDARY.md`
