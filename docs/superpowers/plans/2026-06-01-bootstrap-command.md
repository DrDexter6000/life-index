# Bootstrap Command Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `life-index bootstrap --json`, a read-only state-detection command that replaces the fragile prose state machine in `AGENT_ONBOARDING.md` Step 0 with a deterministic CLI contract plus a short route table.

**Architecture:** Add a new `tools/bootstrap/` package with pure read-only functions for data-state detection, checkout assessment, route decision, and result assembly. The command reports machine state only; it never clones, deletes, repairs, migrates, writes user data, or mutates a checkout. `AGENT_ONBOARDING.md` remains the agent-facing workflow, but Step 0 delegates detection to the command while preserving repair/ambiguous-state handling.

**Tech Stack:** Python 3.11+, `pathlib`, `importlib.metadata`, `json`, existing `tools.migrate.scan_journals`, `argparse`, `pytest`, `tmp_path`.

---

## Revision Notes From Audit

This is the revised plan. It intentionally fixes the blockers found in the independent audit:

- H1 fixed: `AGENT_ONBOARDING.md` editing no longer depends on a placeholder old string. The executor must read the exact current section and replace that exact text.
- H2 fixed: `upgrade` always ends with `life-index health`; health failure remains the repair trigger.
- H3 fixed: a checkout is not adoptable merely because no dev signal is present. Adoption requires a positive origin: `host_managed` or `user_designated`.
- M1 fixed: `version_fresh` is renamed to `install_in_sync`; upstream freshness remains Step 0.1 authority-refresh responsibility.
- M2 fixed: dev-path tokens are weak hints unless combined with `.git`, cross-platform venv, or dev-tool signals.
- M3/D1 fixed: migration scanning uses `tools.migrate.scan_journals()` in process, not a subprocess with timeout swallowing.
- Public-contract fix: `docs/API.md` and command-dispatch contract tests are in scope because `bootstrap` is a new CLI command.
- Portability fix: commands are written for `python -m ...` and PowerShell-safe checks; no `head`, `tail`, or `python3` assumptions.

---

## File Map

| Action | Path | Responsibility |
|---|---|---|
| Create | `tools/bootstrap/__init__.py` | Read-only detection and routing functions: `detect_data_state`, `assess_checkout`, `decide_route`, `build_bootstrap_result` |
| Create | `tools/bootstrap/__main__.py` | CLI entry point for `life-index bootstrap` |
| Modify | `tools/__main__.py` | Add `bootstrap` to `cmd_map` and usage output |
| Create | `tests/unit/test_bootstrap.py` | Unit tests for pure functions and in-process migration handling |
| Create | `tests/contract/test_bootstrap_contract.py` | CLI JSON schema, route behavior, read-only guarantee |
| Modify | `tests/contract/test_main_cli_contract.py` | Include `bootstrap` in stable command-dispatch coverage |
| Modify | `docs/API.md` | Public CLI contract for `life-index bootstrap --json` |
| Modify | `AGENT_ONBOARDING.md` | Replace Step 0 state-machine prose with command-based detection while preserving repair trigger |

---

## Public Contract

`life-index bootstrap --json` returns this top-level schema:

```json
{
  "success": true,
  "schema_version": "m34.bootstrap.v0",
  "command": "bootstrap",
  "detected_state": {
    "has_user_data": false,
    "journal_count": 0,
    "data_dir": "C:/Users/example/Documents/Life-Index",
    "installed_version": "1.2.3",
    "manifest_version": "1.2.3",
    "install_in_sync": true,
    "migration_needed": 0,
    "migration_check_error": null,
    "checkout_assessment": null
  },
  "route": "fresh_install",
  "route_reason": "No existing journal data found",
  "needs_human": [],
  "safe_next_steps": []
}
```

Allowed route values:

- `fresh_install`
- `upgrade`

Allowed checkout verdict values:

- `adopt`
- `ambiguous`
- `dev_dir`
- `invalid`

Allowed `needs_human[].code` values for this command:

- `AMBIGUOUS_CHECKOUT`
- `DEV_DIR_FOUND`
- `INVALID_CHECKOUT`
- `MIGRATION_CHECK_FAILED`

No `refused` field is included. This command is read-only and does not perform action-taking, so a future-facing refusal ledger would be YAGNI.

---

## Task 1: Bootstrap Module Skeleton And Data Detection

**Files:**
- Create: `tools/bootstrap/__init__.py`
- Create: `tests/unit/test_bootstrap.py`

- [ ] **Step 1.1: Write failing tests for data detection**

Create `tests/unit/test_bootstrap.py`:

```python
"""Unit tests for Life Index bootstrap detection."""
from __future__ import annotations

from pathlib import Path

import pytest

import tools.bootstrap as _mod
from tools.bootstrap import detect_data_state


def _write_journal(path: Path, name: str = "life-index_2026-01-01_001.md") -> Path:
    path.mkdir(parents=True, exist_ok=True)
    journal = path / name
    journal.write_text("---\ntitle: t\ndate: 2026-01-01\n---\nbody", encoding="utf-8")
    return journal


class TestDetectDataState:
    def test_nonexistent_data_dir_has_no_user_data(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_mod, "_get_installed_version", lambda: None)
        monkeypatch.setattr(_mod, "_get_manifest_version", lambda: "1.2.3")
        state = detect_data_state(data_dir=str(tmp_path / "Life-Index"))
        assert state["has_user_data"] is False
        assert state["journal_count"] == 0
        assert state["migration_needed"] == 0
        assert state["migration_check_error"] is None

    def test_life_index_journals_are_counted(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_mod, "_get_installed_version", lambda: "1.2.3")
        monkeypatch.setattr(_mod, "_get_manifest_version", lambda: "1.2.3")
        data_dir = tmp_path / "Life-Index"
        _write_journal(data_dir / "Journals" / "2026" / "01")
        (data_dir / "Journals" / "2026" / "01" / "README.md").write_text("ignore", encoding="utf-8")

        state = detect_data_state(data_dir=str(data_dir))

        assert state["has_user_data"] is True
        assert state["journal_count"] == 1

    def test_required_keys_are_present(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_mod, "_get_installed_version", lambda: None)
        monkeypatch.setattr(_mod, "_get_manifest_version", lambda: "1.2.3")
        state = detect_data_state(data_dir=str(tmp_path / "Life-Index"))
        assert set(state) == {
            "has_user_data",
            "journal_count",
            "data_dir",
            "installed_version",
            "manifest_version",
            "install_in_sync",
            "migration_needed",
            "migration_check_error",
        }

    def test_install_in_sync_true_when_versions_match(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_mod, "_get_installed_version", lambda: "1.2.3")
        monkeypatch.setattr(_mod, "_get_manifest_version", lambda: "1.2.3")
        state = detect_data_state(data_dir=str(tmp_path / "Life-Index"))
        assert state["install_in_sync"] is True

    def test_install_in_sync_false_when_versions_differ(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_mod, "_get_installed_version", lambda: "1.2.2")
        monkeypatch.setattr(_mod, "_get_manifest_version", lambda: "1.2.3")
        state = detect_data_state(data_dir=str(tmp_path / "Life-Index"))
        assert state["install_in_sync"] is False

    def test_install_in_sync_none_when_installed_version_unknown(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_mod, "_get_installed_version", lambda: None)
        monkeypatch.setattr(_mod, "_get_manifest_version", lambda: "1.2.3")
        state = detect_data_state(data_dir=str(tmp_path / "Life-Index"))
        assert state["install_in_sync"] is None

    def test_migration_needed_uses_scan_journals_in_process(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_mod, "_get_installed_version", lambda: "1.2.3")
        monkeypatch.setattr(_mod, "_get_manifest_version", lambda: "1.2.3")
        monkeypatch.setattr(_mod, "scan_journals", lambda p: {"needs_migration": 4})
        data_dir = tmp_path / "Life-Index"
        _write_journal(data_dir / "Journals" / "2026" / "01")

        state = detect_data_state(data_dir=str(data_dir))

        assert state["migration_needed"] == 4
        assert state["migration_check_error"] is None

    def test_migration_scan_failure_is_not_reported_as_zero(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_mod, "_get_installed_version", lambda: "1.2.3")
        monkeypatch.setattr(_mod, "_get_manifest_version", lambda: "1.2.3")

        def boom(path):
            raise RuntimeError("scan failed")

        monkeypatch.setattr(_mod, "scan_journals", boom)
        data_dir = tmp_path / "Life-Index"
        _write_journal(data_dir / "Journals" / "2026" / "01")

        state = detect_data_state(data_dir=str(data_dir))

        assert state["migration_needed"] is None
        assert "scan failed" in state["migration_check_error"]
```

- [ ] **Step 1.2: Run tests and confirm RED**

Run:

```powershell
python -m pytest tests/unit/test_bootstrap.py::TestDetectDataState -v
```

Expected: fails with `ModuleNotFoundError` or `ImportError` because `tools.bootstrap` does not exist.

- [ ] **Step 1.3: Implement `tools/bootstrap/__init__.py` detection functions**

Create `tools/bootstrap/__init__.py`:

```python
"""Life Index bootstrap detection.

Read-only. This module never writes user data, checkouts, venvs, indexes, or config.
"""
from __future__ import annotations

import json
import os
import sys
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version
from pathlib import Path
from typing import Any, Literal

from tools.migrate import scan_journals

BOOTSTRAP_SCHEMA_VERSION = "m34.bootstrap.v0"

CheckoutOrigin = Literal["discovered", "host_managed", "user_designated"]

_DEV_PATH_TOKENS_LOWER = frozenset({"projects", "workspace", "repos"})
_DEV_TOOLS = frozenset({"pytest", "black", "mypy", "flake8", "isort", "playwright"})


def _resolve_data_dir(data_dir: str | None = None) -> Path:
    if data_dir:
        return Path(data_dir)
    return Path(
        os.environ.get("LIFE_INDEX_DATA_DIR", str(Path.home() / "Documents" / "Life-Index"))
    )


def _count_journals(data_dir: Path) -> int:
    journals_dir = data_dir / "Journals"
    if not journals_dir.exists():
        return 0
    return len(list(journals_dir.rglob("life-index_*.md")))


def _get_installed_version() -> str | None:
    try:
        return _pkg_version("life-index")
    except PackageNotFoundError:
        return None


def _get_manifest_version() -> str | None:
    manifest = Path(__file__).resolve().parent.parent.parent / "bootstrap-manifest.json"
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
    except Exception:
        return None
    version = payload.get("repo_version")
    return version if isinstance(version, str) else None


def _check_migration(data_dir: Path) -> tuple[int | None, str | None]:
    journals_dir = data_dir / "Journals"
    if not journals_dir.exists():
        return 0, None
    try:
        result = scan_journals(journals_dir)
    except Exception as exc:
        return None, str(exc)
    needs = result.get("needs_migration", 0)
    return int(needs), None


def detect_data_state(data_dir: str | None = None) -> dict[str, Any]:
    """Probe data directory and installed-version state. Read-only."""
    ddir = _resolve_data_dir(data_dir)
    journal_count = _count_journals(ddir)
    installed = _get_installed_version()
    manifest = _get_manifest_version()
    install_in_sync: bool | None = None
    if installed is not None and manifest is not None:
        install_in_sync = installed == manifest
    migration_needed, migration_error = _check_migration(ddir)
    return {
        "has_user_data": journal_count > 0,
        "journal_count": journal_count,
        "data_dir": str(ddir),
        "installed_version": installed,
        "manifest_version": manifest,
        "install_in_sync": install_in_sync,
        "migration_needed": migration_needed,
        "migration_check_error": migration_error,
    }


def assess_checkout(path: Path, checkout_origin: CheckoutOrigin = "discovered") -> dict[str, Any]:
    """Placeholder implemented in Task 2."""
    raise NotImplementedError


def decide_route(
    data_state: dict[str, Any],
    checkout_assessment: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Placeholder implemented in Task 3."""
    raise NotImplementedError


def build_bootstrap_result(
    data_dir: str | None = None,
    checkout_path: str | None = None,
    checkout_origin: CheckoutOrigin = "discovered",
) -> dict[str, Any]:
    """Placeholder implemented in Task 4."""
    raise NotImplementedError
```

- [ ] **Step 1.4: Run detection tests and confirm GREEN**

Run:

```powershell
python -m pytest tests/unit/test_bootstrap.py::TestDetectDataState -v
```

Expected: all tests in `TestDetectDataState` pass.

- [ ] **Step 1.5: Commit Task 1**

Run:

```powershell
git add tools/bootstrap/__init__.py tests/unit/test_bootstrap.py
git commit -m "feat: add bootstrap data detection"
```

---

## Task 2: Checkout Assessment With Positive Adoption Gate

**Files:**
- Modify: `tools/bootstrap/__init__.py`
- Modify: `tests/unit/test_bootstrap.py`

- [ ] **Step 2.1: Add failing checkout assessment tests**

Append to `tests/unit/test_bootstrap.py`:

```python
from tools.bootstrap import assess_checkout


def _make_checkout(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    for name in ("SKILL.md", "pyproject.toml", "bootstrap-manifest.json"):
        (path / name).write_text("x", encoding="utf-8")
    return path


class TestAssessCheckout:
    def test_missing_required_files_is_invalid(self, tmp_path):
        checkout = tmp_path / "skills" / "life-index"
        checkout.mkdir(parents=True)
        (checkout / "SKILL.md").write_text("# Life Index", encoding="utf-8")

        result = assess_checkout(checkout)

        assert result["verdict"] == "invalid"
        assert result["safe_to_adopt"] is False
        assert "pyproject.toml" in result["reason"]

    def test_discovered_clean_checkout_is_ambiguous_not_adopt(self, tmp_path):
        checkout = _make_checkout(tmp_path / "Downloads" / "life-index")

        result = assess_checkout(checkout, checkout_origin="discovered")

        assert result["verdict"] == "ambiguous"
        assert result["safe_to_adopt"] is False
        assert result["origin"] == "discovered"

    def test_host_managed_clean_checkout_is_adoptable(self, tmp_path):
        checkout = _make_checkout(tmp_path / ".agent" / "skills" / "life-index")

        result = assess_checkout(checkout, checkout_origin="host_managed")

        assert result["verdict"] == "adopt"
        assert result["safe_to_adopt"] is True

    def test_user_designated_clean_checkout_is_adoptable(self, tmp_path):
        checkout = _make_checkout(tmp_path / "custom" / "life-index")

        result = assess_checkout(checkout, checkout_origin="user_designated")

        assert result["verdict"] == "adopt"
        assert result["safe_to_adopt"] is True

    def test_cross_platform_venv_is_dev_dir(self, tmp_path):
        checkout = _make_checkout(tmp_path / "skills" / "life-index")
        if sys.platform == "win32":
            (checkout / ".venv" / "bin").mkdir(parents=True)
            (checkout / ".venv" / "bin" / "python").write_text("", encoding="utf-8")
            expected_signal = "linux_venv_from_windows"
        else:
            (checkout / ".venv" / "Scripts").mkdir(parents=True)
            (checkout / ".venv" / "Scripts" / "python.exe").write_text("", encoding="utf-8")
            expected_signal = "windows_venv_from_non_windows"

        result = assess_checkout(checkout, checkout_origin="host_managed")

        assert result["verdict"] == "dev_dir"
        assert result["safe_to_adopt"] is False
        assert expected_signal in result["signals"]

    def test_projects_path_token_alone_is_only_a_hint(self, tmp_path):
        checkout = _make_checkout(tmp_path / "Projects" / "life-index")

        result = assess_checkout(checkout, checkout_origin="host_managed")

        assert result["verdict"] == "adopt"
        assert result["safe_to_adopt"] is True
        assert "dev_path_hint" in result["signals"]

    def test_projects_path_with_git_is_dev_dir(self, tmp_path):
        checkout = _make_checkout(tmp_path / "Projects" / "life-index")
        (checkout / ".git").mkdir()

        result = assess_checkout(checkout, checkout_origin="host_managed")

        assert result["verdict"] == "dev_dir"
        assert result["safe_to_adopt"] is False
        assert "dev_path_with_git" in result["signals"]

    def test_dev_tool_in_venv_is_dev_dir(self, tmp_path):
        checkout = _make_checkout(tmp_path / "skills" / "life-index")
        bin_dir = checkout / ".venv" / ("Scripts" if sys.platform == "win32" else "bin")
        bin_dir.mkdir(parents=True)
        tool = "pytest.exe" if sys.platform == "win32" else "pytest"
        (bin_dir / tool).write_text("", encoding="utf-8")

        result = assess_checkout(checkout, checkout_origin="host_managed")

        assert result["verdict"] == "dev_dir"
        assert result["safe_to_adopt"] is False
        assert "dev_package_pytest" in result["signals"]
```

- [ ] **Step 2.2: Run checkout tests and confirm RED**

Run:

```powershell
python -m pytest tests/unit/test_bootstrap.py::TestAssessCheckout -v
```

Expected: tests fail with `NotImplementedError`.

- [ ] **Step 2.3: Implement `assess_checkout`**

Replace the placeholder `assess_checkout` in `tools/bootstrap/__init__.py` with:

```python
def assess_checkout(path: Path, checkout_origin: CheckoutOrigin = "discovered") -> dict[str, Any]:
    """Assess whether a checkout can be adopted as install target.

    Adoption requires positive origin: host-managed or user-designated.
    A random discovered checkout is ambiguous even when it looks clean.
    """
    signals: list[str] = []
    strong_dev_signals: list[str] = []

    required = ["SKILL.md", "pyproject.toml", "bootstrap-manifest.json"]
    missing = [name for name in required if not (path / name).exists()]

    if (path / ".venv" / "Scripts" / "python.exe").exists() and sys.platform != "win32":
        signals.append("windows_venv_from_non_windows")
        strong_dev_signals.append("windows_venv_from_non_windows")
    if (path / ".venv" / "bin" / "python").exists() and sys.platform == "win32":
        signals.append("linux_venv_from_windows")
        strong_dev_signals.append("linux_venv_from_windows")

    lower_parts = {part.lower() for part in path.parts}
    has_dev_path_hint = bool(lower_parts & _DEV_PATH_TOKENS_LOWER)
    if has_dev_path_hint:
        signals.append("dev_path_hint")
        if (path / ".git").exists():
            signals.append("dev_path_with_git")
            strong_dev_signals.append("dev_path_with_git")

    bin_dir = path / ".venv" / ("Scripts" if sys.platform == "win32" else "bin")
    for tool in sorted(_DEV_TOOLS):
        if (bin_dir / tool).exists() or (bin_dir / f"{tool}.exe").exists():
            signal = f"dev_package_{tool}"
            signals.append(signal)
            strong_dev_signals.append(signal)
            break

    if missing:
        return {
            "path": str(path),
            "origin": checkout_origin,
            "verdict": "invalid",
            "signals": signals,
            "safe_to_adopt": False,
            "reason": f"Missing required files: {', '.join(missing)}",
        }

    if strong_dev_signals:
        return {
            "path": str(path),
            "origin": checkout_origin,
            "verdict": "dev_dir",
            "signals": signals,
            "safe_to_adopt": False,
            "reason": f"Development directory signals: {', '.join(strong_dev_signals)}",
        }

    if checkout_origin not in ("host_managed", "user_designated"):
        return {
            "path": str(path),
            "origin": checkout_origin,
            "verdict": "ambiguous",
            "signals": signals,
            "safe_to_adopt": False,
            "reason": (
                "Checkout looks structurally complete, but it was only discovered; "
                "adoption requires a host-managed or user-designated target."
            ),
        }

    return {
        "path": str(path),
        "origin": checkout_origin,
        "verdict": "adopt",
        "signals": signals,
        "safe_to_adopt": True,
        "reason": "Checkout is complete and has positive adoption origin.",
    }
```

- [ ] **Step 2.4: Run checkout tests and confirm GREEN**

Run:

```powershell
python -m pytest tests/unit/test_bootstrap.py::TestAssessCheckout -v
```

Expected: all checkout tests pass.

- [ ] **Step 2.5: Run all bootstrap unit tests**

Run:

```powershell
python -m pytest tests/unit/test_bootstrap.py -v
```

Expected: all tests pass.

- [ ] **Step 2.6: Commit Task 2**

Run:

```powershell
git add tools/bootstrap/__init__.py tests/unit/test_bootstrap.py
git commit -m "feat: add bootstrap checkout assessment"
```

---

## Task 3: Route Decision With Repair Trigger Preservation

**Files:**
- Modify: `tools/bootstrap/__init__.py`
- Modify: `tests/unit/test_bootstrap.py`

- [ ] **Step 3.1: Add failing route decision tests**

Append to `tests/unit/test_bootstrap.py`:

```python
from tools.bootstrap import decide_route


def _state(
    has_data: bool = False,
    journal_count: int = 0,
    install_in_sync: bool | None = True,
    migration_needed: int | None = 0,
    migration_check_error: str | None = None,
) -> dict:
    return {
        "has_user_data": has_data,
        "journal_count": journal_count,
        "data_dir": "/tmp/Life-Index",
        "installed_version": "1.2.3",
        "manifest_version": "1.2.3",
        "install_in_sync": install_in_sync,
        "migration_needed": migration_needed,
        "migration_check_error": migration_check_error,
    }


def _checkout(verdict: str, safe: bool, reason: str = "reason") -> dict:
    return {
        "path": "/tmp/checkout",
        "origin": "discovered",
        "verdict": verdict,
        "signals": [],
        "safe_to_adopt": safe,
        "reason": reason,
    }


class TestDecideRoute:
    def test_no_data_routes_fresh_install(self):
        result = decide_route(_state())
        assert result["route"] == "fresh_install"
        assert result["safe_next_steps"] == []
        assert result["needs_human"] == []

    def test_existing_data_routes_upgrade(self):
        result = decide_route(_state(has_data=True, journal_count=8))
        assert result["route"] == "upgrade"
        assert "8" in result["route_reason"]

    def test_upgrade_always_appends_health_last(self):
        result = decide_route(
            _state(has_data=True, journal_count=8, install_in_sync=False, migration_needed=2)
        )
        assert "pip install -e ." in result["safe_next_steps"][0]
        assert "life-index migrate --dry-run" in result["safe_next_steps"][1]
        assert "life-index migrate --apply" in result["safe_next_steps"][2]
        assert result["safe_next_steps"][-1] == "life-index health"

    def test_migration_check_failure_requires_human_and_manual_dry_run(self):
        result = decide_route(
            _state(
                has_data=True,
                journal_count=8,
                migration_needed=None,
                migration_check_error="scan failed",
            )
        )
        assert any(item["code"] == "MIGRATION_CHECK_FAILED" for item in result["needs_human"])
        assert any("life-index migrate --dry-run" in step for step in result["safe_next_steps"])
        assert result["safe_next_steps"][-1] == "life-index health"

    def test_ambiguous_checkout_requires_human(self):
        result = decide_route(_state(), _checkout("ambiguous", False))
        assert any(item["code"] == "AMBIGUOUS_CHECKOUT" for item in result["needs_human"])

    def test_dev_dir_checkout_requires_human(self):
        result = decide_route(_state(), _checkout("dev_dir", False))
        assert any(item["code"] == "DEV_DIR_FOUND" for item in result["needs_human"])

    def test_invalid_checkout_requires_human(self):
        result = decide_route(_state(), _checkout("invalid", False))
        assert any(item["code"] == "INVALID_CHECKOUT" for item in result["needs_human"])

    def test_adoptable_checkout_does_not_require_human(self):
        result = decide_route(_state(), _checkout("adopt", True))
        assert result["needs_human"] == []

    def test_result_has_public_contract_keys(self):
        result = decide_route(_state())
        assert set(result) == {"route", "route_reason", "needs_human", "safe_next_steps"}
```

- [ ] **Step 3.2: Run route tests and confirm RED**

Run:

```powershell
python -m pytest tests/unit/test_bootstrap.py::TestDecideRoute -v
```

Expected: fails with `NotImplementedError`.

- [ ] **Step 3.3: Implement `decide_route`**

Replace the placeholder `decide_route` in `tools/bootstrap/__init__.py` with:

```python
def decide_route(
    data_state: dict[str, Any],
    checkout_assessment: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Determine onboarding route from detected state. Pure logic; no I/O."""
    needs_human: list[dict[str, str]] = []
    safe_next_steps: list[str] = []

    if checkout_assessment is not None and not checkout_assessment["safe_to_adopt"]:
        verdict = checkout_assessment["verdict"]
        if verdict == "ambiguous":
            needs_human.append({
                "code": "AMBIGUOUS_CHECKOUT",
                "message": (
                    f"Checkout at {checkout_assessment['path']} is structurally complete "
                    f"but not positively authorized for adoption: {checkout_assessment['reason']}"
                ),
                "suggested_action": (
                    "Use a host-managed skill directory, pass --checkout-origin user_designated "
                    "only after the user explicitly designates this path, or clone a fresh copy."
                ),
            })
        elif verdict == "dev_dir":
            needs_human.append({
                "code": "DEV_DIR_FOUND",
                "message": (
                    f"Checkout at {checkout_assessment['path']} appears to be a development "
                    f"directory: {checkout_assessment['reason']}"
                ),
                "suggested_action": "Do not adopt or repair it; use a host-managed skill directory.",
            })
        else:
            needs_human.append({
                "code": "INVALID_CHECKOUT",
                "message": (
                    f"Checkout at {checkout_assessment['path']} is incomplete: "
                    f"{checkout_assessment['reason']}"
                ),
                "suggested_action": "Delete the partial clone only if it is inside the agent-managed install target, then clone fresh.",
            })

    if data_state["has_user_data"]:
        route = "upgrade"
        route_reason = f"Found {data_state['journal_count']} journal(s) in {data_state['data_dir']}"
    else:
        route = "fresh_install"
        route_reason = "No existing journal data found"

    if data_state.get("install_in_sync") is False:
        safe_next_steps.append("pip install -e .")

    migration = data_state.get("migration_needed")
    if migration is None:
        needs_human.append({
            "code": "MIGRATION_CHECK_FAILED",
            "message": f"Migration check did not complete: {data_state.get('migration_check_error')}",
            "suggested_action": "Run life-index migrate --dry-run manually and inspect the output before proceeding.",
        })
        safe_next_steps.append("life-index migrate --dry-run")
    elif migration > 0:
        safe_next_steps.append(f"life-index migrate --dry-run  # {migration} file(s) need migration")
        safe_next_steps.append("life-index migrate --apply")

    if route == "upgrade":
        safe_next_steps.append("life-index health")

    return {
        "route": route,
        "route_reason": route_reason,
        "needs_human": needs_human,
        "safe_next_steps": safe_next_steps,
    }
```

- [ ] **Step 3.4: Run route tests and confirm GREEN**

Run:

```powershell
python -m pytest tests/unit/test_bootstrap.py::TestDecideRoute -v
```

Expected: all route tests pass.

- [ ] **Step 3.5: Run all bootstrap unit tests**

Run:

```powershell
python -m pytest tests/unit/test_bootstrap.py -v
```

Expected: all bootstrap unit tests pass.

- [ ] **Step 3.6: Commit Task 3**

Run:

```powershell
git add tools/bootstrap/__init__.py tests/unit/test_bootstrap.py
git commit -m "feat: add bootstrap route decision"
```

---

## Task 4: CLI Wiring And Result Assembly

**Files:**
- Modify: `tools/bootstrap/__init__.py`
- Create: `tools/bootstrap/__main__.py`
- Modify: `tools/__main__.py`
- Modify: `tests/unit/test_bootstrap.py`

- [ ] **Step 4.1: Add failing `build_bootstrap_result` tests**

Append to `tests/unit/test_bootstrap.py`:

```python
from tools.bootstrap import BOOTSTRAP_SCHEMA_VERSION, build_bootstrap_result


class TestBuildBootstrapResult:
    def test_result_structure(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_mod, "_get_installed_version", lambda: "1.2.3")
        monkeypatch.setattr(_mod, "_get_manifest_version", lambda: "1.2.3")
        result = build_bootstrap_result(data_dir=str(tmp_path / "Life-Index"))
        assert set(result) == {
            "success",
            "schema_version",
            "command",
            "detected_state",
            "route",
            "route_reason",
            "needs_human",
            "safe_next_steps",
        }
        assert result["success"] is True
        assert result["schema_version"] == BOOTSTRAP_SCHEMA_VERSION
        assert result["command"] == "bootstrap"

    def test_checkout_origin_is_passed_to_assessment(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_mod, "_get_installed_version", lambda: "1.2.3")
        monkeypatch.setattr(_mod, "_get_manifest_version", lambda: "1.2.3")
        checkout = _make_checkout(tmp_path / ".agent" / "skills" / "life-index")
        result = build_bootstrap_result(
            data_dir=str(tmp_path / "Life-Index"),
            checkout_path=str(checkout),
            checkout_origin="host_managed",
        )
        assessment = result["detected_state"]["checkout_assessment"]
        assert assessment["origin"] == "host_managed"
        assert assessment["verdict"] == "adopt"
```

- [ ] **Step 4.2: Run result tests and confirm RED**

Run:

```powershell
python -m pytest tests/unit/test_bootstrap.py::TestBuildBootstrapResult -v
```

Expected: fails with `NotImplementedError`.

- [ ] **Step 4.3: Implement `build_bootstrap_result`**

Replace the placeholder `build_bootstrap_result` in `tools/bootstrap/__init__.py` with:

```python
def build_bootstrap_result(
    data_dir: str | None = None,
    checkout_path: str | None = None,
    checkout_origin: CheckoutOrigin = "discovered",
) -> dict[str, Any]:
    """Build the full bootstrap detection envelope. Read-only."""
    data_state = detect_data_state(data_dir)
    checkout_assessment = (
        assess_checkout(Path(checkout_path), checkout_origin=checkout_origin)
        if checkout_path
        else None
    )
    route_result = decide_route(data_state, checkout_assessment)
    return {
        "success": True,
        "schema_version": BOOTSTRAP_SCHEMA_VERSION,
        "command": "bootstrap",
        "detected_state": {
            **data_state,
            "checkout_assessment": checkout_assessment,
        },
        "route": route_result["route"],
        "route_reason": route_result["route_reason"],
        "needs_human": route_result["needs_human"],
        "safe_next_steps": route_result["safe_next_steps"],
    }
```

- [ ] **Step 4.4: Create `tools/bootstrap/__main__.py`**

Create `tools/bootstrap/__main__.py`:

```python
"""CLI entry point for life-index bootstrap."""
from __future__ import annotations

import argparse
import json
import os
import sys

from . import build_bootstrap_result


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="life-index bootstrap",
        description=(
            "Detect Life Index install/data state and determine the onboarding route. "
            "Read-only: makes no changes to data, venv, or checkouts."
        ),
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    parser.add_argument(
        "--data-dir",
        default=None,
        help="Override Life Index data directory. Also sets LIFE_INDEX_DATA_DIR for this process.",
    )
    parser.add_argument(
        "--checkout-path",
        default=None,
        help="Optional Life Index checkout path to assess.",
    )
    parser.add_argument(
        "--checkout-origin",
        choices=("discovered", "host_managed", "user_designated"),
        default="discovered",
        help=(
            "Authority for --checkout-path. Use host_managed only for an agent platform's "
            "official skill directory; use user_designated only after explicit user selection."
        ),
    )
    args = parser.parse_args()

    if args.data_dir:
        os.environ["LIFE_INDEX_DATA_DIR"] = args.data_dir

    result = build_bootstrap_result(
        data_dir=args.data_dir,
        checkout_path=args.checkout_path,
        checkout_origin=args.checkout_origin,
    )

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0)

    print(f"Route:  {result['route']}")
    print(f"Reason: {result['route_reason']}")
    if result["needs_human"]:
        print("\nNeeds human input:")
        for item in result["needs_human"]:
            print(f"  [{item['code']}] {item['message']}")
            print(f"  Action: {item['suggested_action']}")
    if result["safe_next_steps"]:
        print("\nSafe next steps:")
        for step in result["safe_next_steps"]:
            print(f"  {step}")
    sys.exit(0)
```

- [ ] **Step 4.5: Register `bootstrap` in `tools/__main__.py`**

In `tools/__main__.py`, add this line to the first usage block near the existing `maintenance` line:

```python
    bootstrap    Detect install/data state and route onboarding (read-only)
```

Add this entry to `cmd_map` near existing read-only diagnostic commands:

```python
        "bootstrap": "tools.bootstrap.__main__",
```

Add this line to `print_usage()` near the existing `maintenance` line:

```python
    print("  bootstrap  Detect install/data state and route onboarding (read-only)")
```

- [ ] **Step 4.6: Run unit tests and smoke checks**

Run:

```powershell
python -m pytest tests/unit/test_bootstrap.py -v
python -m tools bootstrap --json | python -m json.tool
python -m tools bootstrap
```

Expected:

- unit tests pass;
- JSON command exits `0` and prints valid JSON;
- text command prints `Route:` and `Reason:`.

- [ ] **Step 4.7: Commit Task 4**

Run:

```powershell
git add tools/bootstrap/__init__.py tools/bootstrap/__main__.py tools/__main__.py tests/unit/test_bootstrap.py
git commit -m "feat: wire bootstrap command"
```

---

## Task 5: Contract Tests And Read-Only Guarantee

**Files:**
- Create: `tests/contract/test_bootstrap_contract.py`
- Modify: `tests/contract/test_main_cli_contract.py`

- [ ] **Step 5.1: Create CLI contract tests**

Create `tests/contract/test_bootstrap_contract.py`:

```python
"""Contract tests for life-index bootstrap."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _run_bootstrap(tmp_path: Path, extra_args: list[str] | None = None) -> dict:
    env = os.environ.copy()
    env["LIFE_INDEX_DATA_DIR"] = str(tmp_path / "Life-Index")
    cmd = [sys.executable, "-m", "tools", "bootstrap", "--json"] + (extra_args or [])
    result = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=60)
    assert result.returncode == 0, f"stdout={result.stdout!r} stderr={result.stderr!r}"
    return json.loads(result.stdout)


def _make_journal(data_dir: Path, date: str = "2026-01-01") -> Path:
    jdir = data_dir / "Journals" / date[:4] / date[5:7]
    jdir.mkdir(parents=True, exist_ok=True)
    journal = jdir / f"life-index_{date}_001.md"
    journal.write_text(
        f"---\ntitle: t\ndate: {date}\ntopic: [life]\n---\nbody",
        encoding="utf-8",
    )
    return journal


def _snapshot(root: Path) -> dict[str, str]:
    if not root.exists():
        return {}
    return {
        str(path.relative_to(root)): path.read_text(encoding="utf-8")
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


class TestBootstrapJsonContract:
    def test_required_top_level_keys_present(self, tmp_path):
        payload = _run_bootstrap(tmp_path)
        assert set(payload) == {
            "success",
            "schema_version",
            "command",
            "detected_state",
            "route",
            "route_reason",
            "needs_human",
            "safe_next_steps",
        }

    def test_schema_version_uses_project_family(self, tmp_path):
        payload = _run_bootstrap(tmp_path)
        assert payload["schema_version"] == "m34.bootstrap.v0"

    def test_detected_state_keys_present(self, tmp_path):
        payload = _run_bootstrap(tmp_path)
        assert set(payload["detected_state"]) == {
            "has_user_data",
            "journal_count",
            "data_dir",
            "installed_version",
            "manifest_version",
            "install_in_sync",
            "migration_needed",
            "migration_check_error",
            "checkout_assessment",
        }

    def test_empty_data_dir_routes_fresh_install(self, tmp_path):
        payload = _run_bootstrap(tmp_path)
        assert payload["route"] == "fresh_install"
        assert payload["detected_state"]["has_user_data"] is False

    def test_existing_journal_routes_upgrade_and_suggests_health(self, tmp_path):
        data_dir = tmp_path / "Life-Index"
        _make_journal(data_dir)
        payload = _run_bootstrap(tmp_path)
        assert payload["route"] == "upgrade"
        assert payload["detected_state"]["journal_count"] == 1
        assert payload["safe_next_steps"][-1] == "life-index health"

    def test_discovered_checkout_is_ambiguous(self, tmp_path):
        checkout = tmp_path / "Downloads" / "life-index"
        checkout.mkdir(parents=True)
        for name in ("SKILL.md", "pyproject.toml", "bootstrap-manifest.json"):
            (checkout / name).write_text("x", encoding="utf-8")
        payload = _run_bootstrap(tmp_path, ["--checkout-path", str(checkout)])
        assessment = payload["detected_state"]["checkout_assessment"]
        assert assessment["verdict"] == "ambiguous"
        assert assessment["safe_to_adopt"] is False
        assert any(item["code"] == "AMBIGUOUS_CHECKOUT" for item in payload["needs_human"])

    def test_user_designated_checkout_is_adoptable(self, tmp_path):
        checkout = tmp_path / "chosen" / "life-index"
        checkout.mkdir(parents=True)
        for name in ("SKILL.md", "pyproject.toml", "bootstrap-manifest.json"):
            (checkout / name).write_text("x", encoding="utf-8")
        payload = _run_bootstrap(
            tmp_path,
            ["--checkout-path", str(checkout), "--checkout-origin", "user_designated"],
        )
        assessment = payload["detected_state"]["checkout_assessment"]
        assert assessment["verdict"] == "adopt"
        assert assessment["safe_to_adopt"] is True

    def test_bootstrap_does_not_modify_data_dir_files(self, tmp_path):
        data_dir = tmp_path / "Life-Index"
        _make_journal(data_dir)
        before = _snapshot(data_dir)
        payload = _run_bootstrap(tmp_path)
        after = _snapshot(data_dir)
        assert payload["success"] is True
        assert after == before
```

- [ ] **Step 5.2: Add command-dispatch coverage**

Open `tests/contract/test_main_cli_contract.py`, find the list or parametrized set of stable top-level commands, and add:

```python
"bootstrap"
```

If the file asserts usage text, add:

```python
"bootstrap"
```

to the expected usage-command list. Keep the existing style in that file.

- [ ] **Step 5.3: Run contract tests**

Run:

```powershell
python -m pytest tests/contract/test_bootstrap_contract.py tests/contract/test_main_cli_contract.py -v
```

Expected: all selected contract tests pass.

- [ ] **Step 5.4: Commit Task 5**

Run:

```powershell
git add tests/contract/test_bootstrap_contract.py tests/contract/test_main_cli_contract.py
git commit -m "test: add bootstrap CLI contract tests"
```

---

## Task 6: Public API Documentation

**Files:**
- Modify: `docs/API.md`

- [ ] **Step 6.1: Add API documentation for bootstrap**

Add this section near the existing diagnostic/maintenance command documentation in `docs/API.md`:

````markdown
## bootstrap

### 端点

```bash
life-index bootstrap --json
python -m tools bootstrap --json
```

### 语义

`bootstrap` 是只读安装/数据状态检测命令，用于 Agent onboarding 前置判断。它不 clone、不 install、不 migrate、不 repair、不写入用户数据、不修改 `.venv`，也不删除任何 checkout。

上游新鲜度仍由 onboarding Step 0.1 的 `bootstrap-manifest.json` authority refresh 负责；`bootstrap` 只报告本机安装包版本是否与当前 checkout manifest 版本一致，字段名为 `install_in_sync`。

### 参数

| 参数 | 必填 | 说明 |
|---|---:|---|
| `--json` | ✅ | 输出 JSON contract |
| `--data-dir <path>` | ❌ | 覆盖 Life Index 数据目录；仅影响本次检测 |
| `--checkout-path <path>` | ❌ | 要评估的本地 checkout 路径 |
| `--checkout-origin discovered\|host_managed\|user_designated` | ❌ | `--checkout-path` 的来源；默认 `discovered` |

### checkout origin 规则

`safe_to_adopt: true` 只会在以下条件同时满足时出现：

1. checkout 含 `SKILL.md`、`pyproject.toml`、`bootstrap-manifest.json`;
2. 未发现强 development-directory 信号；
3. `--checkout-origin` 是 `host_managed` 或 `user_designated`。

随机发现的 checkout 即使结构完整，也返回 `verdict: "ambiguous"`，并通过 `needs_human` 要求 Agent 让用户或 host platform 明确安装目标。

### 返回值

```json
{
  "success": true,
  "schema_version": "m34.bootstrap.v0",
  "command": "bootstrap",
  "detected_state": {
    "has_user_data": true,
    "journal_count": 12,
    "data_dir": "C:/Users/example/Documents/Life-Index",
    "installed_version": "1.2.3",
    "manifest_version": "1.2.3",
    "install_in_sync": true,
    "migration_needed": 0,
    "migration_check_error": null,
    "checkout_assessment": null
  },
  "route": "upgrade",
  "route_reason": "Found 12 journal(s) in C:/Users/example/Documents/Life-Index",
  "needs_human": [],
  "safe_next_steps": ["life-index health"]
}
```

### route 值

| route | 说明 |
|---|---|
| `fresh_install` | 未发现既有 journal 数据 |
| `upgrade` | 已发现既有 journal 数据 |

### needs_human codes

| code | 说明 |
|---|---|
| `AMBIGUOUS_CHECKOUT` | checkout 结构完整但缺少 host/user 正向采纳授权 |
| `DEV_DIR_FOUND` | checkout 有 development-directory 强信号 |
| `INVALID_CHECKOUT` | checkout 缺少必要文件 |
| `MIGRATION_CHECK_FAILED` | in-process migration scan 失败；不得当作无需迁移 |
````

- [ ] **Step 6.2: Run documentation sanity checks**

Run:

```powershell
Select-String -Path docs/API.md -Pattern "m34.bootstrap.v0","install_in_sync","AMBIGUOUS_CHECKOUT"
git diff --check -- docs/API.md
```

Expected: all three strings are found; `git diff --check` exits `0`.

- [ ] **Step 6.3: Commit Task 6**

Run:

```powershell
git add docs/API.md
git commit -m "docs: document bootstrap command contract"
```

---

## Task 7: Rewrite `AGENT_ONBOARDING.md` Step 0

**Files:**
- Modify: `AGENT_ONBOARDING.md`

- [ ] **Step 7.1: Read exact Step 0 section before editing**

Run:

```powershell
$lines = Get-Content AGENT_ONBOARDING.md
$start = ($lines | Select-String -Pattern '^## 2\. Step 0 ' | Select-Object -First 1).LineNumber
$next = ($lines | Select-String -Pattern '^## 3\. Prerequisites' | Select-Object -First 1).LineNumber
$lines[($start-1)..($next-2)]
```

Expected: output starts with `## 2. Step 0` and ends with the `---` separator immediately before `## 3. Prerequisites`.

For edit tools that require `old_string`, copy the exact output from this command as the old string. Do not use ellipses, placeholders, or summarized text.

- [ ] **Step 7.2: Replace Step 0 with the new exact section**

Replace only the section from `## 2. Step 0` through the separator before `## 3. Prerequisites` with this exact text:

````markdown
## 2. Step 0 — Refresh Authority First, Then Run Bootstrap Detection

Do **not** clone, recreate `.venv`, run `health`, adopt a checkout, delete anything, or classify fresh-install vs upgrade until you complete this gate.

### Step 0.1: Refresh authority documents first

Before trusting any local checkout, refresh `bootstrap-manifest.json` from the current upstream repository. Treat that manifest as the version/authority anchor and refresh **every file listed in its `required_authority_docs` array** before proceeding. Treat local copies as potentially stale.

This is the upstream freshness gate. `life-index bootstrap` does **not** perform network freshness checks; it only compares the installed package version against the local manifest version as `install_in_sync`.

### Step 0.2: Run bootstrap detection

If you already have a usable Life Index command:

```bash
life-index bootstrap --json
```

If you are running from a checkout before installation:

```bash
python -m tools bootstrap --json
```

Windows PowerShell and Linux/macOS shells both support the two command forms above when the relevant executable or checkout is available.

If neither command is available, continue to Step 4.1 for a fresh clone/install, then return here after Step 4.3.

If you discovered a checkout during authority refresh, assess it explicitly:

```bash
# Random discovered checkout; default is deliberately conservative.
life-index bootstrap --checkout-path <discovered-path> --json

# Host-managed skill directory exposed by the agent platform.
life-index bootstrap --checkout-path <host-managed-path> --checkout-origin host_managed --json

# User explicitly selected this checkout as the intended install target.
life-index bootstrap --checkout-path <user-selected-path> --checkout-origin user_designated --json
```

**Data safety invariant**: `bootstrap` is read-only. It never deletes existing journal data under `~/Documents/Life-Index/`, never repairs a checkout, never creates a venv, never runs migrations, and never modifies indexes. Phrases like "fresh install", "clean slate", or "start from scratch" do **not** authorize deleting existing journal data.

### Step 0.3: Read `needs_human` first

If `needs_human` is non-empty, relay each item to the user and wait for resolution before proceeding with adoption, cleanup, deletion, repair, or install-target decisions. Common codes:

| `code` | Meaning | Correct action |
|---|---|---|
| `AMBIGUOUS_CHECKOUT` | A checkout looks complete but was only discovered, not positively authorized | Use a host-managed skill directory, ask the user to designate the target, or clone fresh |
| `DEV_DIR_FOUND` | The checkout has development-directory signals | Do not adopt or repair it from this workflow; use a host-managed skill directory or ask the user |
| `INVALID_CHECKOUT` | The checkout is missing required files | Delete/reclone only if it is inside the agent-managed install target; otherwise ask |
| `MIGRATION_CHECK_FAILED` | Migration scan failed and cannot be treated as "no migration needed" | Run `life-index migrate --dry-run` manually and inspect output before proceeding |

### Step 0.4: Read the route and safe next steps

| `route` | Meaning | Proceed to |
|---|---|---|
| `fresh_install` | No existing journal data found | Steps 4.1 → 4.3 → 5.1 → 5.4 |
| `upgrade` | Existing journal data found | Sync/reinstall as needed → run all `safe_next_steps` in order → Steps 5.1 → 5.4 |

If `safe_next_steps` is non-empty, run them in order before the route's verification steps. On `upgrade`, `life-index health` should appear as the final safe next step. If health returns `status: "unhealthy"` after sync/reinstall/migration checks, treat this as **Repair / Ambiguous State**:

1. do **not** pretend this is a clean fresh install;
2. use this document's sync / reinstall / verification flow as the repair baseline;
3. if state remains unclear after basic inspection, ask the user before destructive cleanup.

**Checkout adoption rule**: only adopt a checkout when `detected_state.checkout_assessment.safe_to_adopt` is `true`. A checkout with no dev signals is still not adoptable unless it came from a host-managed path or was explicitly user-designated.

---
````

- [ ] **Step 7.3: Verify onboarding integrity**

Run:

```powershell
$text = Get-Content -Raw AGENT_ONBOARDING.md
if ($text -notmatch 'life-index bootstrap --json') { throw 'bootstrap command missing' }
if ($text -notmatch 'AMBIGUOUS_CHECKOUT') { throw 'ambiguous checkout code missing' }
if ($text -notmatch 'Repair / Ambiguous State') { throw 'repair trigger missing' }
if ($text -notmatch 'install_in_sync') { throw 'install_in_sync wording missing' }
$placeholder = '[' + 'all content'
if ($text -match [regex]::Escape($placeholder)) { throw 'placeholder old_string text remains' }
git diff --check -- AGENT_ONBOARDING.md
```

Expected: no thrown errors; `git diff --check` exits `0`.

- [ ] **Step 7.4: Commit Task 7**

Run:

```powershell
git add AGENT_ONBOARDING.md
git commit -m "docs: route onboarding through bootstrap command"
```

---

## Acceptance Gates

Run these before packaging for push:

```powershell
python -m pytest tests/unit/test_bootstrap.py -v
python -m pytest tests/contract/test_bootstrap_contract.py tests/contract/test_main_cli_contract.py -v
python -m tools bootstrap --json | python -m json.tool
git diff --check
git ls-files | git check-ignore --stdin
```

Expected:

- unit tests pass;
- contract tests pass;
- CLI smoke prints valid JSON;
- whitespace check passes;
- tracked ignored-file check prints no file paths.

Full local gate is not required during early task execution. Per project rule, run the full pre-push gate once before merge/push if the work is going to mainline.

---

## Non-Goals

- Do not change existing `health` behavior in this plan. `bootstrap` defines `journal_count` as files matching `life-index_*.md`; aligning `health` count semantics can be a separate compatibility decision if needed.
- Do not add network freshness checks to `bootstrap`. Upstream freshness belongs to Step 0.1 authority refresh.
- Do not add action-taking repair, migration, clone, delete, or install behavior to `bootstrap`.
- Do not add a `refused` field until the command performs actions that can actually be refused.

---

## Self-Review

**Spec coverage:**

- H1: Task 7.1 requires reading the exact current section and forbids placeholder old strings.
- H2: Task 3 makes health unconditional for `upgrade`; Task 7 preserves Repair / Ambiguous handling.
- H3: Task 2 adds positive adoption origin; Task 7 documents the rule.
- M1: public field is `install_in_sync`; Step 0.1 owns upstream freshness.
- M2: path token alone is `dev_path_hint`, not a hard dev-dir verdict.
- M3/D1: Task 1 uses `scan_journals()` in process and reports failures as `migration_needed: null`.
- L2/L3/L4/L5: no `refused` field, schema uses `m34.bootstrap.v0`, docs use cross-platform command forms, and public API docs are in scope.

**Placeholder scan:**

- No unresolved placeholder markers remain.
- No bracketed section-summary placeholder remains.
- No code step refers to a function that is not introduced in an earlier task.

**Type consistency:**

- `detect_data_state()` returns `install_in_sync`, not `version_fresh`.
- `assess_checkout()` returns `origin`, `verdict`, `signals`, `safe_to_adopt`, and `reason`.
- `decide_route()` returns `route`, `route_reason`, `needs_human`, and `safe_next_steps`.
- `build_bootstrap_result()` returns the public top-level schema documented in `docs/API.md`.
