# Hai TDD: WP-CLI-SYNC-SKILL-AUTOCONVERGE

Closes: #113
Branch: `codex/sync-skill-autoconverge`

## Target Behavior

When `life-index sync-skill --install` is run without `--host-skill-dir` or
`--host-home`, and the only discovered ambiguity is the canonical managed host
skill tree plus its own nested duplicate:

- select the canonical `skills/life-index` directory automatically;
- merge source `SKILL.md`, canonical custom triggers, and nested custom triggers;
- write the canonical playbook before deleting the nested duplicate;
- delete only a managed nested tree accepted by `_managed_nested_skill_tree_reason`;
- emit `HOST_SKILL_DIR_NESTED_DUPLICATE_AUTOCONVERGED`;
- continue to fail closed with `HOST_SKILL_DIR_AMBIGUOUS` for unrelated or unsafe
  candidates.

## RED

- **Test added**:
  `tests/unit/test_sync_skill.py::test_sync_skill_cli_install_auto_converges_managed_nested_duplicate`
- **Behavior asserted**: two-slot discovery (`skills/life-index` and
  `skills/life-index/life-index`) auto-selects canonical, syncs, removes managed
  nested duplicate, preserves canonical and nested custom triggers, and emits the
  autoconverge diagnostic.
- **Command**:
  `git worktree add --detach .codex-red-wp-113 HEAD^`
  `git diff --binary HEAD^ HEAD -- tests/unit/test_sync_skill.py | git -C .codex-red-wp-113 apply`
  `..\.venv\Scripts\python.exe -m pytest tests\unit\test_sync_skill.py -q -k "auto_converges_managed_nested_duplicate"`
- **Observed failure**:
  `FAILED tests/unit/test_sync_skill.py::test_sync_skill_cli_install_auto_converges_managed_nested_duplicate`
  with `AssertionError: assert 'skipped' == 'synced'`.
- **Failure is correct because**: the base implementation reported the two managed
  slots as ambiguous and skipped delivery instead of converging the canonical slot.
  This is the #113 missing behavior, not a test setup or import failure.

## GREEN

- **Minimal implementation**:
  The current branch already contains the minimal implementation in commit
  `79d17d7`:
  - `find_host_skill_dir` tries `_autoconverge_managed_nested_duplicate` only when
    more than one candidate is discovered.
  - `_autoconverge_managed_nested_duplicate` returns a canonical target only when
    there are exactly two matches and one is `<canonical>/life-index`.
  - `_managed_nested_skill_tree_reason` remains the safety guard; unmanaged top
    level content, symlinks, missing `SKILL.md`, and non-directories refuse
    autoconvergence.
  - `sync_skill_artifacts` reads canonical and nested `SKILL.md`, merges custom
    triggers, writes canonical first, then removes only the guarded nested tree.
  - CLI diagnostics from discovery are prepended to the final payload.
- **Command**:
  `.venv\Scripts\python.exe -m pytest tests\unit\test_sync_skill.py -q`
- **Observed pass**:
  `..................... [100%]`

## REFACTOR

- **Refactor done**: no
- **Change**: audit found the current branch already satisfies #113 with scoped
  code and tests; no additional production refactor was needed.
- **Command after refactor**:
  `.venv\Scripts\python.exe -m pytest tests -q --timeout=600`
- **Observed result**:
  full suite passed; skips were expected local/private fixture and platform skips.

## Additional Verification

- `gh issue view 113 --json number,title,state,url,body`
  - issue exists and is `OPEN`.
- `git status --short --branch`
  - branch: `codex/sync-skill-autoconverge...origin/codex/sync-skill-autoconverge`
  - initial worktree: clean.
- `.venv\Scripts\python.exe -m pytest -m blocker -q --timeout=120`
  - passed; 4 Unix-only skips.
- `.venv\Scripts\python.exe -m pytest -m contract -q --timeout=120`
  - passed; expected local/private fixture skips.
- `.venv\Scripts\python.exe -m pytest tests -q --timeout=600`
  - passed; expected local/private fixture and platform skips.
- `.venv\Scripts\python.exe -m mypy tools\ --ignore-missing-imports`
  - `Success: no issues found in 196 source files`.
- `git ls-files | git check-ignore --stdin`
  - no output.
- `.venv\Scripts\python.exe .github\scripts\check_public_surface_allowlist.py`
  - initially failed after adding this report because
    `reports/WP-CLI-SYNC-SKILL-AUTOCONVERGE-report.md` was a new public path.
  - fixed by adding that exact path to `.github/public-surface.allowlist`;
    rerun passed.

## Audit Notes

- Current branch already implemented the behavior before this report pass; no
  extra code changes were necessary.
- True ambiguity remains fail-closed:
  `tests/unit/test_sync_skill.py::test_sync_skill_cli_install_refuses_autoconverge_for_unmanaged_nested_content`
  verifies unmanaged nested top-level content returns `HOST_SKILL_DIR_AMBIGUOUS`
  and leaves the user note intact.
- Data safety: tests use temporary host homes only. No journal data directory was
  read, written, moved, or deleted.

## Next Behavior

Done. Await lead review after PR.
