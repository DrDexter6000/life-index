# WP-CLI-UPGRADE-UX Report

Date: 2026-07-03

Scope: ordinary PR follow-up for dogfood Run-3 UF-1/UF-2/UF-3. This change
does not alter journal data, search semantics, or release version metadata.

## Design

UF-1 promotes upgrade freshness to the session surface:

- `life-index health --json` now includes `data.upgrade_freshness` and a
  `checks[]` entry named `upgrade_freshness`.
- The signal is local-only: installed package version vs bootstrap manifest,
  and checkout HEAD vs the already-known upstream ref. It intentionally does
  not query PyPI; GitHub release/tag + `CHANGELOG.md` remain release authority.
- `SKILL.md` tells host agents to read this field at session start, then run
  the returned `suggested_refresh_step` and `sync-skill --install` when stale.

Chicken problem boundary: code in an old installed version cannot contain a new
detector. This PR reduces future recurrence by putting the rule in the always
loaded playbook plus the always runnable `health` surface. For already-old
installs, `bootstrap-manifest.json` and `CHANGELOG.md` remain the manual
authority anchors.

UF-2 makes explicit install repairable:

- `sync-skill --install --dry-run` previews without mutation.
- `sync-skill --install` converges the legacy double slot
  `skills/life-index/life-index` into canonical `skills/life-index`.
- Only a managed nested skill tree is removed: directory, non-symlink,
  containing `SKILL.md` and optional `references/` only. Anything else is
  reported in `data.dedupe.skipped`.
- Custom triggers from the nested `SKILL.md` are merged into the canonical
  playbook before removal.

UF-3 adds a one-line upgrade cue:

- Non-JSON `sync-skill` output includes `playbook unchanged; changelog:
  CHANGELOG.md` when the playbook body does not change.

Dogfood harness:

- `tests.nl_query_inproc.InprocHarness` exposes
  `measure_time_to_first_grounded_answer()` and `format_metric_line()`.

## RED -> GREEN

RED checks were run before implementation:

```text
python -m pytest tests/unit/test_main_cli.py::TestHealthCheck::test_health_exposes_upgrade_freshness_session_signal -q
FAILED: KeyError: 'upgrade_freshness'

python -m pytest tests/unit/test_sync_skill.py::test_sync_skill_cli_install_dry_run_reports_nested_duplicate_without_mutation tests/unit/test_sync_skill.py::test_sync_skill_install_collapses_nested_duplicate_preserving_custom_triggers -q
FAILED: --install --dry-run refused; nested duplicate not collapsed

python -m pytest tests/unit/test_sync_skill.py::test_sync_skill_reports_playbook_unchanged_with_changelog_pointer -q
FAILED: missing "playbook unchanged; changelog: CHANGELOG.md"

python -m pytest tests/unit/test_inproc_harness.py::TestInprocHarnessPerformance::test_time_to_first_grounded_answer_metric_is_printable -q
FAILED: InprocHarness has no measure_time_to_first_grounded_answer
```

GREEN focused checks after implementation:

```text
python -m pytest tests/unit/test_sync_skill.py -q
19 passed

python -m pytest tests/unit/test_main_cli.py tests/unit/test_onboarding_docs_safety.py -q
29 passed

python -m pytest tests/unit/test_inproc_harness.py -q
10 passed
```

## G2 Freshness Simulation

Command: simulated stale editable checkout by monkeypatching the session
freshness detector, then ran `health_check()`.

Relevant output:

```json
{
  "name": "upgrade_freshness",
  "status": "warning",
  "freshness": "update_available",
  "installed_version": "1.3.4",
  "manifest_version": "1.3.5",
  "update_available": "git-behind",
  "suggested_refresh_step": "git pull --ff-only && python -m pip install -e .",
  "changelog": "CHANGELOG.md",
  "git": {
    "freshness": "behind",
    "upstream": "origin/main",
    "behind_count": 2
  }
}
```

## G3 Nested Skill Simulation

Constructed `<host-home>/skills/life-index/life-index/SKILL.md`, then ran
dry-run and apply.

Dry-run excerpt:

```json
{
  "status": "dry_run",
  "delivered": false,
  "playbook_status": "would_install",
  "dedupe": {
    "status": "would_remove",
    "nested_dir": "<host-home>/skills/life-index/life-index"
  }
}
```

Apply excerpt:

```json
{
  "status": "installed",
  "delivered": true,
  "playbook_status": "installed",
  "dedupe": {
    "status": "removed",
    "removed": ["<host-home>/skills/life-index/life-index"]
  }
}
```

Post-check:

```text
canonical_exists=True
nested_exists=False
  - "/life-index nested"
```

## UF-3 Output Sample

```text
sync-skill: synced (delivered=true)
  SKILL.md
  references/WEATHER_FLOW.md
  playbook unchanged; changelog: CHANGELOG.md
```

## Dogfood Metric Sample

```text
time_to_first_grounded_answer_ms=48.56 status=GROUNDED result_count=1 query='重构'
```
