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
| `actor` | Agents that can act or be related to actions | `human`, `organization`, `software_agent`, `group` |
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
- `--seed` only behind a preview-first facade or sandbox-only workflow.

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
- `--merge` / `--unmerge` through review-backed or user-confirmed actions.
- `keep_separate` / `undo_keep_separate` for durable non-duplicate decisions.
- `--add-alias`, `--update`, `--add`, and future typed update primitives.
- future `normalize` / `migrate-types` planner and applier.

The default maintenance path is repair/normalize/review. Full rebuild is a
last-resort mode and must preserve user assertions by default.

## 5. Primitive Audit

| Primitive | Current role | New workflow owner | Status | Recommendation |
| --- | --- | --- | --- | --- |
| `--list` | Read graph entities, optionally by type | Audit / advanced inspect | Keep | Keep as read-only primitive; not a primary user workflow. |
| `--resolve` | Resolve name/id/alias to one entity | Audit / host-agent navigation | Keep | Keep; future type schema must preserve behavior for confirmed entities. |
| `--add` | Direct confirmed entity write from JSON | Build / maintain | Keep but gate | Keep as advanced primitive; facade should prefer batch preview or explicit confirmed add. Add preview/validation contract before making it user-facing. |
| `--update` | Currently only works with `--add-alias` | Maintain | Misleading | Either implement real typed update or deprecate as a synonym for `--add-alias`. Do not teach it as general update until fixed. |
| `--add-alias` | Add confirmed alias metadata | Maintain | Keep | Keep; requires user confirmation in production. |
| `--audit` | Quality audit and candidate questions | Audit | Keep | Make it a component of `entity audit`; ensure issue wording stays neutral. |
| `--check` | Structural integrity check | Audit | Keep | Keep as low-level structural primitive; combine into `entity audit`. |
| `--stats` | Counts and graph summary | Audit | Keep but demote | Keep as advanced inspect; user-facing health should consume it. |
| `--review` | Queue, preview, import/export, action apply | Maintain | Keep | Core HITL primitive. User-facing docs should teach the workflow, not every action first. |
| `--review --export/--import` | Table round-trip for decisions | Maintain | Keep | Keep as efficient batch decision channel; teach under advanced maintain. |
| `--merge` | Direct merge via historical flag shape | Maintain | Keep compatible, hide | Keep for compatibility. Primary facade should route through preview/review semantics. The required unused positional value is historical burden. |
| `--unmerge` | Restore merge tombstone | Maintain | Keep | Core reversibility primitive. |
| `keep_separate` / `undo_keep_separate` | Persist or remove user non-duplicate decision | Maintain | Keep | Core authority primitive. Audit must respect it. |
| `--propose` | Host-agent candidate lane | Build / maintain | Keep | Keep; it writes candidate state only and fits the double-lane model. |
| `--apply-batch` | User-confirmed batch apply | Build | Keep | Strong build primitive. Keep preview/apply and idempotency as hard contract. |
| `--delete --preview` | Preview entity deletion impact | Maintain / advanced | Keep but high-risk | Keep advanced only. Future facade should require preview and backup before destructive delete. |
| `--delete` | Immediate entity deletion and reference cleanup | Maintain / advanced | Risky | Keep compatible but do not teach as normal maintenance. Consider backup/confirm guard in future. |
| `--seed` | Cold-start from journal frontmatter; writes graph | Build | Deprecated as primary | Do not teach as production workflow. Replace with preview-first build-from-journals facade. |
| `--candidate-edges` | Read-only candidate relationship report | Build / maintain evidence | Keep but rename semantics | Keep as evidence helper. Its `auto-confirm-recommended` wording should be renamed because no CLI path may auto-confirm. |
| write-time candidate capture | Deterministic repeated unknown-name candidate pool | Build / maintain | Keep | Keep. It writes candidate state only and respects threshold config. |
| `check_graph_status()` suggested `--seed` | Search/health graph status hint | Audit / health | Needs update | Future hints should point to preview-first build/audit, not direct `--seed`. |

## 6. Retirement And Demotion Policy

The project should not remove primitives merely because the top-level UX is
being simplified. Use this order:

1. Keep compatibility and stop teaching the primitive as a primary entry.
2. Add facade coverage and tests for the new workflow.
3. Mark the old primitive as advanced or deprecated in docs/help.
4. After two minor releases, delete only if no public contract or consumer uses
   it and the replacement is proven by dogfood.

Immediate deletion candidates are not identified in this spec. Immediate
demotion candidates are `--seed`, direct `--merge`, direct `--delete`, and
misleading `--update`.

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
5. Add `entity build --from-journals --preview` test that proves no graph write;
   then wrap or replace `--seed` behind preview-first planning. **Implemented.**
6. Add `entity maintain --normalize --preview` tests for old-type graph planning
   with no writes.
7. Add `entity maintain --normalize --apply --backup` tests for atomic write,
   backup creation, ID preservation, and tombstone/not-duplicate preservation.
8. Add help/docs tests that primary SKILL guidance teaches only Build / Audit /
   Maintain while advanced primitive references remain available.
9. Add compatibility tests proving old flags still work through at least two
   minor releases.
10. Dogfood on owner-authorized data: read SKILL literally, run audit, run one
    preview-only build/normalize path, and confirm the host-agent workflow is
    understandable without reading primitive docs.

## 10. First Implementation PR Recommendation

The first runtime PR should not delete any primitive. It should add the facade
parser and a read-only `entity audit --json` workflow because that gives users
an immediate lower-cognitive-load entry without risking data writes.

Recommended first slice:

- `entity audit --json`
- help text grouping primary workflows and advanced primitives
- SKILL update: route entity tasks through Build / Audit / Maintain
- no schema migration yet

The second slice should implement normalize preview/apply. Build-from-journals
should wait until preview semantics replace the unsafe production `--seed`
path.
