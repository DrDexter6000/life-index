# Phase 1: Scaffold — TDD Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `life-index serve` starts a working FastAPI app with Jinja2 templates, static file serving, and a health endpoint — all scaffolding needed for Phase 2+.

**Architecture:** FastAPI application factory (`web/app.py`) creates the app, mounts static files and user attachments, configures Jinja2 templates. A thin `web/__main__.py` module provides the CLI `serve` command. Base HTML template uses Tailwind CSS (CDN) + HTMX/Alpine.js (CDN) with dark/light theme toggle.

**Tech Stack:** FastAPI, Uvicorn, Jinja2, Tailwind CSS (CDN), HTMX (CDN), Alpine.js (CDN)

**Spec Reference:** `docs/web-gui/design-spec.md` v1.4 — §2, §4, §5.6, §7, §8

---

## Phase Scope

| Task | Component | Difficulty | Time Est. |
|:--|:--|:--|:--|
| Task 1 | pyproject.toml — `[web]` optional deps | Easy | 5 min |
| Task 2 | E07xx error codes in `errors.py` | Easy | 10 min |
| Task 3 | `web/` directory structure | Easy | 5 min |
| Task 4 | `web/app.py` — FastAPI app factory | Medium | 20 min |
| Task 5 | CLI `serve` command | Medium | 15 min |
| Task 6 | `base.html` — Jinja2 base layout | Medium | 20 min |

**Dependencies:** Tasks 1 & 2 are independent. Task 3 → Task 4 → Tasks 5 & 6.

---

## Prerequisites

Before starting, verify:

```bash
python --version          # Python 3.11+
pip install -e ".[dev]"   # Existing dev install works
python -m pytest tests/unit/ -q  # All existing tests pass
```

Read these files (required context):
- `tools/lib/errors.py` — ErrorCode class structure, RECOVERY_STRATEGIES, ERROR_DESCRIPTIONS
- `tools/__main__.py` lines 286-294 — cmd_map pattern
- `pyproject.toml` lines 72-75 — packages.find section

---

## Task 1: pyproject.toml — Add `[web]` Optional Dependencies

**Files:**
- Modify: `pyproject.toml` (lines 37-59 for optional-dependencies, lines 72-75 for packages.find)
- Test: `tests/unit/test_web_scaffold.py` (create)

**Difficulty:** Easy (~5 min)

**Acceptance Criteria:**
1. `[project.optional-dependencies]` contains a `web = [...]` list with exactly 6 packages per §7
2. `[tool.setuptools.packages.find]` includes `"web*"` in the `include` list
3. `pip install -e ".[web]"` succeeds with exit code 0
4. `pip install -e "."` (without `[web]`) does NOT install FastAPI/uvicorn

**Subagent Governance:**
- MUST DO: Use exact version specifiers from design-spec §7
- MUST DO: Keep existing `dev` and `all` groups unchanged
- MUST DO: Add `"life-index[web]"` to the `all` group
- MUST NOT DO: Move any existing core dependencies into `[web]`
- MUST NOT DO: Add packages not listed in design-spec §7

**Error Handling:** N/A — configuration only.

**TDD Steps:**

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_web_scaffold.py`:

```python
"""Tests for Web GUI scaffold — Phase 1."""

import importlib


class TestWebDependencies:
    """Verify web optional dependencies are declared correctly."""

    def test_web_optional_deps_declared(self) -> None:
        """pyproject.toml declares [web] optional dependencies."""
        # Read pyproject.toml and check for web deps
        from pathlib import Path
        import tomllib

        pyproject_path = Path(__file__).parent.parent.parent / "pyproject.toml"
        with open(pyproject_path, "rb") as f:
            config = tomllib.load(f)

        optional_deps = config["project"]["optional-dependencies"]
        assert "web" in optional_deps, "Missing [web] optional dependency group"

        web_deps = optional_deps["web"]
        # Check all 6 required packages are present
        dep_names = [d.split(">=")[0].split("[")[0].strip() for d in web_deps]
        assert "fastapi" in dep_names
        assert "uvicorn" in dep_names
        assert "jinja2" in dep_names
        assert "python-multipart" in dep_names
        assert "markdown" in dep_names
        assert "httpx" in dep_names

    def test_packages_find_includes_web(self) -> None:
        """packages.find includes web* pattern."""
        from pathlib import Path
        import tomllib

        pyproject_path = Path(__file__).parent.parent.parent / "pyproject.toml"
        with open(pyproject_path, "rb") as f:
            config = tomllib.load(f)

        includes = config["tool"]["setuptools"]["packages"]["find"]["include"]
        assert any("web" in pat for pat in includes), (
            f"packages.find.include must contain 'web*', got: {includes}"
        )
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/unit/test_web_scaffold.py::TestWebDependencies -v
```

Expected: FAIL — `"web"` not in optional-dependencies.

- [ ] **Step 3: Implement — modify pyproject.toml**

Add to `[project.optional-dependencies]` (after the `dev` group):

```toml
# Web GUI dependencies - Web 界面依赖
web = [
    "fastapi>=0.110.0",
    "uvicorn[standard]>=0.27.0",
    "jinja2>=3.1.0",
    "python-multipart>=0.0.9",
    "markdown>=3.5.0",
    "httpx>=0.27.0",
]
```

Update `all` group:

```toml
all = [
    "life-index[dev]",
    "life-index[web]",
]
```

Update `[tool.setuptools.packages.find]`:

```toml
[tool.setuptools.packages.find]
where = ["."]
include = ["tools*", "web*"]
exclude = ["tests*", "docs*", "references*"]
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/unit/test_web_scaffold.py::TestWebDependencies -v
```

Expected: 2 passed.

- [ ] **Step 5: Install web deps and verify**

```bash
pip install -e ".[web]"
python -c "import fastapi; print(fastapi.__version__)"
```

Expected: FastAPI version printed, exit code 0.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml tests/unit/test_web_scaffold.py
git commit -m "feat(web): add [web] optional dependencies to pyproject.toml"
```

---

## Task 2: E07xx Error Codes

**Files:**
- Modify: `tools/lib/errors.py`
- Test: `tests/unit/test_web_scaffold.py` (append)

**Difficulty:** Easy (~10 min)

**Acceptance Criteria:**
1. `ErrorCode` class has 8 new constants: `WEB_GENERAL_ERROR` through `WEB_DEPS_MISSING` (E0700–E0707)
2. `RECOVERY_STRATEGIES` dict maps all 8 codes to correct strategies per §5.6
3. `ERROR_DESCRIPTIONS` dict has entries for all 8 codes
4. Module docstring updated to include `07=web`
5. All existing tests still pass

**Subagent Governance:**
- MUST DO: Place new constants under a `# ========== Web Module (07xx) ==========` comment, following existing section pattern
- MUST DO: Add recovery strategies matching design-spec §5.6 exactly
- MUST DO: Add error descriptions for all 8 codes
- MUST DO: Update module docstring to add `07 - Web GUI operations`
- MUST NOT DO: Modify any existing error codes or recovery strategies
- MUST NOT DO: Create error codes outside the E0700–E0707 range

**Error Handling:** These ARE the error definitions — they define error handling for the entire web module.

**TDD Steps:**

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_web_scaffold.py`:

```python
from tools.lib.errors import ErrorCode, LifeIndexError, ERROR_DESCRIPTIONS


class TestWebErrorCodes:
    """Verify E07xx error codes are defined correctly (per §5.6)."""

    WEB_CODES = {
        "WEB_GENERAL_ERROR": ("E0700", "ask_user"),
        "URL_DOWNLOAD_FAILED": ("E0701", "skip_optional"),
        "URL_CONTENT_TYPE_REJECTED": ("E0702", "ask_user"),
        "LLM_PROVIDER_UNAVAILABLE": ("E0703", "skip_optional"),
        "LLM_EXTRACTION_FAILED": ("E0704", "skip_optional"),
        "GEOLOCATION_FAILED": ("E0705", "skip_optional"),
        "NOMINATIM_UNAVAILABLE": ("E0706", "skip_optional"),
        "WEB_DEPS_MISSING": ("E0707", "fail"),
    }

    def test_error_codes_exist(self) -> None:
        """All E07xx constants are defined on ErrorCode."""
        for name, (code, _) in self.WEB_CODES.items():
            assert hasattr(ErrorCode, name), f"Missing ErrorCode.{name}"
            assert getattr(ErrorCode, name) == code, (
                f"ErrorCode.{name} should be {code!r}"
            )

    def test_recovery_strategies(self) -> None:
        """Each E07xx code has the correct recovery strategy."""
        for name, (code, strategy) in self.WEB_CODES.items():
            assert code in LifeIndexError.RECOVERY_STRATEGIES, (
                f"Missing recovery strategy for {code}"
            )
            assert LifeIndexError.RECOVERY_STRATEGIES[code] == strategy, (
                f"Wrong strategy for {code}: expected {strategy!r}"
            )

    def test_error_descriptions(self) -> None:
        """Each E07xx code has a description."""
        for name, (code, _) in self.WEB_CODES.items():
            assert code in ERROR_DESCRIPTIONS, (
                f"Missing description for {code}"
            )
            assert len(ERROR_DESCRIPTIONS[code]) > 0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/unit/test_web_scaffold.py::TestWebErrorCodes -v
```

Expected: FAIL — `ErrorCode` has no attribute `WEB_GENERAL_ERROR`.

- [ ] **Step 3: Implement — modify `tools/lib/errors.py`**

**3a.** Update module docstring (line 7) — add `07=web`:

```python
# - Module: 00=general, 01=file, 02=write, 03=search, 04=weather, 05=edit, 06=index, 07=web
```

**3b.** Update `ErrorCode` class docstring — add `07 - Web GUI operations`.

**3c.** Add after the `# ========== Index Module (06xx) ==========` section (after line 93):

```python
    # ========== Web Module (07xx) ==========
    WEB_GENERAL_ERROR = "E0700"
    URL_DOWNLOAD_FAILED = "E0701"
    URL_CONTENT_TYPE_REJECTED = "E0702"
    LLM_PROVIDER_UNAVAILABLE = "E0703"
    LLM_EXTRACTION_FAILED = "E0704"
    GEOLOCATION_FAILED = "E0705"
    NOMINATIM_UNAVAILABLE = "E0706"
    WEB_DEPS_MISSING = "E0707"
```

**3d.** Add to `RECOVERY_STRATEGIES` dict (after line 149):

```python
        # Web errors
        ErrorCode.WEB_GENERAL_ERROR: "ask_user",
        ErrorCode.URL_DOWNLOAD_FAILED: "skip_optional",
        ErrorCode.URL_CONTENT_TYPE_REJECTED: "ask_user",
        ErrorCode.LLM_PROVIDER_UNAVAILABLE: "skip_optional",
        ErrorCode.LLM_EXTRACTION_FAILED: "skip_optional",
        ErrorCode.GEOLOCATION_FAILED: "skip_optional",
        ErrorCode.NOMINATIM_UNAVAILABLE: "skip_optional",
        ErrorCode.WEB_DEPS_MISSING: "fail",
```

**3e.** Add to `ERROR_DESCRIPTIONS` dict (after line 233):

```python
    # Web
    ErrorCode.WEB_GENERAL_ERROR: "Web GUI general error",
    ErrorCode.URL_DOWNLOAD_FAILED: "URL attachment download failed",
    ErrorCode.URL_CONTENT_TYPE_REJECTED: "URL file type not in allowed list",
    ErrorCode.LLM_PROVIDER_UNAVAILABLE: "All LLM Providers unavailable",
    ErrorCode.LLM_EXTRACTION_FAILED: "LLM metadata extraction failed",
    ErrorCode.GEOLOCATION_FAILED: "Browser geolocation failed",
    ErrorCode.NOMINATIM_UNAVAILABLE: "Nominatim reverse geocoding failed",
    ErrorCode.WEB_DEPS_MISSING: "Web GUI dependencies not installed",
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/unit/test_web_scaffold.py::TestWebErrorCodes -v
```

Expected: 3 passed.

- [ ] **Step 5: Verify existing tests still pass**

```bash
python -m pytest tests/unit/ -q
```

Expected: All pass, 0 failures.

- [ ] **Step 6: Commit**

```bash
git add tools/lib/errors.py tests/unit/test_web_scaffold.py
git commit -m "feat(web): add E07xx Web Module error codes per design-spec §5.6"
```

---

## Task 3: `web/` Directory Structure

**Files:**
- Create: `web/__init__.py`, `web/__main__.py` (stub), `web/app.py` (stub), `web/config.py`
- Create: `web/routes/__init__.py`, `web/services/__init__.py`
- Create: `web/templates/` (empty dir with `.gitkeep`), `web/static/css/app.css`, `web/static/js/` (empty dir with `.gitkeep`)
- Test: `tests/unit/test_web_scaffold.py` (append)

**Difficulty:** Easy (~5 min)

**Acceptance Criteria:**
1. `web/` is an importable Python package (`import web` succeeds)
2. `web/config.py` exports `DEFAULT_HOST`, `DEFAULT_PORT`, `WEB_DIR`, `TEMPLATES_DIR`, `STATIC_DIR`
3. `web/routes/` and `web/services/` are importable sub-packages
4. `web/templates/` and `web/static/css/` and `web/static/js/` directories exist
5. `web/static/css/app.css` exists (can be empty or minimal)

**Subagent Governance:**
- MUST DO: Create ALL directories/files listed in §4 that are relevant to Phase 1
- MUST DO: Use `pathlib.Path` for all path definitions in `config.py`
- MUST DO: Import from `tools.lib.config` for data paths (USER_DATA_DIR, JOURNALS_DIR, ATTACHMENTS_DIR)
- MUST NOT DO: Create route or service implementation files (those are Phase 2+)
- MUST NOT DO: Add any business logic to `__init__.py` files — keep them empty or minimal

**Error Handling:** N/A — structural setup only.

**TDD Steps:**

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_web_scaffold.py`:

```python
from pathlib import Path


class TestWebPackageStructure:
    """Verify web/ package is importable and correctly structured."""

    def test_web_package_importable(self) -> None:
        """web package can be imported."""
        import web
        assert hasattr(web, "__file__")

    def test_web_config_constants(self) -> None:
        """web.config exports required constants."""
        from web.config import (
            DEFAULT_HOST,
            DEFAULT_PORT,
            WEB_DIR,
            TEMPLATES_DIR,
            STATIC_DIR,
        )
        assert DEFAULT_HOST == "127.0.0.1"
        assert DEFAULT_PORT == 8765
        assert isinstance(WEB_DIR, Path)
        assert isinstance(TEMPLATES_DIR, Path)
        assert isinstance(STATIC_DIR, Path)
        assert TEMPLATES_DIR == WEB_DIR / "templates"
        assert STATIC_DIR == WEB_DIR / "static"

    def test_web_subpackages_importable(self) -> None:
        """web.routes and web.services are importable."""
        import web.routes
        import web.services

    def test_static_directories_exist(self) -> None:
        """Static asset directories exist."""
        from web.config import STATIC_DIR, TEMPLATES_DIR
        assert STATIC_DIR.is_dir(), f"Missing {STATIC_DIR}"
        assert (STATIC_DIR / "css").is_dir()
        assert (STATIC_DIR / "js").is_dir()
        assert TEMPLATES_DIR.is_dir(), f"Missing {TEMPLATES_DIR}"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/unit/test_web_scaffold.py::TestWebPackageStructure -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'web'`.

- [ ] **Step 3: Create directory structure and files**

```bash
# Create directories
mkdir -p web/routes web/services web/templates web/static/css web/static/js
```

Create `web/__init__.py`:

```python
"""Life Index Web GUI — Layer C convenience shell."""
```

Create `web/__main__.py` (stub for Task 5):

```python
"""CLI entry point for `life-index serve`."""


def main() -> None:
    """Start the Web GUI server. Full implementation in Task 5."""
    raise NotImplementedError("Task 5: CLI serve command")
```

Create `web/config.py`:

```python
"""Web GUI configuration constants.

All path constants use pathlib.Path. Data paths import from tools.lib.config (SSOT).
"""

from pathlib import Path

from tools.lib.config import ATTACHMENTS_DIR, JOURNALS_DIR, USER_DATA_DIR

# Web server defaults (per design-spec §8)
DEFAULT_HOST: str = "127.0.0.1"
DEFAULT_PORT: int = 8765

# Template and static asset paths
WEB_DIR: Path = Path(__file__).parent
TEMPLATES_DIR: Path = WEB_DIR / "templates"
STATIC_DIR: Path = WEB_DIR / "static"

# Re-export data paths for convenience (SSOT remains tools.lib.config)
__all__ = [
    "DEFAULT_HOST",
    "DEFAULT_PORT",
    "WEB_DIR",
    "TEMPLATES_DIR",
    "STATIC_DIR",
    "USER_DATA_DIR",
    "JOURNALS_DIR",
    "ATTACHMENTS_DIR",
]
```

Create `web/app.py` (stub for Task 4):

```python
"""FastAPI application factory. Full implementation in Task 4."""
```

Create `web/routes/__init__.py`:

```python
"""Web GUI route blueprints."""
```

Create `web/services/__init__.py`:

```python
"""Web GUI service layer — thin wrappers around tools/ modules."""
```

Create `web/static/css/app.css`:

```css
/* Life Index Web GUI — Custom styles (Tailwind CSS via CDN handles most styling) */
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/unit/test_web_scaffold.py::TestWebPackageStructure -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add web/ tests/unit/test_web_scaffold.py
git commit -m "feat(web): create web/ package structure per design-spec §4"
```

---

## Task 4: `web/app.py` — FastAPI Application Factory

**Files:**
- Modify: `web/app.py`
- Test: `tests/unit/test_web_scaffold.py` (append)

**Difficulty:** Medium (~20 min)

**Acceptance Criteria:**
1. `create_app()` returns a `FastAPI` instance
2. Static files mounted at `/static` from `web/static/`
3. User attachments mounted at `/attachments` from `~/Documents/Life-Index/attachments/`
4. Jinja2 templates configured from `web/templates/`
5. `GET /api/health` returns `{"status": "ok", "version": "..."}` with HTTP 200
6. Attachments mount handles missing directory gracefully (no crash if `attachments/` doesn't exist)

**Subagent Governance:**
- MUST DO: Use `create_app()` factory function pattern (not module-level `app = FastAPI()`)
- MUST DO: Import paths from `web.config` (TEMPLATES_DIR, STATIC_DIR) and `tools.lib.config` (ATTACHMENTS_DIR)
- MUST DO: Use `fastapi.staticfiles.StaticFiles` for static file mounting
- MUST DO: Use `fastapi.templating.Jinja2Templates` for template configuration
- MUST DO: Include app version from `importlib.metadata` or hardcode as fallback
- MUST DO: Guard attachments mount with `if ATTACHMENTS_DIR.exists()`
- MUST NOT DO: Add any routes beyond `/api/health` — other routes are Phase 2+
- MUST NOT DO: 在 `web` 包的非运行时入口制造 FastAPI 导入副作用；FastAPI 依赖应集中在 `web/app.py` / `web.__main__` 这类运行时模块中，避免普通包导入时提前炸掉
- MUST NOT DO: Add middleware, CORS, or authentication — those are Phase 5

**Error Handling:**
- If `ATTACHMENTS_DIR` doesn't exist, skip mounting (log a warning, don't crash)
- FastAPI import failure should be caught at serve time (Task 5), not here

**TDD Steps:**

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_web_scaffold.py`:

```python
import pytest


class TestAppFactory:
    """Verify FastAPI app factory creates a working application."""

    def test_create_app_returns_fastapi(self) -> None:
        """create_app() returns a FastAPI instance."""
        from web.app import create_app
        from fastapi import FastAPI

        app = create_app()
        assert isinstance(app, FastAPI)

    def test_health_endpoint(self) -> None:
        """GET /api/health returns status ok."""
        from web.app import create_app
        from fastapi.testclient import TestClient

        app = create_app()
        client = TestClient(app)
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data

    def test_static_files_mounted(self) -> None:
        """Static files are mounted at /static."""
        from web.app import create_app
        from fastapi.testclient import TestClient

        app = create_app()
        client = TestClient(app)
        # app.css should be servable
        response = client.get("/static/css/app.css")
        assert response.status_code == 200

    def test_templates_configured(self) -> None:
        """Jinja2 templates are configured on the app."""
        from web.app import create_app

        app = create_app()
        assert hasattr(app.state, "templates")

    def test_app_handles_missing_attachments_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """App creation doesn't crash when attachments dir is missing."""
        # Point ATTACHMENTS_DIR to a non-existent path
        fake_dir = tmp_path / "nonexistent"
        monkeypatch.setattr("web.app.ATTACHMENTS_DIR", fake_dir)

        from web.app import create_app
        app = create_app()  # Should not raise
        assert app is not None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/unit/test_web_scaffold.py::TestAppFactory -v
```

Expected: FAIL — `create_app` not found or not returning FastAPI.

- [ ] **Step 3: Implement `web/app.py`**

```python
"""FastAPI application factory.

Creates and configures the Web GUI application. All data access goes through
tools/ modules — this layer never touches the filesystem directly.

Usage:
    from web.app import create_app
    app = create_app()
"""

from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.responses import JSONResponse

from tools.lib.config import ATTACHMENTS_DIR
from web.config import STATIC_DIR, TEMPLATES_DIR


def _get_version() -> str:
    """Get package version from metadata, with fallback."""
    try:
        from importlib.metadata import version
        return version("life-index")
    except Exception:
        return "dev"


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI instance with static files, templates, and health endpoint.
    """
    app = FastAPI(
        title="Life Index Web GUI",
        version=_get_version(),
        docs_url=None,   # Disable Swagger UI in production
        redoc_url=None,   # Disable ReDoc in production
    )

    # --- Static files ---
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # --- User attachments (may not exist on fresh install) ---
    if ATTACHMENTS_DIR.exists():
        app.mount(
            "/attachments",
            StaticFiles(directory=str(ATTACHMENTS_DIR)),
            name="attachments",
        )

    # --- Jinja2 templates ---
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    app.state.templates = templates

    # --- Health endpoint ---
    @app.get("/api/health")
    async def health() -> dict[str, Any]:
        return {"status": "ok", "version": app.version}

    return app
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/unit/test_web_scaffold.py::TestAppFactory -v
```

Expected: 5 passed.

- [ ] **Step 5: Verify existing tests still pass**

```bash
python -m pytest tests/unit/ -q
```

Expected: All pass, 0 failures.

- [ ] **Step 6: Commit**

```bash
git add web/app.py tests/unit/test_web_scaffold.py
git commit -m "feat(web): implement FastAPI app factory with health endpoint"
```

---

## Task 5: CLI `serve` Command

**Files:**
- Modify: `web/__main__.py`
- Modify: `tools/__main__.py` (line ~294 — add to cmd_map)
- Test: `tests/unit/test_web_scaffold.py` (append)

**Difficulty:** Medium (~15 min)

**Acceptance Criteria:**
1. `life-index serve` starts the Uvicorn server on `127.0.0.1:8765`
2. `life-index serve --port 9000 --host 0.0.0.0` uses custom host/port
3. `life-index serve --reload` enables auto-reload for development
4. If web dependencies are not installed, outputs JSON error with code E0707 and exits with code 1
5. `serve` appears in `cmd_map` in `tools/__main__.py`

**Subagent Governance:**
- MUST DO: Add `"serve": "web.__main__"` to `cmd_map` in `tools/__main__.py`
- MUST DO: Use `argparse` for CLI argument parsing (consistent with other tools)
- MUST DO: Check for FastAPI/uvicorn import BEFORE starting — catch `ImportError` and output E0707 JSON
- MUST DO: Use `uvicorn.run()` programmatically (not subprocess)
- MUST DO: Import `create_app` from `web.app` inside `main()` to defer the import
- MUST NOT DO: Add `serve` to the help text in a way that breaks existing help format
- MUST NOT DO: Start the server in tests — only test argument parsing and dep checking

**Error Handling:**
- Missing web deps → `E0707` JSON error + `sys.exit(1)`
- Use `create_error_response()` from `tools.lib.errors` for consistent error format

**TDD Steps:**

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_web_scaffold.py`:

```python
import json
import subprocess
import sys


class TestServeCommand:
    """Verify CLI serve command setup."""

    def test_serve_in_cmd_map(self) -> None:
        """'serve' is registered in tools/__main__.py cmd_map."""
        # We can't easily import cmd_map without running main(),
        # so we check the source file directly
        from pathlib import Path
        main_path = Path(__file__).parent.parent.parent / "tools" / "__main__.py"
        source = main_path.read_text(encoding="utf-8")
        assert '"serve"' in source, "Missing 'serve' in cmd_map"
        assert "web.__main__" in source, "Missing web.__main__ module reference"

    def test_web_main_has_main_function(self) -> None:
        """web.__main__ exports a main() function."""
        from web.__main__ import main
        assert callable(main)

    def test_web_main_parses_port_argument(self) -> None:
        """web.__main__ accepts --port argument."""
        from web.__main__ import parse_args
        args = parse_args(["--port", "9000"])
        assert args.port == 9000

    def test_web_main_parses_host_argument(self) -> None:
        """web.__main__ accepts --host argument."""
        from web.__main__ import parse_args
        args = parse_args(["--host", "0.0.0.0"])
        assert args.host == "0.0.0.0"

    def test_web_main_default_values(self) -> None:
        """web.__main__ uses correct defaults."""
        from web.__main__ import parse_args
        args = parse_args([])
        assert args.port == 8765
        assert args.host == "127.0.0.1"
        assert args.reload is False

    def test_web_main_reload_flag(self) -> None:
        """web.__main__ accepts --reload flag."""
        from web.__main__ import parse_args
        args = parse_args(["--reload"])
        assert args.reload is True

    def test_missing_deps_returns_e0707(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When web deps missing, main() prints E0707 JSON and exits."""
        import builtins
        original_import = builtins.__import__

        def mock_import(name: str, *args: Any, **kwargs: Any) -> Any:
            if name == "uvicorn":
                raise ImportError("No module named 'uvicorn'")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)

        # Need to reload the module to trigger the import check
        from web.__main__ import check_deps
        success, error = check_deps()
        assert success is False
        assert error is not None
        assert error["error"]["code"] == "E0707"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/unit/test_web_scaffold.py::TestServeCommand -v
```

Expected: FAIL — `parse_args` not found, `check_deps` not found.

- [ ] **Step 3a: Add `serve` to cmd_map in `tools/__main__.py`**

At line ~294 (after the `"backup"` entry), add:

```python
        "serve": "web.__main__",
```

- [ ] **Step 3b: Implement `web/__main__.py`**

```python
"""CLI entry point for `life-index serve`.

Usage:
    life-index serve [--port 8765] [--host 127.0.0.1] [--reload]
"""

import argparse
import json
import sys
from typing import Any, Optional

from web.config import DEFAULT_HOST, DEFAULT_PORT


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    """Parse serve command arguments.

    Args:
        argv: Argument list (defaults to sys.argv[1:] if None).

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        description="Start the Life Index Web GUI server",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"Port to listen on (default: {DEFAULT_PORT})",
    )
    parser.add_argument(
        "--host",
        type=str,
        default=DEFAULT_HOST,
        help=f"Host to bind to (default: {DEFAULT_HOST})",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        default=False,
        help="Enable auto-reload for development",
    )
    return parser.parse_args(argv)


def check_deps() -> tuple[bool, Optional[dict[str, Any]]]:
    """Check if web dependencies are installed.

    Returns:
        Tuple of (success, error_response). error_response is None on success.
    """
    try:
        import uvicorn  # noqa: F401
        import fastapi  # noqa: F401
        return True, None
    except ImportError:
        from tools.lib.errors import create_error_response, ErrorCode
        error = create_error_response(
            ErrorCode.WEB_DEPS_MISSING,
            "Web GUI dependencies not installed. Run: pip install life-index[web]",
        )
        return False, error


def main() -> None:
    """Start the Web GUI server."""
    args = parse_args()

    # Check dependencies before importing anything else
    ok, error = check_deps()
    if not ok:
        print(json.dumps(error, ensure_ascii=False, indent=2))
        sys.exit(1)

    import uvicorn
    from web.app import create_app

    app = create_app()
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/unit/test_web_scaffold.py::TestServeCommand -v
```

Expected: 7 passed.

- [ ] **Step 5: Manual smoke test** (optional but recommended)

```bash
life-index serve &
curl http://127.0.0.1:8765/api/health
# Expected: {"status":"ok","version":"..."}
# Then kill the background process
kill %1
```

- [ ] **Step 6: Commit**

```bash
git add web/__main__.py tools/__main__.py tests/unit/test_web_scaffold.py
git commit -m "feat(web): add 'life-index serve' CLI command with dep checking"
```

---

## Task 6: `base.html` — Jinja2 Base Layout

**Files:**
- Create: `web/templates/base.html`
- Test: `tests/unit/test_web_scaffold.py` (append)

**Difficulty:** Medium (~20 min)

**Acceptance Criteria:**
1. Template renders without errors via Jinja2
2. Contains `{% block title %}{% endblock %}` and `{% block content %}{% endblock %}`
3. Includes Tailwind CSS via CDN (`<script src="https://cdn.tailwindcss.com">`)
4. Includes HTMX via CDN (`<script src="https://unpkg.com/htmx.org@...">`)
5. Includes Alpine.js via CDN (`<script src="https://cdn.jsdelivr.net/npm/alpinejs@...">`)
6. Has dark/light theme toggle using Alpine.js + `prefers-color-scheme` detection
7. Navigation bar with links: 仪表盘 (`/`), 搜索 (`/search`), 写日志 (`/write`)
8. Footer with "Life Index" branding
9. All UI text is in Chinese
10. `<html>` tag has `lang="zh-CN"` attribute

**Subagent Governance:**
- MUST DO: Use CDN links for Tailwind, HTMX, Alpine.js (per design-spec §2 Phase 1 decision)
- MUST DO: Implement theme toggle with `localStorage` persistence + `prefers-color-scheme` initial detection
- MUST DO: Use semantic HTML (`<nav>`, `<main>`, `<footer>`)
- MUST DO: Add `dark:` Tailwind variants for all colored elements
- MUST DO: Use Chinese text for all user-facing strings
- MUST NOT DO: Add page-specific content — this is the BASE template only
- MUST NOT DO: Include ECharts — that's Dashboard-specific (Phase 2)
- MUST NOT DO: Add complex JavaScript beyond theme toggle logic
- MUST NOT DO: Use local JS files (CDN is fine for Phase 1, per design-spec §2)

**Error Handling:** N/A — template rendering errors will surface at runtime.

**TDD Steps:**

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_web_scaffold.py`:

```python
class TestBaseTemplate:
    """Verify base.html template structure and rendering."""

    def test_base_template_exists(self) -> None:
        """base.html exists in templates directory."""
        from web.config import TEMPLATES_DIR
        assert (TEMPLATES_DIR / "base.html").is_file()

    def test_base_template_renders(self) -> None:
        """base.html renders without errors via Jinja2."""
        from jinja2 import Environment, FileSystemLoader
        from web.config import TEMPLATES_DIR

        env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
        template = env.get_template("base.html")
        html = template.render(request=None)
        assert len(html) > 0

    def test_base_template_has_blocks(self) -> None:
        """base.html defines title and content blocks."""
        from web.config import TEMPLATES_DIR
        source = (TEMPLATES_DIR / "base.html").read_text(encoding="utf-8")
        assert "{% block title %}" in source
        assert "{% block content %}" in source

    def test_base_template_includes_cdn_deps(self) -> None:
        """base.html includes Tailwind, HTMX, Alpine.js CDN links."""
        from web.config import TEMPLATES_DIR
        source = (TEMPLATES_DIR / "base.html").read_text(encoding="utf-8")
        assert "tailwindcss" in source.lower() or "cdn.tailwindcss.com" in source
        assert "htmx" in source.lower()
        assert "alpinejs" in source.lower() or "alpine" in source.lower()

    def test_base_template_has_theme_toggle(self) -> None:
        """base.html has dark/light theme toggle mechanism."""
        from web.config import TEMPLATES_DIR
        source = (TEMPLATES_DIR / "base.html").read_text(encoding="utf-8")
        assert "localStorage" in source, "Theme toggle should persist to localStorage"
        assert "prefers-color-scheme" in source or "dark" in source

    def test_base_template_has_navigation(self) -> None:
        """base.html has navigation links."""
        from web.config import TEMPLATES_DIR
        source = (TEMPLATES_DIR / "base.html").read_text(encoding="utf-8")
        assert "<nav" in source
        # Check for Chinese navigation text
        assert "仪表盘" in source or "首页" in source
        assert "搜索" in source
        assert "写日志" in source or "写入" in source

    def test_base_template_has_chinese_lang(self) -> None:
        """base.html has lang='zh-CN' attribute."""
        from web.config import TEMPLATES_DIR
        source = (TEMPLATES_DIR / "base.html").read_text(encoding="utf-8")
        assert 'lang="zh-CN"' in source or "lang='zh-CN'" in source

    def test_base_template_has_footer(self) -> None:
        """base.html has a footer with branding."""
        from web.config import TEMPLATES_DIR
        source = (TEMPLATES_DIR / "base.html").read_text(encoding="utf-8")
        assert "<footer" in source
        assert "Life Index" in source
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/unit/test_web_scaffold.py::TestBaseTemplate -v
```

Expected: FAIL — `base.html` not found.

- [ ] **Step 3: Create `web/templates/base.html`**

```html
<!DOCTYPE html>
<html lang="zh-CN" x-data="{ darkMode: localStorage.getItem('theme') === 'dark' || (!localStorage.getItem('theme') && window.matchMedia('(prefers-color-scheme: dark)').matches) }"
      :class="{ 'dark': darkMode }">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Life Index{% endblock %}</title>

    <!-- Tailwind CSS (CDN — Phase 1) -->
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {
            darkMode: 'class',
        }
    </script>

    <!-- Custom styles -->
    <link rel="stylesheet" href="/static/css/app.css">

    <!-- Alpine.js (CDN — Phase 1) -->
    <script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js"></script>

    <!-- HTMX (CDN — Phase 1) -->
    <script src="https://unpkg.com/htmx.org@2.0.4"></script>
</head>
<body class="min-h-screen bg-gray-50 text-gray-900 dark:bg-gray-900 dark:text-gray-100 transition-colors duration-200">

    <!-- Navigation -->
    <nav class="bg-white dark:bg-gray-800 shadow-sm border-b border-gray-200 dark:border-gray-700">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div class="flex justify-between h-16">
                <!-- Logo & Nav Links -->
                <div class="flex items-center space-x-8">
                    <a href="/" class="text-xl font-bold text-indigo-600 dark:text-indigo-400">
                        Life Index
                    </a>
                    <div class="hidden sm:flex space-x-4">
                        <a href="/"
                           class="px-3 py-2 rounded-md text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700">
                            仪表盘
                        </a>
                        <a href="/search"
                           class="px-3 py-2 rounded-md text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700">
                            搜索
                        </a>
                        <a href="/write"
                           class="px-3 py-2 rounded-md text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 dark:bg-indigo-500 dark:hover:bg-indigo-600 rounded-lg">
                            写日志
                        </a>
                    </div>
                </div>

                <!-- Theme Toggle -->
                <div class="flex items-center">
                    <button @click="darkMode = !darkMode; localStorage.setItem('theme', darkMode ? 'dark' : 'light')"
                            class="p-2 rounded-md text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700"
                            :title="darkMode ? '切换到亮色模式' : '切换到暗色模式'">
                        <!-- Sun icon (shown in dark mode) -->
                        <svg x-show="darkMode" class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                                  d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"/>
                        </svg>
                        <!-- Moon icon (shown in light mode) -->
                        <svg x-show="!darkMode" class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                                  d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"/>
                        </svg>
                    </button>
                </div>
            </div>
        </div>
    </nav>

    <!-- Main Content -->
    <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {% block content %}{% endblock %}
    </main>

    <!-- Footer -->
    <footer class="bg-white dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700 mt-auto">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
            <p class="text-center text-sm text-gray-500 dark:text-gray-400">
                Life Index — 你的人生档案馆
            </p>
        </div>
    </footer>

</body>
</html>
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/unit/test_web_scaffold.py::TestBaseTemplate -v
```

Expected: 8 passed.

- [ ] **Step 5: Visual smoke test** (optional but recommended)

```bash
life-index serve &
# Open http://127.0.0.1:8765/api/health in browser to verify template
# (Note: no route renders base.html yet — that's Phase 2)
kill %1
```

- [ ] **Step 6: Commit**

```bash
git add web/templates/base.html tests/unit/test_web_scaffold.py
git commit -m "feat(web): add base.html Jinja2 template with theme toggle"
```

---

## Phase 1 Completion Checklist

Run all checks before declaring Phase 1 complete:

- [ ] **All Phase 1 tests pass:**

```bash
python -m pytest tests/unit/test_web_scaffold.py -v
```

Expected: All tests in `TestWebDependencies`, `TestWebErrorCodes`, `TestWebPackageStructure`, `TestAppFactory`, `TestServeCommand`, `TestBaseTemplate` pass.

- [ ] **All existing tests still pass:**

```bash
python -m pytest tests/unit/ -q
```

Expected: 0 failures.

- [ ] **Web deps install cleanly:**

```bash
pip install -e ".[web]" && python -c "import fastapi; import uvicorn; import jinja2; print('OK')"
```

Expected: `OK`

- [ ] **Health endpoint responds:**

```bash
life-index serve &
sleep 2
curl -s http://127.0.0.1:8765/api/health | python -m json.tool
kill %1
```

Expected: `{"status": "ok", "version": "..."}`

- [ ] **Static files served:**

```bash
life-index serve &
sleep 2
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8765/static/css/app.css
kill %1
```

Expected: `200`

- [ ] **Directory structure matches §4:**

```
web/
├── __init__.py          ✅
├── __main__.py          ✅
├── app.py               ✅
├── config.py            ✅
├── routes/
│   └── __init__.py      ✅
├── services/
│   └── __init__.py      ✅
├── templates/
│   └── base.html        ✅
└── static/
    ├── css/
    │   └── app.css      ✅
    └── js/              ✅
```

**Phase 1 is complete when all checkboxes above are checked. Proceed to Phase 2: Dashboard.**
