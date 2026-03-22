# Phase 4b: Write Route + Template — TDD Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Write page provides a rich form for creating journal entries with smart-fill UI, writing template selector, file upload + URL attachment input, and browser geolocation. Form submits to a POST route that orchestrates LLM metadata fill, weather query, attachment processing, and delegates to Write Service (Phase 4a).

**Architecture:** `web/routes/write.py` exposes `GET /write` (render form) and `POST /write` (process submission). The GET route loads writing templates from `writing_templates.json`, checks LLM provider availability, and renders `write.html`. The POST route collects multipart form data (including file uploads), calls `prepare_journal_data()` and `write_journal_web()` from Phase 4a's Write Service, and redirects to the new journal on success. `web/templates/write.html` provides a 10+ field form with dynamic placeholders that adapt to LLM availability, a template selector dropdown, tag input components, file upload area, and URL attachment input.

**Tech Stack:** Python 3.11+ (pathlib, json, asyncio), FastAPI (Form, File, UploadFile, Request, Response), Jinja2, HTMX (optional partial updates), Alpine.js (client-side interactivity), Tailwind CSS

**Spec Reference:** `docs/web-gui/design-spec.md` v1.4 — §5.4, §5.4.1–§5.4.5, §3.3.4, §6.3

---

## Phase Scope

| Task | Component | Difficulty | Time Est. |
|:--|:--|:--|:--|
| Task 11b | Write Route + Template — `web/routes/write.py` + `web/templates/write.html` | Hard | 55 min |

**Dependencies:** Task 11b depends on Phase 4a Task 11a (`web/services/write.py`, `web/services/llm_provider.py`, `web/templates/writing_templates.json`), Phase 1 Task 4 (`web/app.py` factory), and Phase 1 Task 6 (`base.html`). Phase 4c and Phase 5 depend on Phase 4b.

## Split Navigation

- Write route: [plan-phase4b1-write-route.md](plan-phase4b1-write-route.md)
- Write template: [plan-phase4b2-write-template.md](plan-phase4b2-write-template.md)

> 本文件暂时保留完整 legacy TDD 细节；新的执行入口应优先查看上述 split subplans。

---

## Prerequisites

Before starting, verify Phase 1 and Phase 4a are complete:

```bash
python -m pytest tests/unit/test_web_scaffold.py -v   # All Phase 1 tests pass
python -m pytest tests/unit/test_web_write.py -v       # All Phase 4a tests pass
python -m pytest tests/unit/ -q                         # All tests pass, 0 failures
life-index serve &                                      # Server starts
curl -s http://127.0.0.1:8765/api/health                # {"status":"ok",...}
kill %1
```

Verify Phase 4a modules import cleanly:

```bash
python -c "from web.services.write import prepare_journal_data, write_journal_web; print('OK')"
python -c "from web.services.llm_provider import get_provider; print('OK')"
python -c "import json; data = json.load(open('web/templates/writing_templates.json', encoding='utf-8')); print(f'{len(data)} templates')"
# Expected: OK, OK, 7 templates
```

Read these files (required context):
- `docs/web-gui/design-spec.md` §5.4 — Write page full spec (§5.4.1 form fields, §5.4.2 submission flow, §5.4.3 attachments, §5.4.4 geolocation, §5.4.5 templates UI)
- `docs/web-gui/design-spec.md` §3.3.4 — LLM unavailable fallback strategy
- `docs/web-gui/design-spec.md` §6.3 — Security (CSRF for POST /write)
- `web/services/write.py` — `prepare_journal_data()` and `write_journal_web()` signatures
- `web/services/llm_provider.py` — `get_provider()` signature, LLMProvider ABC
- `web/templates/writing_templates.json` — 7 preset templates structure
- `web/templates/base.html` — Block names (`{% block title %}`, `{% block content %}`, `{% block scripts %}`)
- `web/app.py` — `create_app()` factory, `app.state.templates`, lazy router imports
- `web/routes/dashboard.py` or `web/routes/search.py` — Existing route patterns for consistency

### Key Data Contracts

**`prepare_journal_data(form_data, provider)` — `web.services.write`:**

```python
# form_data dict keys:
#   REQUIRED: content (str)
#   OPTIONAL: date (str "YYYY-MM-DD"), title (str), topic (list[str]),
#             mood (list[str]), tags (list[str]), people (list[str]),
#             location (str), project (str), attachments (list)
#
# provider: LLMProvider instance or None
#
# Returns: complete data dict for write_journal()
# Raises: ValueError if content missing, or topic missing when no LLM
```

**`write_journal_web(data, dry_run)` — `web.services.write`:**

```python
# Returns: write_journal() result dict
# {
#     "success": True/False,
#     "journal_path": "C:/Users/.../Documents/Life-Index/Journals/.../journal.md",
#     "error": None or "error message",
#     ...
# }
```

**`get_provider()` — `web.services.llm_provider`:**

```python
# Returns: LLMProvider instance or None (all unavailable)
```

**Writing templates JSON structure:**

```python
[
    {
        "id": "blank",           # unique identifier
        "name": "空白日志",       # display name (Chinese)
        "topic": [],             # list[str] — preset topics
        "content": "",           # str — skeleton content
        "tags": []               # list[str] — preset tags
    },
    # ... 6 more templates
]
```

### Attachment Handling Notes

File uploads arrive as `UploadFile` objects via FastAPI multipart. The route must:
1. Save uploaded files to a temporary location
2. Pass file paths in `data["attachments"]` for `write_journal` to process
3. Clean up temp files after write completes (success or failure)

URL attachments are handled in Phase 5 (Task 13) — Phase 4b only needs to pass URL strings through in the form but does NOT implement the download logic. The form UI should include a URL input area, but the POST handler should collect URLs and store them for Phase 5 processing.

### CSRF Protection Notes

Per design-spec §6.3, POST endpoints need CSRF protection. For MVP, the authoritative pattern is the route-level **double-submit cookie** approach:
- Generate a random token per session/request and embed it in a hidden form field
- Validate the token on POST submission
- Use `secrets.token_urlsafe()` for token generation

**Implementation approach**: Store CSRF token in a cookie (set on GET /write), validate the cookie value matches the hidden form field value `csrf_token` on POST. This avoids server-side session storage and is the same contract later reused by Edit.

---

## Task 11b: Write Route + Template (`web/routes/write.py` + `web/templates/write.html`)

**Files:**
- Create: `web/routes/write.py`
- Create: `web/templates/write.html`
- Modify: `web/app.py` (register write router)
- Test: `tests/unit/test_web_write_route.py` (create)

**Difficulty:** Hard (~55 min)

**Acceptance Criteria:**
1. `GET /write` returns HTTP 200 with a rendered HTML form
2. Form contains fields for: content (textarea, required), date (datetime picker), title, topic (multi-select from 7 options), mood (tag input), tags (tag input), people (tag input), location (text + 📍 button), project (text), attachments (file upload + URL input)
3. Template selector dropdown is visible above the content textarea, default selection is "空白日志"
4. Selecting a template fills the content textarea and topic/tags fields (client-side JavaScript)
5. Template change confirmation: if user has modified form content, switching template triggers a confirm dialog
6. Placeholder text adapts to LLM availability: "AI 将自动生成标题" vs "请手动填写标题"
7. When LLM is unavailable, topic field shows a red asterisk (required indicator)
8. `POST /write` accepts multipart form data, processes file uploads, calls `prepare_journal_data()` then `write_journal_web()`
9. On success, POST redirects (HTTP 303) to the newly created journal view page (`/journal/{relative_path}`)
10. On failure, POST re-renders the write form with error message and preserved user input (no data loss)
11. CSRF token is generated on GET and validated on POST
12. Write router is registered in `create_app()` via `app.include_router()`
13. File uploads are saved to temp directory, paths passed to write service, temp files cleaned up after
14. Navigation: "返回" link to dashboard, breadcrumb showing "首页 > 写日志"
15. Content textarea supports Markdown (plain text editing, not WYSIWYG)

**Subagent Governance:**

- MUST DO: Use `from __future__ import annotations` in all Python files
- MUST DO: Use `pathlib.Path` for all path operations
- MUST DO: Import `prepare_journal_data`, `write_journal_web` from `web.services.write`
- MUST DO: Import `get_provider` from `web.services.llm_provider`
- MUST DO: Load writing templates from `web/templates/writing_templates.json` using `json.load()`
- MUST DO: Use `app.state.templates.TemplateResponse()` for rendering
- MUST DO: Include `request` in template context (required by Starlette/Jinja2)
- MUST DO: Register write router in `web/app.py` via `app.include_router(write_router)` using lazy import inside `create_app()`
- MUST DO: Use `secrets.token_urlsafe()` for CSRF token generation
- MUST DO: Set CSRF token as cookie on GET and validate cookie vs form field on POST
- MUST DO: Handle `UploadFile` objects from FastAPI for file attachments
- MUST DO: Use `tempfile.mkdtemp()` for temporary file storage during upload processing
- MUST DO: Clean up temp files in a `finally` block to prevent leaks
- MUST DO: Use Chinese text for all user-facing strings (form labels, placeholders, error messages, button text)
- MUST DO: Use semantic HTML and Tailwind CSS classes consistent with `base.html`
- MUST DO: Use `class TestXxx:` pattern for all test classes
- MUST DO: Use `@pytest.mark.asyncio` for async test methods
- MUST DO: Include `valid_topics` list in template context for the topic multi-select: `["work", "learn", "health", "relation", "think", "create", "life"]`
- MUST DO: Return HTTP 303 (See Other) redirect on successful POST to prevent form resubmission
- MUST NOT DO: 在 route 中直接做 journal 持久化读写或索引更新——这些必须委托给 services / tools
- MUST NOT DO: Implement URL download logic — that is Phase 5 (Task 13). Only collect URL strings from the form
- MUST NOT DO: Modify any `tools/` module code
- MUST NOT DO: Modify `web/services/write.py` or `web/services/llm_provider.py` — use them as-is from Phase 4a
- MUST NOT DO: Suppress type errors with `# type: ignore`, `as any`, etc.
- MUST NOT DO: Use bare `except:` clauses — always catch specific exceptions
- MUST NOT DO: Block the async event loop with synchronous I/O
- MUST NOT DO: Store CSRF tokens in server-side sessions (use cookie-based approach)

**Error Handling:**
- CSRF token mismatch → HTTP 403 with "请求验证失败，请刷新页面重试" message
- `prepare_journal_data()` raises `ValueError` → re-render form with error message and preserved input
- `write_journal_web()` returns `{"success": False}` → re-render form with error from result dict
- File upload exceeds size limit → re-render form with "文件大小超出限制" error
- File upload I/O error → log warning, skip the failed file, report in response (non-blocking for other files)
- Template JSON load failure → log error, use empty templates list (form still works, just no template selector)
- `get_provider()` returns `None` → render form in LLM-unavailable mode (topic required, different placeholders)

**TDD Steps:**

- [ ] **Step 1: Write the failing tests — write route GET**

Create `tests/unit/test_web_write_route.py`:

```python
"""Tests for Web GUI Write Route + Template — Phase 4b (Task 11b)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


def _get_test_client() -> TestClient:
    """Create a TestClient for the FastAPI app."""
    from web.app import create_app

    app = create_app()
    return TestClient(app)


# ── GET /write Route Tests ──────────────────────────────


class TestWriteRouteGET:
    """Test GET /write returns the write form."""

    def test_get_write_returns_200(self) -> None:
        """GET /write returns HTTP 200."""
        client = _get_test_client()
        response = client.get("/write")
        assert response.status_code == 200

    def test_get_write_contains_form(self) -> None:
        """GET /write response contains a form element."""
        client = _get_test_client()
        response = client.get("/write")
        assert "<form" in response.text
        assert 'method="post"' in response.text.lower() or 'method="POST"' in response.text

    def test_get_write_contains_content_textarea(self) -> None:
        """GET /write has a content textarea (required field)."""
        client = _get_test_client()
        response = client.get("/write")
        assert "content" in response.text
        assert "<textarea" in response.text.lower()

    def test_get_write_contains_topic_select(self) -> None:
        """GET /write has topic selection options."""
        client = _get_test_client()
        response = client.get("/write")
        # Should contain the 7 valid topics
        assert "work" in response.text
        assert "learn" in response.text
        assert "think" in response.text

    def test_get_write_contains_template_selector(self) -> None:
        """GET /write has a template selector dropdown."""
        client = _get_test_client()
        response = client.get("/write")
        # Template names from writing_templates.json
        assert "空白日志" in response.text

    def test_get_write_contains_csrf_token(self) -> None:
        """GET /write includes a hidden CSRF token field."""
        client = _get_test_client()
        response = client.get("/write")
        assert "csrf_token" in response.text

    def test_get_write_sets_csrf_cookie(self) -> None:
        """GET /write sets a CSRF token cookie."""
        client = _get_test_client()
        response = client.get("/write")
        assert "csrf_token" in response.cookies or "csrf" in str(response.headers.get("set-cookie", "")).lower()

    def test_get_write_contains_date_input(self) -> None:
        """GET /write has a date input field."""
        client = _get_test_client()
        response = client.get("/write")
        assert "date" in response.text

    def test_get_write_contains_location_input(self) -> None:
        """GET /write has a location input field."""
        client = _get_test_client()
        response = client.get("/write")
        assert "location" in response.text

    def test_get_write_contains_file_upload(self) -> None:
        """GET /write has a file upload input."""
        client = _get_test_client()
        response = client.get("/write")
        assert 'type="file"' in response.text.lower()

    def test_get_write_contains_submit_button(self) -> None:
        """GET /write has a submit button."""
        client = _get_test_client()
        response = client.get("/write")
        # Submit button text in Chinese
        assert "提交" in response.text or "保存" in response.text or "发布" in response.text


class TestWriteRouteLLMMode:
    """Test GET /write adapts to LLM availability."""

    @patch("web.routes.write.get_provider")
    def test_llm_available_shows_ai_hints(self, mock_get: MagicMock) -> None:
        """When LLM is available, form shows AI-related placeholder hints."""
        mock_get.return_value = AsyncMock()  # LLM available
        client = _get_test_client()
        response = client.get("/write")
        # Should contain AI-related hint text
        assert "AI" in response.text or "自动" in response.text

    @patch("web.routes.write.get_provider")
    def test_llm_unavailable_shows_manual_hints(self, mock_get: MagicMock) -> None:
        """When LLM is unavailable, form shows manual-fill hints."""
        mock_get.return_value = None  # LLM unavailable
        client = _get_test_client()
        response = client.get("/write")
        # The form should still render successfully
        assert response.status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/unit/test_web_write_route.py::TestWriteRouteGET -v
python -m pytest tests/unit/test_web_write_route.py::TestWriteRouteLLMMode -v
```

Expected: FAIL — either `ModuleNotFoundError: No module named 'web.routes.write'` or HTTP 404 (route not registered).

- [ ] **Step 3: Write the failing tests — write route POST**

Append to `tests/unit/test_web_write_route.py`:

```python
# ── POST /write Route Tests ──────────────────────────────


class TestWriteRoutePOST:
    """Test POST /write submission flow."""

    @patch("web.routes.write.write_journal_web")
    @patch("web.routes.write.prepare_journal_data")
    @patch("web.routes.write.get_provider")
    def test_post_write_success_redirects(
        self,
        mock_provider: MagicMock,
        mock_prepare: MagicMock,
        mock_write: MagicMock,
    ) -> None:
        """Successful POST /write redirects to journal view (HTTP 303)."""
        mock_provider.return_value = None
        mock_prepare.return_value = {
            "content": "测试正文",
            "date": "2026-03-07",
            "title": "测试标题",
            "topic": ["work"],
            "mood": [],
            "tags": [],
            "people": [],
            "abstract": "测试正文"[:100],
            "location": "Lagos, Nigeria",
        }
        mock_write.return_value = {
            "success": True,
            "journal_path": "C:/Users/.../Documents/Life-Index/Journals/2026/03/life-index_2026-03-07_001.md",
            "error": None,
        }

        client = _get_test_client()
        # First GET to obtain CSRF token
        get_response = client.get("/write")
        # Extract CSRF token from cookie
        csrf_token = get_response.cookies.get("csrf_token", "test-token")

        response = client.post(
            "/write",
            data={
                "content": "测试正文",
                "date": "2026-03-07",
                "topic": "work",
                "csrf_token": csrf_token,
            },
            cookies={"csrf_token": csrf_token},
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert "/journal/" in response.headers.get("location", "")

    @patch("web.routes.write.write_journal_web")
    @patch("web.routes.write.prepare_journal_data")
    @patch("web.routes.write.get_provider")
    def test_post_write_failure_rerenders_form(
        self,
        mock_provider: MagicMock,
        mock_prepare: MagicMock,
        mock_write: MagicMock,
    ) -> None:
        """Failed write re-renders the form with error message."""
        mock_provider.return_value = None
        mock_prepare.return_value = {
            "content": "测试正文",
            "date": "2026-03-07",
            "title": "测试",
            "topic": ["work"],
            "mood": [],
            "tags": [],
            "people": [],
            "abstract": "测试",
            "location": "Lagos",
        }
        mock_write.return_value = {
            "success": False,
            "error": "磁盘空间不足",
        }

        client = _get_test_client()
        get_response = client.get("/write")
        csrf_token = get_response.cookies.get("csrf_token", "test-token")

        response = client.post(
            "/write",
            data={
                "content": "测试正文",
                "date": "2026-03-07",
                "topic": "work",
                "csrf_token": csrf_token,
            },
            cookies={"csrf_token": csrf_token},
        )

        # Should re-render the form (200), not redirect
        assert response.status_code == 200
        assert "磁盘空间不足" in response.text or "错误" in response.text

    @patch("web.routes.write.prepare_journal_data")
    @patch("web.routes.write.get_provider")
    def test_post_write_validation_error_rerenders(
        self,
        mock_provider: MagicMock,
        mock_prepare: MagicMock,
    ) -> None:
        """ValueError from prepare_journal_data re-renders form with error."""
        mock_provider.return_value = None
        mock_prepare.side_effect = ValueError("LLM 不可用时，topic 为必填字段")

        client = _get_test_client()
        get_response = client.get("/write")
        csrf_token = get_response.cookies.get("csrf_token", "test-token")

        response = client.post(
            "/write",
            data={
                "content": "测试正文",
                "csrf_token": csrf_token,
            },
            cookies={"csrf_token": csrf_token},
        )

        assert response.status_code == 200
        assert "topic" in response.text

    def test_post_write_missing_content_shows_error(self) -> None:
        """POST /write with empty content shows validation error."""
        client = _get_test_client()
        get_response = client.get("/write")
        csrf_token = get_response.cookies.get("csrf_token", "test-token")

        response = client.post(
            "/write",
            data={
                "content": "",
                "csrf_token": csrf_token,
            },
            cookies={"csrf_token": csrf_token},
        )

        assert response.status_code == 200
        # Should show content-related error
        assert "content" in response.text.lower() or "正文" in response.text or "必填" in response.text


class TestWriteRouteCSRF:
    """Test CSRF protection on POST /write."""

    def test_post_without_csrf_returns_403(self) -> None:
        """POST /write without CSRF token returns HTTP 403."""
        client = _get_test_client()
        response = client.post(
            "/write",
            data={"content": "测试"},
        )
        assert response.status_code == 403

    def test_post_with_mismatched_csrf_returns_403(self) -> None:
        """POST /write with mismatched CSRF token returns HTTP 403."""
        client = _get_test_client()
        response = client.post(
            "/write",
            data={"content": "测试", "csrf_token": "invalid-token"},
            cookies={"csrf_token": "different-token"},
        )
        assert response.status_code == 403
```

- [ ] **Step 4: Run POST tests to verify they fail**

```bash
python -m pytest tests/unit/test_web_write_route.py::TestWriteRoutePOST -v
python -m pytest tests/unit/test_web_write_route.py::TestWriteRouteCSRF -v
```

Expected: FAIL — route not registered or module not found.

- [ ] **Step 5: Implement `web/routes/write.py`**

```python
"""Write route — journal creation form and submission handler.

GET /write:  Render the write form with template selector and smart-fill UI.
POST /write: Process form submission, call Write Service, redirect on success.

Per design-spec §5.4.
"""

from __future__ import annotations

import json
import logging
import secrets
import shutil
import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, Request, Response, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse

from web.services.llm_provider import get_provider
from web.services.write import prepare_journal_data, write_journal_web

logger = logging.getLogger(__name__)

router = APIRouter()

# Valid topic values (from AGENTS.md)
VALID_TOPICS: list[dict[str, str]] = [
    {"value": "work", "label": "工作 (work)"},
    {"value": "learn", "label": "学习 (learn)"},
    {"value": "health", "label": "健康 (health)"},
    {"value": "relation", "label": "关系 (relation)"},
    {"value": "think", "label": "思考 (think)"},
    {"value": "create", "label": "创作 (create)"},
    {"value": "life", "label": "生活 (life)"},
]

# Cache loaded templates (loaded once on first request)
_templates_cache: list[dict[str, Any]] | None = None


def _load_templates() -> list[dict[str, Any]]:
    """Load writing templates from JSON file.

    Returns cached templates after first load. Returns empty list on error.
    """
    global _templates_cache
    if _templates_cache is not None:
        return _templates_cache

    templates_path = Path(__file__).parent.parent / "templates" / "writing_templates.json"
    try:
        with open(templates_path, encoding="utf-8") as f:
            _templates_cache = json.load(f)
        logger.info("已加载 %d 个写作模板", len(_templates_cache))
        return _templates_cache
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error("加载写作模板失败: %s", e)
        _templates_cache = []
        return _templates_cache


def _generate_csrf_token() -> str:
    """Generate a cryptographically secure CSRF token."""
    return secrets.token_urlsafe(32)


def _validate_csrf(request: Request, form_token: str | None) -> bool:
    """Validate CSRF token from cookie matches form field.

    Args:
        request: FastAPI Request object.
        form_token: CSRF token from the submitted form field.

    Returns:
        True if tokens match and are non-empty, False otherwise.
    """
    cookie_token = request.cookies.get("csrf_token")
    if not cookie_token or not form_token:
        return False
    return secrets.compare_digest(cookie_token, form_token)


@router.get("/write", response_class=HTMLResponse)
async def write_form(request: Request) -> Response:
    """Render the journal write form.

    Checks LLM provider availability to adapt form placeholders.
    Loads writing templates for the template selector.
    Sets CSRF token cookie for form protection.
    """
    # Check LLM availability
    provider = await get_provider()
    llm_available = provider is not None

    # Load templates
    templates = _load_templates()

    # Generate CSRF token
    csrf_token = _generate_csrf_token()

    # Render template
    context = {
        "request": request,
        "llm_available": llm_available,
        "templates": templates,
        "templates_json": json.dumps(templates, ensure_ascii=False),
        "valid_topics": VALID_TOPICS,
        "csrf_token": csrf_token,
        "error": None,
        "form_data": {},
    }

    response = request.app.state.templates.TemplateResponse(
        "write.html",
        context,
    )
    # Set CSRF cookie (HttpOnly for security, SameSite=Strict)
    response.set_cookie(
        "csrf_token",
        csrf_token,
        httponly=True,
        samesite="strict",
        max_age=3600,  # 1 hour
    )
    return response


@router.post("/write", response_class=HTMLResponse)
async def write_submit(
    request: Request,
    content: str = Form(""),
    date: str = Form(""),
    title: str = Form(""),
    topic: list[str] = Form([]),
    mood: str = Form(""),
    tags: str = Form(""),
    people: str = Form(""),
    location: str = Form(""),
    project: str = Form(""),
    csrf_token: str = Form(""),
    attachment_urls: str = Form(""),
    attachments: list[UploadFile] = File([]),
) -> Response:
    """Process journal write form submission.

    Flow per design-spec §5.4.2:
    1. Validate CSRF token
    2. Collect user-filled fields from form
    3. Process file uploads to temp directory
    4. Call prepare_journal_data() with LLM provider
    5. Call write_journal_web() to write the journal
    6. On success: redirect to new journal
    7. On failure: re-render form with error + preserved input
    """
    # ── CSRF Validation ──
    if not _validate_csrf(request, csrf_token):
        return Response(
            content="请求验证失败，请刷新页面重试",
            status_code=403,
            media_type="text/html; charset=utf-8",
        )

    # ── Collect form data for re-rendering on error ──
    form_data_for_rerender: dict[str, Any] = {
        "content": content,
        "date": date,
        "title": title,
        "topic": topic,
        "mood": mood,
        "tags": tags,
        "people": people,
        "location": location,
        "project": project,
        "attachment_urls": attachment_urls,
    }

    temp_dir: str | None = None
    try:
        # ── Build form_data dict for Write Service ──
        form_data: dict[str, Any] = {}

        # Required field
        form_data["content"] = content.strip()

        # Optional fields — only include if non-empty
        if date.strip():
            form_data["date"] = date.strip()
        if title.strip():
            form_data["title"] = title.strip()
        if topic:
            # Topic comes as list from multi-select
            form_data["topic"] = [t for t in topic if t.strip()]
        if mood.strip():
            # Mood comes as comma-separated string from tag input
            form_data["mood"] = [m.strip() for m in mood.split(",") if m.strip()]
        if tags.strip():
            # Tags come as comma-separated string from tag input
            form_data["tags"] = [t.strip() for t in tags.split(",") if t.strip()]
        if people.strip():
            # People come as comma-separated string from tag input
            form_data["people"] = [p.strip() for p in people.split(",") if p.strip()]
        if location.strip():
            form_data["location"] = location.strip()
        if project.strip():
            form_data["project"] = project.strip()

        # ── Process file uploads ──
        attachment_paths: list[str] = []
        if attachments:
            uploaded_files = [f for f in attachments if f.filename and f.size and f.size > 0]
            if uploaded_files:
                temp_dir = tempfile.mkdtemp(prefix="life-index-upload-")
                for upload_file in uploaded_files:
                    try:
                        dest = Path(temp_dir) / upload_file.filename
                        with open(dest, "wb") as f:
                            content_bytes = await upload_file.read()
                            f.write(content_bytes)
                        attachment_paths.append(str(dest))
                        logger.info("已保存上传文件: %s", upload_file.filename)
                    except (IOError, OSError) as e:
                        logger.warning("上传文件保存失败 (%s): %s", upload_file.filename, e)

        if attachment_paths:
            form_data["attachments"] = attachment_paths

        # ── Collect URL attachments (Phase 5 will process these) ──
        if attachment_urls.strip():
            url_list = [u.strip() for u in attachment_urls.strip().split("\n") if u.strip()]
            if url_list:
                # Store URLs for future Phase 5 processing
                # For now, just pass them through (write_journal may or may not handle them)
                if "attachments" not in form_data:
                    form_data["attachments"] = []
                form_data["attachments"].extend(url_list)

        # ── Get LLM Provider ──
        provider = await get_provider()

        # ── Prepare journal data (LLM fill + fallback) ──
        prepared_data = await prepare_journal_data(form_data, provider)

        # ── Write journal ──
        result = await write_journal_web(prepared_data)

        if result.get("success"):
            # ── Success → redirect to new journal ──
            journal_path = result.get("journal_path", "")
            # Convert absolute path to relative path for URL
            # journal_path from write_journal may be absolute, or occasionally USER_DATA_DIR-relative
            # normalize to JOURNALS_DIR-relative path for routing
            relative_path = str(journal_path)
            if "Journals/" in relative_path:
                relative_path = relative_path.split("Journals/", 1)[1]
            elif "Journals\\" in relative_path:
                relative_path = relative_path.split("Journals\\", 1)[1]
            # Normalize path separators for URL
            relative_path = relative_path.replace("\\", "/")

            return RedirectResponse(
                url=f"/journal/{relative_path}",
                status_code=303,
            )
        else:
            # ── Failure → re-render form with error ──
            error_msg = result.get("error", "日志写入失败，请重试")
            return await _render_write_form(
                request, error=error_msg, form_data=form_data_for_rerender
            )

    except ValueError as e:
        # Validation error from prepare_journal_data
        return await _render_write_form(
            request, error=str(e), form_data=form_data_for_rerender
        )
    except Exception as e:
        logger.error("日志写入异常: %s", e, exc_info=True)
        return await _render_write_form(
            request, error=f"写入失败: {e}", form_data=form_data_for_rerender
        )
    finally:
        # ── Clean up temp files ──
        if temp_dir:
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
                logger.debug("已清理临时目录: %s", temp_dir)
            except Exception as e:
                logger.warning("清理临时目录失败: %s", e)


async def _render_write_form(
    request: Request,
    error: str | None = None,
    form_data: dict[str, Any] | None = None,
) -> Response:
    """Re-render the write form with error message and preserved input.

    Used when POST fails — preserves user input so they don't lose their work.
    """
    provider = await get_provider()
    llm_available = provider is not None
    templates = _load_templates()
    csrf_token = _generate_csrf_token()

    context = {
        "request": request,
        "llm_available": llm_available,
        "templates": templates,
        "templates_json": json.dumps(templates, ensure_ascii=False),
        "valid_topics": VALID_TOPICS,
        "csrf_token": csrf_token,
        "error": error,
        "form_data": form_data or {},
    }

    response = request.app.state.templates.TemplateResponse(
        "write.html",
        context,
    )
    response.set_cookie(
        "csrf_token",
        csrf_token,
        httponly=True,
        samesite="strict",
        max_age=3600,
    )
    return response
```

- [ ] **Step 6: Create `web/templates/write.html`**

```html
{% extends "base.html" %}

{% block title %}写日志 — Life Index{% endblock %}

{% block content %}
<div class="max-w-4xl mx-auto">
    <!-- 面包屑导航 -->
    <nav class="mb-6 text-sm text-gray-500">
        <a href="/" class="hover:text-blue-600">首页</a>
        <span class="mx-2">/</span>
        <span class="text-gray-800">写日志</span>
    </nav>

    <h1 class="text-2xl font-bold text-gray-800 mb-6">📝 写日志</h1>

    <!-- 错误提示 -->
    {% if error %}
    <div class="bg-red-50 border-l-4 border-red-500 p-4 mb-6 rounded">
        <div class="flex items-center">
            <span class="text-red-500 mr-2">⚠️</span>
            <p class="text-red-700">{{ error }}</p>
        </div>
    </div>
    {% endif %}

    <!-- 写入表单 -->
    <form method="POST" action="/write" enctype="multipart/form-data" class="space-y-6">
        <!-- CSRF Token -->
        <input type="hidden" name="csrf_token" value="{{ csrf_token }}">

        <!-- 模板选择器 -->
        <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">选择模板</label>
            <select id="template-selector"
                    class="w-full sm:w-auto px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    onchange="applyTemplate(this.value)">
                {% for tmpl in templates %}
                <option value="{{ tmpl.id }}">{{ tmpl.name }}</option>
                {% endfor %}
            </select>
        </div>

        <!-- 正文内容 (必填) -->
        <div>
            <label for="content" class="block text-sm font-medium text-gray-700 mb-1">
                日志正文 <span class="text-red-500">*</span>
            </label>
            <textarea id="content" name="content" rows="12" required
                      class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 font-mono text-sm"
                      placeholder="写下今天的故事...（支持 Markdown 格式）"
                      >{{ form_data.get('content', '') }}</textarea>
        </div>

        <!-- 元数据区域 -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <!-- 日期 -->
            <div>
                <label for="date" class="block text-sm font-medium text-gray-700 mb-1">日期</label>
                <input type="date" id="date" name="date"
                       value="{{ form_data.get('date', '') }}"
                       class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
            </div>

            <!-- 标题 -->
            <div>
                <label for="title" class="block text-sm font-medium text-gray-700 mb-1">标题</label>
                <input type="text" id="title" name="title"
                       value="{{ form_data.get('title', '') }}"
                       class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                       placeholder="{% if llm_available %}如不填写，AI 将自动生成标题{% else %}请手动填写标题{% endif %}">
            </div>

            <!-- 主题 (Topic) -->
            <div>
                <label for="topic" class="block text-sm font-medium text-gray-700 mb-1">
                    主题 {% if not llm_available %}<span class="text-red-500">*</span>{% endif %}
                </label>
                <select id="topic" name="topic" multiple
                        class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                        {% if not llm_available %}required{% endif %}>
                    {% for t in valid_topics %}
                    <option value="{{ t.value }}"
                            {% if t.value in form_data.get('topic', []) %}selected{% endif %}>
                        {{ t.label }}
                    </option>
                    {% endfor %}
                </select>
                <p class="mt-1 text-xs text-gray-500">
                    {% if llm_available %}如不填写，AI 将自动判断主题{% else %}请手动选择主题（LLM 不可用时为必填）{% endif %}
                </p>
            </div>

            <!-- 地点 -->
            <div>
                <label for="location" class="block text-sm font-medium text-gray-700 mb-1">地点</label>
                <div class="flex gap-2">
                    <input type="text" id="location" name="location"
                           value="{{ form_data.get('location', '') }}"
                           class="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                           placeholder="如不填写，将使用默认地点并自动查询天气">
                    <button type="button" onclick="getGeolocation()"
                            class="px-3 py-2 bg-gray-100 border border-gray-300 rounded-lg hover:bg-gray-200 text-sm"
                            title="获取当前位置">📍</button>
                </div>
            </div>
        </div>

        <!-- 标签类字段 -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
            <!-- 心情 (Mood) -->
            <div>
                <label for="mood" class="block text-sm font-medium text-gray-700 mb-1">心情</label>
                <input type="text" id="mood" name="mood"
                       value="{{ form_data.get('mood', '') }}"
                       class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                       placeholder="{% if llm_available %}如不填写，AI 将自动感知情绪{% else %}用逗号分隔，如：开心,充实{% endif %}">
            </div>

            <!-- 标签 (Tags) -->
            <div>
                <label for="tags" class="block text-sm font-medium text-gray-700 mb-1">标签</label>
                <input type="text" id="tags" name="tags"
                       value="{{ form_data.get('tags', '') }}"
                       class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                       placeholder="{% if llm_available %}如不填写，AI 将自动提取标签{% else %}用逗号分隔，如：编程,学习{% endif %}">
            </div>

            <!-- 人物 (People) -->
            <div>
                <label for="people" class="block text-sm font-medium text-gray-700 mb-1">人物</label>
                <input type="text" id="people" name="people"
                       value="{{ form_data.get('people', '') }}"
                       class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                       placeholder="{% if llm_available %}如不填写，AI 将自动识别提及的人物{% else %}用逗号分隔{% endif %}">
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

        <!-- 附件 -->
        <div class="space-y-4">
            <label class="block text-sm font-medium text-gray-700">附件</label>

            <!-- 文件上传 -->
            <div class="border-2 border-dashed border-gray-300 rounded-lg p-4">
                <label class="block text-center cursor-pointer">
                    <span class="text-gray-500">📎 点击选择文件或拖放到此处</span>
                    <input type="file" name="attachments" multiple class="hidden"
                           onchange="updateFileList(this)">
                </label>
                <div id="file-list" class="mt-2 text-sm text-gray-600"></div>
            </div>

            <!-- URL 附件输入 -->
            <div>
                <label for="attachment_urls" class="block text-xs text-gray-500 mb-1">
                    或输入文件 URL（每行一个）
                </label>
                <textarea id="attachment_urls" name="attachment_urls" rows="2"
                          class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm"
                          placeholder="https://example.com/photo.jpg"
                          >{{ form_data.get('attachment_urls', '') }}</textarea>
            </div>
        </div>

        <!-- 提交按钮 -->
        <div class="flex items-center justify-between pt-4 border-t border-gray-200">
            <a href="/" class="text-gray-600 hover:text-blue-600 text-sm">← 返回首页</a>
            <button type="submit"
                    class="px-6 py-2 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-colors">
                保存日志
            </button>
        </div>
    </form>
</div>
{% endblock %}

{% block scripts %}
<script>
// ── 模板数据 (from server) ──
const templates = {{ templates_json|safe }};

// ── 模板切换 ──
function applyTemplate(templateId) {
    const template = templates.find(t => t.id === templateId);
    if (!template) return;

    const contentEl = document.getElementById('content');
    const topicEl = document.getElementById('topic');

    // 如果用户已修改内容，弹出确认
    if (contentEl.value.trim() && templateId !== 'blank') {
        if (!confirm('切换模板将覆盖当前内容，确定吗？')) {
            // 恢复选择器到当前值
            document.getElementById('template-selector').value = 'blank';
            return;
        }
    }

    // 填充 content
    contentEl.value = template.content;

    // 填充 topic
    if (topicEl && template.topic) {
        Array.from(topicEl.options).forEach(opt => {
            opt.selected = template.topic.includes(opt.value);
        });
    }

    // 填充 tags
    if (template.tags && template.tags.length > 0) {
        const tagsEl = document.getElementById('tags');
        if (tagsEl && !tagsEl.value.trim()) {
            tagsEl.value = template.tags.join(', ');
        }
    }
}

// ── 浏览器地理定位 (§5.4.4) ──
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
                // 反向地理编码 (Nominatim)
                const response = await fetch(
                    `https://nominatim.openstreetmap.org/reverse?lat=${latitude}&lon=${longitude}&format=json&accept-language=zh`,
                    {
                        headers: {
                            'User-Agent': 'LifeIndex/2.0 (life-index-web-gui)'
                        }
                    }
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
                    document.getElementById('location').value = locationStr;
                } else {
                    document.getElementById('location').value = `${latitude.toFixed(4)}, ${longitude.toFixed(4)}`;
                }
            } catch (e) {
                document.getElementById('location').value = `${latitude.toFixed(4)}, ${longitude.toFixed(4)}`;
                console.warn('反向地理编码失败:', e);
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

// ── 文件列表更新 ──
function updateFileList(input) {
    const list = document.getElementById('file-list');
    if (input.files.length === 0) {
        list.textContent = '';
        return;
    }
    const names = Array.from(input.files).map(f => `📄 ${f.name} (${(f.size / 1024).toFixed(1)} KB)`);
    list.innerHTML = names.join('<br>');
}
</script>
{% endblock %}
```

- [ ] **Step 7: Register write router in `web/app.py`**

Add the following inside `create_app()`, after existing router registrations:

```python
from web.routes.write import router as write_router
app.include_router(write_router)
```

Follow the same lazy-import pattern used by existing routers (dashboard, journal, search).

- [ ] **Step 8: Run GET /write tests to verify they pass**

```bash
python -m pytest tests/unit/test_web_write_route.py::TestWriteRouteGET -v
python -m pytest tests/unit/test_web_write_route.py::TestWriteRouteLLMMode -v
```

Expected: All `TestWriteRouteGET` and `TestWriteRouteLLMMode` tests pass.

- [ ] **Step 9: Run POST /write tests to verify they pass**

```bash
python -m pytest tests/unit/test_web_write_route.py::TestWriteRoutePOST -v
python -m pytest tests/unit/test_web_write_route.py::TestWriteRouteCSRF -v
```

Expected: All `TestWriteRoutePOST` and `TestWriteRouteCSRF` tests pass.

- [ ] **Step 10: Run all Phase 4b tests**

```bash
python -m pytest tests/unit/test_web_write_route.py -v
```

Expected: All tests pass.

- [ ] **Step 11: Verify existing tests still pass**

```bash
python -m pytest tests/unit/ -q
```

Expected: 0 failures (including all Phase 1 + Phase 2 + Phase 3 + Phase 4a tests).

- [ ] **Step 12: Verify write form renders in browser**

```bash
life-index serve &
sleep 2
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8765/write
# Expected: 200
kill %1
```

- [ ] **Step 13: Commit**

```bash
git add web/routes/write.py web/templates/write.html tests/unit/test_web_write_route.py web/app.py
git commit -m "feat(web): add write route and template with smart-fill UI (Phase 4b)"
```

---

## Phase 4b Completion Checklist

Run all checks before declaring Phase 4b complete:

- [ ] **All Phase 4b tests pass:**

```bash
python -m pytest tests/unit/test_web_write_route.py -v
```

Expected: All tests in `TestWriteRouteGET`, `TestWriteRouteLLMMode`, `TestWriteRoutePOST`, `TestWriteRouteCSRF` pass.

- [ ] **All existing tests still pass:**

```bash
python -m pytest tests/unit/ -q
```

Expected: 0 failures (including all Phase 1 + Phase 2 + Phase 3 + Phase 4a tests).

- [ ] **Write route imports cleanly:**

```bash
python -c "from web.routes.write import router; print('OK')"
```

Expected: `OK` (no import errors).

- [ ] **Write form renders:**

```bash
life-index serve &
sleep 2
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8765/write
kill %1
```

Expected: `200`.

- [ ] **CSRF cookie is set:**

```bash
life-index serve &
sleep 2
curl -s -D - http://127.0.0.1:8765/write 2>/dev/null | grep -i "set-cookie.*csrf"
kill %1
```

Expected: `Set-Cookie: csrf_token=...` header present.

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
├── routes/
│   ├── dashboard.py         (existing — Phase 2)
│   ├── journal.py           (existing — Phase 3)
│   ├── search.py            (existing — Phase 3)
│   └── write.py             ✅ (created)
├── templates/
│   ├── base.html            (existing)
│   ├── dashboard.html       (existing — Phase 2)
│   ├── journal.html         (existing — Phase 3)
│   ├── search.html          (existing — Phase 3)
│   └── write.html           ✅ (created)
└── app.py                   (modified — register write router)

tests/unit/
└── test_web_write_route.py  ✅ (created)
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
task(subagent_type="momus", prompt="D:\\Loster AI\\Projects\\life-index\\docs\\web-gui\\plan-phase4b-write-route-template.md")
```
