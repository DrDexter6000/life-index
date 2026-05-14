# M03 Deterministic Analyze Foundation Design

## Goal

Make deterministic aggregate/analyze a clearer public CLI capability while
preserving the existing aggregate contract and evidence-backed output.

## Scope

M03 is a narrow continuation of RFC-001 and M02/A+. It does not add a broad
natural-language analyzer, LLM counting, multimodal retrieval, or a new Index
Tree API.

In scope:

- Add `life-index analyze` and `python -m tools analyze` as aliases for the
  existing deterministic `aggregate` primitive.
- Keep the returned JSON contract identical to `aggregate`; the output
  `command` remains `"aggregate"` because `run_aggregate()` is still the single
  calculator.
- Document that `analyze` is an alias, not a separate reasoning engine.
- Add contract tests proving the alias is read-only and contract-compatible.
- Preserve M02/A+ `claim_envelope` and `evidence_pack` behavior.

Out of scope:

- LLM-derived counts or trend values.
- Free-form predicate grammar.
- Composite predicates such as `AND` / `OR`.
- Batch/cursor processing.
- Media ingestion or multimodal embedding replacement.
- New Index Tree API. Existing `index_node_ref` remains only a future hook.

## Architecture

The unified CLI dispatcher maps both `aggregate` and `analyze` to
`tools.aggregate.__main__`. `tools.aggregate.core.run_aggregate()` remains the
only deterministic calculator. The alias exists to match user mental models and
agent orchestration language without creating a second implementation.

The contract stays intentionally conservative:

- `aggregate` is the primitive name.
- `analyze` is an entry-point alias.
- `command` in JSON remains `"aggregate"`.
- `claim_envelope.source_command` remains `"aggregate"`.
- `evidence_pack.source_command` remains `"aggregate"`.

## Product Semantics

Agents may choose `analyze` when the user's wording is analytical, but they must
still provide explicit `--range`, `--unit`, and whitelisted `--predicate`
arguments. The alias does not infer predicates from natural language by itself.

For questions such as "how many days did I stay up late in the past 60 days",
the agent should choose a declared predicate such as `entry_time_after=22:00`
and surface limitations. If time fields are missing, the correct answer remains
`not_measurable`, not a fabricated zero.

## Index Tree Role

Index Tree is not part of M03 execution. It remains a future routing and
evidence-navigation affordance. M03 should not read monthly index files or
depend on generated index-tree freshness. The existing `index_node_ref` hook in
the evidence pack is sufficient for this milestone.

## Acceptance Criteria

- `python -m tools analyze ...` works for the same arguments accepted by
  `python -m tools aggregate ...`.
- The alias emits valid JSON with `command == "aggregate"`.
- The alias includes `claim_envelope` and `evidence_pack`.
- The alias does not write to the data directory.
- Existing aggregate tests remain green.
- API documentation no longer says the `analyze` alias is unimplemented.
