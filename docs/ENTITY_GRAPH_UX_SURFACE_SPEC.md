# Entity Graph UX Surface Spec

> Status: Active implementation reference
> Date: 2026-07-05
> Scope: Entity Graph user-facing workflow surface, primitive audit, and future
> migration/normalization direction.

Implemented slices as of 2026-07-05:

- `entity audit --json`
- `entity maintain --normalize --preview/--apply --backup --json`
- `entity build --from-batch FILE --preview/--apply --json`
- `entity build --from-journals --preview --json`

This spec is subordinate to `CHARTER.md`, `docs/API.md`, and
`docs/ENTITY_GRAPH.md`. It does not deprecate or remove any existing public
command by itself; deprecation requires implementation, compatibility tests,
documentation, and release notes in a later PR.

## 1. Goal

Entity Graph has grown from a small lookup file into a durable user-knowledge
surface with provenance, review queues, candidate capture, batch apply,
reversible merge, and keep-separate decisions. The primitive layer is useful,
but the top-level user and host-agent mental model is now too wide.

The goal is to keep the deterministic primitives while presenting three stable
workflows:

1. `build` - create or extend the graph from journals, user-confirmed batches,
   conversation-derived structures, or future controlled rebuild plans.
2. `audit` - answer whether the graph is healthy, what needs human judgment,
   and which next workflow should run.
3. `maintain` - resolve audit/review items, normalize schema, migrate types,
   and repair graph state without silently overriding user judgments.

This is a UX and contract design layer over existing primitives. It must not
move reasoning into the CLI. Host agents still analyze evidence and interview
the user; CLI tools only read, validate, plan, preview, or apply deterministic
changes.

## 2. Governing Constraints

- CHARTER APEX remains binding: CLI core is deterministic L2 tooling; host
  agents own planning, interpretation, synthesis, and ambiguous judgment.
- User-confirmed graph state is authoritative. `source=user,status=confirmed`
  with empty evidence is healthy, not suspicious.
- Candidate state is a suggestion pool, not a decision. Candidate entities and
  candidate relationships must not affect confirmed search/entity expansion.
- Confirmed graph writes require human judgment: explicit per-item confirmation
  or explicit batch authorization.
- Entity Graph is not a pure derived index. It contains user judgments,
  tombstones, non-duplicate decisions, aliases, and relationships that cannot
  be rebuilt from journals alone.
- Any destructive, broad, or schema-changing operation must be preview-first,
  atomic on apply, backed up, and able to report what cannot be preserved.

## 3. Proposed Top-Level Entity Type Direction

The future schema should use a small stable `type` set plus open-ended
`attributes` and explicit relationships:

| Top-level type | Purpose | Typical `attributes.kind` values |
| --- | --- | --- |
| `actor` | Agents that can act or be related to actions | `human`, `organization`, `software_agent` |
| `place` | Physical or logical locations | `city`, `country`, `home`, `venue` |
| `project` | Ongoing efforts with lifecycle and work context | `personal`, `work`, `product`, `research` |
| `event` | Time-bounded happenings | `trip`, `meeting`, `birthday`, `milestone` |
| `artifact` | Created or used objects and media | `ai_model`, `app`, `book`, `document`, `device` |
| `concept` | Abstract ideas, topics, themes, and categories | `topic`, `value`, `method`, `theme` |

Current schema types (`person`, `place`, `project`, `event`, `concept`) remain
backward-compatible during migration. The first migration should preserve
entity IDs and move meaning into `type` + `attributes`; ID renaming is a later
optional cleanup only if it is proven safe.

## 4. User-Facing Workflows

### 4.1 Build

Build creates or extends a graph. It is not a blind rebuild.

Expected future facade examples:

```bash
life-index entity build --from-journals --preview --json
life-index entity build --from-batch family.yaml --preview --json
life-index entity build --from-batch family.yaml --apply --json
life-index entity build --rebuild-plan --preview --preserve-user-assertions --json
```

Build maps to existing primitives:

- `--apply-batch` for user-confirmed structured batch input.
- `--propose` for host-agent hypotheses that should enter review as candidates.
- write-time candidate capture for repeated unknown names.
- `--candidate-edges` as a read-only evidence discovery helper.
- build-from-journals preview for journal-derived cold-start candidates.

Build must never silently write confirmed graph state from host-agent inference.
When a user provides a table, paragraph, spreadsheet, or image-derived
structure, the host agent parses it, restates the structure, obtains user
authorization, then calls deterministic apply primitives.

### 4.2 Audit

Audit answers: "Is the graph healthy, and what should the agent do next?"

Expected future facade example:

```bash
life-index entity audit --json
```

Audit should combine structural and quality signals:

- `--check`: structural validity, dangling refs, duplicate lookups, schema
  issues.
- `--audit`: duplicate candidates, incomplete relationship questions, pending
  candidate items, neutral facts.
- `--stats`: counts by type, alias count, relationship count.
- `health.entity_maintenance`: traffic light, pending count, and stale audit
  signal.

Audit output should point to `entity maintain` / `entity --review`, not present
a wall of low-level commands. Archive/delete language is forbidden for
user-confirmed entities or relationships.

### 4.3 Maintain

Maintain resolves review items, applies user decisions, and performs safe
normalization/migration.

Expected future facade examples:

```bash
life-index entity maintain --review --json
life-index entity maintain --normalize --preview --json
life-index entity maintain --normalize --apply --backup --json
life-index entity maintain --rebuild --preview --preserve-user-assertions --json
```

Maintain maps to existing primitives:

- `--review` queue, preview, export/import, and actions.
- review-backed merge actions plus `--unmerge` for reversibility.
- `keep_separate` / `undo_keep_separate` for durable non-duplicate decisions.
- `--add-alias`, `--add`, and future typed update primitives.
- future `normalize` / `migrate-types` planner and applier.

The default maintenance path is repair/normalize/review. Full rebuild is a
last-resort mode and must preserve user assertions by default.

## 5. Primitive Audit

| Primitive | Current role | New workflow owner | Status | Recommendation |
| --- | --- | --- | --- | --- |
| `--list` | Read graph entities, optionally by type | Audit / advanced inspect | Keep | Keep as read-only primitive; not a primary user workflow. |
| `--resolve` | Resolve name/id/alias to one entity | Audit / host-agent navigation | Keep | Keep; future type schema must preserve behavior for confirmed entities. |
| `--add` | Direct confirmed entity write from JSON | Build / maintain | Keep but gate | Keep as advanced primitive; facade should prefer batch preview or explicit confirmed add. Add preview/validation contract before making it user-facing. |
| `--update` | Historical alias-only flag | Maintain | Removed | Use `--add-alias ALIAS --id ENTITY_ID`. |
| `--add-alias` | Add confirmed alias metadata | Maintain | Keep | Keep; requires user confirmation in production. |
| `--audit` | Quality audit and candidate questions | Audit | Keep | Make it a component of `entity audit`; ensure issue wording stays neutral. |
| `--check` | Structural integrity check | Audit | Keep | Keep as low-level structural primitive; combine into `entity audit`. |
| `--stats` | Counts and graph summary | Audit | Keep but demote | Keep as advanced inspect; user-facing health should consume it. |
| `--review` | Queue, preview, import/export, action apply | Maintain | Keep | Core HITL primitive. User-facing docs should teach the workflow, not every action first. |
| `--review --export/--import` | Table round-trip for decisions | Maintain | Keep | Keep as efficient batch decision channel; teach under advanced maintain. |
| `--merge` | Direct merge via historical flag shape | Maintain | Removed | Use `--review --action preview`, then `--review --action merge_as_alias`. |
| `--unmerge` | Restore merge tombstone | Maintain | Keep | Core reversibility primitive. |
| `keep_separate` / `undo_keep_separate` | Persist or remove user non-duplicate decision | Maintain | Keep | Core authority primitive. Audit must respect it. |
| `--propose` | Host-agent candidate lane | Build / maintain | Keep | Keep; it writes candidate state only and fits the double-lane model. |
| `--apply-batch` | User-confirmed batch apply | Build | Keep | Strong build primitive. Keep preview/apply and idempotency as hard contract. |
| `maintain --delete` | Preview/apply entity deletion with backup | Maintain | Keep | Destructive delete path; preview first, apply requires backup. |
| `--delete` | Immediate entity deletion and reference cleanup | Maintain | Removed | Use `maintain --delete --id ENTITY_ID --preview`, then `--apply --backup`. |
| `--seed` | Cold-start from journal frontmatter; writes graph | Build | Removed | Use preview-first build-from-journals plus user-authorized batch/review apply. |
| `--candidate-edges` | Read-only candidate relationship report | Build / maintain evidence | Keep but rename semantics | Keep as evidence helper. Its `auto-confirm-recommended` wording should be renamed because no CLI path may auto-confirm. |
| write-time candidate capture | Deterministic repeated unknown-name candidate pool | Build / maintain | Keep | Keep. It writes candidate state only and respects threshold config. |
| `check_graph_status()` suggested direct seed | Search/health graph status hint | Audit / health | Fixed | Hints point to preview-first build/audit, not direct cold-start writes. |

## 6. Retirement Decision

Owner decision on 2026-07-05 replaces the earlier conservative two-minor
demotion policy for this work package. Life Index has no historical install
base depending on the legacy top-level entity flags, so the safer path is a
single clean cutover with structured replacement errors.

Removed top-level primitives and replacements:

| Removed primitive | Replacement |
| --- | --- |
| `--seed` | `entity build --from-journals --preview --json`, then user-authorized batch/review apply |
| `--update` | `entity --add-alias ALIAS --id ENTITY_ID` |
| `--merge` | `entity --review --action preview`, then `entity --review --action merge_as_alias` |
| `--delete` | `entity maintain --delete --id ENTITY_ID --preview --json`, then `--apply --backup` |

Any call to a removed top-level primitive must return structured
`ENTITY_PRIMITIVE_REMOVED` JSON with the replacement command. This is an
intentional contract break for 1.3.7 accumulation, not a hidden argparse
failure.

## 7. Normalize And Migration Model

Future type migration should be implemented as a deterministic plan/apply
primitive under Maintain, not as a rebuild:

```bash
life-index entity maintain --normalize --preview --json
life-index entity maintain --normalize --apply --backup --json
```

Required behavior:

- Preview outputs a complete plan and does not write.
- Apply validates the whole graph before writing and creates a backup.
- Clear mappings can apply automatically:
  - `person` with human signals -> `actor` + `attributes.kind=human`
  - `person` with AI assistant signals -> `actor` + `attributes.kind=software_agent`
  - `person` with family role labels -> `actor` + `attributes.kind=human`
  - organization-like entities -> `actor` + `attributes.kind=organization`
  - model/app/book/document/device-like entities -> `artifact` with matching kind
  - `place`, `project`, `event`, `concept` mostly preserve type unless a rule is
    unambiguous.
- Ambiguous mappings become review questions, not automatic rewrites.
- Entity IDs are preserved in the first migration.
- Relationships, aliases, evidence, source/status/created_at, tombstones, and
  `not_duplicate_of` records are preserved.
- Candidate entities and candidate relationships stay candidate after
  migration.

## 8. Controlled Rebuild Model

Full rebuild is allowed only as a last-resort maintenance workflow, not as the
normal way to keep the graph healthy.

Required behavior:

- Must be explicit: `--rebuild`, not implied by `build`.
- Must be preview-first and produce a diff.
- Must back up the current graph on apply.
- Must preserve `source=user,status=confirmed` entities and relationships by
  default, even when evidence is empty.
- Must preserve `not_duplicate_of`, `merged_entities`, aliases, and provenance.
- Must report any user assertion it cannot preserve and refuse apply unless the
  user explicitly authorizes loss.
- Must not treat journals as the only authority source.

## 9. Proposed TDD Implementation Order

1. Add read-only facade help/contract tests for `entity build`, `entity audit`,
   and `entity maintain`; make them fail because subcommands do not exist.
2. Implement parser facade without changing primitive behavior.
3. Add `entity audit --json` contract test that combines check/audit/stats into
   one traffic-light payload and points next steps to review/maintain.
4. Add `entity build --from-batch FILE --preview/--apply` tests that delegate to
   existing batch behavior without changing output semantics.
5. Add `entity build --from-journals --preview` test that proves no graph write,
   then route cold-start through preview-first planning. **Implemented.**
6. Add `entity maintain --normalize --preview` tests for old-type graph planning
   with no writes.
7. Add `entity maintain --normalize --apply --backup` tests for atomic write,
   backup creation, ID preservation, and tombstone/not-duplicate preservation.
8. Add help/docs tests that primary SKILL guidance teaches only Build / Audit /
   Maintain.
9. Add successor tests proving removed top-level flags return structured
   replacement errors.
10. Dogfood on owner-authorized data: read SKILL literally, run audit, run one
    preview-only build/normalize path, and confirm the host-agent workflow is
    understandable without reading primitive docs.

## 10. Implementation Status

The initial facade slices have landed. Owner decision on 2026-07-05 changed the
primitive retirement plan from long demotion to a clean cutover for the four
legacy top-level flags listed in §6.

Recommended first slice:

- `entity audit --json`
- help text grouping primary workflows and remaining advanced primitives
- SKILL update: route entity tasks through Build / Audit / Maintain
- no schema migration yet

Later slices should continue reducing surface area only after the replacement
workflow has an explicit facade and successor tests.
