# Agent Onboarding Guide: Life Index

> Purpose: install or upgrade Life Index by running `life-index bootstrap --json`
> and executing only the structured plan it returns.
>
> Authority: `CHARTER.md` owns invariants. `bootstrap-manifest.json` owns the
> current required authority documents.

This document is intentionally short. `bootstrap` diagnoses the local state and
prints the plan. The agent executes that plan; it does not rebuild a parallel
decision tree from prose.

## 1. Before You Start

Verify the host has:

- Python 3.11+
- Git
- enough disk space for the package and indexes
- network access unless the user is explicitly installing from an already
  available checkout

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

`bootstrap` is read-only. It does not install, migrate, rebuild indexes, sync
skills, modify `.venv`, or touch user journal content. Those actions happen
only if their exact commands appear in `safe_next_steps`.

If `life-index sync-skill` reports `delivered=false`, surface that warning. Do
not claim the agent playbook was delivered.

Do not wait for semantic indexing. Keyword readiness is enough for onboarding.
Report semantic status as informational when the commands expose it.

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
