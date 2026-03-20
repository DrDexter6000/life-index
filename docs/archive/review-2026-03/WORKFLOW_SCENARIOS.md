# Workflow Scenarios

> **Document role**: Test-first scenario set for Phase 1 workflow clarification work
> **Audience**: Reviewers, implementers, and future agents using the review bundle in `docs/review/`
> **Authority**: Review-scoped evaluation artifact; does not redefine runtime SSOT
> **Related artifacts**: `docs/review/execution/TOOL_RESPONSIBILITY_MATRIX.md`, `docs/review/execution/CANONICAL_WORKFLOWS.md`, `docs/review/execution/WRITE_FAILURE_SEMANTICS.md`, `docs/review/execution/WEATHER_EDIT_BOUNDARY.md`

---

## 1. How to use this file

Each scenario is designed to test whether the current Phase 1 artifacts provide a clear answer to these questions:

1. Which workflow is this?
2. Which tool(s) are involved?
3. What does the agent own?
4. What does the tool own?
5. Is clarification required?
6. Is confirmation required?
7. If something fails, how should the outcome be classified?

This is not yet an automated test suite. It is a review/evaluation corpus for validating the clarity of the current operational contract.

---

## 2. Scenario Set

## Scenario 01 — Write journal with complete metadata

### User input

“帮我记一篇日志：今天下午在拉各斯和朋友吃饭，聊了很久创业的事情，我感觉既兴奋又焦虑。标题就叫《拉各斯午后》。”

### Expected workflow

- Workflow: **Write Journal**
- Primary tool: `write_journal`

### Expected agent behavior

- Recognize this as a new-entry workflow
- Extract/prepare required structured payload
- Call `write_journal`
- Handle confirmation if the tool requests it

### Expected tool behavior

- Perform deterministic write execution
- Return structured result

### Clarification required?

- Not necessarily, if the agent can prepare the minimum viable payload confidently

### Confirmation required?

- Only if the tool returns `needs_confirmation`

### Failure classification focus

- If file write fails: **Write failed**
- If write succeeds and confirmation is pending: **Saved, confirmation still needed**

---

## Scenario 02 — Write journal with missing weather context

### User input

“记一下：今天晚上散步的时候突然觉得最近心态平和了很多。”

### Expected workflow

- Workflow: **Write Journal**
- Primary tool: `write_journal`

### Expected agent behavior

- Treat this as a write flow, not a search/edit flow
- Prepare the minimum viable payload for the write
- Let the write path handle current weather-related enrichment behavior if applicable

### Expected tool behavior

- Attempt write-side enrichment behavior without making weather the same thing as core write success

### Clarification required?

- Only if the minimum required write payload cannot be prepared

### Confirmation required?

- Possible, if enrichment output needs confirmation

### Failure classification focus

- Missing or unresolved weather should not automatically mean **write failed** if the journal can still be durably stored

---

## Scenario 03 — Write journal requiring confirmation

### User input

“帮我记录：今天在北京出差，开完会之后心情很复杂，既满足又疲惫。”

### Expected workflow

- Workflow: **Write Journal**
- Primary tool: `write_journal`

### Expected agent behavior

- Do not stop when the tool returns `success: true`
- If `needs_confirmation` exists, surface the question to the user
- Treat user rejection as correction flow, not as proof that no journal was saved

### Expected tool behavior

- Return structured result and, if applicable, `needs_confirmation`

### Clarification required?

- Not if payload is sufficiently clear

### Confirmation required?

- **Yes**, if tool signals it

### Failure classification focus

- Saved-but-unconfirmed must remain distinct from unsaved

---

## Scenario 04 — Edit location without weather refresh

### User input

“把昨天那篇日志的地点从 Lagos 改成 Abuja。”

### Expected workflow

- Workflow: **Edit Journal**
- Primary tool: `edit_journal`
- Secondary tool consideration: `query_weather` may be needed depending on semantic expectations

### Expected agent behavior

- Recognize this as edit, not write
- Identify the target journal first
- Decide whether the user expects weather to stay aligned with the new location
- If semantic alignment matters, do not stop at a location-only edit

### Expected tool behavior

- `edit_journal` performs deterministic mutation only
- It does not auto-refresh weather

### Clarification required?

- Often yes, if user intent about weather alignment is unclear

### Confirmation required?

- Not by default

### Failure classification focus

- A location-only edit may succeed while leaving weather semantically stale; that is a boundary issue, not automatically an edit failure

---

## Scenario 05 — Edit location with pre-fetched weather

### User input

“把那篇日志地点改成 Abuja，并同步更新天气。”

### Expected workflow

- Workflow: **Edit Journal** with weather coupling
- Tools: `query_weather` → `edit_journal`

### Expected agent behavior

- Identify target journal
- Recognize coupled-field requirement
- Call `query_weather` first
- Then call `edit_journal` with both updated location and weather values

### Expected tool behavior

- `query_weather` provides capability only
- `edit_journal` applies deterministic mutation only

### Clarification required?

- Only if target journal or weather date context is unclear

### Confirmation required?

- Not by default

### Failure classification focus

- If weather lookup fails, the system must distinguish between edit status and weather-refresh status

---

## Scenario 06 — Search exact keyword

### User input

“帮我找所有提到‘乐乐’的日志。”

### Expected workflow

- Workflow: **Search Journals**
- Primary tool: `search_journals`

### Expected agent behavior

- Recognize exact retrieval intent
- Translate the user request into an appropriate query
- Present the returned results meaningfully

### Expected tool behavior

- Execute retrieval through current search pipeline
- Return ranked results

### Clarification required?

- No, unless the user also implies hidden filters

### Confirmation required?

- Not by default

### Failure classification focus

- Do not collapse tool failure into “no results” unless that is truly what happened

---

## Scenario 07 — Search conceptually similar content

### User input

“帮我找那种‘想念女儿、又有点伤感’的记录。”

### Expected workflow

- Workflow: **Search Journals**
- Primary tool: `search_journals`

### Expected agent behavior

- Recognize conceptual retrieval intent rather than exact keyword-only intent
- Use the search tool as retrieval engine, not as user-facing interpreter

### Expected tool behavior

- Execute current retrieval stack, including semantic/hybrid behavior where configured

### Clarification required?

- Possibly, if the user later wants narrower scope such as date range or specific person

### Confirmation required?

- Not by default

### Failure classification focus

- Distinguish weak/empty retrieval from outright search failure

---

## Scenario 08 — Search with no useful results

### User input

“找一下我写过的关于冰岛极光的日志。”

### Expected workflow

- Workflow: **Search Journals**
- Primary tool: `search_journals`

### Expected agent behavior

- Run retrieval flow
- If no useful matches are found, report that honestly
- Offer reformulation or broader/narrower search framing if helpful

### Expected tool behavior

- Return either empty results or low-confidence matches depending on current implementation

### Clarification required?

- Usually not before first search attempt

### Confirmation required?

- Not by default

### Failure classification focus

- Empty result is not the same as tool failure

---

## Scenario 09 — Weather API unavailable during write

### User input

“帮我记下来：今天在 Nairobi 出门散步时，突然觉得最近生活终于稳定了一些。”

### Expected workflow

- Workflow: **Write Journal**
- Primary tool: `write_journal`
- Weather capability may degrade

### Expected agent behavior

- Preserve the distinction between journal write status and weather enrichment status
- If the journal is durably saved, do not present the entire operation as failed solely because weather enrichment degraded

### Expected tool behavior

- Attempt current write path behavior
- Surface enough signal for caller to distinguish degraded enrichment from core write failure where possible

### Clarification required?

- Not necessarily

### Confirmation required?

- Only if the tool returns a confirmation requirement

### Failure classification focus

- This scenario tests whether weather degradation is treated as non-blocking rather than automatically collapsing into unsaved

---

## Scenario 10 — Manual file change followed by rebuild/recovery concern

### User input

“我手动改过一篇日志的 frontmatter，现在帮我确认搜索还能正常找到它。”

### Expected workflow

- Primary workflow: starts as **Search Journals** or maintenance-oriented follow-up depending on how the agent frames it
- Search tool may be used first to observe behavior
- Rebuild/index repair may be implicated as follow-up work outside the four-tool scope

### Expected agent behavior

- Recognize that the request touches retrieval health and possible index consistency
- Avoid pretending search truth is independent from index state
- Preserve distinction between journal file state and search visibility state

### Expected tool behavior

- `search_journals` only owns retrieval execution, not index rebuilding

### Clarification required?

- Yes, if the user actually wants repair rather than diagnosis

### Confirmation required?

- Not by default

### Failure classification focus

- Journal existence and search visibility are different states; lack of search visibility does not automatically mean the journal itself is missing

---

## 3. Coverage summary

This scenario set covers the minimum roadmap-required cases:

- [x] Write journal with complete metadata
- [x] Write journal with missing weather
- [x] Write journal requiring confirmation
- [x] Edit location without weather refresh
- [x] Edit location with pre-fetched weather
- [x] Search exact keyword
- [x] Search conceptually similar content
- [x] Search with no results
- [x] Weather API unavailable during write
- [x] Rebuild/index recovery after manual file change

---

## 4. Review use criteria

Phase 1 artifacts should be considered aligned with this scenario set only if a reviewer can use them to answer, for every scenario:

- which workflow applies
- which tool(s) apply
- whether clarification is needed
- whether confirmation is needed
- how failure/degraded state should be described
