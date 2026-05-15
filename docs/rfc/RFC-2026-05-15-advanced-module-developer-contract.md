---
type: implementation-rfc
status: accepted-in-pack
created: 2026-05-15
title: Advanced Module Developer Contract
pack: LONGRUN-EVIDENCE-ANALYZE-MODULE-SUBSTRATE-2026-05-15
related:
  - CHARTER.md §1.9
  - CHARTER.md §1.10
  - docs/rfc/RFC-2026-05-14-module-foundation-boundary.md
---

# RFC-2026-05-15: Advanced Module Developer Contract

## 1. Summary

This RFC turns the module-foundation boundary into developer-facing guidance for
future L3/L4 advanced modules. It does not add a plugin loader, runtime module
registry, new CLI command, or new persistent data layout. It defines how a
module may consume the Life Index CLI foundation safely.

The default model is:

```text
advanced module
  -> CLI JSON contract or documented tools.* public API
  -> Life Index L2 primitives
  -> local Markdown/YAML truth source
```

Modules may be long-running, resumable, and intelligent, but the Life Index CLI
foundation remains deterministic and evidence-first.

## 2. Contract Surface

Modules may consume Life Index through two stable surfaces:

| Surface | Allowed Use | Constraint |
|---|---|---|
| CLI JSON-in/JSON-out | Run public commands such as `search`, `smart-search`, `aggregate`, `analyze`, `entity`, `timeline`, `health`, and `generate-index`. | Treat documented JSON shape, field semantics, error codes, and SLOs as the contract. |
| Documented `tools.*` public APIs | Use public helper functions only when already documented or clearly exported for module use. | Do not depend on SQLite table shape, vector index layout, jieba internals, private helper names, or file walking shortcuts. |

The CLI command contract is preferred when building third-party modules because
it is easier to test, shell, sandbox, and keep independent of internal Python
refactors.

## 3. Module State

Modules may own process state, but not user data truth.

Allowed module-local process state:

- `run_id` ledgers;
- cursors and checkpoints;
- intermediate evidence packs;
- module-local notes, routers, trees, or wiki pages;
- temporary caches that can be deleted and rebuilt.

Forbidden module state:

- writable module folders under `~/Documents/Life-Index`;
- direct journal/frontmatter/entity writes that bypass CLI commands;
- a second source of truth for journals, entities, tags, topics, metrics, or
  user-data schema;
- hidden cloud sync or provider state for raw journal content.

Example module-owned directory:

```text
.openclaw/workspace/skills/life-index/models/late_sleep_analyzer/
  runs/
    2026-05-15T000000Z/
      checkpoint.json
      notes.md
      evidence-pack.json
      route-tree.md
```

This path is illustrative, not a runtime discovery rule. Equivalent
module-owned install directories are acceptable when they remain outside
`~/Documents/Life-Index` and outside the CLI core truth source.

## 4. Long-running Workflows

Advanced modules may be slow. They should make that explicit instead of
pressuring L2 primitives to become monolithic.

A module that expects long execution should expose:

| Field | Meaning |
|---|---|
| `estimated_steps` | Number of planned CLI calls or batches. |
| `estimated_entries` | Approximate entries or index nodes to inspect. |
| `checkpoint_path` | Module-local checkpoint location. |
| `resume_strategy` | How the module resumes after interruption. |
| `evidence_policy` | Whether it stores paths only, snippets, or full evidence; default should be paths and minimized snippets. |
| `limitations` | Known semantic limits, such as "journal write time is not sleep time." |

Long-running modules should prefer Index Tree node boundaries for progress and
resume because month/year nodes are stable, local, and auditable.

## 5. Evidence-first Output

Modules should output evidence before interpretation.

Recommended shape:

```json
{
  "success": true,
  "module": "late_sleep_analyzer",
  "schema_version": "module.local.v0",
  "claim_envelope": {},
  "evidence_pack": {},
  "module_notes_ref": "runs/2026-05-15T000000Z/notes.md",
  "limitations": [],
  "next_actions": []
}
```

The module may later ask a calling agent to synthesize prose, but the prose is
not the machine-trusted evidence. Evidence paths, predicates, exactness, and
limitations must remain available.

## 6. Promotion Back To CLI

A module-local helper may be proposed as a Life Index L2 primitive only when it
is:

- deterministic;
- useful across multiple modules or explicitly determined by the developer/user
  to have long-term foundation value;
- low-LLM or no-LLM in its default path;
- stable in meaning across 10/20/50 years of logs;
- testable with explicit input/output contracts.

Promotion requires an RFC and must identify:

| Question | Required Answer |
|---|---|
| Which modules need it? | At least one real consumer and, preferably, multiple likely consumers. |
| Why not keep it module-local? | Concrete reuse or long-term stability reason. |
| What is the CLI contract? | JSON shape, field semantics, error codes, and SLO. |
| What is the privacy boundary? | Data read/write scope and provider exposure, if any. |
| What is the eval gate? | Unit, contract, real-data probe, or gold/eval criterion. |

## 7. Non-goals

This RFC does not:

- implement dynamic plugin loading;
- define package discovery or entry points;
- add a runtime module registry;
- add new L2 commands;
- authorize direct writes to real user data;
- authorize default LLM calls inside modules.

## 8. Acceptance Criteria

Future advanced modules should be considered contract-compliant when:

1. they consume Life Index through CLI JSON or documented public APIs;
2. they keep process state in module-owned directories, not user data;
3. they preserve evidence, provenance, exactness, and limitations;
4. they do not make CLI internals part of their contract;
5. any requested CLI primitive promotion comes with an RFC and eval gate.
