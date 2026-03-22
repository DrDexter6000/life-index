# Phase 5: Polish (URL Download + CSRF + E2E) — TDD Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** URL download service downloads remote attachments with Content-Type validation and size limits. Existing route-level CSRF contract is verified and kept consistent across Write/Edit. E2E smoke test verifies the full write→search→view→edit flow with mocked tools/ modules.

**Architecture:** `web/services/url_download.py` uses `httpx.AsyncClient` with semaphore-based concurrency limiting (max 3). Content-Type allowlist rejects dangerous types. CSRF stays on the existing route-level double-submit-cookie pattern established in Phase 4b/4c (`csrf_token` cookie + hidden `csrf_token` form field); Phase 5 verifies and de-duplicates that contract rather than replacing it with middleware/session state. `tests/integration/test_web_e2e.py` uses FastAPI TestClient with fully mocked tools/ modules for deterministic testing.

**Tech Stack:** Python 3.11+ (asyncio, httpx, pathlib), FastAPI, Starlette Middleware, FastAPI TestClient

**Spec Reference:** `docs/web-gui/design-spec.md` v1.4 — §5.4.3 (URL Download Constraints), §6.3 (CSRF Protection), §6.4 (Testing)

---

## Phase Scope

| Task | Component | Difficulty | Time Est. |
|:--|:--|:--|:--|
| Task 13 | URL Download Service — `web/services/url_download.py` + `tests/unit/test_web_url_download.py` | Medium | 40 min |
| Task 14 | CSRF Contract Verification + E2E Smoke Test — `tests/unit/test_web_csrf.py` + `tests/integration/test_web_e2e.py` | Medium | 50 min |

## Status note

- ✅ Phase 4 write / edit 主链路现已跑通，且已通过更大范围 web regression
- ✅ 独立 `web/services/url_download.py` 已抽离，并已接入当前 write flow
- ✅ URL download 单测、CSRF contract 测试、integration/E2E smoke test 已补齐
- ⚠️ Phase 5 剩余价值已转为 **更严格 spec 对齐与细节 polish**，而非主链路缺失

**Dependencies:** Task 13 depends on Phase 4 Task 11 (write page — the integration point). Task 14 depends on Phase 4 Tasks 11 and 12 (write + edit pages — POST endpoints need CSRF protection). Tasks 13 and 14 are independent of each other.

## Current residual deltas

- 当前 `url_download.py` 已覆盖：HTTP→HTTPS upgrade、timeout classification、allowlist 测试、50MB limit、filename conflict suffixing、YYYY/MM archival layout、batch concurrency guard
- 仍建议持续关注的 residual polish：
  - 设计文档与测试矩阵的 reject-list 描述保持完全一致（如 `application/javascript`）
  - 设计文档对 4xx/5xx → `E0701` 的映射说明更明确
  - 如后续需要，可继续补更严格的下载错误消息与更细粒度流式大小测试

---

## Prerequisites

Before starting, verify Phase 4 is complete:

```bash
python -m pytest tests/unit/test_web_write.py -v   # All Phase 4 write tests pass
python -m pytest tests/unit/test_web_edit.py -v   # All Phase 4 edit tests pass
python -m pytest tests/unit/ -q                    # All tests pass
life-index serve &                                 # Server starts
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8765/  # 200
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8765/write  # 200
kill %1
```

Read these files (required context):
- `docs/web-gui/design-spec.md` §5.4.3 — URL download constraints (protocol, size, timeout, concurrency, Content-Type allowlist)
- `docs/web-gui/design-spec.md` §6.3 — CSRF protection requirements (token in cookie, form field, 403 on mismatch)
- `docs/web-gui/design-spec.md` §6.4 — Testing strategy (TestClient, mocks, E2E coverage)
- `tools/lib/errors.py` — E0701, E0702 error code definitions and recovery strategies
- `tools/lib/config.py` — `ATTACHMENTS_DIR` constant for download target directory
- `tools/write_journal/attachments.py` — `_strip_cjk_spaces()` utility used in filename handling
- `web/app.py` — `create_app()` factory pattern (existing Phase 1-3 code)
- `web/services/write.py` — Write service with `write_journal()` call (Phase 4 code)

### Key Data Contracts

**URL download result dict:**
```python
# Success
{
    "success": True,
    "path": Path("/full/path/to/attachments/2026/03/file.jpg"),
    "filename": "photo.jpg",
    "size": 102400,
    "content_type": "image/jpeg"
}

# Failure
{
    "success": False,
    "url": "https://evil.example.com/file.exe",
    "error": "Content-Type application/x-executable rejected",
    "error_code": "E0702"
}
```

**CSRF contract behavior:**
```python
# GET request (safe method): route generates token and sets csrf_token cookie

# POST request (unsafe method): route validates token
# - Read token from cookie "csrf_token"
# - Read token from form field "csrf_token"
# - If match: call next
# - If mismatch or missing: return HTTP 403
```

**download_urls() function signature:**
```python
async def download_urls(
    urls: list[str],
    target_dir: Path,
    *,
    max_concurrent: int = 3,
) -> list[dict[str, Any]]:
    """Download multiple URLs with concurrency limit.

    Args:
        urls: List of HTTPS URLs to download
        target_dir: Directory to save downloaded files
        max_concurrent: Max simultaneous downloads (default 3)

    Returns:
        List of result dicts (see above)
    """
```

---

## Task 13: URL Download Service (`web/services/url_download.py`)

**Files:**
- Create: `web/services/url_download.py`
- Create: `tests/unit/test_web_url_download.py`

**Difficulty:** Medium (~40 min)

**Acceptance Criteria:**
1. `download_url()` downloads a single URL to `target_dir` using `httpx.AsyncClient`
2. HTTPS-only enforcement: HTTP URLs are auto-upgraded to HTTPS
3. File size limit enforced: 50 MB max, using `Content-Length` header when available, streaming byte-count when missing
4. Download timeout enforced: 30 seconds per URL
5. Concurrency limit enforced: max 3 simultaneous downloads via `asyncio.Semaphore`
6. Content-Type allowlist enforced: `image/*`, `audio/*`, `video/*`, `application/pdf`, `application/zip`, `text/plain`, `text/markdown`. Rejects `text/html`, `application/x-executable`, etc.
7. Content-Type missing → infer from file extension using `mimetypes.guess_type()`
8. File naming: preserve original filename; on conflict (file exists), append `_{n}` sequence
9. Returns structured result dict with `success`, `path`, `filename`, `size`, `content_type` (on success) or `success=False`, `url`, `error`, `error_code` (on failure)
10. `download_urls()` downloads multiple URLs concurrently with semaphore limiting
11. Failed URLs are listed with error reason; single URL failure does NOT block other downloads
12. Downloaded files archived to `attachments/YYYY/MM/` subdirectory structure
13. Error code `E0701` (URL_DOWNLOAD_FAILED) for network errors/timeouts; error code `E0702` (URL_CONTENT_TYPE_REJECTED) for disallowed Content-Type
14. All file I/O uses `pathlib.Path`

**Subagent Governance:**
- MUST DO: Use `httpx.AsyncClient` with async context manager (`async with`)
- MUST DO: Use `asyncio.Semaphore` for concurrency limiting
- MUST DO: Use streaming (`response.aiter_bytes()`) to enforce size limits without reading entire file into memory
- MUST DO: Check `Content-Length` header when present; fall back to streaming byte count when absent
- MUST DO: Auto-upgrade HTTP URLs to HTTPS before downloading
- MUST DO: Use `mimetypes.guess_type()` to infer Content-Type from file extension when header is missing
- MUST DO: Implement Content-Type allowlist per design-spec §5.4.3 table
- MUST DO: Use `shutil.copyfileobj()` for efficient file writing from response stream
- MUST DO: Return structured dict with `success`, `path`, `filename`, `size`, `content_type` keys on success
- MUST DO: Return structured dict with `success=False`, `url`, `error`, `error_code` keys on failure
- MUST DO: Create target subdirectory `YYYY/MM/` under `target_dir` if it does not exist
- MUST DO: Handle filename conflicts by appending `_{n}` sequence before extension
- MUST DO: Use Chinese text for all user-facing error messages
- MUST NOT DO: Use `requests` library — must use `httpx` for async support
- MUST NOT DO: Read entire file into memory before writing — stream it
- MUST NOT DO: Skip Content-Type validation — this is a security requirement
- MUST NOT DO: Block on download failure — return error dict and continue processing other URLs

**Error Handling:**
- Network error (timeout, DNS, connection refused) → `E0701` with error message
- HTTP 4xx/5xx response → `E0701` with status code in error message
- Content-Type rejected → `E0702` with allowed types in error message
- File write error (disk full, permission) → `E0701` with error message
- Invalid URL (missing scheme) → `E0701` with error message

**TDD Steps:**

- [ ] **Step 1: Write the failing tests — URL download service**

Create `tests/unit/test_web_url_download.py`:

```python
"""Tests for Web GUI URL Download Service — Phase 5 (Task 13)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import patch, MagicMock, AsyncMock

import pytest


class TestDownloadUrl:
    """Test single URL download function."""

    @pytest.mark.asyncio
    async def test_download_url_success(self, tmp_path: Path) -> None:
        """Successful download returns success dict with path, size, content_type."""
        from web.services.url_download import download_url

        mock_response = AsyncMock()
        mock_response.headers = {"Content-Type": "image/jpeg", "Content-Length": "1024"}
        mock_response.aiter_bytes = lambda chunk_size: iter([b"fake image data"])

        async def mock_async_iter_bytes(chunk_size: int = 8192):
            yield b"fake image data"

        mock_response.aiter_bytes = mock_async_iter_bytes
        mock_response.status_code = 200

        with patch("web.services.url_download.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await download_url(
                "https://example.com/photo.jpg",
                tmp_path,
                timeout=30.0,
            )

        assert result["success"] is True
        assert "path" in result
        assert result["filename"] == "photo.jpg"
        assert result["size"] > 0
        assert result["content_type"] == "image/jpeg"

    @pytest.mark.asyncio
    async def test_download_url_http_upgraded_to_https(self, tmp_path: Path) -> None:
        """HTTP URLs are auto-upgraded to HTTPS."""
        from web.services.url_download import download_url

        mock_response = AsyncMock()
        mock_response.headers = {"Content-Type": "image/png"}
        mock_response.aiter_bytes = lambda chunk_size: iter([b"png data"])
        mock_response.status_code = 200

        async def mock_async_iter_bytes(chunk_size: int = 8192):
            yield b"png data"

        mock_response.aiter_bytes = mock_async_iter_bytes

        with patch("web.services.url_download.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            await download_url("http://example.com/photo.png", tmp_path)

            # Verify HTTPS was used
            called_url = mock_client.get.call_args[0][0]
            assert called_url.startswith("https://")

    @pytest.mark.asyncio
    async def test_download_url_content_type_rejected(self, tmp_path: Path) -> None:
        """Disallowed Content-Type returns error dict with E0702."""
        from web.services.url_download import download_url

        mock_response = AsyncMock()
        mock_response.headers = {"Content-Type": "application/x-executable"}
        mock_response.status_code = 200
        mock_response.aiter_bytes = lambda chunk_size: iter([b"binary data"])

        async def mock_async_iter_bytes(chunk_size: int = 8192):
            yield b"binary data"

        mock_response.aiter_bytes = mock_async_iter_bytes

        with patch("web.services.url_download.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await download_url(
                "https://example.com/evil.exe",
                tmp_path,
            )

        assert result["success"] is False
        assert result["error_code"] == "E0702"
        assert "Content-Type" in result["error"]

    @pytest.mark.asyncio
    async def test_download_url_infers_content_type_from_extension(
        self, tmp_path: Path
    ) -> None:
        """Missing Content-Type header: infer from file extension."""
        from web.services.url_download import download_url

        mock_response = AsyncMock()
        mock_response.headers = {}  # No Content-Type header
        mock_response.status_code = 200

        async def mock_async_iter_bytes(chunk_size: int = 8192):
            yield b"pdf content"

        mock_response.aiter_bytes = mock_async_iter_bytes

        with patch("web.services.url_download.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await download_url(
                "https://example.com/document.pdf",
                tmp_path,
            )

        assert result["success"] is True
        assert result["content_type"] == "application/pdf"

    @pytest.mark.asyncio
    async def test_download_url_timeout(self, tmp_path: Path) -> None:
        """Timeout raises exception caught and returned as E0701 error."""
        from web.services.url_download import download_url
        import httpx

        with patch("web.services.url_download.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get = AsyncMock(
                side_effect=httpx.TimeoutException("Request timeout")
            )
            mock_client_class.return_value = mock_client

            result = await download_url(
                "https://example.com/slow.jpg",
                tmp_path,
            )

        assert result["success"] is False
        assert result["error_code"] == "E0701"

    @pytest.mark.asyncio
    async def test_download_url_content_length_exceeds_limit(self, tmp_path: Path) -> None:
        """Content-Length > 50MB returns error without downloading body."""
        from web.services.url_download import download_url

        mock_response = AsyncMock()
        mock_response.headers = {
            "Content-Type": "image/jpeg",
            "Content-Length": str(60 * 1024 * 1024),  # 60MB
        }
        mock_response.status_code = 200
        mock_response.aiter_bytes = lambda chunk_size: iter([])

        with patch("web.services.url_download.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await download_url(
                "https://example.com/huge.jpg",
                tmp_path,
            )

        assert result["success"] is False
        assert result["error_code"] == "E0701"
        assert "50" in result["error"]  # mentions size limit

    @pytest.mark.asyncio
    async def test_download_url_filename_conflict_gets_sequence(
        self, tmp_path: Path
    ) -> None:
        """When filename exists, appends _1, _2 etc. sequence."""
        from web.services.url_download import download_url

        # Create existing file
        existing = tmp_path / "photo.jpg"
        existing.write_bytes(b"existing")

        mock_response = AsyncMock()
        mock_response.headers = {"Content-Type": "image/jpeg"}
        mock_response.status_code = 200

        async def mock_async_iter_bytes(chunk_size: int = 8192):
            yield b"new photo"

        mock_response.aiter_bytes = mock_async_iter_bytes

        with patch("web.services.url_download.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await download_url(
                "https://example.com/photo.jpg",
                tmp_path,
            )

        assert result["success"] is True
        assert result["filename"] == "photo_1.jpg"

    @pytest.mark.asyncio
    async def test_download_url_creates_YYYY_MM_subdirectory(
        self, tmp_path: Path
    ) -> None:
        """Download creates YYYY/MM subdirectory under target_dir."""
        from web.services.url_download import download_url

        mock_response = AsyncMock()
        mock_response.headers = {"Content-Type": "image/png"}
        mock_response.status_code = 200

        async def mock_async_iter_bytes(chunk_size: int = 8192):
            yield b"png"

        mock_response.aiter_bytes = mock_async_iter_bytes

        with patch("web.services.url_download.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            # Use a date in March 2026
            result = await download_url(
                "https://example.com/img.png",
                tmp_path,
            )

        assert result["success"] is True
        # Path should include 2026/03 subdirectory
        rel_parts = result["path"].relative_to(tmp_path).parts
        assert "2026" in rel_parts
        assert "03" in rel_parts


class TestDownloadUrls:
    """Test batch URL download with concurrency limiting."""

    @pytest.mark.asyncio
    async def test_download_urls_respects_max_concurrent(self, tmp_path: Path) -> None:
        """download_urls limits concurrency to max_concurrent."""
        from web.services.url_download import download_urls

        call_count = 0
        max_concurrent = 0

        async def mock_download_url(url: str, target_dir: Path, **kwargs) -> dict:
            nonlocal call_count, max_concurrent
            call_count += 1
            current = call_count
            max_concurrent = max(max_concurrent, current)
            await asyncio.sleep(0.05)  # Simulate network delay
            return {"success": True, "url": url, "path": target_dir / "f.txt", "filename": "f.txt", "size": 1, "content_type": "text/plain"}

        with patch("web.services.url_download.download_url", new=mock_download_url):
            urls = [f"https://example.com/file{i}.txt" for i in range(6)]
            results = await download_urls(urls, tmp_path, max_concurrent=2)

        # With max_concurrent=2, we should never have more than 2 in-flight
        assert max_concurrent <= 2
        assert len(results) == 6
        assert all(r["success"] for r in results)

    @pytest.mark.asyncio
    async def test_download_urls_partial_failure_continues(self, tmp_path: Path) -> None:
        """Single URL failure does not block other downloads."""
        from web.services.url_download import download_urls

        async def mock_download_url(url: str, target_dir: Path, **kwargs) -> dict:
            if "fail" in url:
                return {
                    "success": False,
                    "url": url,
                    "error": "Network error",
                    "error_code": "E0701",
                }
            return {
                "success": True,
                "url": url,
                "path": target_dir / "ok.txt",
                "filename": "ok.txt",
                "size": 1,
                "content_type": "text/plain",
            }

        with patch("web.services.url_download.download_url", new=mock_download_url):
            urls = [
                "https://example.com/ok1.txt",
                "https://example.com/fail.txt",
                "https://example.com/ok2.txt",
            ]
            results = await download_urls(urls, tmp_path)

        assert len(results) == 3
        # Both ok files should succeed
        assert results[0]["success"] is True
        assert results[2]["success"] is True
        # Fail file should be marked as failure
        assert results[1]["success"] is False
        assert results[1]["error_code"] == "E0701"


class TestContentTypeAllowlist:
    """Test Content-Type allowlist validation."""

    ALLOWED_TYPES = [
        ("image/jpeg", True),
        ("image/png", True),
        ("image/gif", True),
        ("audio/mpeg", True),
        ("audio/wav", True),
        ("video/mp4", True),
        ("application/pdf", True),
        ("application/zip", True),
        ("text/plain", True),
        ("text/markdown", True),
        ("text/html", False),
        ("application/x-executable", False),
        ("application/javascript", False),
    ]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("content_type,allowed", ALLOWED_TYPES)
    async def test_content_type_allowlist(
        self, content_type: str, allowed: bool, tmp_path: Path
    ) -> None:
        """Content-Type allowlist is enforced correctly."""
        from web.services.url_download import download_url

        mock_response = AsyncMock()
        mock_response.headers = {"Content-Type": content_type}
        mock_response.status_code = 200

        async def mock_async_iter_bytes(chunk_size: int = 8192):
            yield b"data"

        mock_response.aiter_bytes = mock_async_iter_bytes

        with patch("web.services.url_download.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await download_url(
                f"https://example.com/file.{content_type.split('/')[-1]}",
                tmp_path,
            )

        if allowed:
            assert result["success"] is True, f"{content_type} should be allowed"
        else:
            assert result["success"] is False
            assert result["error_code"] == "E0702"
