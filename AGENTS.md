<!-- AGENTS.md - Life Index public agent entry -->

# Agent Entry

> First read `CHARTER.md`, especially the North Star APEX.
>
> APEX summary: Life Index provides deterministic, composable tools and domain
> skills. Planning, multi-hop reasoning, interpretation, and synthesis belong
> to the host agent. Client interfaces present results.
>
> Consequence: any change that makes Life Index decide, reason, or orchestrate
> on behalf of the host agent must be treated as a constitutional-risk change
> until proven otherwise.

This file is the public bootstrap for coding agents. It is deliberately small.
Stable product contracts live in public docs. Machine- or operator-specific
workflow overlays may exist locally, but they must not override the public
contracts and must not be copied into public docs.

## Authority Order

1. `CHARTER.md` owns constitutional invariants.
2. `AGENTS.md` owns public agent bootstrap guidance.
3. `docs/API.md` owns CLI and server API contracts.
4. `docs/ARCHITECTURE.md` owns implementation architecture.
5. `docs/ENTITY_GRAPH.md` and `docs/VERSIONING.md` own their named domains.
6. `docs/CI_HARD_CHECKS.md` owns the public CI hard-check inventory.

When documents conflict, stop and resolve the conflict instead of silently
choosing the convenient rule.

## Project Overview

Life Index is an agent-native, local-first personal journal and retrieval
system.

- The CLI co-packages deterministic Core tools with non-Core public routes.
  `docs/ARCHITECTURE.md` owns the exact public-command classification;
  `docs/API.md` owns command semantics.
- User data lives outside the repository in the configured Life Index data
  directory.
- Journal storage is plain text: Markdown plus YAML frontmatter.
- Agents use natural language for planning, but call deterministic CLI tools
  when atomicity, repeatability, or evidence matters.

## Required Reads By Task

| Task | Read |
|---|---|
| First project handoff | `CHARTER.md`, then this file, then `AGENT_ONBOARDING.md` and `SKILL.md` if setup or skill usage is needed |
| Architecture or module boundary change | `CHARTER.md` and `docs/ARCHITECTURE.md` |
| API, CLI, server, or envelope change | `docs/API.md` and relevant tests |
| Data format or schema change | `CHARTER.md` data-boundary sections and `docs/ARCHITECTURE.md` data-format sections |
| Entity graph change | `docs/ENTITY_GRAPH.md` |
| Version or release change | `docs/VERSIONING.md` and `CHANGELOG.md` |
| Search behavior or ranking change | `CHARTER.md` search invariants and `docs/ARCHITECTURE.md` search sections |
| Agent-facing behavior change (tools / retrieval / nav / entity) | `SKILL.md`, and dogfood the change as the host agent on real/authorized data |
| CI hard-check or local gate change | `docs/CI_HARD_CHECKS.md` and the relevant workflow/script |

Do not read historical documents by default. Use them only for explicit
historical research.

## Working Rules

- Scale process to blast radius. Tiny docs or hygiene edits need one focused
  pass. Runtime, contract, CI, schema, or data-boundary work needs explicit
  verification and review.
- Inspect the Git state before editing. Do not overwrite, revert, stage, or
  format work you do not own.
- Use explicit path staging. Do not use broad staging commands for mixed work.
- Keep public docs product-generic. Do not publish local paths, private
  workflow evidence, operator-specific notes, credentials, or temporary plans.
- Never write test data into the real user data directory. Use a temporary or
  explicitly configured sandbox for tests and smoke checks.
- Do not change user journal content unless the task explicitly asks for that
  data operation.
- If a doc claims a code, schema, YAML, JSON, or config artifact changed, the
  same commit must include the actual artifact diff or mark the implementation
  as pending.
- `SKILL.md` (+ references/) is a first-class deliverable. Any agent-facing
  change (tools, retrieval/navigation, entity graph) updates `SKILL.md` in the
  same change; install/upgrade must deliver the current `SKILL.md`, Index, and
  entity graph to the host agent. Tools without the current playbook are
  incomplete.
- Done = the host-agent outcome on real data, not CI alone. Before claiming
  done on an agent-facing change, operate it as the host agent would: read
  `SKILL.md`, run the tools on real or owner-authorized data, and confirm the
  user's actual question is answered (GROUNDED) — following `SKILL.md` literally
  rather than relying on cleverness a weaker host agent lacks. CI is necessary,
  not sufficient.
- Treat CI as the merge-readiness authority for required checks. Local tests are
  useful diagnostics, not a substitute for required CI.

## Tool Invocation

Prefer module execution for developer-mode CLI calls:

```bash
python -m tools.write_journal --data '{"title":"...","content":"...","date":"2026-03-07","topic":"work"}'
```

Avoid directly executing package scripts unless a documented command requires
that form.

## Common Commands

```bash
life-index write --data '{"title":"...","content":"...","date":"2026-03-07","topic":"work"}'
life-index confirm
life-index search --query "keyword" --level 3
life-index smart-search --query "natural language query"
life-index edit --journal "Journals/2026/03/life-index_2026-03-07_001.md" --set-weather "sunny"
life-index abstract --month 2026-03
life-index weather --location "London,United Kingdom"
life-index index
life-index index --rebuild
life-index generate-index
life-index backup --dest "/path/to/backups/Life-Index"
life-index verify --json
life-index timeline --range 2026-01 2026-03
life-index migrate --dry-run
life-index migrate --apply
life-index entity --audit
life-index entity --stats
life-index entity --check
life-index entity --review
life-index eval
life-index aggregate --range 2026-01-01..2026-03-31 --unit month --predicate journal_count
life-index analyze --range 2026-01-01..2026-03-31 --unit day --predicate entry_time_after=22:00
life-index health
life-index health --data-audit
life-index version
life-index on-this-day --date 2026-05-19 --years-back 3 --json
```

Full command details live in `docs/API.md`.

## Data And Privacy Boundary

- Repository files are code, docs, tests, and deterministic tooling.
- User data is external to the repository and must remain physically separate.
- Tests must use temporary directories or explicit sandbox data directories.
- Public documentation must not include personal paths, credentials, operator
  workflow details, temporary report paths, or private runtime notes.
- New public paths must match `.github/public-surface.allowlist`; update that
  file deliberately when a new public surface is intentional.

## Design Floor

```text
Prefer simple functionality over system complexity.
Prefer manual maintenance over automation traps.
Prefer reliability over performance when they conflict.
```
