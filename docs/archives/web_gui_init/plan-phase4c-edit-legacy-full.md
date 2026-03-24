# Phase 4c: Edit Service + Route + Template — TDD Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Edit page allows users to modify existing journal entries — updating frontmatter metadata and replacing body content. The edit form pre-fills all fields from the existing journal, computes a diff of changed fields on submission, handles the location→weather coupling (E0504), and delegates to `tools.edit_journal.edit_journal()`. The edit page is accessed from the journal view page via an "编辑" button.

**Architecture:** `web/services/edit.py` wraps `edit_journal()` with diff computation (comparing submitted form data against original journal data to produce `frontmatter_updates` and optional `replace_content`) and handles the location→weather auto-query coupling. `web/routes/edit.py` exposes `GET /journal/{path:path}/edit` (pre-filled edit form) and `POST /journal/{path:path}/edit` (submit changes). Both routes use the same path traversal protection as the journal view route (Phase 3). `web/templates/edit.html` renders a pre-filled form with all editable fields, a 📍 geolocation button, and client-side JavaScript for the 500ms debounce weather query on location change.

**Tech Stack:** Python 3.11+ (pathlib, asyncio), FastAPI, Jinja2, Tailwind CSS, JavaScript (debounce)

**Spec Reference:** `docs/web-gui/design-spec.md` v1.4 — §5.5, §5.4.4 (geolocation reuse), §6.3 (CSRF)

---

## Phase Scope

| Task | Component | Difficulty | Time Est. |
|:--|:--|:--|:--|
| Task 12 | Edit Service + Route + Template — `web/services/edit.py` + `web/routes/edit.py` + `web/templates/edit.html` | Hard | 55 min |

**Dependencies:** Task 12 depends on Phase 3 Task 9 (`web/services/journal.py` for `get_journal()`), Phase 4b Task 11b (CSRF pattern reuse from `web/routes/write.py`), and Phase 1 Task 6 (`base.html`). Phase 5 depends on Phase 4c being complete.

## Split Navigation

- Edit service: [plan-phase4c1-edit-service.md](plan-phase4c1-edit-service.md)
- Edit route + template: [plan-phase4c2-edit-route-template.md](plan-phase4c2-edit-route-template.md)

> 本文件暂时保留完整 legacy TDD 细节；新的执行入口应优先查看上述 split subplans。

---

## Prerequisites

Before starting, verify Phase 1, Phase 3, and Phase 4b are complete:

```bash
python -m pytest tests/unit/test_web_scaffold.py -v       # All Phase 1 tests pass
python -m pytest tests/unit/test_web_journal_search.py -v  # All Phase 3 tests pass
python -m pytest tests/unit/test_web_write_route.py -v     # All Phase 4b tests pass
python -m pytest tests/unit/ -q                             # All tests pass, 0 failures
life-index serve &                                          # Server starts
curl -s http://127.0.0.1:8765/api/health                    # {"status":"ok",...}
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8765/write  # 200
kill %1
```

Read these files (required context):
- `docs/web-gui/design-spec.md` §5.5 — Edit page full spec (editable fields, location/weather coupling, submission flow, security)
- `docs/web-gui/design-spec.md` §5.4.4 — Geolocation (reused in edit page)
- `docs/web-gui/design-spec.md` §6.3 — Security (CSRF for POST endpoints)
- `tools/edit_journal/__init__.py` — `edit_journal(journal_path, frontmatter_updates, append_content, replace_content, dry_run)` full signature and return structure
- `tools/lib/frontmatter.py` — `parse_journal_file()` return structure
- `tools/query_weather/__init__.py` — `geocode_location()` and `query_weather()` signatures (for weather auto-query on location change)
- `web/services/journal.py` — `get_journal()` for loading existing journal data
- `web/routes/write.py` — CSRF pattern to reuse (`_generate_csrf_token`, `_validate_csrf`)
- `web/routes/journal.py` — Path traversal validation pattern to reuse
- `web/templates/base.html` — Block names
- `web/app.py` — Router registration pattern

### Key Data Contracts

**`edit_journal(journal_path, frontmatter_updates, append_content, replace_content, dry_run)` — `tools.edit_journal`:**

```python
# Args:
#   journal_path: Path — absolute path to journal file
#   frontmatter_updates: Dict[str, Any] — fields to update
#   append_content: Optional[str] — text to append to body
#   replace_content: Optional[str] — text to replace entire body
#   dry_run: bool — if True, preview only
#
# Returns:
{
    "success": True,
    "journal_path": "/path/to/journal.md",
    "changes": {
        "title": {"old": "旧标题", "new": "新标题"},
        "weather": {"old": "晴天", "new": "多云"},
    },
    "content_modified": False,
    "indices_updated": ["by-topic/主题_work.md"],
    "error": None,
}

# Location without weather → E0504 error:
{
    "success": False,
    "error": "修改地点时，必须同时更新天气",
    "error_code": "E0504",
}
```

**`parse_journal_file(path)` — `tools.lib.frontmatter`:**

```python
{
    "title": "日志标题",
    "date": "2026-03-07T14:30:00",
    "location": "Lagos, Nigeria",
    "weather": "晴天 28°C",
    "mood": ["专注", "充实"],
    "tags": ["重构", "优化"],
    "topic": ["work", "create"],
    "people": ["团团"],
    "project": "LifeIndex",
    "abstract": "100字内摘要",
    "_title": "日志标题",
    "_body": "# 日志标题\n\n正文内容...",
    "_file": "/full/path/to/journal.md",
    "_error": None,  # present only on error
}
```

**`geocode_location(location)` and `query_weather(lat, lon, date, timezone)` — `tools.query_weather`:**

```python
# geocode_location returns:
{"name": "Lagos", "latitude": 6.5244, "longitude": 3.3792, "country": "Nigeria", "admin1": "Lagos"}
# or None on failure

# query_weather returns:
{
    "success": True,
    "weather": {"simple": "晴天", "temperature_max": 32.5, "temperature_min": 24.1},
}
# or {"success": False, "error": "..."}
```

### Location/Weather Coupling (E0504)

The `edit_journal` tool enforces: if `location` is in `frontmatter_updates`, `weather` must also be present (non-empty string). The edit service must handle this by:
1. Detecting when the user changes the location field
2. Auto-querying weather for the new location via `geocode_location()` → `query_weather()`
3. Including both `location` and `weather` in `frontmatter_updates`
4. If weather query fails, the user must provide weather manually (or keep original location)

### API Route for Weather Query

The edit page needs a server-side API endpoint for the client-side debounce weather query:
- `GET /api/weather?location=Lagos,Nigeria&date=2026-03-07` → returns weather string
- This is a lightweight API endpoint in the edit route file (or a shared utility route)
- The client calls this endpoint 500ms after the user stops typing in the location field

---

## Task 12: Edit Service + Route + Template (`web/services/edit.py` + `web/routes/edit.py` + `web/templates/edit.html`)

**Files:**
- Create: `web/services/edit.py`
- Create: `web/routes/edit.py`
- Create: `web/templates/edit.html`
- Modify: `web/app.py` (register edit router)
- Test: `tests/unit/test_web_edit.py` (create)

**Difficulty:** Hard (~55 min)

**Acceptance Criteria:**
1. `GET /journal/{path}/edit` returns HTTP 200 with a pre-filled edit form for an existing journal
2. All editable fields from §5.5 are present: title, content, location, weather, mood, tags, people, topic, project, abstract
3. Form fields are pre-filled with current journal values from `parse_journal_file()`
4. Path traversal attempts return HTTP 404 (same protection as journal view)
5. Non-existent journal paths return HTTP 404 with "日志未找到" message
6. `POST /journal/{path}/edit` computes diff between submitted data and original journal data
7. Only changed fields are included in `frontmatter_updates` (unchanged fields are NOT submitted to `edit_journal`)
8. If content body is changed, `replace_content` parameter is used
9. Location change triggers weather auto-query: if location is modified and weather is not manually provided, the service queries weather for the new location
10. If weather query fails when location is changed, the edit still proceeds but weather uses the submitted form value (user can manually input)
11. On success, POST redirects (HTTP 303) to the updated journal view page
12. On failure, POST re-renders the edit form with error message and preserved input
13. CSRF protection on POST (same pattern as write route)
14. `GET /api/weather?location=...&date=...` returns JSON `{"weather": "晴天 28°C"}` or `{"error": "查询失败"}`
15. Edit router is registered in `create_app()` via `app.include_router()`
16. Navigation: "返回" link to journal view page, breadcrumb showing "首页 > 日志 > 编辑"

**Subagent Governance:**

- MUST DO: Use `from __future__ import annotations` in all Python files
- MUST DO: Use `pathlib.Path` for all path operations
- MUST DO: Import `edit_journal` from `tools.edit_journal`
- MUST DO: Import `parse_journal_file` from `tools.lib.frontmatter`
- MUST DO: Import `JOURNALS_DIR` from `tools.lib.config`
- MUST DO: Import `geocode_location` and `query_weather` from `tools.query_weather` for weather auto-fill
- MUST DO: Validate `path` parameter against `JOURNALS_DIR` using `Path.resolve()` — reject if resolved path is outside `JOURNALS_DIR` (same pattern as `web/routes/journal.py`)
- MUST DO: Use `app.state.templates.TemplateResponse()` for rendering
- MUST DO: Include `request` in template context (required by Starlette/Jinja2)
- MUST DO: Register edit router in `web/app.py` via `app.include_router(edit_router)` using lazy import inside `create_app()`
- MUST DO: Reuse CSRF token pattern from `web/routes/write.py` (`secrets.token_urlsafe`, cookie-based validation)
- MUST DO: Compute diff before calling `edit_journal` — only submit fields that actually changed
- MUST DO: Handle E0504 (location without weather) by auto-querying weather when location changes
- MUST DO: Use `asyncio.to_thread()` for calling synchronous `edit_journal()` to avoid blocking the event loop
- MUST DO: Use Chinese text for all user-facing strings
- MUST DO: Use semantic HTML and Tailwind CSS classes consistent with `base.html` and `write.html`
- MUST DO: Use `class TestXxx:` pattern for all test classes
- MUST DO: Use `@pytest.mark.asyncio` for async test methods
- MUST DO: Return HTTP 303 redirect on successful POST
- MUST DO: Include list-type fields (mood, tags, topic, people) as comma-separated strings in form, parse on POST
- MUST NOT DO: 在 route 中直接做 journal 持久化修改或索引更新——这些必须委托给 services / tools；安全性的路径校验属于允许的最小路由职责
- MUST NOT DO: Modify any `tools/` module code
- MUST NOT DO: Submit unchanged fields to `edit_journal` — this wastes index updates and creates false change records
- MUST NOT DO: Suppress type errors with `# type: ignore`, `as any`, etc.
- MUST NOT DO: Use bare `except:` clauses — always catch specific exceptions
- MUST NOT DO: Block the async event loop with synchronous I/O

**Error Handling:**
- Path traversal detected → HTTP 404 (do not reveal the reason)
- File not found → HTTP 404 with "日志未找到" message
- CSRF token mismatch → HTTP 403 with "请求验证失败，请刷新页面重试"
- `edit_journal()` returns `{"success": False}` → re-render edit form with error message and preserved input
- `edit_journal()` E0504 (location without weather) → re-render with "修改地点时必须同时提供天气" error
- Weather query failure → log warning, proceed with user-provided weather value (or empty)
- Geocoding failure → log warning, skip weather auto-query, user must provide weather manually
- No changes detected → redirect to journal view with info message (no `edit_journal` call needed)

**TDD Steps:**

- [ ] **Step 1: Write the failing tests — edit service**

Create `tests/unit/test_web_edit.py`:

```python
"""Tests for Web GUI Edit Service + Route — Phase 4c (Task 12)."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── Edit Service Tests ──────────────────────────────────


class TestComputeDiff:
    """compute_edit_diff() calculates which fields changed."""

    def test_no_changes_returns_empty(self) -> None:
        """When submitted data matches original, diff is empty."""
        from web.services.edit import compute_edit_diff

        original = {
            "title": "测试标题",
            "mood": ["专注"],
            "tags": ["python"],
            "topic": ["work"],
            "people": [],
            "location": "Lagos, Nigeria",
            "weather": "晴天 28°C",
            "project": "LifeIndex",
            "abstract": "测试摘要",
        }
        submitted = dict(original)

        fm_updates, content_changed = compute_edit_diff(original, submitted, "原始正文", "原始正文")
        assert fm_updates == {}
        assert content_changed is False

    def test_title_change_detected(self) -> None:
        """Changed title appears in frontmatter_updates."""
        from web.services.edit import compute_edit_diff

        original = {"title": "旧标题", "mood": [], "tags": [], "topic": ["work"], "people": [], "location": "", "weather": "", "project": "", "abstract": ""}
        submitted = dict(original)
        submitted["title"] = "新标题"

        fm_updates, _ = compute_edit_diff(original, submitted, "", "")
        assert fm_updates == {"title": "新标题"}

    def test_mood_change_detected(self) -> None:
        """Changed mood list appears in frontmatter_updates."""
        from web.services.edit import compute_edit_diff

        original = {"title": "", "mood": ["专注"], "tags": [], "topic": ["work"], "people": [], "location": "", "weather": "", "project": "", "abstract": ""}
        submitted = dict(original)
        submitted["mood"] = ["开心", "充实"]

        fm_updates, _ = compute_edit_diff(original, submitted, "", "")
        assert fm_updates == {"mood": ["开心", "充实"]}

    def test_content_change_detected(self) -> None:
        """Changed body content sets content_changed flag."""
        from web.services.edit import compute_edit_diff

        original = {"title": "", "mood": [], "tags": [], "topic": ["work"], "people": [], "location": "", "weather": "", "project": "", "abstract": ""}

        fm_updates, content_changed = compute_edit_diff(original, original, "旧正文", "新正文")
        assert content_changed is True

    def test_location_change_includes_weather(self) -> None:
        """When location changes, weather is included even if unchanged."""
        from web.services.edit import compute_edit_diff

        original = {"title": "", "mood": [], "tags": [], "topic": ["work"], "people": [], "location": "Lagos", "weather": "晴天", "project": "", "abstract": ""}
        submitted = dict(original)
        submitted["location"] = "Beijing"
        submitted["weather"] = "多云"

        fm_updates, _ = compute_edit_diff(original, submitted, "", "")
        assert "location" in fm_updates
        assert "weather" in fm_updates

    def test_multiple_changes(self) -> None:
        """Multiple field changes are all captured."""
        from web.services.edit import compute_edit_diff

        original = {"title": "旧", "mood": ["专注"], "tags": ["a"], "topic": ["work"], "people": [], "location": "", "weather": "", "project": "", "abstract": "旧摘要"}
        submitted = dict(original)
        submitted["title"] = "新"
        submitted["tags"] = ["a", "b"]
        submitted["abstract"] = "新摘要"

        fm_updates, _ = compute_edit_diff(original, submitted, "", "")
        assert "title" in fm_updates
        assert "tags" in fm_updates
        assert "abstract" in fm_updates
        assert len(fm_updates) == 3


class TestWeatherAutoQuery:
    """query_weather_for_location() handles geocoding + weather lookup."""

    @pytest.mark.asyncio
    @patch("web.services.edit.query_weather")
    @patch("web.services.edit.geocode_location")
    async def test_successful_weather_query(
        self,
        mock_geocode: MagicMock,
        mock_weather: MagicMock,
    ) -> None:
        """Returns weather string when geocoding and weather query succeed."""
        from web.services.edit import query_weather_for_location

        mock_geocode.return_value = {"name": "Lagos", "latitude": 6.52, "longitude": 3.38, "country": "Nigeria"}
        mock_weather.return_value = {
            "success": True,
            "weather": {"simple": "晴天", "temperature_max": 32.5, "temperature_min": 24.1},
        }

        result = await query_weather_for_location("Lagos, Nigeria", "2026-03-07")
        assert "晴天" in result
        assert "32" in result or "℃" in result or "°C" in result

    @pytest.mark.asyncio
    @patch("web.services.edit.geocode_location")
    async def test_geocode_failure_returns_none(
        self,
        mock_geocode: MagicMock,
    ) -> None:
        """Returns None when geocoding fails."""
        from web.services.edit import query_weather_for_location

        mock_geocode.return_value = None

        result = await query_weather_for_location("InvalidPlace", "2026-03-07")
        assert result is None

    @pytest.mark.asyncio
    @patch("web.services.edit.query_weather")
    @patch("web.services.edit.geocode_location")
    async def test_weather_query_failure_returns_none(
        self,
        mock_geocode: MagicMock,
        mock_weather: MagicMock,
    ) -> None:
        """Returns None when weather query fails."""
        from web.services.edit import query_weather_for_location

        mock_geocode.return_value = {"name": "Lagos", "latitude": 6.52, "longitude": 3.38}
        mock_weather.return_value = {"success": False, "error": "API error"}

        result = await query_weather_for_location("Lagos", "2026-03-07")
        assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/unit/test_web_edit.py::TestComputeDiff -v
python -m pytest tests/unit/test_web_edit.py::TestWeatherAutoQuery -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'web.services.edit'`.

- [ ] **Step 3: Implement `web/services/edit.py`**

```python
"""Edit Service — diff computation and weather auto-query for journal editing.

Handles:
- Computing diff between original and submitted journal data (only changed fields)
- Location→weather coupling: auto-queries weather when location changes
- Delegating to tools.edit_journal.edit_journal()

Per design-spec §5.5.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from tools.lib.errors import ErrorCode
from tools.query_weather import geocode_location, query_weather

logger = logging.getLogger(__name__)

# Fields that can be edited via the edit form
EDITABLE_FRONTMATTER_FIELDS: list[str] = [
    "title", "mood", "tags", "topic", "people",
    "location", "weather", "project", "abstract",
]


def compute_edit_diff(
    original: dict[str, Any],
    submitted: dict[str, Any],
    original_body: str,
    submitted_body: str,
) -> tuple[dict[str, Any], bool]:
    """Compare original and submitted data, return only changed fields.

    Args:
        original: Original frontmatter values from the journal.
        submitted: Submitted form values.
        original_body: Original Markdown body text.
        submitted_body: Submitted body text.

    Returns:
        Tuple of (frontmatter_updates dict, content_changed bool).
        frontmatter_updates contains only fields that differ.
        If location changed, weather is always included (E0504 coupling).
    """
    frontmatter_updates: dict[str, Any] = {}

    for field in EDITABLE_FRONTMATTER_FIELDS:
        orig_val = original.get(field, "" if field not in ("mood", "tags", "topic", "people") else [])
        sub_val = submitted.get(field, "" if field not in ("mood", "tags", "topic", "people") else [])

        # Normalize for comparison
        if isinstance(orig_val, list) and isinstance(sub_val, list):
            if sorted(orig_val) != sorted(sub_val):
                frontmatter_updates[field] = sub_val
        elif orig_val != sub_val:
            frontmatter_updates[field] = sub_val

    # E0504 coupling: if location changed, ensure weather is also included
    if "location" in frontmatter_updates and "weather" not in frontmatter_updates:
        # Include weather from submitted data (even if unchanged)
        frontmatter_updates["weather"] = submitted.get("weather", "")

    content_changed = original_body.strip() != submitted_body.strip()

    return frontmatter_updates, content_changed


async def query_weather_for_location(
    location: str,
    date: str,
) -> str | None:
    """Query weather for a given location and date.

    Uses geocode_location() → query_weather() pipeline.
    Runs synchronous tools functions via asyncio.to_thread().

    Args:
        location: Location string (e.g., "Lagos, Nigeria").
        date: Date string (YYYY-MM-DD).

    Returns:
        Weather description string (e.g., "晴天 32°C/24°C"), or None on failure.
    """
    try:
        # Geocode location (synchronous → run in thread)
        geo_result = await asyncio.to_thread(geocode_location, location)
        if not geo_result:
            logger.warning("地理编码失败: %s", location)
            return None

        lat = geo_result.get("latitude")
        lon = geo_result.get("longitude")
        if lat is None or lon is None:
            logger.warning("地理编码缺少坐标: %s", geo_result)
            return None

        # Query weather (synchronous → run in thread)
        weather_result = await asyncio.to_thread(query_weather, lat, lon, date)
        if not weather_result or not weather_result.get("success"):
            logger.warning(
                "[%s] 天气查询失败: %s",
                ErrorCode.WEB_GENERAL_ERROR,
                weather_result.get("error", "unknown"),
            )
            return None

        weather_data = weather_result.get("weather", {})
        simple = weather_data.get("simple", "")
        temp_max = weather_data.get("temperature_max")
        temp_min = weather_data.get("temperature_min")

        if temp_max is not None and temp_min is not None:
            return f"{simple} {temp_max}°C/{temp_min}°C"
        elif simple:
            return simple
        else:
            return None

    except Exception as e:
        logger.warning("天气查询异常: %s", e)
        return None
```

- [ ] **Step 4: Run edit service tests to verify they pass**

```bash
python -m pytest tests/unit/test_web_edit.py::TestComputeDiff -v
python -m pytest tests/unit/test_web_edit.py::TestWeatherAutoQuery -v
```

Expected: All `TestComputeDiff` and `TestWeatherAutoQuery` tests pass.

- [ ] **Step 5: Write the failing tests — edit route**

Append to `tests/unit/test_web_edit.py`:

```python
from fastapi.testclient import TestClient


def _get_test_client() -> TestClient:
    """Create a TestClient for the FastAPI app."""
    from web.app import create_app

    app = create_app()
    return TestClient(app)


# ── Edit Route GET Tests ──────────────────────────────


class TestEditRouteGET:
    """Test GET /journal/{path}/edit returns pre-filled edit form."""

    @patch("web.routes.edit.parse_journal_file")
    @patch("web.routes.edit.JOURNALS_DIR", new=Path("/fake/journals"))
    def test_get_edit_returns_200(self, mock_parse: MagicMock) -> None:
        """GET /journal/{path}/edit returns HTTP 200 for valid journal."""
        mock_parse.return_value = {
            "title": "测试日志",
            "date": "2026-03-07T14:30:00",
            "mood": ["专注"],
            "tags": ["python"],
            "topic": ["work"],
            "people": [],
            "location": "Lagos, Nigeria",
            "weather": "晴天 28°C",
            "project": "LifeIndex",
            "abstract": "测试摘要",
            "_title": "测试日志",
            "_body": "# 测试日志\n\n正文内容",
            "_file": "/fake/journals/2026/03/test.md",
        }

        with patch.object(Path, "resolve", return_value=Path("/fake/journals/2026/03/test.md")):
            with patch.object(Path, "exists", return_value=True):
                client = _get_test_client()
                response = client.get("/journal/2026/03/test.md/edit")

        assert response.status_code == 200
        assert "<form" in response.text

    @patch("web.routes.edit.JOURNALS_DIR", new=Path("/fake/journals"))
    def test_get_edit_path_traversal_returns_404(self) -> None:
        """GET /journal/../../etc/passwd/edit returns HTTP 404."""
        client = _get_test_client()
        response = client.get("/journal/../../etc/passwd/edit")
        assert response.status_code == 404

    @patch("web.routes.edit.parse_journal_file")
    @patch("web.routes.edit.JOURNALS_DIR", new=Path("/fake/journals"))
    def test_get_edit_prefills_fields(self, mock_parse: MagicMock) -> None:
        """Edit form pre-fills fields with existing journal values."""
        mock_parse.return_value = {
            "title": "预填标题",
            "date": "2026-03-07T14:30:00",
            "mood": ["专注", "充实"],
            "tags": ["python", "重构"],
            "topic": ["work"],
            "people": ["团团"],
            "location": "Lagos",
            "weather": "晴天",
            "project": "LifeIndex",
            "abstract": "预填摘要",
            "_title": "预填标题",
            "_body": "# 预填标题\n\n预填正文",
            "_file": "/fake/journals/2026/03/test.md",
        }

        with patch.object(Path, "resolve", return_value=Path("/fake/journals/2026/03/test.md")):
            with patch.object(Path, "exists", return_value=True):
                client = _get_test_client()
                response = client.get("/journal/2026/03/test.md/edit")

        assert "预填标题" in response.text
        assert "预填正文" in response.text
        assert "预填摘要" in response.text

    @patch("web.routes.edit.JOURNALS_DIR", new=Path("/fake/journals"))
    def test_get_edit_nonexistent_returns_404(self) -> None:
        """GET /journal/nonexistent.md/edit returns HTTP 404."""
        with patch.object(Path, "resolve", return_value=Path("/fake/journals/nonexistent.md")):
            with patch.object(Path, "exists", return_value=False):
                client = _get_test_client()
                response = client.get("/journal/nonexistent.md/edit")

        assert response.status_code == 404


# ── Edit Route POST Tests ──────────────────────────────


class TestEditRoutePOST:
    """Test POST /journal/{path}/edit submission."""

    @patch("web.routes.edit.edit_journal")
    @patch("web.routes.edit.parse_journal_file")
    @patch("web.routes.edit.JOURNALS_DIR", new=Path("/fake/journals"))
    def test_post_edit_success_redirects(
        self,
        mock_parse: MagicMock,
        mock_edit: MagicMock,
    ) -> None:
        """Successful POST redirects to journal view (HTTP 303)."""
        mock_parse.return_value = {
            "title": "旧标题",
            "date": "2026-03-07T14:30:00",
            "mood": ["专注"],
            "tags": ["python"],
            "topic": ["work"],
            "people": [],
            "location": "Lagos",
            "weather": "晴天",
            "project": "",
            "abstract": "旧摘要",
            "_title": "旧标题",
            "_body": "旧正文",
            "_file": "/fake/journals/2026/03/test.md",
        }
        mock_edit.return_value = {
            "success": True,
            "changes": {"title": {"old": "旧标题", "new": "新标题"}},
            "content_modified": False,
            "indices_updated": [],
        }

        with patch.object(Path, "resolve", return_value=Path("/fake/journals/2026/03/test.md")):
            with patch.object(Path, "exists", return_value=True):
                client = _get_test_client()
                # GET to obtain CSRF token
                get_response = client.get("/journal/2026/03/test.md/edit")
                csrf_token = get_response.cookies.get("csrf_token", "test")

                response = client.post(
                    "/journal/2026/03/test.md/edit",
                    data={
                        "title": "新标题",
                        "content": "旧正文",
                        "mood": "专注",
                        "tags": "python",
                        "topic": "work",
                        "people": "",
                        "location": "Lagos",
                        "weather": "晴天",
                        "project": "",
                        "abstract": "旧摘要",
                        "csrf_token": csrf_token,
                    },
                    cookies={"csrf_token": csrf_token},
                    follow_redirects=False,
                )

        assert response.status_code == 303
        assert "/journal/" in response.headers.get("location", "")

    @patch("web.routes.edit.JOURNALS_DIR", new=Path("/fake/journals"))
    def test_post_edit_csrf_missing_returns_403(self) -> None:
        """POST without CSRF token returns HTTP 403."""
        with patch.object(Path, "resolve", return_value=Path("/fake/journals/2026/03/test.md")):
            with patch.object(Path, "exists", return_value=True):
                client = _get_test_client()
                response = client.post(
                    "/journal/2026/03/test.md/edit",
                    data={"title": "新标题", "content": "正文"},
                )

        assert response.status_code == 403


# ── Weather API Tests ──────────────────────────────


class TestWeatherAPI:
    """Test GET /api/weather endpoint."""

    @patch("web.routes.edit.query_weather_for_location")
    def test_weather_api_success(self, mock_query: MagicMock) -> None:
        """GET /api/weather returns weather string on success."""
        mock_query.return_value = "晴天 32°C/24°C"

        client = _get_test_client()
        response = client.get("/api/weather?location=Lagos&date=2026-03-07")

        assert response.status_code == 200
        data = response.json()
        assert "weather" in data
        assert "晴天" in data["weather"]

    @patch("web.routes.edit.query_weather_for_location")
    def test_weather_api_failure(self, mock_query: MagicMock) -> None:
        """GET /api/weather returns error on failure."""
        mock_query.return_value = None

        client = _get_test_client()
        response = client.get("/api/weather?location=InvalidPlace&date=2026-03-07")

        assert response.status_code == 200
        data = response.json()
        assert "error" in data

    def test_weather_api_missing_location(self) -> None:
        """GET /api/weather without location returns error."""
        client = _get_test_client()
        response = client.get("/api/weather")

        assert response.status_code == 200
        data = response.json()
        assert "error" in data
```

- [ ] **Step 6: Run route tests to verify they fail**

```bash
python -m pytest tests/unit/test_web_edit.py::TestEditRouteGET -v
python -m pytest tests/unit/test_web_edit.py::TestEditRoutePOST -v
python -m pytest tests/unit/test_web_edit.py::TestWeatherAPI -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'web.routes.edit'` or HTTP 404.

- [ ] **Step 7: Implement `web/routes/edit.py`**

```python
"""Edit route — journal editing form and submission handler.

GET /journal/{path}/edit:  Pre-filled edit form for existing journal.
POST /journal/{path}/edit: Process edits, compute diff, call edit_journal.
GET /api/weather:          Weather query API for location→weather auto-fill.

Per design-spec §5.5.
"""

from __future__ import annotations

import asyncio
import logging
import secrets
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Form, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from tools.edit_journal import edit_journal
from tools.lib.config import JOURNALS_DIR
from tools.lib.frontmatter import parse_journal_file

from web.services.edit import compute_edit_diff, query_weather_for_location

logger = logging.getLogger(__name__)

router = APIRouter()

# Valid topic values
VALID_TOPICS: list[dict[str, str]] = [
    {"value": "work", "label": "工作 (work)"},
    {"value": "learn", "label": "学习 (learn)"},
    {"value": "health", "label": "健康 (health)"},
    {"value": "relation", "label": "关系 (relation)"},
    {"value": "think", "label": "思考 (think)"},
    {"value": "create", "label": "创作 (create)"},
    {"value": "life", "label": "生活 (life)"},
]


def _generate_csrf_token() -> str:
    """Generate a cryptographically secure CSRF token."""
    return secrets.token_urlsafe(32)


def _validate_csrf(request: Request, form_token: str | None) -> bool:
    """Validate CSRF token from cookie matches form field."""
    cookie_token = request.cookies.get("csrf_token")
    if not cookie_token or not form_token:
        return False
    return secrets.compare_digest(cookie_token, form_token)


def _validate_path(relative_path: str) -> Path | None:
    """Validate and resolve journal path, return None if traversal detected.

    Args:
        relative_path: Relative path within JOURNALS_DIR.

    Returns:
        Resolved absolute Path if valid, None if path traversal detected or outside JOURNALS_DIR.
    """
    try:
        full_path = (JOURNALS_DIR / relative_path).resolve()
        if not str(full_path).startswith(str(JOURNALS_DIR.resolve())):
            return None
        return full_path
    except (ValueError, OSError):
        return None


@router.get("/journal/{path:path}/edit", response_class=HTMLResponse)
async def edit_form(request: Request, path: str) -> Response:
    """Render the pre-filled journal edit form.

    Loads existing journal data and fills all form fields.
    """
    # ── Path validation ──
    journal_path = _validate_path(path)
    if journal_path is None or not journal_path.exists():
        return Response(content="日志未找到", status_code=404, media_type="text/html; charset=utf-8")

    # ── Parse existing journal ──
    journal_data = parse_journal_file(journal_path)
    if "_error" in journal_data:
        return Response(content="日志未找到", status_code=404, media_type="text/html; charset=utf-8")

    # ── Prepare form data from journal ──
    form_data = {
        "title": journal_data.get("title", ""),
        "content": journal_data.get("_body", ""),
        "date": str(journal_data.get("date", ""))[:10],  # Extract date part
        "mood": ", ".join(journal_data.get("mood", [])),
        "tags": ", ".join(journal_data.get("tags", [])),
        "topic": journal_data.get("topic", []),
        "people": ", ".join(journal_data.get("people", [])),
        "location": journal_data.get("location", ""),
        "weather": journal_data.get("weather", ""),
        "project": journal_data.get("project", ""),
        "abstract": journal_data.get("abstract", ""),
    }

    # ── CSRF token ──
    csrf_token = _generate_csrf_token()

    context = {
        "request": request,
        "journal_path": path,
        "form_data": form_data,
        "valid_topics": VALID_TOPICS,
        "csrf_token": csrf_token,
        "error": None,
        "success_message": None,
    }

    response = request.app.state.templates.TemplateResponse("edit.html", context)
    response.set_cookie("csrf_token", csrf_token, httponly=True, samesite="strict", max_age=3600)
    return response


@router.post("/journal/{path:path}/edit", response_class=HTMLResponse)
async def edit_submit(
    request: Request,
    path: str,
    title: str = Form(""),
    content: str = Form(""),
    mood: str = Form(""),
    tags: str = Form(""),
    topic: list[str] = Form([]),
    people: str = Form(""),
    location: str = Form(""),
    weather: str = Form(""),
    project: str = Form(""),
    abstract: str = Form(""),
    csrf_token: str = Form(""),
) -> Response:
    """Process journal edit form submission.

    Flow per design-spec §5.5:
    1. Validate CSRF and path
    2. Load original journal data
    3. Compute diff (only changed fields)
    4. Handle location→weather coupling
    5. Call edit_journal()
    6. Redirect on success, re-render on failure
    """
    # ── CSRF Validation ──
    if not _validate_csrf(request, csrf_token):
        return Response(content="请求验证失败，请刷新页面重试", status_code=403, media_type="text/html; charset=utf-8")

    # ── Path validation ──
    journal_path = _validate_path(path)
    if journal_path is None or not journal_path.exists():
        return Response(content="日志未找到", status_code=404, media_type="text/html; charset=utf-8")

    # ── Preserve form data for re-rendering ──
    form_data_for_rerender: dict[str, Any] = {
        "title": title,
        "content": content,
        "mood": mood,
        "tags": tags,
        "topic": topic,
        "people": people,
        "location": location,
        "weather": weather,
        "project": project,
        "abstract": abstract,
    }

    try:
        # ── Load original journal ──
        original_data = parse_journal_file(journal_path)
        if "_error" in original_data:
            return await _render_edit_form(
                request, path, error="无法读取原始日志", form_data=form_data_for_rerender
            )

        # ── Build submitted data dict ──
        submitted: dict[str, Any] = {
            "title": title.strip(),
            "mood": [m.strip() for m in mood.split(",") if m.strip()] if mood.strip() else [],
            "tags": [t.strip() for t in tags.split(",") if t.strip()] if tags.strip() else [],
            "topic": [t for t in topic if t.strip()],
            "people": [p.strip() for p in people.split(",") if p.strip()] if people.strip() else [],
            "location": location.strip(),
            "weather": weather.strip(),
            "project": project.strip(),
            "abstract": abstract.strip(),
        }

        # ── Build original data dict for comparison ──
        original: dict[str, Any] = {
            "title": original_data.get("title", ""),
            "mood": original_data.get("mood", []),
            "tags": original_data.get("tags", []),
            "topic": original_data.get("topic", []),
            "people": original_data.get("people", []),
            "location": original_data.get("location", ""),
            "weather": original_data.get("weather", ""),
            "project": original_data.get("project", ""),
            "abstract": original_data.get("abstract", ""),
        }
        original_body = original_data.get("_body", "")

        # ── Compute diff ──
        fm_updates, content_changed = compute_edit_diff(original, submitted, original_body, content)

        # ── No changes → redirect back ──
        if not fm_updates and not content_changed:
            return RedirectResponse(url=f"/journal/{path}", status_code=303)

        # ── Handle location→weather coupling ──
        if "location" in fm_updates and not fm_updates.get("weather", "").strip():
            # Auto-query weather for new location
            date_str = str(original_data.get("date", ""))[:10]
            auto_weather = await query_weather_for_location(fm_updates["location"], date_str)
            if auto_weather:
                fm_updates["weather"] = auto_weather
                logger.info("自动查询天气: %s → %s", fm_updates["location"], auto_weather)
            else:
                # Weather query failed — submit without weather, edit_journal will return E0504
                logger.warning("天气自动查询失败，尝试使用用户输入")

        # ── Call edit_journal ──
        replace_content = content if content_changed else None

        result = await asyncio.to_thread(
            edit_journal,
            journal_path,
            fm_updates if fm_updates else {},
            None,  # append_content
            replace_content,
            False,  # dry_run
        )

        if result.get("success"):
            return RedirectResponse(url=f"/journal/{path}", status_code=303)
        else:
            error_msg = result.get("error", "编辑失败，请重试")
            return await _render_edit_form(
                request, path, error=error_msg, form_data=form_data_for_rerender
            )

    except Exception as e:
        logger.error("日志编辑异常: %s", e, exc_info=True)
        return await _render_edit_form(
            request, path, error=f"编辑失败: {e}", form_data=form_data_for_rerender
        )


@router.get("/api/weather")
async def weather_api(
    location: str = "",
    date: str = "",
) -> JSONResponse:
    """Weather query API for client-side location→weather auto-fill.

    Called by edit page JavaScript when location field changes (500ms debounce).

    Args:
        location: Location string to query weather for.
        date: Date string (YYYY-MM-DD) for weather query.

    Returns:
        JSON with "weather" key on success, "error" key on failure.
    """
    if not location.strip():
        return JSONResponse({"error": "请输入地点"})

    if not date.strip():
        from datetime import date as date_cls
        date = date_cls.today().isoformat()

    result = await query_weather_for_location(location.strip(), date.strip())
    if result:
        return JSONResponse({"weather": result})
    else:
        return JSONResponse({"error": "天气查询失败，请手动输入"})


async def _render_edit_form(
    request: Request,
    path: str,
    error: str | None = None,
    form_data: dict[str, Any] | None = None,
) -> Response:
    """Re-render edit form with error and preserved input."""
    csrf_token = _generate_csrf_token()

    context = {
        "request": request,
        "journal_path": path,
        "form_data": form_data or {},
        "valid_topics": VALID_TOPICS,
        "csrf_token": csrf_token,
        "error": error,
        "success_message": None,
    }

    response = request.app.state.templates.TemplateResponse("edit.html", context)
    response.set_cookie("csrf_token", csrf_token, httponly=True, samesite="strict", max_age=3600)
    return response
```

- [ ] **Step 8: Create `web/templates/edit.html`**

```html
{% extends "base.html" %}

{% block title %}编辑日志 — Life Index{% endblock %}

{% block content %}
<div class="max-w-4xl mx-auto">
    <!-- 面包屑导航 -->
    <nav class="mb-6 text-sm text-gray-500">
        <a href="/" class="hover:text-blue-600">首页</a>
        <span class="mx-2">/</span>
        <a href="/journal/{{ journal_path }}" class="hover:text-blue-600">日志</a>
        <span class="mx-2">/</span>
        <span class="text-gray-800">编辑</span>
    </nav>

    <h1 class="text-2xl font-bold text-gray-800 mb-6">✏️ 编辑日志</h1>

    <!-- 错误提示 -->
    {% if error %}
    <div class="bg-red-50 border-l-4 border-red-500 p-4 mb-6 rounded">
        <div class="flex items-center">
            <span class="text-red-500 mr-2">⚠️</span>
            <p class="text-red-700">{{ error }}</p>
        </div>
    </div>
    {% endif %}

    <!-- 编辑表单 -->
    <form method="POST" action="/journal/{{ journal_path }}/edit" class="space-y-6">
        <!-- CSRF Token -->
        <input type="hidden" name="csrf_token" value="{{ csrf_token }}">

        <!-- 标题 -->
        <div>
            <label for="title" class="block text-sm font-medium text-gray-700 mb-1">标题</label>
            <input type="text" id="title" name="title"
                   value="{{ form_data.get('title', '') }}"
                   class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
        </div>

        <!-- 正文内容 -->
        <div>
            <label for="content" class="block text-sm font-medium text-gray-700 mb-1">
                日志正文 <span class="text-red-500">*</span>
            </label>
            <textarea id="content" name="content" rows="12" required
                      class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 font-mono text-sm"
                      >{{ form_data.get('content', '') }}</textarea>
        </div>

        <!-- 元数据区域 -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <!-- 主题 (Topic) -->
            <div>
                <label for="topic" class="block text-sm font-medium text-gray-700 mb-1">主题</label>
                <select id="topic" name="topic" multiple
                        class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
                    {% for t in valid_topics %}
                    <option value="{{ t.value }}"
                            {% if t.value in form_data.get('topic', []) %}selected{% endif %}>
                        {{ t.label }}
                    </option>
                    {% endfor %}
                </select>
            </div>

            <!-- 摘要 -->
            <div>
                <label for="abstract" class="block text-sm font-medium text-gray-700 mb-1">摘要</label>
                <input type="text" id="abstract" name="abstract"
                       value="{{ form_data.get('abstract', '') }}"
                       class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                       placeholder="100字以内的摘要">
            </div>

            <!-- 地点 -->
            <div>
                <label for="location" class="block text-sm font-medium text-gray-700 mb-1">地点</label>
                <div class="flex gap-2">
                    <input type="text" id="location" name="location"
                           value="{{ form_data.get('location', '') }}"
                           class="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                           placeholder="修改地点将自动查询天气">
                    <button type="button" onclick="getGeolocation()"
                            class="px-3 py-2 bg-gray-100 border border-gray-300 rounded-lg hover:bg-gray-200 text-sm"
                            title="获取当前位置">📍</button>
                </div>
            </div>

            <!-- 天气 -->
            <div>
                <label for="weather" class="block text-sm font-medium text-gray-700 mb-1">
                    天气
                    <span id="weather-loading" class="hidden text-xs text-blue-500 ml-2">⏳ 查询中...</span>
                </label>
                <input type="text" id="weather" name="weather"
                       value="{{ form_data.get('weather', '') }}"
                       class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                       placeholder="修改地点后自动查询，也可手动输入">
            </div>
        </div>

        <!-- 标签类字段 -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
            <!-- 心情 -->
            <div>
                <label for="mood" class="block text-sm font-medium text-gray-700 mb-1">心情</label>
                <input type="text" id="mood" name="mood"
                       value="{{ form_data.get('mood', '') }}"
                       class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                       placeholder="用逗号分隔，如：开心, 充实">
            </div>

            <!-- 标签 -->
            <div>
                <label for="tags" class="block text-sm font-medium text-gray-700 mb-1">标签</label>
                <input type="text" id="tags" name="tags"
                       value="{{ form_data.get('tags', '') }}"
                       class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                       placeholder="用逗号分隔">
            </div>

            <!-- 人物 -->
            <div>
                <label for="people" class="block text-sm font-medium text-gray-700 mb-1">人物</label>
                <input type="text" id="people" name="people"
                       value="{{ form_data.get('people', '') }}"
                       class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                       placeholder="用逗号分隔">
            </div>
        </div>

        <!-- 项目 -->
        <div>
            <label for="project" class="block text-sm font-medium text-gray-700 mb-1">关联项目</label>
            <input type="text" id="project" name="project"
                   value="{{ form_data.get('project', '') }}"
                   class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                   placeholder="关联项目（可选）">
        </div>

        <!-- 提交按钮 -->
        <div class="flex items-center justify-between pt-4 border-t border-gray-200">
            <a href="/journal/{{ journal_path }}" class="text-gray-600 hover:text-blue-600 text-sm">← 返回日志</a>
            <button type="submit"
                    class="px-6 py-2 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-colors">
                保存修改
            </button>
        </div>
    </form>
</div>
{% endblock %}

{% block scripts %}
<script>
// ── 地点→天气 Debounce (500ms, §5.5) ──
let weatherTimer = null;
const locationInput = document.getElementById('location');
const weatherInput = document.getElementById('weather');
const weatherLoading = document.getElementById('weather-loading');
const originalLocation = locationInput ? locationInput.value : '';

if (locationInput) {
    locationInput.addEventListener('blur', function() {
        const newLocation = this.value.trim();
        if (newLocation && newLocation !== originalLocation) {
            clearTimeout(weatherTimer);
            weatherTimer = setTimeout(() => queryWeather(newLocation), 500);
        }
    });

    locationInput.addEventListener('input', function() {
        clearTimeout(weatherTimer);
    });
}

async function queryWeather(location) {
    weatherLoading.classList.remove('hidden');
    try {
        const dateEl = document.querySelector('input[name="date"]');
        const date = dateEl ? dateEl.value : '';
        const params = new URLSearchParams({ location, date });
        const response = await fetch(`/api/weather?${params}`);
        const data = await response.json();
        if (data.weather) {
            weatherInput.value = data.weather;
        } else if (data.error) {
            console.warn('天气查询:', data.error);
        }
    } catch (e) {
        console.warn('天气查询失败:', e);
    } finally {
        weatherLoading.classList.add('hidden');
    }
}

// ── 浏览器地理定位 (复用 §5.4.4) ──
function getGeolocation() {
    if (!navigator.geolocation) {
        alert('您的浏览器不支持地理定位');
        return;
    }

    const btn = event.target;
    const origText = btn.textContent;
    btn.textContent = '⏳';
    btn.disabled = true;

    navigator.geolocation.getCurrentPosition(
        async (position) => {
            const { latitude, longitude } = position.coords;
            try {
                const response = await fetch(
                    `https://nominatim.openstreetmap.org/reverse?lat=${latitude}&lon=${longitude}&format=json&accept-language=zh`,
                    { headers: { 'User-Agent': 'LifeIndex/2.0 (life-index-web-gui)' } }
                );
                if (response.ok) {
                    const data = await response.json();
                    const parts = [];
                    if (data.address) {
                        if (data.address.city || data.address.town || data.address.village) {
                            parts.push(data.address.city || data.address.town || data.address.village);
                        }
                        if (data.address.state) parts.push(data.address.state);
                        if (data.address.country) parts.push(data.address.country);
                    }
                    const locationStr = parts.length > 0 ? parts.join(', ') : `${latitude.toFixed(4)}, ${longitude.toFixed(4)}`;
                    locationInput.value = locationStr;
                    // Trigger weather query for new location
                    queryWeather(locationStr);
                } else {
                    locationInput.value = `${latitude.toFixed(4)}, ${longitude.toFixed(4)}`;
                }
            } catch (e) {
                locationInput.value = `${latitude.toFixed(4)}, ${longitude.toFixed(4)}`;
            }
            btn.textContent = origText;
            btn.disabled = false;
        },
        (error) => {
            let msg = '定位失败';
            if (error.code === 1) msg = '定位权限被拒绝';
            else if (error.code === 2) msg = '无法获取位置信息';
            else if (error.code === 3) msg = '定位超时';
            alert(msg);
            btn.textContent = origText;
            btn.disabled = false;
        },
        { enableHighAccuracy: false, timeout: 10000 }
    );
}
</script>
{% endblock %}
```

- [ ] **Step 9: Register edit router in `web/app.py`**

Add the following inside `create_app()`, after existing router registrations:

```python
from web.routes.edit import router as edit_router
app.include_router(edit_router)
```

Follow the same lazy-import pattern used by existing routers.

- [ ] **Step 10: Run all tests to verify they pass**

```bash
python -m pytest tests/unit/test_web_edit.py -v
```

Expected: All `TestComputeDiff`, `TestWeatherAutoQuery`, `TestEditRouteGET`, `TestEditRoutePOST`, `TestWeatherAPI` tests pass.

- [ ] **Step 11: Verify existing tests still pass**

```bash
python -m pytest tests/unit/ -q
```

Expected: 0 failures (including all Phase 1 + Phase 2 + Phase 3 + Phase 4a + Phase 4b tests).

- [ ] **Step 12: Verify edit form renders in browser**

```bash
life-index serve &
sleep 2
# Assumes at least one journal exists
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8765/api/health
# Test weather API
curl -s "http://127.0.0.1:8765/api/weather?location=Lagos&date=2026-03-07"
kill %1
```

- [ ] **Step 13: Commit**

```bash
git add web/services/edit.py web/routes/edit.py web/templates/edit.html tests/unit/test_web_edit.py web/app.py
git commit -m "feat(web): add edit service, route, and template with weather auto-query (Phase 4c)"
```

---

## Phase 4c Completion Checklist

Run all checks before declaring Phase 4c complete:

- [ ] **All Phase 4c tests pass:**

```bash
python -m pytest tests/unit/test_web_edit.py -v
```

Expected: All tests in `TestComputeDiff`, `TestWeatherAutoQuery`, `TestEditRouteGET`, `TestEditRoutePOST`, `TestWeatherAPI` pass.

- [ ] **All existing tests still pass:**

```bash
python -m pytest tests/unit/ -q
```

Expected: 0 failures (including all Phase 1–4b tests).

- [ ] **Edit service imports cleanly:**

```bash
python -c "from web.services.edit import compute_edit_diff, query_weather_for_location; print('OK')"
```

Expected: `OK`.

- [ ] **Edit route imports cleanly:**

```bash
python -c "from web.routes.edit import router; print('OK')"
```

Expected: `OK`.

- [ ] **Weather API works:**

```bash
life-index serve &
sleep 2
curl -s "http://127.0.0.1:8765/api/weather?location=Lagos&date=2026-03-07"
kill %1
```

Expected: JSON response with `weather` or `error` key.

- [ ] **Health endpoint still works:**

```bash
life-index serve &
sleep 2
curl -s http://127.0.0.1:8765/api/health | python -m json.tool
kill %1
```

Expected: `{"status": "ok", "version": "..."}`.

- [ ] **Files created/modified:**

```
web/
├── services/
│   ├── stats.py             (existing — Phase 2)
│   ├── journal.py           (existing — Phase 3)
│   ├── search.py            (existing — Phase 3)
│   ├── llm_provider.py      (existing — Phase 4a)
│   ├── write.py             (existing — Phase 4a)
│   └── edit.py              ✅ (created)
├── routes/
│   ├── dashboard.py         (existing — Phase 2)
│   ├── journal.py           (existing — Phase 3)
│   ├── search.py            (existing — Phase 3)
│   ├── write.py             (existing — Phase 4b)
│   └── edit.py              ✅ (created)
├── templates/
│   ├── base.html            (existing)
│   ├── dashboard.html       (existing — Phase 2)
│   ├── journal.html         (existing — Phase 3)
│   ├── search.html          (existing — Phase 3)
│   ├── write.html           (existing — Phase 4b)
│   └── edit.html            ✅ (created)
└── app.py                   (modified — register edit router)

tests/unit/
└── test_web_edit.py         ✅ (created)
```

---

## Plan Review Note

After reviewing this plan, dispatch `momus` (plan reviewer) with this file path to validate:
- Acceptance criteria completeness
- TDD step coverage vs. acceptance criteria
- Code correctness and consistency
- Error handling coverage
- Missing edge cases

```
task(subagent_type="momus", prompt="D:\\Loster AI\\Projects\\life-index\\docs\\web-gui\\plan-phase4c-edit.md")
```
