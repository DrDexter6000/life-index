# Phase 3: Journal View + Search — TDD Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Journal view page renders Markdown journals with frontmatter metadata display, inline attachments, and path traversal protection. Search page provides full-parameter search with HTMX partial rendering of results.

**Architecture:** `web/services/journal.py` wraps `frontmatter.parse_journal_file()` and Python `markdown` library to produce rendered HTML + metadata. `web/routes/journal.py` exposes `GET /journal/{path:path}` with path safety validation. `web/services/search.py` wraps `search_journals.core.hierarchical_search()` into Web-friendly result structures. `web/routes/search.py` exposes `GET /search` with HTMX partial support via `partials/search_results.html`. All routes validate paths against `JOURNALS_DIR` to prevent traversal attacks.

**Tech Stack:** Python 3.11+ (pathlib, markdown), FastAPI, Jinja2, HTMX (partial rendering), Tailwind CSS

**Spec Reference:** `docs/web-gui/design-spec.md` v1.4 — §5.2, §5.3, §6.1, §6.3

---

## Phase Scope

| Task | Component | Difficulty | Time Est. |
|:--|:--|:--|:--|
| Task 9 | Journal View — `web/services/journal.py` + `web/routes/journal.py` + `journal.html` | Medium | 35 min |
| Task 10 | Search — `web/services/search.py` + `web/routes/search.py` + `search.html` + `partials/search_results.html` | Hard | 50 min |

**Dependencies:** Task 9 depends on Phase 1 Task 6 (base.html). Task 10 depends on Phase 1 Task 6 (base.html). Tasks 9 and 10 are independent of each other (can be implemented in parallel, but sequential is recommended for consistency).

## Split Navigation

- Task 9 focused doc: [plan-phase3a-journal-view.md](plan-phase3a-journal-view.md)
- Task 10 focused doc: [plan-phase3b-search.md](plan-phase3b-search.md)

> 本文件暂时保留完整 legacy TDD 细节；新的执行入口应优先查看上述 split subplans。

---

## Prerequisites

Before starting, verify Phase 1 and Phase 2 are complete:

```bash
python -m pytest tests/unit/test_web_scaffold.py -v   # All Phase 1 tests pass
python -m pytest tests/unit/test_web_dashboard.py -v   # All Phase 2 tests pass
life-index serve &                                      # Server starts
curl -s http://127.0.0.1:8765/api/health                # {"status":"ok",...}
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8765/  # 200
kill %1
```

Read these files (required context):
- `docs/web-gui/design-spec.md` §5.2 — Search parameters, HTMX interaction flow
- `docs/web-gui/design-spec.md` §5.3 — Journal view, Markdown rendering, attachment display, path traversal protection
- `tools/lib/frontmatter.py` line 77 — `parse_journal_file()` return structure (`_body`, `_file`, `_title`, `_abstract` keys)
- `tools/search_journals/core.py` line 34 — `hierarchical_search()` full signature and return structure (`merged_results`, `l1_results`, etc.)
- `tools/search_journals/__main__.py` lines 40-84 — CLI parameter mapping
- `tools/lib/config.py` — `USER_DATA_DIR`, `JOURNALS_DIR`, `ATTACHMENTS_DIR` constants
- `web/app.py` — `create_app()` factory pattern, `app.state.templates`, lazy import of routers
- `web/templates/base.html` — Block names (`{% block title %}`, `{% block content %}`, `{% block scripts %}`)

### Key Data Contracts

**`parse_journal_file(path)` returns `Dict[str, Any]`:**

```python
{
    "date": "2026-03-07T14:30:00",          # str (ISO datetime from frontmatter)
    "title": "日志标题",                      # str (from frontmatter, if present)
    "location": "Lagos, Nigeria",            # str | None
    "weather": "晴天 28°C",                  # str | None
    "mood": ["专注", "充实"],                 # List[str]
    "tags": ["重构", "优化"],                 # List[str]
    "topic": ["work", "create"],             # List[str]
    "people": ["乐乐"],                       # List[str]
    "project": "LifeIndex",                  # str | None
    "abstract": "100字内摘要",                # str | None
    "_title": "日志标题",                     # str (extracted from first # heading, or filename stem)
    "_abstract": "第一个非空非标题段落...",    # str (extracted from body, max 100 chars)
    "_body": "# 日志标题\n\n正文内容...",     # str (full Markdown body below frontmatter)
    "_file": "/full/path/to/journal.md",     # str (absolute file path)
}
```

**On error** (file missing, corrupt, unreadable):
```python
{"_error": "error message", "_file": "/path/to/file.md"}
```

**`hierarchical_search()` returns `Dict[str, Any]`:**

```python
{
    "success": True,
    "query_params": { ... },
    "l1_results": [...],
    "l2_results": [...],
    "l3_results": [...],
    "semantic_results": [...],
    "merged_results": [                      # ← PRIMARY result list (RRF-fused)
        {
            "path": "C:/Users/.../Documents/Life-Index/Journals/2026/03/life-index_2026-03-07_001.md",  # current runtime often returns absolute path
            "journal_route_path": "2026/03/life-index_2026-03-07_001.md",  # normalized for Web routes
            "title": "日志标题",
            "date": "2026-03-07",
            "rrf_score": 0.0312,
            "snippet": "匹配片段...",         # str | None (from L3/semantic)
            # Additional fields depend on search level
        },
    ],
    "total_found": 5,
    "semantic_available": True,
    "performance": { "total_time_ms": 42.5 },
}
```

### Path Traversal Protection

No existing `get_safe_path()` utility exists in the codebase. The journal service must implement manual path validation:

```python
resolved = (JOURNALS_DIR / relative_path).resolve()
if not str(resolved).startswith(str(JOURNALS_DIR.resolve())):
    raise ValueError("Path traversal detected")
```

This pattern validates that the resolved path is still within `JOURNALS_DIR` after symlink/`..` resolution.

---

## Task 9: Journal View (`web/services/journal.py` + `web/routes/journal.py` + `journal.html`)

**Files:**
- Create: `web/services/journal.py`
- Create: `web/routes/journal.py`
- Create: `web/templates/journal.html`
- Modify: `web/app.py` (register journal router)
- Test: `tests/unit/test_web_journal_search.py` (create)

**Difficulty:** Medium (~35 min)

**Acceptance Criteria:**
1. `get_journal(relative_path)` returns a dict with `metadata`, `html_content`, and `attachments` keys
2. Path traversal attempts (e.g., `../../etc/passwd`) raise `ValueError` and result in HTTP 404
3. Paths are validated against `JOURNALS_DIR` using `.resolve()` comparison
4. Markdown body is rendered to HTML using Python `markdown` library with `fenced_code` and `tables` extensions
5. Non-existent journal files return HTTP 404 with a user-friendly error page
6. Frontmatter metadata (mood, tags, topic, weather, location, people, date) is displayed in the page header
7. Attachment references in content are rewritten to use the FastAPI static mount path (`/attachments/`)
8. Page title is `"{journal_title} — Life Index"`
9. Journal route is registered in `create_app()` via `app.include_router()`
10. "编辑" button links to `/journal/{relative_path}/edit` (Phase 4 route — link only, no implementation)
11. "返回" navigation links to search page or dashboard
12. Search/Journal web payloads normalize raw tool paths into `journal_route_path` before rendering links or redirects

**Subagent Governance:**
- MUST DO: Import `parse_journal_file` from `tools.lib.frontmatter`
- MUST DO: Import `JOURNALS_DIR` and `ATTACHMENTS_DIR` from `tools.lib.config`
- MUST DO: Validate `relative_path` against `JOURNALS_DIR` using `Path.resolve()` — reject if resolved path is outside `JOURNALS_DIR`
- MUST DO: Use `markdown.markdown()` with extensions `["fenced_code", "tables"]` for Markdown→HTML conversion
- MUST DO: Use `app.state.templates.TemplateResponse()` for rendering
- MUST DO: Include `request` in template context (required by Starlette/Jinja2)
- MUST DO: Register journal router in `web/app.py` via `app.include_router(journal_router)` using lazy import inside `create_app()`
- MUST DO: Use the `_body` key (not `body`) from `parse_journal_file()` return value
- MUST DO: Use the `_title` key for display title (fallback from frontmatter `title` field)
- MUST DO: Handle `_error` key in parse result — return 404 when present
- MUST DO: Display all list-type metadata (mood, tags, topic, people) as colored tag badges
- MUST DO: Use Chinese text for all user-facing strings
- MUST DO: Use semantic HTML and Tailwind CSS classes consistent with `base.html`
- MUST NOT DO: Access the filesystem directly in the route — delegate to the service
- MUST NOT DO: Skip path traversal validation — this is a security requirement
- MUST NOT DO: Use client-side JavaScript for Markdown rendering — server-side only (per §5.3)
- MUST NOT DO: Modify any `tools/` module code
- MUST NOT DO: Implement the edit route in this task — only provide the link

**Error Handling:**
- Path traversal detected → HTTP 404 (do not reveal the reason to prevent information leakage)
- File not found or parse error (`_error` key present) → HTTP 404 with "日志未找到" message
- Markdown rendering failure → Return raw text body as fallback, log warning

**TDD Steps:**

- [ ] **Step 1: Write the failing tests — journal service**

Create `tests/unit/test_web_journal_search.py`:

```python
"""Tests for Web GUI Journal View + Search — Phase 3 (Tasks 9–10)."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch, MagicMock

import pytest


# ── Task 9: Journal View Service + Route ──────────────────────


class TestJournalServicePathSafety:
    """Path traversal protection in journal service."""

    @patch("web.services.journal.JOURNALS_DIR", new_callable=lambda: property(lambda self: Path("/fake/journals")))
    def test_path_traversal_rejected(self) -> None:
        """Paths escaping JOURNALS_DIR raise ValueError."""
        from web.services.journal import get_journal

        with pytest.raises(ValueError, match="[Pp]ath"):
            get_journal("../../etc/passwd")

    def test_normal_path_accepted(self) -> None:
        """Valid relative path within JOURNALS_DIR does not raise ValueError."""
        # This test will fail until service is implemented, but verifies
        # that the import works and accepts valid paths (file may not exist)
        from web.services.journal import get_journal

        # A valid path structure — will fail with FileNotFoundError or return
        # error dict, but should NOT raise ValueError
        try:
            result = get_journal("2026/03/life-index_2026-03-07_001.md")
        except ValueError:
            pytest.fail("Valid path should not raise ValueError")
        except FileNotFoundError:
            pass  # Expected — file doesn't exist in test env
        # If it returns an error dict, that's also acceptable
        if isinstance(result, dict) and result.get("error"):
            pass  # Service returned error for missing file — acceptable

    def test_dotdot_in_middle_rejected(self) -> None:
        """Paths with .. components that escape JOURNALS_DIR are rejected."""
        from web.services.journal import get_journal

        with pytest.raises(ValueError, match="[Pp]ath"):
            get_journal("2026/03/../../../../../../etc/shadow")


class TestJournalServiceParsing:
    """Journal service parses frontmatter and renders Markdown."""

    @patch("web.services.journal.parse_journal_file")
    @patch("web.services.journal.JOURNALS_DIR", new=Path("/fake/journals"))
    def test_returns_metadata_and_html(
        self, mock_parse: MagicMock
    ) -> None:
        """get_journal returns metadata, html_content, and attachments."""
        mock_parse.return_value = {
            "title": "测试日志",
            "date": "2026-03-07T14:30:00",
            "mood": ["专注"],
            "tags": ["python"],
            "topic": ["work"],
            "people": [],
            "location": "Lagos, Nigeria",
            "weather": "Sunny 28°C",
            "abstract": "测试摘要",
            "_title": "测试日志",
            "_abstract": "测试摘要",
            "_body": "# 测试日志\n\n这是正文内容。\n\n```python\nprint('hello')\n```\n",
            "_file": "/fake/journals/2026/03/life-index_2026-03-07_001.md",
        }

        # Mock Path.resolve() to return a path within JOURNALS_DIR
        with patch.object(Path, "resolve") as mock_resolve:
            mock_resolve.return_value = Path("/fake/journals/2026/03/life-index_2026-03-07_001.md")
            with patch.object(Path, "exists", return_value=True):
                from web.services.journal import get_journal
                result = get_journal("2026/03/life-index_2026-03-07_001.md")

        assert "metadata" in result
        assert "html_content" in result
        assert result["metadata"]["title"] == "测试日志"
        # HTML should contain rendered Markdown
        assert "<h1>" in result["html_content"] or "测试日志" in result["html_content"]
        # Code block should be rendered with fenced_code extension
        assert "<code" in result["html_content"] or "print" in result["html_content"]

    @patch("web.services.journal.parse_journal_file")
    @patch("web.services.journal.JOURNALS_DIR", new=Path("/fake/journals"))
    def test_parse_error_returns_error(
        self, mock_parse: MagicMock
    ) -> None:
        """Parse errors (corrupt file) return error dict."""
        mock_parse.return_value = {
            "_error": "UnicodeDecodeError: invalid start byte",
            "_file": "/fake/journals/bad.md",
        }

        with patch.object(Path, "resolve") as mock_resolve:
            mock_resolve.return_value = Path("/fake/journals/bad.md")
            with patch.object(Path, "exists", return_value=True):
                from web.services.journal import get_journal
                result = get_journal("bad.md")

        assert "error" in result

    @patch("web.services.journal.parse_journal_file")
    @patch("web.services.journal.JOURNALS_DIR", new=Path("/fake/journals"))
    def test_markdown_fenced_code_rendered(
        self, mock_parse: MagicMock
    ) -> None:
        """Fenced code blocks are rendered to HTML."""
        mock_parse.return_value = {
            "title": "Code Test",
            "_title": "Code Test",
            "_body": "# Code Test\n\n```python\nx = 1\n```\n",
            "_file": "/fake/journals/code.md",
            "_abstract": "code",
            "mood": [],
            "tags": [],
            "topic": ["work"],
            "people": [],
        }

        with patch.object(Path, "resolve") as mock_resolve:
            mock_resolve.return_value = Path("/fake/journals/code.md")
            with patch.object(Path, "exists", return_value=True):
                from web.services.journal import get_journal
                result = get_journal("code.md")

        assert "<code" in result["html_content"]

    @patch("web.services.journal.parse_journal_file")
    @patch("web.services.journal.JOURNALS_DIR", new=Path("/fake/journals"))
    def test_markdown_tables_rendered(
        self, mock_parse: MagicMock
    ) -> None:
        """Markdown tables are rendered to HTML tables."""
        mock_parse.return_value = {
            "title": "Table Test",
            "_title": "Table Test",
            "_body": "# Table\n\n| A | B |\n|---|---|\n| 1 | 2 |\n",
            "_file": "/fake/journals/table.md",
            "_abstract": "table",
            "mood": [],
            "tags": [],
            "topic": ["work"],
            "people": [],
        }

        with patch.object(Path, "resolve") as mock_resolve:
            mock_resolve.return_value = Path("/fake/journals/table.md")
            with patch.object(Path, "exists", return_value=True):
                from web.services.journal import get_journal
                result = get_journal("table.md")

        assert "<table" in result["html_content"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/unit/test_web_journal_search.py::TestJournalServicePathSafety -v
python -m pytest tests/unit/test_web_journal_search.py::TestJournalServiceParsing -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'web.services.journal'`.

- [ ] **Step 3: Write the failing tests — journal route**

Append to `tests/unit/test_web_journal_search.py`:

```python
class TestJournalRoute:
    """Test GET /journal/{path} route."""

    @patch("web.services.journal.get_journal")
    def test_journal_returns_200(self, mock_get: MagicMock) -> None:
        """GET /journal/{path} returns HTTP 200 for valid journal."""
        mock_get.return_value = {
            "metadata": {
                "title": "测试日志",
                "date": "2026-03-07T14:30:00",
                "mood": ["专注"],
                "tags": ["python"],
                "topic": ["work"],
                "people": [],
                "location": "Lagos",
                "weather": "Sunny",
            },
            "html_content": "<h1>测试日志</h1><p>正文</p>",
            "attachments": [],
        }

        from web.app import create_app
        from fastapi.testclient import TestClient

        app = create_app()
        client = TestClient(app)
        response = client.get("/journal/2026/03/life-index_2026-03-07_001.md")
        assert response.status_code == 200
        assert "测试日志" in response.text

    @patch("web.services.journal.get_journal")
    def test_journal_404_on_error(self, mock_get: MagicMock) -> None:
        """GET /journal/{path} returns HTTP 404 when journal not found."""
        mock_get.return_value = {"error": "日志未找到"}

        from web.app import create_app
        from fastapi.testclient import TestClient

        app = create_app()
        client = TestClient(app)
        response = client.get("/journal/nonexistent.md")
        assert response.status_code == 404

    @patch("web.services.journal.get_journal")
    def test_journal_404_on_traversal(self, mock_get: MagicMock) -> None:
        """GET /journal/{path} returns 404 for path traversal attempts."""
        mock_get.side_effect = ValueError("Path traversal detected")

        from web.app import create_app
        from fastapi.testclient import TestClient

        app = create_app()
        client = TestClient(app)
        response = client.get("/journal/../../etc/passwd")
        assert response.status_code == 404

    @patch("web.services.journal.get_journal")
    def test_journal_has_edit_link(self, mock_get: MagicMock) -> None:
        """Journal page contains edit button link."""
        mock_get.return_value = {
            "metadata": {
                "title": "编辑测试",
                "date": "2026-03-07",
                "mood": [],
                "tags": [],
                "topic": ["work"],
                "people": [],
            },
            "html_content": "<h1>编辑测试</h1>",
            "attachments": [],
        }

        from web.app import create_app
        from fastapi.testclient import TestClient

        app = create_app()
        client = TestClient(app)
        response = client.get("/journal/2026/03/test.md")
        assert response.status_code == 200
        assert "编辑" in response.text
        assert "/edit" in response.text

    @patch("web.services.journal.get_journal")
    def test_journal_metadata_displayed(self, mock_get: MagicMock) -> None:
        """Journal page displays frontmatter metadata as tag badges."""
        mock_get.return_value = {
            "metadata": {
                "title": "元数据测试",
                "date": "2026-03-07T14:30:00",
                "mood": ["专注", "充实"],
                "tags": ["python", "重构"],
                "topic": ["work"],
                "people": ["乐乐"],
                "location": "Lagos, Nigeria",
                "weather": "晴天 28°C",
            },
            "html_content": "<h1>元数据测试</h1>",
            "attachments": [],
        }

        from web.app import create_app
        from fastapi.testclient import TestClient

        app = create_app()
        client = TestClient(app)
        response = client.get("/journal/2026/03/test.md")
        html = response.text

        assert "专注" in html
        assert "充实" in html
        assert "python" in html
        assert "乐乐" in html
        assert "Lagos" in html
        assert "晴天" in html


class TestJournalRouterRegistration:
    """Verify journal router is registered in app."""

    def test_journal_route_exists(self) -> None:
        """App has a route registered at /journal/{path}."""
        from web.app import create_app
        app = create_app()
        paths = [r.path for r in app.routes if hasattr(r, "path")]
        journal_paths = [p for p in paths if "journal" in p]
        assert len(journal_paths) > 0, f"No journal routes found. Routes: {paths}"
```

- [ ] **Step 4: Run route tests to verify they fail**

```bash
python -m pytest tests/unit/test_web_journal_search.py::TestJournalRoute -v
python -m pytest tests/unit/test_web_journal_search.py::TestJournalRouterRegistration -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'web.services.journal'` or `No module named 'web.routes.journal'`.

- [ ] **Step 5: Implement `web/services/journal.py`**

```python
"""Journal view service — parse and render journal files.

Wraps tools.lib.frontmatter.parse_journal_file() and Python markdown
library to produce rendered HTML + metadata for the journal view page.

This service handles path traversal validation and Markdown→HTML rendering.
Per design-spec §5.3, Markdown is rendered server-side, not client-side.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import markdown

from tools.lib.config import JOURNALS_DIR, ATTACHMENTS_DIR
from tools.lib.frontmatter import parse_journal_file

logger = logging.getLogger(__name__)

# Markdown extensions for rendering (per §5.3)
MARKDOWN_EXTENSIONS: list[str] = ["fenced_code", "tables"]

# Frontmatter fields to extract for display
METADATA_DISPLAY_FIELDS: list[str] = [
    "title", "date", "location", "weather", "mood", "tags",
    "topic", "people", "project", "abstract",
]


def _validate_path(relative_path: str) -> Path:
    """Validate relative_path is within JOURNALS_DIR.

    Resolves symlinks and '..' components, then verifies the resolved
    path is still under JOURNALS_DIR.

    Args:
        relative_path: Relative path from JOURNALS_DIR root.

    Returns:
        Resolved absolute Path to the journal file.

    Raises:
        ValueError: If resolved path escapes JOURNALS_DIR (traversal attack).
    """
    journals_root = JOURNALS_DIR.resolve()
    target = (JOURNALS_DIR / relative_path).resolve()

    if not str(target).startswith(str(journals_root)):
        raise ValueError(
            f"Path traversal detected: {relative_path!r} resolves outside JOURNALS_DIR"
        )

    return target


def get_journal(relative_path: str) -> dict[str, Any]:
    """Load, parse, and render a journal file.

    Args:
        relative_path: Path relative to JOURNALS_DIR
            (e.g., "2026/03/life-index_2026-03-07_001.md").

    Returns:
        Dict with keys:
        - "metadata": dict of frontmatter fields for display
        - "html_content": rendered HTML from Markdown body
        - "attachments": list of attachment info dicts (future use)

        On error:
        - "error": error message string

    Raises:
        ValueError: If path traversal is detected.
    """
    # ── Path validation ──
    file_path = _validate_path(relative_path)

    if not file_path.exists():
        return {"error": "日志未找到"}

    # ── Parse journal ──
    parsed = parse_journal_file(file_path)

    if "_error" in parsed:
        logger.warning("Failed to parse journal %s: %s", relative_path, parsed["_error"])
        return {"error": f"日志解析失败: {parsed['_error']}"}

    # ── Extract metadata for display ──
    metadata: dict[str, Any] = {}
    for field in METADATA_DISPLAY_FIELDS:
        if field in parsed:
            metadata[field] = parsed[field]

    # Use _title as display title (extracted from # heading or filename)
    if "_title" in parsed:
        metadata["title"] = parsed.get("title") or parsed["_title"]

    # ── Render Markdown → HTML ──
    body = parsed.get("_body", "")
    try:
        html_content = markdown.markdown(
            body,
            extensions=MARKDOWN_EXTENSIONS,
            output_format="html",
        )
    except Exception:
        logger.warning("Markdown rendering failed for %s, using raw text", relative_path)
        html_content = f"<pre>{body}</pre>"

    # ── Collect attachment references (future use) ──
    attachments: list[dict[str, Any]] = []

    return {
        "metadata": metadata,
        "html_content": html_content,
        "attachments": attachments,
    }
```

- [ ] **Step 6: Implement `web/routes/journal.py`**

```python
"""Journal view route — GET /journal/{path} renders a journal.

Calls journal service and passes metadata + rendered HTML to the template.
Handles path traversal by catching ValueError and returning 404.
Per design-spec §6.3, path traversal returns 404 (no info leakage).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from web.services.journal import get_journal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/journal")


@router.get("/{path:path}", response_class=HTMLResponse)
async def view_journal(request: Request, path: str) -> HTMLResponse:
    """Render a journal view page.

    Args:
        request: FastAPI request.
        path: Relative path to journal file within JOURNALS_DIR.

    Returns:
        Rendered journal.html template, or 404 error page.
    """
    templates = request.app.state.templates

    try:
        result = get_journal(path)
    except ValueError:
        # Path traversal attempt — return 404 without info leakage
        logger.warning("Path traversal attempt blocked: %s", path)
        return templates.TemplateResponse(
            "journal.html",
            {"request": request, "error": "日志未找到"},
            status_code=404,
        )

    if "error" in result:
        return templates.TemplateResponse(
            "journal.html",
            {"request": request, "error": result["error"]},
            status_code=404,
        )

    return templates.TemplateResponse(
        "journal.html",
        {
            "request": request,
            "metadata": result["metadata"],
            "html_content": result["html_content"],
            "attachments": result["attachments"],
            "journal_path": path,
        },
    )
```

- [ ] **Step 7: Create `web/templates/journal.html`**

```html
{% extends "base.html" %}

{% block title %}
{% if metadata %}{{ metadata.title or "日志" }} — Life Index{% else %}日志未找到 — Life Index{% endif %}
{% endblock %}

{% block content %}
{% if error %}
<!-- ── Error State ──────────────────────────────────────── -->
<div class="max-w-3xl mx-auto text-center py-16">
    <div class="text-6xl mb-4">📄</div>
    <h1 class="text-2xl font-bold text-gray-800 dark:text-gray-200 mb-2">
        {{ error }}
    </h1>
    <p class="text-gray-500 dark:text-gray-400 mb-6">
        请检查日志路径是否正确。
    </p>
    <div class="flex justify-center gap-4">
        <a href="/"
           class="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm">
            返回仪表盘
        </a>
        <a href="/search"
           class="px-4 py-2 bg-gray-200 hover:bg-gray-300 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-800 dark:text-gray-200 rounded-lg text-sm">
            搜索日志
        </a>
    </div>
</div>

{% else %}
<!-- ── Journal View ────────────────────────────────────── -->
<div class="max-w-3xl mx-auto">

    <!-- Navigation bar -->
    <div class="flex justify-between items-center mb-6">
        <a href="/search"
           class="text-sm text-gray-500 dark:text-gray-400 hover:text-indigo-600 dark:hover:text-indigo-400">
            ← 返回搜索
        </a>
        <a href="/journal/{{ journal_path }}/edit"
           class="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm">
            编辑
        </a>
    </div>

    <!-- Metadata header -->
    <header class="mb-8 pb-6 border-b border-gray-200 dark:border-gray-700">
        <h1 class="text-3xl font-bold text-gray-900 dark:text-gray-100 mb-4">
            {{ metadata.title or "无标题" }}
        </h1>

        <div class="flex flex-wrap gap-4 text-sm text-gray-500 dark:text-gray-400 mb-4">
            {% if metadata.date %}
            <span>📅 {{ metadata.date }}</span>
            {% endif %}
            {% if metadata.location %}
            <span>📍 {{ metadata.location }}</span>
            {% endif %}
            {% if metadata.weather %}
            <span>🌤️ {{ metadata.weather }}</span>
            {% endif %}
        </div>

        <!-- Topic badges -->
        {% if metadata.topic %}
        <div class="flex flex-wrap gap-2 mb-3">
            <span class="text-xs text-gray-400 dark:text-gray-500 self-center">主题:</span>
            {% for t in metadata.topic %}
            <a href="/search?topic={{ t }}"
               class="text-xs px-2.5 py-1 rounded-full bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 hover:bg-blue-200 dark:hover:bg-blue-800/40">
                {{ t }}
            </a>
            {% endfor %}
        </div>
        {% endif %}

        <!-- Mood badges -->
        {% if metadata.mood %}
        <div class="flex flex-wrap gap-2 mb-3">
            <span class="text-xs text-gray-400 dark:text-gray-500 self-center">情绪:</span>
            {% for m in metadata.mood %}
            <span class="text-xs px-2.5 py-1 rounded-full bg-pink-100 dark:bg-pink-900/30 text-pink-700 dark:text-pink-300">
                {{ m }}
            </span>
            {% endfor %}
        </div>
        {% endif %}

        <!-- Tag badges -->
        {% if metadata.tags %}
        <div class="flex flex-wrap gap-2 mb-3">
            <span class="text-xs text-gray-400 dark:text-gray-500 self-center">标签:</span>
            {% for tag in metadata.tags %}
            <a href="/search?q={{ tag | urlencode }}"
               class="text-xs px-2.5 py-1 rounded-full bg-indigo-100 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-300 hover:bg-indigo-200 dark:hover:bg-indigo-800/40">
                {{ tag }}
            </a>
            {% endfor %}
        </div>
        {% endif %}

        <!-- People badges -->
        {% if metadata.people %}
        <div class="flex flex-wrap gap-2 mb-3">
            <span class="text-xs text-gray-400 dark:text-gray-500 self-center">人物:</span>
            {% for person in metadata.people %}
            <a href="/search?q={{ person | urlencode }}"
               class="text-xs px-2.5 py-1 rounded-full bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300 hover:bg-green-200 dark:hover:bg-green-800/40">
                {{ person }}
            </a>
            {% endfor %}
        </div>
        {% endif %}

        <!-- Project -->
        {% if metadata.project %}
        <div class="text-sm text-gray-500 dark:text-gray-400">
            📁 项目: {{ metadata.project }}
        </div>
        {% endif %}
    </header>

    <!-- Rendered Markdown content -->
    <article class="prose prose-indigo dark:prose-invert max-w-none
                    prose-headings:text-gray-800 dark:prose-headings:text-gray-200
                    prose-p:text-gray-700 dark:prose-p:text-gray-300
                    prose-code:text-indigo-600 dark:prose-code:text-indigo-400
                    prose-pre:bg-gray-50 dark:prose-pre:bg-gray-800/50">
        {{ html_content | safe }}
    </article>

    <!-- Attachments (if any) -->
    {% if attachments %}
    <section class="mt-8 pt-6 border-t border-gray-200 dark:border-gray-700">
        <h2 class="text-lg font-semibold mb-4 text-gray-800 dark:text-gray-200">
            附件
        </h2>
        <div class="grid grid-cols-2 md:grid-cols-3 gap-4">
            {% for att in attachments %}
            <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-3">
                {% if att.type == "image" %}
                <img src="/attachments/{{ att.path }}" alt="{{ att.name }}"
                     class="w-full h-32 object-cover rounded mb-2">
                {% elif att.type == "video" %}
                <video controls class="w-full h-32 rounded mb-2">
                    <source src="/attachments/{{ att.path }}">
                </video>
                {% elif att.type == "audio" %}
                <audio controls class="w-full mb-2">
                    <source src="/attachments/{{ att.path }}">
                </audio>
                {% else %}
                <div class="h-32 flex items-center justify-center bg-gray-100 dark:bg-gray-700 rounded mb-2">
                    <span class="text-3xl">📎</span>
                </div>
                {% endif %}
                <p class="text-xs text-gray-500 dark:text-gray-400 truncate">
                    {{ att.name }}
                </p>
            </div>
            {% endfor %}
        </div>
    </section>
    {% endif %}

    <!-- Bottom navigation -->
    <div class="mt-8 pt-6 border-t border-gray-200 dark:border-gray-700 flex justify-between">
        <a href="/"
           class="text-sm text-gray-500 dark:text-gray-400 hover:text-indigo-600 dark:hover:text-indigo-400">
            ← 返回仪表盘
        </a>
        <a href="/journal/{{ journal_path }}/edit"
           class="text-sm text-indigo-600 dark:text-indigo-400 hover:text-indigo-700 dark:hover:text-indigo-300">
            编辑此日志 →
        </a>
    </div>

</div>
{% endif %}
{% endblock %}
```

- [ ] **Step 8: Register journal router in `web/app.py`**

Add the following import and `include_router` call inside `create_app()`, after the dashboard router registration and before `return app`:

```python
    from web.routes.journal import router as journal_router
    app.include_router(journal_router)
```

The import is inside `create_app()` to maintain the lazy-import pattern.

- [ ] **Step 9: Run tests to verify they pass**

```bash
python -m pytest tests/unit/test_web_journal_search.py -k "Journal" -v
```

Expected: All `TestJournalServicePathSafety`, `TestJournalServiceParsing`, `TestJournalRoute`, and `TestJournalRouterRegistration` tests pass.

- [ ] **Step 10: Verify existing tests still pass**

```bash
python -m pytest tests/unit/ -q
```

Expected: 0 failures (including all Phase 1 + Phase 2 tests).

- [ ] **Step 11: Commit**

```bash
git add web/services/journal.py web/routes/journal.py web/templates/journal.html web/app.py tests/unit/test_web_journal_search.py
git commit -m "feat(web): add journal view with Markdown rendering and path traversal protection"
```

---

## Task 10: Search (`web/services/search.py` + `web/routes/search.py` + `search.html` + `partials/search_results.html`)

**Files:**
- Create: `web/services/search.py`
- Create: `web/routes/search.py`
- Create: `web/templates/search.html`
- Create: `web/templates/partials/search_results.html`
- Modify: `web/app.py` (register search router)
- Test: `tests/unit/test_web_journal_search.py` (append)

**Difficulty:** Hard (~50 min)

**Acceptance Criteria:**
1. `search_journals_web(params)` calls `hierarchical_search()` with correctly mapped parameters and returns a Web-friendly result dict
2. `GET /search` without parameters renders the empty search form page
3. `GET /search?q=关键词` renders search results inline (full page)
4. `GET /search?q=关键词` with `HX-Request` header returns only `partials/search_results.html` (HTMX partial)
5. Search parameters map correctly: `q`→`query`, `topic`→`topic`, `date_from`→`date_from`, `date_to`→`date_to`, `mood`→`mood`, `level`→`level`
6. Each result item shows: title, date, mood badges, snippet (if available), and links to journal view page
7. Empty results show "未找到匹配的日志" message with search tips
8. Search form includes: text input, topic dropdown (7 topics), date range pickers, mood input
9. Page title is `"搜索 — Life Index"` (or `"搜索: {query} — Life Index"` when query present)
10. Search route is registered in `create_app()` via `app.include_router()`
11. Performance info (total_time_ms, total_found) displayed in results footer
12. Results link to `/journal/{path}` for each matched journal

**Subagent Governance:**
- MUST DO: Import `hierarchical_search` from `tools.search_journals.core`
- MUST DO: Map Web query parameters to `hierarchical_search()` kwargs correctly (see mapping table in §5.2)
- MUST DO: Default `level=3` and `semantic=True` for Web searches
- MUST DO: Check for `HX-Request` header to determine full-page vs. HTMX partial response
- MUST DO: Use `app.state.templates.TemplateResponse()` for both full-page and partial rendering
- MUST DO: Include `request` in template context
- MUST DO: Register search router in `web/app.py` via `app.include_router(search_router)` using lazy import
- MUST DO: Use Chinese text for all user-facing strings
- MUST DO: Handle `hierarchical_search()` errors gracefully — return empty results with error message
- MUST DO: Display `merged_results` from search output (primary result list after RRF fusion)
- MUST DO: Link each result to `/journal/{result.path}` (the `path` field in merged_results is relative to USER_DATA_DIR)
- MUST DO: Use Tailwind CSS classes consistent with `base.html` and `dashboard.html`
- MUST DO: The search form must use `GET` method (results are bookmarkable URLs)
- MUST NOT DO: Import or call any `web/services/journal.py` code — this is an independent service
- MUST NOT DO: Perform filesystem access directly — delegate to `hierarchical_search()`
- MUST NOT DO: Create new API endpoints — this is a server-rendered page with HTMX partial support only
- MUST NOT DO: Modify any `tools/` module code
- MUST NOT DO: Skip the HTMX partial rendering — full page AND partial MUST both work

**Error Handling:**
- `hierarchical_search()` raises an exception → catch, log, return empty result set with error message
- Invalid parameters (e.g., bad date format) → render form with validation error message, do not crash
- No search parameters → render empty search form (no search executed)

**TDD Steps:**

- [ ] **Step 1: Write the failing tests — search service**

Append to `tests/unit/test_web_journal_search.py`:

```python
# ── Task 10: Search Service + Route ───────────────────────────


class TestSearchService:
    """Test search service parameter mapping and result handling."""

    @patch("web.services.search.hierarchical_search")
    def test_search_calls_hierarchical_search(
        self, mock_search: MagicMock
    ) -> None:
        """search_journals_web calls hierarchical_search with mapped params."""
        mock_search.return_value = {
            "success": True,
            "merged_results": [],
            "total_found": 0,
            "performance": {"total_time_ms": 10.0},
            "semantic_available": True,
        }

        from web.services.search import search_journals_web

        result = search_journals_web(query="测试关键词", topic="work")
        mock_search.assert_called_once()

        # Verify parameter mapping
        call_kwargs = mock_search.call_args[1]
        assert call_kwargs["query"] == "测试关键词"
        assert call_kwargs["topic"] == "work"
        assert call_kwargs["level"] == 3  # default
        assert call_kwargs["semantic"] is True  # default

    @patch("web.services.search.hierarchical_search")
    def test_search_returns_web_friendly_result(
        self, mock_search: MagicMock
    ) -> None:
        """search_journals_web returns a Web-friendly result dict."""
        mock_search.return_value = {
            "success": True,
            "merged_results": [
                {
                    "path": "C:/Users/.../Documents/Life-Index/Journals/2026/03/life-index_2026-03-07_001.md",
                    "journal_route_path": "2026/03/life-index_2026-03-07_001.md",
                    "title": "测试日志",
                    "date": "2026-03-07",
                    "rrf_score": 0.031,
                    "snippet": "这是匹配的片段...",
                },
            ],
            "total_found": 1,
            "performance": {"total_time_ms": 42.5},
            "semantic_available": True,
        }

        from web.services.search import search_journals_web

        result = search_journals_web(query="测试")
        assert result["success"] is True
        assert result["total_found"] == 1
        assert len(result["results"]) == 1
        assert result["results"][0]["title"] == "测试日志"
        assert result["results"][0]["journal_route_path"] == "2026/03/life-index_2026-03-07_001.md"
        assert "time_ms" in result

    @patch("web.services.search.hierarchical_search")
    def test_search_empty_query_no_search(
        self, mock_search: MagicMock
    ) -> None:
        """Empty query with no filters returns empty results without calling search."""
        from web.services.search import search_journals_web

        result = search_journals_web()
        mock_search.assert_not_called()
        assert result["total_found"] == 0
        assert result["results"] == []

    @patch("web.services.search.hierarchical_search")
    def test_search_error_handled_gracefully(
        self, mock_search: MagicMock
    ) -> None:
        """Search errors return empty results with error message."""
        mock_search.side_effect = Exception("Database error")

        from web.services.search import search_journals_web

        result = search_journals_web(query="测试")
        assert result["success"] is False
        assert result["total_found"] == 0
        assert "error" in result

    @patch("web.services.search.hierarchical_search")
    def test_search_date_params_passed(
        self, mock_search: MagicMock
    ) -> None:
        """Date range parameters are correctly passed to hierarchical_search."""
        mock_search.return_value = {
            "success": True,
            "merged_results": [],
            "total_found": 0,
            "performance": {"total_time_ms": 5.0},
            "semantic_available": True,
        }

        from web.services.search import search_journals_web

        search_journals_web(
            date_from="2026-01-01",
            date_to="2026-03-31",
        )
        call_kwargs = mock_search.call_args[1]
        assert call_kwargs["date_from"] == "2026-01-01"
        assert call_kwargs["date_to"] == "2026-03-31"

    @patch("web.services.search.hierarchical_search")
    def test_search_mood_param_as_list(
        self, mock_search: MagicMock
    ) -> None:
        """Mood parameter is passed as a list."""
        mock_search.return_value = {
            "success": True,
            "merged_results": [],
            "total_found": 0,
            "performance": {"total_time_ms": 5.0},
            "semantic_available": True,
        }

        from web.services.search import search_journals_web

        search_journals_web(mood="专注")
        call_kwargs = mock_search.call_args[1]
        assert call_kwargs["mood"] == ["专注"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/unit/test_web_journal_search.py::TestSearchService -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'web.services.search'`.

- [ ] **Step 3: Write the failing tests — search route**

Append to `tests/unit/test_web_journal_search.py`:

```python
class TestSearchRoute:
    """Test GET /search route."""

    def test_search_page_returns_200(self) -> None:
        """GET /search without params returns 200 with empty form."""
        from web.app import create_app
        from fastapi.testclient import TestClient

        app = create_app()
        client = TestClient(app)
        response = client.get("/search")
        assert response.status_code == 200
        assert "搜索" in response.text

    @patch("web.services.search.search_journals_web")
    def test_search_with_query_returns_results(
        self, mock_search: MagicMock
    ) -> None:
        """GET /search?q=keyword renders search results."""
        mock_search.return_value = {
            "success": True,
            "results": [
                {
                    "title": "匹配的日志",
                    "date": "2026-03-07",
                    "journal_route_path": "2026/03/test.md",
                    "mood": ["专注"],
                    "snippet": "这里有关键词...",
                },
            ],
            "total_found": 1,
            "time_ms": 42.5,
        }

        from web.app import create_app
        from fastapi.testclient import TestClient

        app = create_app()
        client = TestClient(app)
        response = client.get("/search?q=关键词")
        assert response.status_code == 200
        assert "匹配的日志" in response.text
        assert "2026-03-07" in response.text

    @patch("web.services.search.search_journals_web")
    def test_search_htmx_returns_partial(
        self, mock_search: MagicMock
    ) -> None:
        """GET /search with HX-Request header returns partial HTML only."""
        mock_search.return_value = {
            "success": True,
            "results": [
                {
                    "title": "HTMX结果",
                    "date": "2026-03-07",
                    "journal_route_path": "2026/03/test.md",
                    "mood": [],
                    "snippet": None,
                },
            ],
            "total_found": 1,
            "time_ms": 10.0,
        }

        from web.app import create_app
        from fastapi.testclient import TestClient

        app = create_app()
        client = TestClient(app)
        response = client.get(
            "/search?q=测试",
            headers={"HX-Request": "true"},
        )
        assert response.status_code == 200
        html = response.text
        assert "HTMX结果" in html
        # Partial should NOT contain full page structure
        assert "<!DOCTYPE" not in html

    @patch("web.services.search.search_journals_web")
    def test_search_empty_results_message(
        self, mock_search: MagicMock
    ) -> None:
        """Empty search results show helpful message."""
        mock_search.return_value = {
            "success": True,
            "results": [],
            "total_found": 0,
            "time_ms": 15.0,
        }

        from web.app import create_app
        from fastapi.testclient import TestClient

        app = create_app()
        client = TestClient(app)
        response = client.get("/search?q=不存在的关键词")
        assert response.status_code == 200
        assert "未找到" in response.text

    @patch("web.services.search.search_journals_web")
    def test_search_results_link_to_journal(
        self, mock_search: MagicMock
    ) -> None:
        """Search results contain links to journal view page."""
        mock_search.return_value = {
            "success": True,
            "results": [
                {
                    "title": "链接测试",
                    "date": "2026-03-07",
                    "path": "Journals/2026/03/life-index_2026-03-07_001.md",
                    "mood": [],
                    "snippet": None,
                },
            ],
            "total_found": 1,
            "time_ms": 5.0,
        }

        from web.app import create_app
        from fastapi.testclient import TestClient

        app = create_app()
        client = TestClient(app)
        response = client.get("/search?q=链接")
        html = response.text
        assert "/journal/2026/03/life-index_2026-03-07_001.md" in html

    def test_search_form_has_all_controls(self) -> None:
        """Search form includes all required input controls."""
        from web.app import create_app
        from fastapi.testclient import TestClient

        app = create_app()
        client = TestClient(app)
        response = client.get("/search")
        html = response.text

        # Search text input
        assert 'name="q"' in html
        # Topic selector
        assert "topic" in html
        # Date range
        assert "date_from" in html
        assert "date_to" in html

    @patch("web.services.search.search_journals_web")
    def test_search_performance_displayed(
        self, mock_search: MagicMock
    ) -> None:
        """Search results footer shows performance info."""
        mock_search.return_value = {
            "success": True,
            "results": [
                {
                    "title": "性能测试",
                    "date": "2026-03-07",
                    "path": "Journals/2026/03/test.md",
                    "mood": [],
                    "snippet": None,
                },
            ],
            "total_found": 1,
            "time_ms": 42.5,
        }

        from web.app import create_app
        from fastapi.testclient import TestClient

        app = create_app()
        client = TestClient(app)
        response = client.get("/search?q=性能")
        html = response.text
        # Should show result count and/or time
        assert "1" in html  # total_found


class TestSearchRouterRegistration:
    """Verify search router is registered in app."""

    def test_search_route_exists(self) -> None:
        """App has a route registered at /search."""
        from web.app import create_app
        app = create_app()
        paths = [r.path for r in app.routes if hasattr(r, "path")]
        assert "/search" in paths, f"No /search route found. Routes: {paths}"
```

- [ ] **Step 4: Run route tests to verify they fail**

```bash
python -m pytest tests/unit/test_web_journal_search.py::TestSearchRoute -v
python -m pytest tests/unit/test_web_journal_search.py::TestSearchRouterRegistration -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'web.services.search'` or `No module named 'web.routes.search'`.

- [ ] **Step 5: Implement `web/services/search.py`**

```python
"""Search service — wrap hierarchical_search for Web consumption.

Maps Web query parameters to hierarchical_search() kwargs and
transforms raw search results into a Web-friendly format.

This service NEVER accesses the filesystem directly — all search
is delegated to tools.search_journals.core.hierarchical_search().
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from tools.search_journals.core import hierarchical_search

logger = logging.getLogger(__name__)

# Valid topic values per AGENTS.md
VALID_TOPICS: list[str] = [
    "work", "learn", "health", "relation", "think", "create", "life",
]


def search_journals_web(
    *,
    query: Optional[str] = None,
    topic: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    mood: Optional[str] = None,
    level: int = 3,
    semantic: bool = True,
    limit: Optional[int] = None,
) -> dict[str, Any]:
    """Execute a journal search with Web-friendly parameters and results.

    Args:
        query: Search keywords.
        topic: Filter by topic (one of VALID_TOPICS).
        date_from: Start date (YYYY-MM-DD).
        date_to: End date (YYYY-MM-DD).
        mood: Filter by mood (single mood string, converted to list).
        level: Search level (1=index, 2=metadata, 3=full pipeline).
        semantic: Enable semantic search.
        limit: Max results to return.

    Returns:
        Dict with keys:
        - "success": bool
        - "results": list of result dicts with title, date, path, mood, snippet
        - "total_found": int
        - "time_ms": float
        - "error": str (only on failure)
    """
    # No parameters → don't execute search
    has_params = any([query, topic, date_from, date_to, mood])
    if not has_params:
        return {
            "success": True,
            "results": [],
            "total_found": 0,
            "time_ms": 0.0,
        }

    # Build search kwargs
    search_kwargs: dict[str, Any] = {
        "query": query,
        "topic": topic,
        "date_from": date_from,
        "date_to": date_to,
        "mood": [mood] if mood else None,
        "level": level,
        "semantic": semantic,
    }

    try:
        raw_result = hierarchical_search(**search_kwargs)
    except Exception as e:
        logger.exception("Search failed: %s", e)
        return {
            "success": False,
            "results": [],
            "total_found": 0,
            "time_ms": 0.0,
            "error": f"搜索失败: {e}",
        }

    # Transform merged_results into Web-friendly format
    merged = raw_result.get("merged_results", [])

    # Apply limit
    if limit and limit > 0:
        merged = merged[:limit]

    results: list[dict[str, Any]] = []
    for item in merged:
        results.append({
            "title": item.get("title", "无标题"),
            "date": item.get("date", ""),
            "path": item.get("path", ""),
            "mood": item.get("mood", []),
            "snippet": item.get("snippet"),
            "rrf_score": item.get("rrf_score"),
            "tags": item.get("tags", []),
            "topic": item.get("topic", []),
        })

    return {
        "success": raw_result.get("success", True),
        "results": results,
        "total_found": raw_result.get("total_found", len(results)),
        "time_ms": raw_result.get("performance", {}).get("total_time_ms", 0.0),
        "semantic_available": raw_result.get("semantic_available", False),
    }
```

- [ ] **Step 6: Implement `web/routes/search.py`**

```python
"""Search route — GET /search renders the search page.

Supports both full-page rendering and HTMX partial updates.
When HX-Request header is present, returns only the results partial.
Per design-spec §5.2, search uses GET method for bookmarkable URLs.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse

from web.services.search import search_journals_web, VALID_TOPICS

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/search", response_class=HTMLResponse)
async def search_page(
    request: Request,
    q: Optional[str] = Query(None, description="Search keywords"),
    topic: Optional[str] = Query(None, description="Filter by topic"),
    date_from: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    mood: Optional[str] = Query(None, description="Filter by mood"),
    level: int = Query(3, ge=1, le=3, description="Search level"),
) -> HTMLResponse:
    """Render the search page with optional search results.

    Without parameters: renders empty search form.
    With parameters: executes search and renders results.
    With HX-Request header: returns only the results partial.
    """
    templates = request.app.state.templates

    # Execute search if any parameters provided
    search_result = search_journals_web(
        query=q,
        topic=topic,
        date_from=date_from,
        date_to=date_to,
        mood=mood,
        level=level,
    )

    has_query = any([q, topic, date_from, date_to, mood])

    context = {
        "request": request,
        "search_result": search_result,
        "has_query": has_query,
        "query": q or "",
        "topic": topic or "",
        "date_from": date_from or "",
        "date_to": date_to or "",
        "mood": mood or "",
        "level": level,
        "valid_topics": VALID_TOPICS,
    }

    # HTMX partial rendering
    is_htmx = request.headers.get("HX-Request") == "true"
    if is_htmx and has_query:
        return templates.TemplateResponse(
            "partials/search_results.html",
            context,
        )

    # Full page rendering
    return templates.TemplateResponse("search.html", context)
```

- [ ] **Step 7: Create `web/templates/search.html`**

```html
{% extends "base.html" %}

{% block title %}
{% if has_query %}搜索: {{ query }} — Life Index{% else %}搜索 — Life Index{% endif %}
{% endblock %}

{% block content %}
<div class="max-w-4xl mx-auto">

    <h1 class="text-2xl font-bold text-gray-800 dark:text-gray-200 mb-6">
        搜索日志
    </h1>

    <!-- ── Search Form ─────────────────────────────────────── -->
    <form method="GET" action="/search"
          hx-get="/search"
          hx-target="#search-results"
          hx-push-url="true"
          class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 mb-8">

        <!-- Main search input -->
        <div class="mb-4">
            <div class="relative">
                <input type="text"
                       name="q"
                       value="{{ query }}"
                       placeholder="输入关键词搜索日志..."
                       class="w-full px-4 py-3 pl-10 rounded-lg border border-gray-300 dark:border-gray-600
                              bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-200
                              focus:ring-2 focus:ring-indigo-500 focus:border-transparent
                              placeholder-gray-400 dark:placeholder-gray-500">
                <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <span class="text-gray-400">🔍</span>
                </div>
            </div>
        </div>

        <!-- Filter row -->
        <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
            <!-- Topic dropdown -->
            <div>
                <label class="block text-xs text-gray-500 dark:text-gray-400 mb-1">主题</label>
                <select name="topic"
                        class="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600
                               bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-200 text-sm">
                    <option value="">全部主题</option>
                    {% for t in valid_topics %}
                    <option value="{{ t }}" {% if topic == t %}selected{% endif %}>{{ t }}</option>
                    {% endfor %}
                </select>
            </div>

            <!-- Date from -->
            <div>
                <label class="block text-xs text-gray-500 dark:text-gray-400 mb-1">开始日期</label>
                <input type="date"
                       name="date_from"
                       value="{{ date_from }}"
                       class="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600
                              bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-200 text-sm">
            </div>

            <!-- Date to -->
            <div>
                <label class="block text-xs text-gray-500 dark:text-gray-400 mb-1">结束日期</label>
                <input type="date"
                       name="date_to"
                       value="{{ date_to }}"
                       class="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600
                              bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-200 text-sm">
            </div>

            <!-- Mood filter -->
            <div>
                <label class="block text-xs text-gray-500 dark:text-gray-400 mb-1">情绪</label>
                <input type="text"
                       name="mood"
                       value="{{ mood }}"
                       placeholder="如：专注、平静"
                       class="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600
                              bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-200 text-sm
                              placeholder-gray-400 dark:placeholder-gray-500">
            </div>
        </div>

        <!-- Submit button -->
        <div class="flex justify-end">
            <button type="submit"
                    class="px-6 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm
                           transition-colors">
                搜索
            </button>
        </div>
    </form>

    <!-- ── Search Results ──────────────────────────────────── -->
    <div id="search-results">
        {% if has_query %}
            {% include "partials/search_results.html" %}
        {% endif %}
    </div>

</div>
{% endblock %}
```

- [ ] **Step 8: Create `web/templates/partials/search_results.html`**

```html
<!-- Search results partial — rendered by HTMX or included in full page -->

{% if search_result.error %}
<!-- Error state -->
<div class="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-6 text-center">
    <p class="text-red-600 dark:text-red-400">
        {{ search_result.error }}
    </p>
</div>

{% elif search_result.results %}
<!-- Results header -->
<div class="flex justify-between items-center mb-4">
    <p class="text-sm text-gray-500 dark:text-gray-400">
        找到 <span class="font-semibold text-gray-700 dark:text-gray-300">{{ search_result.total_found }}</span> 条结果
        {% if search_result.time_ms %}
        <span class="ml-2">（{{ "%.1f" | format(search_result.time_ms) }} ms）</span>
        {% endif %}
    </p>
</div>

<!-- Result list -->
<div class="space-y-4">
    {% for item in search_result.results %}
    <a href="/journal/{{ item.path }}"
       class="block bg-white dark:bg-gray-800 rounded-lg shadow hover:shadow-md
              transition-shadow p-5 group">
        <div class="flex justify-between items-start mb-2">
            <h3 class="text-lg font-semibold text-gray-800 dark:text-gray-200
                       group-hover:text-indigo-600 dark:group-hover:text-indigo-400">
                {{ item.title }}
            </h3>
            <span class="text-sm text-gray-400 dark:text-gray-500 whitespace-nowrap ml-4">
                {{ item.date }}
            </span>
        </div>

        {% if item.snippet %}
        <p class="text-sm text-gray-600 dark:text-gray-400 mb-3 line-clamp-2">
            {{ item.snippet }}
        </p>
        {% endif %}

        <div class="flex flex-wrap gap-1.5">
            {% if item.topic %}
            {% for t in item.topic %}
            <span class="text-xs px-2 py-0.5 rounded-full bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300">
                {{ t }}
            </span>
            {% endfor %}
            {% endif %}

            {% if item.mood %}
            {% for m in item.mood %}
            <span class="text-xs px-2 py-0.5 rounded-full bg-pink-100 dark:bg-pink-900/30 text-pink-700 dark:text-pink-300">
                {{ m }}
            </span>
            {% endfor %}
            {% endif %}

            {% if item.tags %}
            {% for tag in item.tags %}
            <span class="text-xs px-2 py-0.5 rounded-full bg-indigo-100 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-300">
                {{ tag }}
            </span>
            {% endfor %}
            {% endif %}
        </div>
    </a>
    {% endfor %}
</div>

{% else %}
<!-- Empty results -->
<div class="bg-white dark:bg-gray-800 rounded-lg shadow p-8 text-center">
    <div class="text-4xl mb-4">🔍</div>
    <p class="text-lg text-gray-600 dark:text-gray-400 mb-2">
        未找到匹配的日志
    </p>
    <p class="text-sm text-gray-400 dark:text-gray-500">
        试试其他关键词，或放宽筛选条件。
    </p>
</div>
{% endif %}
```

- [ ] **Step 9: Register search router in `web/app.py`**

Add the following import and `include_router` call inside `create_app()`, after the journal router registration and before `return app`:

```python
    from web.routes.search import router as search_router
    app.include_router(search_router)
```

The import is inside `create_app()` to maintain the lazy-import pattern.

- [ ] **Step 10: Run tests to verify they pass**

```bash
python -m pytest tests/unit/test_web_journal_search.py -k "Search" -v
```

Expected: All `TestSearchService`, `TestSearchRoute`, and `TestSearchRouterRegistration` tests pass.

- [ ] **Step 11: Run all Phase 3 tests**

```bash
python -m pytest tests/unit/test_web_journal_search.py -v
```

Expected: All Task 9 + Task 10 tests pass.

- [ ] **Step 12: Verify existing tests still pass**

```bash
python -m pytest tests/unit/ -q
```

Expected: 0 failures (including all Phase 1 + Phase 2 tests).

- [ ] **Step 13: Commit**

```bash
git add web/services/search.py web/routes/search.py web/templates/search.html web/templates/partials/search_results.html web/app.py tests/unit/test_web_journal_search.py
git commit -m "feat(web): add search page with HTMX partial rendering and parameter mapping"
```

---

## Phase 3 Completion Checklist

Run all checks before declaring Phase 3 complete:

- [ ] **All Phase 3 tests pass:**

```bash
python -m pytest tests/unit/test_web_journal_search.py -v
```

Expected: All tests in `TestJournalServicePathSafety`, `TestJournalServiceParsing`, `TestJournalRoute`, `TestJournalRouterRegistration`, `TestSearchService`, `TestSearchRoute`, `TestSearchRouterRegistration` pass.

- [ ] **All existing tests still pass:**

```bash
python -m pytest tests/unit/ -q
```

Expected: 0 failures (including all Phase 1 + Phase 2 tests).

- [ ] **Journal view renders at GET /journal/{path}:**

```bash
life-index serve &
sleep 2
# Test with a known journal file path (adjust to your data)
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8765/journal/2026/03/life-index_2026-03-07_001.md
# Expected: 200 (if file exists) or 404 (if not)
kill %1
```

- [ ] **Path traversal returns 404:**

```bash
life-index serve &
sleep 2
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8765/journal/../../etc/passwd
# Expected: 404
kill %1
```

- [ ] **Search form renders at GET /search:**

```bash
life-index serve &
sleep 2
curl -s http://127.0.0.1:8765/search | head -5
kill %1
```

Expected: HTML output containing "搜索日志".

- [ ] **Search returns results (if journals exist):**

```bash
life-index serve &
sleep 2
curl -s "http://127.0.0.1:8765/search?q=日志" | grep -c "journal"
kill %1
```

Expected: Count > 0 (if journals exist in data directory).

- [ ] **HTMX partial rendering works:**

```bash
life-index serve &
sleep 2
# Full page should contain <!DOCTYPE
curl -s "http://127.0.0.1:8765/search?q=test" | head -1
# Partial should NOT contain <!DOCTYPE
curl -s -H "HX-Request: true" "http://127.0.0.1:8765/search?q=test" | head -1
kill %1
```

Expected: Full page starts with `<!DOCTYPE html>`, partial does NOT.

- [ ] **Health endpoint still works:**

```bash
life-index serve &
sleep 2
curl -s http://127.0.0.1:8765/api/health | python -m json.tool
kill %1
```

Expected: `{"status": "ok", "version": "..."}`.

- [ ] **Dashboard still works:**

```bash
life-index serve &
sleep 2
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8765/
kill %1
```

Expected: 200.

- [ ] **Files created/modified:**

```
web/
├── services/
│   ├── stats.py             (existing — Phase 2)
│   ├── journal.py           ✅ (created)
│   └── search.py            ✅ (created)
├── routes/
│   ├── dashboard.py         (existing — Phase 2)
│   ├── journal.py           ✅ (created)
│   └── search.py            ✅ (created)
├── templates/
│   ├── base.html            (existing)
│   ├── dashboard.html       (existing — Phase 2)
│   ├── journal.html         ✅ (created)
│   ├── search.html          ✅ (created)
│   └── partials/
│       └── search_results.html  ✅ (created)
└── app.py                   ✅ (modified — registered journal + search routers)

tests/unit/
└── test_web_journal_search.py   ✅ (created)
```

**Phase 3 is complete when all checkboxes above are checked. Proceed to Phase 4: Write + Edit.**
