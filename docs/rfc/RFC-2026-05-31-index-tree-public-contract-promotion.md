# RFC: Index Tree Evidence Navigation Public Contract Promotion

Status: Accepted
Created: 2026-05-31
Accepted: 2026-05-31 via delegated ACK_2 from `副审_Opus`
Classification: public-surface promotion RFC; no implementation in this RFC;
no version bump until M4 release gate
Related:
`docs/rfc/RFC-2026-05-14-index-tree-evidence-navigation.md`,
`docs/API.md`, `CHARTER.md`,
`tools/generate_index/navigation.py`,
`tools/dev/index_tree_evidence_manifest.py`

## 1. Decision

Promote **Index Tree Evidence Navigation** from private `tools/dev` research
toward a public, read-only CLI contract only if the implementation satisfies
the gates in this RFC.

The public command family is proposed as:

```bash
life-index index-tree <subcommand> --json
python -m tools index-tree <subcommand> --json
```

The public schema family is proposed as:

```text
m31.index_tree.v1
```

This RFC authorizes implementation planning and TDD execution after acceptance.
It does not itself change public CLI behavior, public JSON output, version
metadata, or search ranking.

## 2. Real Consumers

The Foundation Freeze §1.10 real-consumer gate is satisfied by the user's
2026-05-31 answer:

```text
1 and 2, plus smart-search enhancement and already-running advanced modules.
```

Mapped into Life Index modules and RFC terminology:

| Consumer | Public-contract need | Hard boundary |
|---|---|---|
| M24 `on-this-day` | Reflection/navigation lens over root/year/month evidence nodes. | Navigation aid only; journal content remains truth. |
| GUI | Evidence navigation/lens display through CLI JSON envelopes. | GUI must not parse `tools/dev` artifacts or write durable journal data. |
| `smart-search` enhancement | Aggregate/search diagnostics and candidate-set explainability. | Recall preservation is mandatory; no default ranking/order mutation in this milestone. |
| Advanced modules already in development | Shared evidence navigation envelopes for L3 consumers. | Consumers may use public CLI/API envelopes or explicitly approved internal APIs only. |

Generic future usefulness is not enough. The promotion remains tied to these
named consumers.

## 3. Scope

The public surface may include:

| Subcommand | Purpose | Side effects |
|---|---|---|
| `nodes` | Emit root/year/month node summaries, freshness, counts, and evidence refs. | read-only |
| `lens` | Emit cross-time derived lenses over `topic`, `people`, or `project`. | read-only |
| `shadow` | Emit search-shadow diagnostics for a query. | read-only, diagnostic only |

The implementation must keep journals as the only durable truth source. Index
Markdown, manifests, lenses, reports, and sidecars are rebuildable derived
artifacts.

## 4. Non-Goals

This promotion must not:

- adopt an EverOS-style service stack, daemon, HTTP substrate, database, or
  second persistence authority;
- create persona memory truth, profile-as-truth, relationship judgment truth,
  therapeutic judgment, or LLM narrative truth inside CLI core;
- call LLMs from L2/default module paths;
- start social historical import;
- start Tranche C `ai_drafting`;
- change default `life-index search` ranking or order;
- change default `smart-search` ranking or output semantics;
- change public `generate-index --json` shape;
- change journal frontmatter schema or require data migration;
- let GUI consume private `tools/dev` artifacts;
- write or mutate journal files from evidence navigation commands.

## 5. Architecture

### Before

```text
Journals/*.md
  -> generate-index
       -> Markdown Index Tree
  -> search / smart-search / aggregate read journals directly

tools/dev/index_tree_evidence_manifest.py
  -> private prototype manifest only
```

### After

```text
Journals/*.md
  -> shared deterministic index model
       -> Markdown Index Tree
       -> public index-tree JSON envelopes
       -> optional private/dev diagnostic reports

Consumers
  -> on-this-day reflection/navigation lens
  -> GUI evidence navigation views
  -> smart-search diagnostic shadow checks
  -> approved advanced modules
```

The shared model must be deterministic and journal-derived. Markdown reverse
parsing may remain a compatibility or audit fallback, but it must not become
the long-term primary path for public JSON generation.

## 6. Public Envelope Requirements

All JSON envelopes must include:

- `schema_version`;
- `command`;
- `generated_at`;
- `data_dir_fingerprint` or equivalent non-path source identity when needed;
- relative paths only, never absolute user paths;
- freshness status for any derived node/lens data;
- signal coverage denominators where frontmatter signals are emitted;
- structured `errors` when an operation fails or disables narrowing;
- no journal body text unless a later consumer-specific contract explicitly
  authorizes it.

Any frontmatter signal dictionary may contain real person names, project names,
or locations. Persisted reports containing those dictionaries have the same
privacy level as the underlying journals.

## 7. Search Shadow Gate

`index-tree shadow` is diagnostic only. It may report candidate narrowing,
freshness, dropped-path evidence, and recall-preservation status, but it must
not mutate default search or `smart-search` behavior.

Minimum falsifiable tests:

1. Default `search` output and order are unchanged before/after shadow helpers.
2. Default `smart-search` output semantics are unchanged by this milestone.
3. For fixture queries, `baseline_paths <= shadow_candidate_paths`.
4. A deliberately bad node filter fails with dropped-path evidence.
5. Stale or missing index data disables narrowing and reports a structured
   reason.

## 8. Compatibility And Versioning

Compatibility policy for `m31.index_tree.v1`:

- existing fields and semantics are stable;
- additive optional fields are allowed without a schema bump;
- incompatible shape or semantic changes require a new schema version;
- paths remain relative to `LIFE_INDEX_DATA_DIR`.

Version policy:

- This RFC itself does not bump the project version.
- If implementation reaches M4 with public CLI/API/docs/handoff/full gate and
  delegated ack #2, release as a patch bump from `1.2.1` to `1.2.2`.
- If implementation lands but is not released, keep version `1.2.1` and record
  the capability under `CHANGELOG.md` `[Unreleased]`.

## 9. Required Tests

Implementation must add or extend tests for:

```text
tests/unit/test_generate_index_builder.py
tests/unit/test_index_tree_lens.py
tests/unit/test_index_tree_search_shadow.py
tests/contract/test_index_tree_contract.py
tests/contract/test_main_cli_contract.py
```

Focused verification before M4:

```bash
python -m pytest tests/contract/test_index_tree_contract.py tests/contract/test_main_cli_contract.py -q
python -m pytest tests/unit/test_generate_index_builder.py tests/unit/test_index_tree_lens.py tests/unit/test_index_tree_search_shadow.py tests/unit/test_index_tree_navigation.py -q
python -m black --check <changed Python files>
python -m flake8 <changed Python files> --count --max-complexity=40 --max-line-length=100 --show-source --statistics
python -m py_compile <changed Python files>
git diff --check
```

Full release gate before push:

```bash
D:\Program Files\Git\bin\bash.exe scripts/pre-push-gate.sh
```

## 10. Acceptance Criteria

This RFC is accepted when:

1. Real consumers are named as in §2.
2. Non-goals in §4 remain binding.
3. The public schema/version policy in §8 is accepted.
4. Search Shadow Mode remains diagnostic-only with recall-preservation gates.
5. GUI and advanced modules are constrained to public envelopes or explicitly
   approved internal APIs.

Runtime implementation may start only after this RFC is accepted.
