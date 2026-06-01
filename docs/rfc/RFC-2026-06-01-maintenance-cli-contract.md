# RFC: Maintenance CLI Contract Promotion

Status: Accepted by owner ack #1 to the Data Doctor Maintenance PRD
Created: 2026-06-01
Accepted: 2026-06-01 via owner ack #1 in
`.agent-governance/docs/projects/data-doctor-maintenance/PRD.md`
Classification: public-surface promotion RFC; no implementation in this RFC;
no version bump until Phase 4 release gate
Related:
`.agent-governance/docs/projects/data-doctor-maintenance/PRD.md`,
`docs/API.md`, `CHARTER.md`, `tools/maintenance/`

## 1. Decision

Promote user-data maintenance from the existing `m16.maintenance.v0`
dry-run/report-only surface into a stable public `maintenance` command family
only if implementation satisfies the accepted Data Doctor Maintenance PRD.

The public command family is:

```bash
life-index maintenance audit --json
life-index maintenance audit --domain index,links,entity --json
life-index maintenance plan --issue-id <id> --json
life-index maintenance repair --issue-id <id> --dry-run --json
life-index maintenance repair --issue-id <id> --apply --json
life-index maintenance proposal validate --file proposal.json --json
```

The public schema family is:

```text
m33.maintenance_audit.v0
m33.maintenance_plan.v0
m33.maintenance_repair.v0
m33.maintenance_proposal.v0
```

This RFC authorizes TDD implementation after acceptance. It does not itself
change CLI behavior, JSON output, version metadata, search ranking, import
behavior, or user data.

## 2. Rationale And Real Consumers

The real user-data audit exposed that scattered health commands cannot answer a
basic maintenance question: which files, indexes, links, attachments, entity
records, generated artifacts, imports, migrations, backups, configs, and path
portability risks are unhealthy, stale, orphaned, redundant, or unsafe.

Named consumers:

| Consumer | Need | Boundary |
|---|---|---|
| CLI user | One deterministic maintenance audit and dry-run plan surface. | No hidden writes in audit or plan. |
| GUI maintenance console | Stable JSON envelope, counts, detector status, issue IDs, and repair risk classes. | GUI consumes CLI only; no direct L1 mutation. |
| L3 agents | Evidence-backed maintenance recommendations and proposal validation. | Agents may interpret or propose; CLI Core validates deterministically and never calls LLM. |
| Existing `m16.health.v0` / `m16.maintenance.v0` users | Compatibility with current health and maintenance checks. | New `m33.*.v0` surfaces coexist; legacy contracts are not removed. |

This satisfies CHARTER §1.10 because the promotion has concrete existing
consumers, is deterministic, has low LLM content, and exposes reusable L2
maintenance primitives rather than an L3 workflow.

## 3. Scope

Implementation may add:

| Surface | Purpose | Side effects |
|---|---|---|
| `maintenance audit --json` | Emit complete deterministic issue inventory with taxonomy, counts, detector status, and relative evidence paths. | read-only |
| `maintenance plan --issue-id` | Emit dry-run plan metadata for one issue. | read-only |
| `maintenance repair --dry-run` | Preview allowed repair action and touched paths. | read-only |
| `maintenance repair --apply` | Apply only low-risk derived-artifact repairs approved by the PRD. | bounded writes to derived artifacts only |
| `maintenance proposal validate` | Validate L3/user proposal files for durable repair suggestions. | read-only |

## 4. Non-Goals

This promotion must not:

- call LLMs from CLI Core;
- add an L3 workflow engine, daemon, service, or provider configuration;
- change search or smart-search ranking;
- change import planning/running/rollback semantics;
- add new import sources;
- migrate or rewrite journals automatically;
- mutate `entity_graph.yaml` automatically;
- delete attachments, revisions, orphan files, import sources, or user-created
  Markdown;
- print secrets or absolute local user paths in public JSON;
- remove or break `m16.maintenance.v0` or `m16.health.v0`;
- create a second data authority outside `~/Documents/Life-Index/`.

## 5. Public Envelope Requirements

All `m33.maintenance_*.v0` envelopes must include:

- `success`;
- `schema_version`;
- `command`;
- structured `error` or `errors` on failure;
- relative paths only;
- no raw secret values;
- stable issue IDs for issue-targeted commands;
- explicit risk and repairability metadata when a repair decision is relevant.

`m33.maintenance_audit.v0` must also include:

- complete issue enumeration by default;
- `total_issues`;
- per-domain issue counts;
- detector status values of `ok`, `skipped`, or `error`;
- non-truncation semantics; if a display limit is ever added, `limit`,
  `offset`, `has_more`, and full `total_issues` are mandatory.

## 6. Safety Model

The command family has four safety levels:

| Level | Surface | Write authority |
|---|---|---|
| L0 | audit | none |
| L1 | plan / repair dry-run | none |
| L2 | repair apply | derived artifacts only |
| L3 | proposal validate | none; validates proposals for external user/agent review |

Durable user content, metadata, attachments, entity graph records, import
sources, migrations, and config secrets remain outside automatic repair scope.
Any future apply path for those categories requires a separate PRD/RFC or an
existing safe command with explicit preview and user ack.

## 7. Objections Addressed

### Objection 1: Maintenance is too broad for one public contract.

Accepted as an implementation risk. The PRD splits audit, detectors, plan,
derived repair, and proposal validation into separate Steps. The public schema
family remains explicit and versioned so later incompatible changes require a
new version or schema name.

### Objection 2: A repair command could destroy user memories.

Accepted as the primary safety risk. Apply mode is limited to rebuildable
derived artifacts and generated-safe Markdown. Journals, attachments,
hand-curated files, entity graph data, import sources, and migrations stay
preview/proposal-only.

### Objection 3: LLM-assisted maintenance would violate the deterministic boundary.

Accepted for CLI Core, rejected for the broader product. CLI Core remains
deterministic and validates proposals only. LLM assistance may exist in L3 with
explicit user opt-in and minimal context, but it does not become L2 truth.

### Objection 4: Existing `health` / `maintenance` commands may already cover this.

Rejected. Existing commands provide useful checks, but they do not expose a
complete issue inventory, stable issue IDs, per-domain counts, detector status,
proposal validation, or bounded derived repair contract for GUI/L3 consumers.

## 8. Impact List

Implementation is expected to touch:

- `tools/maintenance/**`;
- `tests/contract/test_maintenance_data_doctor_contract.py`;
- maintenance fixtures under `tests/fixtures/`;
- `docs/API.md`;
- `CHANGELOG.md`;
- possibly `tests/contract/test_main_cli_contract.py` if command discovery
  assertions require updates.

No CHARTER amendment is required. The RFC reinforces §1.1, §1.2, §1.3, §1.4,
§1.5, §1.6, §1.7, §1.8, and §1.10.

## 9. Compatibility And Versioning

Compatibility policy for `m33.maintenance_*.v0`:

- existing fields and semantics are stable after release;
- additive optional fields are allowed without a schema bump;
- incompatible shape or semantic changes require a new schema version or schema
  name;
- issue evidence paths remain relative to `LIFE_INDEX_DATA_DIR`.

Legacy `m16.maintenance.v0` and `m16.health.v0` remain supported. The existing
`maintenance --dry-run --output=json` behavior must continue to pass its
contract tests.

This RFC itself does not bump the project version. Version and release metadata
changes belong to Phase 4 packaging after focused tests and owner ack #2.

## 10. Required Tests

Implementation must add or extend focused tests for:

```text
tests/contract/test_maintenance_data_doctor_contract.py
tests/contract/test_maintenance_contract.py
tests/contract/test_main_cli_contract.py
```

Focused verification before Phase 4:

```powershell
python -m pytest tests/contract/test_maintenance_data_doctor_contract.py tests/contract/test_maintenance_contract.py -q
python -m pytest tests/contract/test_main_cli_contract.py -q
python -m py_compile <changed Python files>
python -m black --check <changed Python files>
python -m flake8 <changed Python files> --count --max-complexity=40 --max-line-length=100 --show-source --statistics
git diff --check
```

Full local gate is merge/push-only and uses:

```powershell
& "D:\Program Files\Git\bin\bash.exe" scripts/pre-push-gate.sh
```

## 11. Acceptance Criteria

This RFC is accepted when:

1. The accepted PRD ack #1 is recorded.
2. Real consumers are named in §2.
3. Non-goals in §4 remain binding.
4. The envelope requirements in §5 are reflected in TDD tests.
5. Safety levels in §6 are preserved.
6. Compatibility policy in §9 is preserved.

Runtime implementation may start only after these criteria are satisfied.
