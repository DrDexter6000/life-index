# Workflow Eval Cases

> **Document role**: Evaluation corpus for validating workflow routing, clarification, confirmation, and degraded-state handling
> **Audience**: Reviewers, implementers, and future agents working from the review bundle in `docs/review/`
> **Authority**: Review-scoped evaluation artifact; does not redefine runtime SSOT
> **Related artifacts**: `docs/review/execution/CANONICAL_WORKFLOWS.md`, `docs/review/execution/TOOL_RESPONSIBILITY_MATRIX.md`, `docs/review/execution/WRITE_FAILURE_SEMANTICS.md`, `docs/review/execution/WEATHER_EDIT_BOUNDARY.md`, `docs/review/execution/INDEX_CONSISTENCY_POLICY.md`

---

## 1. Purpose

These eval cases are designed to test whether the current review-phase workflow contract is operationally usable.

Each case should be judged against questions like:

1. Did the system choose the correct workflow?
2. Did the system ask for clarification only when needed?
3. Did the system preserve the correct Agent-vs-Tool boundary?
4. Did the system handle confirmation correctly?
5. Did the system describe degraded states accurately instead of collapsing them into generic success/failure?

---

## 2. Evaluation format

Each case includes:

- **Case ID**
- **User input**
- **Primary workflow expectation**
- **Expected tool path**
- **Clarification expectation**
- **Confirmation expectation**
- **Degraded-state expectation**
- **Pass condition**

---

## 3. Eval cases

## Case WF-01 — Clean write routing

### User input

“帮我记一篇日志：今天晚上和朋友吃饭，聊了很久产品方向，我有点兴奋也有点焦虑。”

### Primary workflow expectation

- Route to **Write Journal**

### Expected tool path

- `write_journal`

### Clarification expectation

- Clarification is **not required** if the system can produce the minimum viable write payload confidently

### Confirmation expectation

- Only if `needs_confirmation` is returned

### Degraded-state expectation

- Do not invent degradation if the core write succeeds cleanly

### Pass condition

- The system routes to write flow directly, keeps orchestration at the agent layer, and does not over-clarify

---

## Case WF-02 — Ambiguous write vs edit intent

### User input

“把今天那段关于晚饭的内容记进去，或者如果已经有了就补进去。”

### Primary workflow expectation

- Ambiguous between **Write Journal** and **Edit Journal**

### Expected tool path

- No immediate tool call until intent is clarified

### Clarification expectation

- Clarification is **required**

### Confirmation expectation

- Not applicable before intent clarification

### Degraded-state expectation

- None yet; the key risk is wrong routing, not degraded execution

### Pass condition

- The system explicitly clarifies whether the user wants a new journal or a modification to an existing one before invoking tools

---

## Case WF-03 — Write requiring confirmation handling

### User input

“帮我记录：今天在北京出差，开完会以后整个人很累，但也觉得有收获。”

### Primary workflow expectation

- Route to **Write Journal**

### Expected tool path

- `write_journal`

### Clarification expectation

- Not required if minimum write payload is achievable

### Confirmation expectation

- If the tool returns `needs_confirmation`, confirmation is **mandatory before ending the flow**

### Degraded-state expectation

- If the write is durably saved but confirmation is pending, the system must describe it as saved-but-unconfirmed, not unsaved

### Pass condition

- The system does not stop at `success: true` and correctly enters confirmation flow when signaled

---

## Case WF-04 — Minimal write with weak context

### User input

“记一下：今天突然觉得轻松了很多。”

### Primary workflow expectation

- Route to **Write Journal** if the system can still build a viable payload

### Expected tool path

- `write_journal` after any necessary pre-tool clarification

### Clarification expectation

- Clarification is required **only if** the minimum viable payload cannot be responsibly produced

### Confirmation expectation

- Only if tool signals it

### Degraded-state expectation

- Missing enrichment context should not be confused with core write failure

### Pass condition

- The system distinguishes “thin but still writable” from “too underspecified to write safely”

---

## Case WF-05 — Exact search routing

### User input

“帮我找所有提到‘团团’的日志。”

### Primary workflow expectation

- Route to **Search Journals**

### Expected tool path

- `search_journals`

### Clarification expectation

- Not required before initial retrieval

### Confirmation expectation

- Not required by default

### Degraded-state expectation

- Search failure must remain distinct from empty results

### Pass condition

- The system treats this as retrieval, not summary, edit, or write; and reports no-results vs failure correctly

---

## Case WF-06 — Conceptual search routing

### User input

“帮我找那种怀念女儿、但又有点伤感的记录。”

### Primary workflow expectation

- Route to **Search Journals**

### Expected tool path

- `search_journals`

### Clarification expectation

- Optional only if the user later needs narrower framing

### Confirmation expectation

- Not required by default

### Degraded-state expectation

- Weak matches or no useful matches should not be framed as retrieval tool failure unless the tool actually failed

### Pass condition

- The system recognizes conceptual retrieval and still preserves the tool/agent separation between retrieval and interpretation

---

## Case WF-07 — Edit target ambiguity

### User input

“把那篇写深圳见客户的日志改一下。”

### Primary workflow expectation

- Route toward **Edit Journal**, but do not invoke tool yet if the target is ambiguous

### Expected tool path

- Clarify target first, then `edit_journal`

### Clarification expectation

- Clarification is **required** if multiple journals could match

### Confirmation expectation

- Only if the final intended edit is destructive or ambiguous

### Degraded-state expectation

- None initially; key risk is wrong target mutation

### Pass condition

- The system does not mutate an entry until the target is sufficiently identified

---

## Case WF-08 — Edit location without explicit weather expectation

### User input

“把昨天那篇日志里的地点从 Lagos 改成 Abuja。”

### Primary workflow expectation

- Route to **Edit Journal**

### Expected tool path

- Possibly clarification first, then `edit_journal`

### Clarification expectation

- Clarification is recommended if user expectation about weather alignment is unclear

### Confirmation expectation

- Not required by default

### Degraded-state expectation

- If location changes without weather refresh, the system should preserve the distinction between successful edit and incomplete semantic alignment

### Pass condition

- The system does not falsely imply that weather was auto-refreshed unless it actually orchestrated that work

---

## Case WF-09 — Edit location with explicit weather refresh requirement

### User input

“把那篇日志地点改成 Abuja，并且把天气也一起更新。”

### Primary workflow expectation

- Route to **Edit Journal** with weather-coupled orchestration

### Expected tool path

- `query_weather` → `edit_journal`

### Clarification expectation

- Only if target journal or weather context remains unclear

### Confirmation expectation

- Not required by default

### Degraded-state expectation

- If weather lookup fails, the system must not collapse the entire situation into a generic edit failure if journal mutation status is still distinguishable

### Pass condition

- The system preserves the caller-owned orchestration rule: weather lookup first, then edit

---

## Case WF-10 — Weather degradation during write

### User input

“帮我记下来：今天在 Nairobi 出门散步时，突然觉得最近生活终于稳定了一些。”

### Primary workflow expectation

- Route to **Write Journal**

### Expected tool path

- `write_journal`

### Clarification expectation

- Not necessarily required

### Confirmation expectation

- Only if tool signals it

### Degraded-state expectation

- If the journal is durably saved but weather enrichment is degraded, the system must describe the outcome as saved-with-degraded-enrichment rather than write-failed

### Pass condition

- The system preserves the difference between storage failure and enrichment degradation

---

## Case WF-11 — Search empty-result handling

### User input

“找一下我写过的关于冰岛极光的日志。”

### Primary workflow expectation

- Route to **Search Journals**

### Expected tool path

- `search_journals`

### Clarification expectation

- Not required before first attempt

### Confirmation expectation

- Not required by default

### Degraded-state expectation

- Empty result should be described as empty result, not tool failure

### Pass condition

- The system reports no useful matches honestly and can optionally suggest reformulation without inventing false system errors

---

## Case WF-12 — Search visibility lag after manual change

### User input

“我手动改过一篇日志，现在帮我确认搜索还能不能找到它。”

### Primary workflow expectation

- Route first to retrieval/diagnostic behavior, not automatically to write/edit

### Expected tool path

- likely `search_journals` first, with possible later repair-oriented follow-up outside the current tool set

### Clarification expectation

- Clarification is required if the user actually wants repair rather than diagnosis

### Confirmation expectation

- Not required by default

### Degraded-state expectation

- Search lag or stale visibility must not be described as proof that the journal source file is missing

### Pass condition

- The system preserves the distinction between source truth and retrieval visibility, consistent with index policy

---

## 4. Coverage summary

This file currently provides **12 workflow eval cases**, which is above the roadmap minimum of 10.

Coverage includes:

- write routing
- write clarification
- write confirmation
- write degradation handling
- exact search
- conceptual search
- empty search results
- edit target clarification
- edit weather/location coordination
- search visibility lag / stale retrieval state

---

## 5. Review criteria

This eval corpus is useful only if a reviewer can use it to verify that the current artifacts answer, for each case:

- which workflow applies
- which tools apply
- what the caller must do
- what the tool must do
- whether clarification is necessary
- whether confirmation is necessary
- how degraded state should be described
