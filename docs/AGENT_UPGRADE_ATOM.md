# Agent Upgrade Atom Design

## Purpose

`life-index upgrade` is a deterministic, read-only operations primitive for
diagnosing an installed Life Index CLI. It reports whether the program is
current or must be replaced. It is not an installer, package manager, recovery
state machine, or developer release workflow.

User data is the durable asset. Dedicated venvs, host-managed checkouts, package
metadata, and dependencies are disposable program state. Shared/global Python
environments and developer- or user-owned checkouts are never mutated or
deleted by this command.

## Contract

Two modes are exposed:

```bash
life-index upgrade --plan --json
life-index upgrade --apply --json
```

Both modes perform only diagnostics: installed/package version, bootstrap
manifest version, non-yanked PyPI freshness, optional checkout status and
read-only remote probe, health JSON parseability, and sync-skill discovery.

`--plan` returns `actions[]` and `recommended_next_step`. It never emits an
executable in-place `git pull`, `git fetch`, `pip install --upgrade`,
`pip install -e`, or `sync-skill --install` action.

When an update or program inconsistency requires replacement, the plan emits one
human-required action:

```json
{
  "id": "reinstall_managed_environment",
  "side_effect": "write",
  "command": null,
  "safe_to_run": false,
  "requires_human": true
}
```

Its guidance points to `AGENT_ONBOARDING.md`: leave the existing environment
and checkout untouched and create a fresh dedicated install. It never suggests
deleting user data or repairing a shared/developer environment in place.

`--apply` does not apply git, pip, skill-delivery, or environment writes. It
builds the same read-only plan and returns one of these outcomes:

- update or inconsistency: `success: false`,
  `error.code: "UPGRADE_REINSTALL_REQUIRED"`,
  `data.reinstall_required: true`, and `data.applied_actions: []`;
- healthy/current with no action: `success: true`,
  `data.reinstall_required: false`, and `data.applied_actions: []`;
- dirty, ahead, diverged, unreachable, unknown, or otherwise human-risk state:
  the existing fail-closed error semantics, with no writes.

## Freshness And Safety

Version equality is not enough for editable/source diagnostics. A behind local
tracking ref or a read-only remote probe that sees newer commits requires a
fresh dedicated install. Dirty, ahead, and diverged checkouts remain explicit
human-review states. Remote probe failure marks freshness unknown and the report
partial; it never authorizes mutation or deletion.

PyPI metadata remains advisory. Network failure produces a partial report.
Yanked releases are never recommended as targets. A known newer non-yanked
release or package/manifest inconsistency requires clean program replacement.

Health and `sync-skill --list --json` remain read-only diagnostics. Missing or
inconsistent program/skill state points to clean replacement; `upgrade` never
runs `sync-skill --install`.

## JSON Purity And Version

All `--json` stdout is directly parseable with `json.loads`. Reinstall-required
apply exits 1; healthy no-op exits 0. The top-level envelope remains
`schema_version = "m36.upgrade.v0"`; `command: null` is inside action objects
and validates under the existing v0 output contract.
