# M02 Evidence-Based Aggregate & Analysis Foundation Design

## Goal

Add a minimal evidence-backed claim layer to deterministic aggregate/analyze output so Life Index can answer measurable natural-language aggregate questions with auditable values, limitations, and source references.

## Scope

M02/A+ builds on the existing `life-index aggregate` primitive and D2 smart-search aggregate delegation. It does not introduce a new product module, full Index Tree API, or batch/cursor framework.

In scope:

- Add an additive `claim_envelope` object to successful aggregate results.
- Add an additive aggregate-specific `evidence_pack` object to successful aggregate results.
- Preserve the existing `aggregate_result` contract used by `smart-search`.
- Add optional future-compatibility hooks: `index_node_ref` on evidence items and `page_info` / `cursor_hint` in the evidence pack.
- Cover exact, approximate, and not-measurable aggregate outcomes.
- Add focused unit/contract tests and update API documentation.

Out of scope:

- Full `life-index analyze` alias.
- Full Index Tree navigation API.
- Full batch/cursor processing platform.
- Any LLM-based counting, relationship interpretation, persona analysis, digital letters, or creative emulation.
- Any writes to real user journals or production data.

## Architecture

`tools.aggregate.core.run_aggregate()` remains the deterministic calculator and single source of aggregate truth. A small aggregate claim/evidence builder should convert the existing aggregate payload plus scanned entry metadata into two additive objects:

- `claim_envelope`: a compact machine-readable statement of the claim, value, exactness, confidence, limitations, and source command.
- `evidence_pack`: a deterministic source map listing matched/excluded/unknown entries with relative paths, dates, roles, bucket keys, and optional `index_node_ref`.

The builder must be pure and deterministic. It must not call LLMs, search, semantic retrieval, or filesystem writes. It may derive index node references from entry dates and relative journal paths.

## Claim Envelope v0

Required fields:

- `schema_version`: fixed string, `m02a.claim_envelope.v0`.
- `claim_type`: one of `measurable_exact`, `measurable_approximate`, `not_measurable`.
- `source_command`: fixed string, `aggregate`.
- `query`: original natural-language query, if provided.
- `metric`: copied from aggregate result.
- `unit`: copied from aggregate result.
- `time_range`: copied from aggregate result `range`.
- `predicate`: copied from aggregate result predicate.
- `value`: copied from `result.count`.
- `denominator`: copied from `result.denominator`.
- `exactness`: copied from `result.exactness`.
- `confidence`: copied from `result.confidence`.
- `limitations`: copied from aggregate result limitations.
- `evidence_pack_ref`: fixed string, `aggregate.evidence_pack`.

Mapping:

- `exact` -> `measurable_exact`
- `approximate` -> `measurable_approximate`
- `not_measurable` -> `not_measurable`

## Evidence Pack v0

Required fields:

- `schema_version`: fixed string, `m02a.aggregate_evidence_pack.v0`.
- `source_command`: fixed string, `aggregate`.
- `query`: original natural-language query, if provided.
- `time_range`: copied from aggregate result `range`.
- `predicate`: copied from aggregate result predicate.
- `items`: evidence item list.
- `page_info`: fixed minimal object with `has_more: false`, `cursor: null`, `cursor_hint: null`.

Evidence item fields:

- `path`: relative journal path using forward slashes.
- `date`: journal date in `YYYY-MM-DD` when available.
- `role`: `matched`, `excluded`, or `unknown`.
- `bucket`: bucket key used by the aggregate result when available.
- `reason`: unknown/exclusion reason when available.
- `index_node_ref`: optional future hook pointing to the deterministic monthly Index Tree node, for example:

```json
{
  "type": "month",
  "id": "Journals/2026/03",
  "path": "Journals/2026/03/index_2026-03.md"
}
```

## Compatibility

Existing aggregate fields remain unchanged. `claim_envelope` and `evidence_pack` are additive. `smart-search` continues to return `aggregate_result` for aggregate-routed queries; the new objects appear inside `aggregate_result`, not as new top-level smart-search fields.

No existing `search` or ordinary `smart-search` contract changes.

## Testing

Required tests:

- `journal_count` returns `claim_type=measurable_exact` and an evidence pack with matched items.
- `term_presence` returns `claim_type=measurable_approximate`.
- missing time for `entry_time_after` returns `claim_type=not_measurable`, count `0`, and unknown evidence items.
- evidence items never contain absolute paths or backslashes.
- smart-search aggregate delegation includes `aggregate_result.claim_envelope` and `aggregate_result.evidence_pack` without calling LLM.

## Acceptance Criteria

- A natural-language aggregate query such as `过去60天我有多少天晚睡` is deterministically routed and returns an aggregate result containing the new claim/evidence objects.
- LLM never computes aggregate values.
- Tests cover exact, approximate, and not-measurable outcomes.
- API documentation describes the additive fields and future hooks.
- No real user data is modified.
