---
type: rfc
status: proposal/draft
id: RFC-001
title: Aggregate / Analyze MVP
author: 码农B_Kimi
owner: 主审_GPT
date: 2026-05-13
---

# RFC-001: Aggregate / Analyze MVP

> **Status**: Proposal / Draft — **NOT a stable API promise**. This document is a tracked RFC intended to guide C-phase implementation. Any CLI signature, JSON contract, or predicate semantics described herein may change during review and implementation.
>
> **Scope**: Turn the current ignored C-design and B' real-data diagnosis into a concise tracked proposal that can guide C implementation without prematurely changing the stable public API contract.

---

## 1. Summary

B' real-data probe (20 queries over production journal corpus) shows that ordinary lookup and smart-search recall are functional, but **aggregate/trend queries currently lack auditable settlement**. The two representative failures are:

- `过去60天我有多少次晚睡` — smart-search returned a low-confidence cited answer admitting it could not derive an exact count.
- `统计一下我今年写日志的频率趋势` — smart-search returned an answer without validated citations and explicitly stated a dedicated statistics function was needed.

This RFC proposes a new deterministic CLI primitive, `life-index aggregate` (internal alias `analyze`), to settle counts and trends over structured fields with explicit predicates, evidence trails, and calibrated exactness semantics. The primitive is intentionally narrow: no LLM free-form counting, no schema migration, no broad natural-language predicate language in v0.

---

## 2. Evidence from B' Real-Data Probe

**Source**: `.agent-reports/realdata-search-quality/B_PRIME_20_QUERY_CAPABILITY_DIAGNOSIS.md` (2026-05-12)

| Dimension | Result |
|---|---|
| Keyword precision | 5/8 queries returned results; 3/8 returned no results |
| Smart-search citation-backed answer rate | 9/12 produced citation-backed answers |
| Invalid citation count | 0/12 |
| Aggregate/trend settlement | **Absent** — no deterministic count/trend primitive exists |

**Key aggregate/trend failures**:

| Query | Mode | Result Label | Failure Mode |
|---|---|---|---|
| `过去60天我有多少次晚睡` | smart | `ANSWER_WITH_CITATIONS` | `smart_low_confidence` — answer admitted no exact count could be derived |
| `统计一下我今年写日志的频率趋势` | smart | `ANSWER_NO_CITATIONS` | `smart_answer_no_citations` — answer explicitly requested a dedicated statistics function |

**Interpretation**: The dominant product gap is not "make smart-search more confident." It is "add a deterministic analysis primitive that can settle counts/trends with explicit definitions and evidence."

---

## 3. Problem Statement

Current `search` and `smart-search` are designed for **retrieval and synthesis**, not for **auditable computation**:

- `search` returns candidate journals and evidence; it does not count, trend, or settle aggregates.
- `smart-search` synthesizes answers over bounded evidence with citation trust gates; it must not pretend uncertain aggregates are exact.
- Neither tool exposes a deterministic, reproducible count or trend computation that an Agent or user can audit.

When a user asks "how many times did I stay up late in the past 60 days," the system currently has no structured way to:
1. Define what "stay up late" means in terms of available data fields.
2. Count matching entries deterministically.
3. Report exactness, confidence, and limitations explicitly.

---

## 4. Goals

1. **Deterministic count primitive**: Given a date range, a unit (day/entry/month), and an explicit predicate, return a reproducible count with evidence paths.
2. **Trend primitive**: Given a date range and a metric (e.g., `journal_count`), return grouped buckets (day/week/month) with deterministic aggregation.
3. **Exactness semantics**: Distinguish `exact`, `approximate`, and `not_measurable` counts, never fabricating a count when the data field is unreliable or absent.
4. **Evidence trail**: Every count/trend result must list `matched_entries`, `excluded_entries`, and `unknown_entries` with full relative paths.
5. **No LLM dependency**: The aggregate executor must be a pure deterministic Python module; LLM may only interpret/explain the result, never compute it.
6. **Stable API isolation**: The new command is additive; it does not modify `search`, `smart-search`, or any existing CLI contract.

---

## 5. Non-Goals

- No schema migration in the MVP.
- No LLM free-form counting over snippets.
- No public API stability promise for `aggregate` until the design is reviewed and accepted.
- No automatic claim that "late journal timestamp" means "actual late sleep" — the semantics must be explicit.
- No broad natural-language predicate language in v0; predicates are whitelisted and typed.
- No real-time streaming or sub-second latency guarantee; target is "fast enough for CLI" (< 2s for typical ranges).
- No modification to `docs/API.md`, `docs/ARCHITECTURE.md`, or existing eval gates in this RFC phase.

---

## 6. Capability Boundary

| Capability | Responsibility | NOT Responsible For |
|---|---|---|
| `search` | Retrieve candidate journals and evidence. | Counting, trend analysis, final natural-language claims. |
| `smart-search` | Synthesize answers over bounded evidence with citation trust gates. | Free-form counting over snippets or pretending uncertain aggregates are exact. |
| `aggregate` / `analyze` | Deterministically compute counts/trends over structured fields and explicit predicates. | Broad semantic interpretation without a declared predicate or evidence trail. |
| Agent / LLM | Interpret user intent, choose or propose a predicate, explain uncertainty, present results. | Being the calculator or source of truth. |

**Design principle**: LLM may interpret/explain but must not be the calculator or source of truth.

---

## 7. Proposed CLI/API Draft

### 7.1 Command Signature (v0 Proposal)

```bash
life-index aggregate --range <since>..<until> --unit <unit> --predicate <predicate> [--explain] [--json]
```

**Parameters**:

| Name | Type | Required | Default | Description |
|---|---|---|---|---|
| `--range` | string | ✅ | — | Date range in ISO 8601 `YYYY-MM-DD..YYYY-MM-DD`. Inclusive on both ends. |
| `--unit` | enum | ✅ | — | Aggregation unit: `day`, `week`, `month`, `entry`. `day` deduplicates multiple entries on the same calendar day; `entry` counts each journal file. |
| `--predicate` | string | ✅ | — | Whitelisted predicate expression (see §9). |
| `--explain` | flag | ❌ | false | Include human-readable interpretation of predicate, exactness, and limitations. |
| `--json` | flag | ❌ | false | Output full JSON contract (see §8). |

### 7.2 MVP Examples

**Example 1: Journal frequency trend**
```bash
life-index aggregate --range 2026-01-01..2026-05-12 --unit month --predicate "journal_count" --explain --json
```

**Example 2: Late entry time count**
```bash
life-index aggregate --range 2026-03-13..2026-05-12 --unit day --predicate "entry_time_after=22:00" --explain --json
```
> **Important**: "late journal write time" (`entry_time_after=22:00`) is **not** the same as "late sleep" unless the data field is reliable. The output semantics must surface this limitation.

**Example 3: Term presence count**
```bash
life-index aggregate --range 2026-01-01..2026-05-12 --unit day --predicate "term_presence=晚睡" --explain --json
```
> This counts days where the term appears in retrieved content. It is a recall-backed count, not proof of the real-world behavior.

---

## 8. JSON Output Contract Draft

```json
{
  "success": true,
  "query": "过去60天我有多少次晚睡",
  "command": "aggregate",
  "metric": "entry_count",
  "unit": "day",
  "range": {
    "since": "2026-03-13",
    "until": "2026-05-12"
  },
  "predicate": {
    "type": "entry_time_after",
    "threshold": "22:00",
    "definition": "journal timestamp later than 22:00; not proof of actual sleep time"
  },
  "result": {
    "count": 0,
    "denominator": 61,
    "exactness": "not_measurable",
    "confidence": "high"
  },
  "matched_entries": [],
  "excluded_entries": [],
  "unknown_entries": [
    {
      "path": "Journals/2026/03/life-index_2026-03-14_001.md",
      "reason": "no_time_field_available"
    }
  ],
  "evidence_paths": [],
  "limitations": [
    "No reliable time-of-day field was available for these journal entries."
  ],
  "performance": {
    "total_time_ms": 145.2
  }
}
```

### 8.1 Field Semantics

| Field | Type | Description |
|---|---|---|
| `success` | bool | Command execution succeeded (may still return `not_measurable`). |
| `query` | string | Original natural-language query, if provided by caller; otherwise empty. |
| `command` | string | Fixed `"aggregate"`. |
| `metric` | string | Computed metric name: `entry_count`, `journal_count`, `term_presence_count`. |
| `unit` | string | `day`, `week`, `month`, or `entry`. |
| `range` | object | Resolved date range. |
| `predicate` | object | Parsed predicate with `type`, `threshold` (if applicable), and `definition` (human-readable semantics). |
| `result.count` | int | The computed count. May be `0`. |
| `result.denominator` | int | Total candidate units in range (e.g., 61 days). |
| `result.exactness` | enum | `exact` — all units evaluated, predicate unambiguously true/false. `approximate` — some units inferred or heuristic. `not_measurable` — required data field missing or unreliable; count is `0` by convention. |
| `result.confidence` | enum | `high`, `medium`, `low`. Reflects data quality and predicate reliability, not LLM opinion. |
| `matched_entries` | array | Paths of units where predicate evaluated to true. |
| `excluded_entries` | array | Paths of units where predicate evaluated to false. |
| `unknown_entries` | array | Paths of units where predicate could not be evaluated, with `reason`. |
| `evidence_paths` | array | All relative paths that contributed to the result (union of matched + excluded + unknown). |
| `limitations` | array | Human-readable strings explaining why `exactness` is not `exact` or why interpretation is bounded. |
| `performance.total_time_ms` | float | Execution time. |

---

## 9. Predicate Whitelist and Exactness Semantics

### 9.1 MVP Predicate Whitelist

| Predicate | Syntax | Data Requirement | Exactness | Example |
|---|---|---|---|---|
| `journal_count` | `journal_count` | Date range + journal paths only | `exact` | Count entries per bucket. |
| `entry_time_after` | `entry_time_after=HH:MM` | Frontmatter `date` must contain time component (ISO 8601 datetime) | `exact` if all entries have datetime; `not_measurable` if any entry lacks time | `entry_time_after=22:00` |
| `term_presence` | `term_presence=TERM` | FTS or keyword search over title + content + abstract | `approximate` (recall-backed, not behavior proof) | `term_presence=晚睡` |
| `entity_presence` | `entity_presence=ENTITY_ID` | Entity Graph alias expansion + search match | `approximate` (recall-backed) | `entity_presence=concept-sleep` |

### 9.2 Exactness Rules

1. **`exact`**: Every unit in the range was evaluated against the predicate using reliable structured data, and the predicate returned a Boolean result. No inference or heuristic was used.
2. **`approximate`**: The predicate relies on search recall (term/entity presence), which may have false positives or false negatives. The count is bounded by retrieval quality, not ground truth.
3. **`not_measurable`**: The required data field is missing or unreliable for one or more units. The count is reported as `0` (or omitted), and `unknown_entries` lists the affected paths with `reason`. The caller must not treat `not_measurable` as `0` in a statistical sense.

---

## 10. Data / Privacy Constraints

- **Local-first**: All computation happens on the user's machine. No journal content, metadata, or aggregate results leave the local device.
- **No production data writes**: The `aggregate` command is read-only. It must not create, modify, or delete journals, indexes, or entity graph files.
- **Sandbox-compatible**: The implementation must work correctly when `LIFE_INDEX_DATA_DIR` points to a temporary sandbox directory (for TDD and evaluation).
- **Minimal data access**: The executor should only read frontmatter and, for `term_presence` / `entity_presence`, invoke the existing `search` primitive. It must not read full journal bodies unless required by the predicate.
- **Evidence path privacy**: Output paths must be relative (`Journals/YYYY/MM/...`), never absolute file system paths.

---

## 11. TDD Implementation Plan

### Phase 1: RED — Define Failure Cases

1. **Sandbox with dated entries only** (no time field): `entry_time_after=22:00` returns `not_measurable`, not a fabricated count.
2. **Sandbox with explicit datetime metadata**: `entry_time_after=22:00` counts unique days and lists matched entries.
3. **Sandbox with multiple entries same day**: `--unit day` deduplicates while `--unit entry` counts each file.
4. **Sandbox with monthly buckets**: `journal_count` grouped by month returns deterministic trend buckets.
5. **Sandbox with term presence**: `term_presence=晚睡` returns matched paths and `limitations` clarifying "mention count is not behavior proof."

### Phase 2: GREEN — Minimal Executor

6. Implement minimal parser for the whitelisted predicate grammar.
7. Implement deterministic executor with no LLM dependency.
8. Integrate with existing `search_journals` primitive for `term_presence` and `entity_presence` predicates.
9. Ensure JSON output contract compliance.

### Phase 3: Gate — Quality Assurance

10. Unit tests for each predicate type and exactness class.
11. Contract tests verifying JSON schema against the draft in §8.
12. No production data writes in any test.
13. Run `life-index eval` to confirm existing eval gates are not regressed.

---

## 12. Acceptance Gates for C

C-phase implementation is accepted when:

- [ ] All 5 RED test cases from §11 Phase 1 are implemented and failing as expected.
- [ ] All 5 RED test cases pass after GREEN implementation.
- [ ] JSON output contract matches §8 schema (validated by contract test).
- [ ] No existing `search`, `smart-search`, or eval gate regressions.
- [ ] No production data writes occur during any test or execution.
- [ ] Command is registered in `tools/__main__.py` with appropriate help text.
- [ ] `docs/rfc/RFC-001-aggregate-analyze-mvp.md` is updated with any deviations from this proposal (with rationale).

---

## 13. D-Trigger Decision Rule

Do D (retrieval / Entity Graph tuning) before aggregate implementation **only if** a future labeled 20-query gold set shows ordinary lookup/recall failures dominate, for example:

- More than one third of realistic lookup queries are `NO_RESULTS` despite known relevant evidence.
- Entity alias mismatch is the primary failure in multiple high-value queries.
- CJK/English mixed recall fails independently of aggregate/trend needs.

**Current B' evidence does not cross that threshold** (keyword precision 5/8, smart-search citation-backed rate 9/12, invalid citations 0/12).

Therefore, **proceed to C (aggregate/analyze MVP) before D**.

---

## 14. Open Questions

1. **Command naming**: Should the user-facing command be `life-index aggregate`, `life-index analyze`, or both with `analyze` as an alias? This RFC proposes `aggregate` as primary and `analyze` as internal submode / alias.
2. **Predicate grammar evolution**: v0 uses a simple `key=value` whitelist. Should v1 support composite predicates (`entry_time_after=22:00 AND term_presence=晚睡`)? If so, what is the minimal boolean grammar?
3. **Time field reliability**: Current journal frontmatter uses `date: YYYY-MM-DD` (date-only) or `date: YYYY-MM-DDTHH:MM:SS` (datetime). Should the executor treat datetime as reliable for `entry_time_after`, or require an additional `recorded_at` / `written_at` field?
4. **Trend visualization**: Should the JSON output include a `trend` array suitable for simple chart rendering, or should that be a separate `life-index visualize` command?
5. **Integration with smart-search**: Should `smart-search` detect aggregate intent and internally delegate to `aggregate`, or should the Agent explicitly choose the tool?
6. **Schema migration path**: If future schema additions (e.g., `bedtime` field) enable more reliable predicates, what is the migration and backward-compatibility strategy?
7. **Performance at scale**: Has the executor been tested with >10,000 journal entries? What is the acceptable latency ceiling?

---

## Appendix A: Motivating Cases

### Case 1: `过去60天我有多少次晚睡`

**User intent**: Count late sleep events in the past 60 days.
**Data reality**: Journals have `date` (often date-only) and no dedicated `bedtime` field.
**MVP behavior**: Agent proposes predicate `entry_time_after=22:00`. `aggregate` returns `exactness: not_measurable` if time fields are absent, with `limitations: ["No reliable time-of-day field was available..."]`. The user may then choose to:
- Accept the limitation.
- Start recording `bedtime` in future journals.
- Use `term_presence=晚睡` as an approximate proxy (with `exactness: approximate`).

### Case 2: `统计一下我今年写日志的频率趋势`

**User intent**: Trend of journal writing frequency year-to-date.
**Data reality**: Journal paths and frontmatter dates are reliable structured data.
**MVP behavior**: `aggregate --range 2026-01-01..2026-05-12 --unit month --predicate journal_count` returns `exactness: exact` with monthly buckets and `evidence_paths` for each bucket. No LLM needed.

---

## Appendix B: Document Provenance

- **B' evidence**: `.agent-reports/realdata-search-quality/B_PRIME_20_QUERY_CAPABILITY_DIAGNOSIS.md`
- **C design draft**: `.agent-reports/realdata-search-quality/C_DESIGN_AGGREGATE_ANALYZE_MVP_2026-05-12.md`
- **Governance context**: `AGENTS.md`, `.agents.local.md`, `.agent-governance/README.md`, `.agent-governance/ACTIVE_SESSIONS.md`, `.agent-governance/maestro/MAESTRO-ORCHESTRATION-SOP.md`
- **Public API / Architecture context**: `docs/API.md`, `docs/ARCHITECTURE.md`, `docs/ENTITY_GRAPH.md`

## Appendix C: C-Phase Implementation Notes

- The MVP implemented `aggregate` only; the optional `analyze` alias remains deferred.
- `entry_time_after=HH:MM` accepts both ISO datetime in `date` and a separate frontmatter `time` field. If any candidate lacks reliable time data, `exactness` is `not_measurable` and `result.count` is `0` by convention, while matched/unknown entries remain available as evidence.
- `term_presence` and `entity_presence` use simple case-insensitive substring matching via `casefold()` in the MVP. They do not yet delegate to `search_journals` / FTS, so their `exactness` remains `approximate`.
- D2 adds deterministic smart-search delegation for a small whitelist of clear aggregate/count/trend intents, returning top-level `aggregate_result` without letting LLM compute counts.

---

*End of RFC-001*
