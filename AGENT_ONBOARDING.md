# Agent Onboarding Guide: Life Index

> Purpose: install or upgrade Life Index by running `life-index bootstrap --json`
> and executing only the structured plan it returns.
>
> Authority: `CHARTER.md` owns invariants. `bootstrap-manifest.json` owns the
> current required authority documents.

This document is intentionally short: `bootstrap` diagnoses the local state and prints the plan; the agent executes that plan instead of rebuilding a parallel decision tree from prose.

## System Overview

Life Index is a deterministic toolset for a host agent, not a standalone human-facing intelligent app. CLI (life-index) is the deterministic tool layer installed in the host agent environment. It records and retrieves journals through explicit commands and has no built-in LLM.
Host agent (for example, Hermes) is the intelligence layer. It reads skills, plans work, orchestrates CLI tools, and synthesizes grounded answers. GUI is the optional UX layer over the same CLI-backed capabilities. It presents data and relays AI+ questions through /host-agent; the intelligence comes from your host agent, not from the GUI. Data stays separate from program code. Journals are your local data and remain independent from this repository.

## 1. Before You Start

Verify the host has Python 3.11+, Git, enough disk space for the package and indexes, and network access unless the user is explicitly installing from an already available checkout.
If a prerequisite is missing, stop and report the exact missing item.

## 2. Data Safety Rule

Never delete, overwrite, move, or "clean slate" the user's data directory.

The default data directory is `~/Documents/Life-Index`. Existing data there
stays physically separate from the code checkout. The phrases "fresh install",
"repair", "reinstall", or "upgrade" only authorize code/package work unless the
user explicitly asks for a data operation.

## 3. Get A Runnable Bootstrap Command

Use an existing Life Index command if one works:

```bash
life-index bootstrap --json
```

If you are already inside a Life Index checkout, use:

```bash
python -m tools bootstrap --json
```

If neither command exists yet, install clean code in a normal product checkout
without touching user data:

```bash
git clone https://github.com/DrDexter6000/life-index.git <target>/life-index
cd <target>/life-index
python -m venv .venv
.venv/bin/pip install -e .      # Windows: .venv\Scripts\pip install -e .
python -m tools bootstrap --json
```

For an existing confirmed checkout, refresh code before trusting a same-version
install. A matching package version does not prove the checkout is current. For
editable git installs, use `git pull --ff-only && pip install -e .`.

When evaluating an existing checkout, pass it to bootstrap instead of deciding
from prose:

```bash
life-index bootstrap --checkout-path <path> --checkout-origin host_managed --json
life-index bootstrap --checkout-path <path> --checkout-origin user_designated --json
life-index bootstrap --checkout-path <path> --json
```

Use `LIFE_INDEX_NO_NET=1` only when the environment is intentionally offline.
Then `freshness: "unknown"` is expected and not a failure.

## 4. Execute The Bootstrap Plan

Read the JSON in this order:

1. `needs_human`: if non-empty, relay every item to the user and stop. Do not
   adopt, delete, repair, or continue around it.
2. `execution_policy`: obey it literally. It means:
   - run `safe_next_steps` in order without additions;
   - on uncertainty or command failure, stop and report exact output;
   - recovery is code/package refresh only, then rerun bootstrap;
   - data is never deleted or overwritten.
3. `safe_next_steps`: run each command exactly as listed, using the active
   Life Index environment. Do not skip, reorder, or append commands.
4. `detected_state`: use it for reporting facts such as `data_dir`,
   `install_type`, `freshness`, and `update_available`.

### Mixed distribution conflict

If `detected_state.install_inventory.state` is `"conflict"`, or `needs_human` contains `INSTALL_DISTRIBUTION_CONFLICT`, stop: do not run `git pull`, `pip install -e .`, or delete a `site-packages/tools` directory. After the owner identifies a trusted checkout, run exactly:

```bash
ACTIVE_VENV_PYTHON -I TRUSTED_CHECKOUT/tools/upgrade/install_integrity.py recover --source-root TRUSTED_CHECKOUT --json
```

`ACTIVE_VENV_PYTHON` must be a supported standard virtual environment (`sys.prefix != sys.base_prefix`); otherwise relay the authority error without substituting a system interpreter or attempting a package operation. The report has `schema_version: "m37.install_integrity.v0"`; every failure has `error.recovery_strategy` (only pre-uninstall wheel preflight uses `retry`; authority, uninstall, orphan-shadow, target-install, and probe failures use `ask_user`).
Before any wheel build or pip operation, recovery canonicalizes RECORD ownership. An ownership conflict (`INSTALL_RECOVERY_OWNERSHIP_CONFLICT`) preserves every overlapped file and performs zero package operations.
Neutral verification is an internal `-I -S` child in `isolated_no_site_explicit_target` mode, so `.pth` finders cannot decide origin. For an explicit trusted editable source target it derives `SOURCE_SUFFIXES`, `BYTECODE_SUFFIXES`, and `EXTENSION_SUFFIXES`, then reports `tools{suffix}`, `tools/__init__{suffix}`, or `tools/__main__{suffix}` (for example `tools.pyc`, `tools/__init__.py`, or `tools.py`) as `INSTALL_RECOVERY_ORPHAN_SHADOW` without loading, executing, or deleting it.
The launcher validates the trusted source, stages a local wheel before any uninstall, uses only active-interpreter pip, performs a fresh isolated probe, and reruns `life-index bootstrap --json` only after success.

`bootstrap` is read-only. It does not install, migrate, rebuild indexes, sync
skills, modify `.venv`, or touch user journal content. Those actions happen
only if their exact commands appear in `safe_next_steps`.

If `life-index sync-skill` reports `delivered=false`, surface that warning. Do
not claim the agent playbook was delivered. For explicit first install into a
known host home, preview first, then apply:

```bash
life-index sync-skill --install --host-home <host-home> --dry-run --json
life-index sync-skill --install --host-home <host-home> --json
```

Bare `sync-skill` still does not create host directories. To inspect prior agent playbook delivery, run `life-index sync-skill --list --json`; to reverse it, run `life-index sync-skill --uninstall --host-home <host-home> --json`.

`sync-skill --uninstall` only removes agent skill artifacts under `<host-home>/skills/life-index` or `<host-home>/skills/<category>/life-index`; it never deletes journals, the data directory, source checkouts, packages, or host-home parent directories.

Retrieval is keyword (FTS5) + Entity Graph — there is no semantic/vector
indexing to wait for, so keyword readiness is all onboarding needs. The
`--semantic*` flags are accepted as deprecated no-ops for backward
compatibility (see WP-CLI-SEM-RM).

## 5. Completion Report

After all `safe_next_steps` finish, report concisely:

- status: success, stopped for `needs_human`, or failed at a specific command
- route
- install location
- data directory
- safe next steps executed
- health status, if `life-index health` was listed
- skill delivery status, if `life-index sync-skill` was listed
- non-blocking warnings

If a command fails, include its exact command, exit code, stdout, and stderr.

Do not write test entries in the real data directory. If a user asks for a smoke
test, use an explicit temporary `LIFE_INDEX_DATA_DIR` sandbox.
