# Agent Upgrade Atom Design

## Purpose

`life-index upgrade` is a deterministic operations primitive for host agents and
users upgrading an installed Life Index CLI. It is not a developer release
workflow and does not replace PR review, CI, merge, tag, GitHub Release, PyPI
publish, or post-release smoke.

The command exists because host agents need one stable place to answer:

- which CLI version and bootstrap manifest are installed;
- whether PyPI recommends a newer non-yanked release;
- whether a source checkout is dirty, ahead, behind, diverged, or stale relative
  to a read-only remote probe;
- whether `health --json` is parseable;
- whether `sync-skill` can deliver the current playbook to the canonical host
  skill slot.

## Non-Goals

- No GUI repository operations.
- No LLM calls, reasoning, or synthesis.
- No release publishing, tagging, PR merging, or PyPI upload.
- No writes to journals or user source data.
- No automatic stash, reset, rebase, merge, or push.

## Contract

Two modes are exposed:

```bash
life-index upgrade --plan --json
life-index upgrade --apply --json
```

`--plan` is read-only. It returns current installed package version, bootstrap
manifest `repo_version`, PyPI release status, optional git checkout status,
health JSON parse status, sync-skill canonical slot status, `actions[]`, and a
`recommended_next_step`.

`--apply` executes only actions marked safe by the plan:

- package installs may upgrade to the recommended non-yanked PyPI version;
- editable/source checkouts may refresh remote refs and run `git pull --ff-only`
  only when clean, behind, and not ahead;
- any action with `safe_to_run=false` or `requires_human=true` blocks apply
  before write actions;
- `health --json` is run and parsed;
- `sync-skill --install --json` is run through the existing sync-skill command.

Every action reports:

- `id`
- `description`
- `side_effect`: `read` or `write`
- `command`
- `reason`
- `safe_to_run`
- `requires_human`

## Freshness Rules

Version is not enough. If package version and manifest version are equal but the
source checkout is behind its upstream ref, or the remote probe sees commits not
visible in local tracking refs, `--plan` still recommends a git refresh. Dirty,
ahead, or diverged checkouts are fail-closed and require a human. Apply never
stashes, resets, rebases, merges, or pushes.

Plan uses read-only remote probing and does not fetch, because fetch mutates
`.git`. Apply may run a remote refresh first, then reinspect the checkout, and
only run `git pull --ff-only` when the refreshed state is clean, behind, and not
ahead.

## PyPI Rules

PyPI metadata is obtained through a provider abstraction. Production uses the
PyPI JSON API; tests use fake providers. Network failure produces a partial
report and does not block local git, health, or skill checks. Yanked releases
are never recommended as targets. A yanked current version is a warning and
points to the latest non-yanked release when one exists.

## Skill Delivery Rule

`upgrade --apply` does not duplicate skill installation logic. It calls
`life-index sync-skill --install --json` and reports the returned status,
including the canonical `<host-home>/skills/life-index` target and any recovery
diagnostics.

## JSON Purity

All `--json` stdout must be directly parseable with `json.loads`. Logs, third
party progress, and diagnostics belong on stderr or inside the JSON payload.
