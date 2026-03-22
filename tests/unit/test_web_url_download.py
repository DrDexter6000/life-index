#!/usr/bin/env python3
"""Tests for Web GUI URL download service — Phase 5."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime
from pathlib import Path
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestDownloadUrl:
    @pytest.mark.asyncio
    async def test_download_url_success(self, tmp_path: Path) -> None:
        from web.services.url_download import download_url

        mock_response = MagicMock()
        mock_response.headers = {
            "Content-Type": "image/jpeg",
            "Content-Length": "12",
        }
        mock_response.raise_for_status = MagicMock()

        async def iter_bytes() -> AsyncIterator[bytes]:
            yield b"hello world!"

        mock_response.aiter_bytes = iter_bytes

        with patch("web.services.url_download.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get.return_value = mock_response
            mock_client_class.return_value = mock_client

            result = await download_url("https://example.com/photo.jpg", tmp_path)

        assert result["success"] is True
        assert result["filename"] == "photo.jpg"
        assert result["content_type"] == "image/jpeg"
        assert result["size"] == 12
        assert Path(result["path"]).is_file()

    @pytest.mark.asyncio
    async def test_download_url_http_upgrades_to_https(self, tmp_path: Path) -> None:
        from web.services.url_download import download_url

        mock_response = MagicMock()
        mock_response.headers = {"Content-Type": "text/plain"}
        mock_response.raise_for_status = MagicMock()

        async def iter_bytes() -> AsyncIterator[bytes]:
            yield b"ok"

        mock_response.aiter_bytes = iter_bytes

        with patch("web.services.url_download.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get.return_value = mock_response
            mock_client_class.return_value = mock_client

            await download_url("http://example.com/file.txt", tmp_path)

        called_url = mock_client.get.await_args.args[0]
        assert called_url.startswith("https://")

    @pytest.mark.asyncio
    async def test_download_url_rejects_disallowed_content_type(
        self, tmp_path: Path
    ) -> None:
        from web.services.url_download import download_url

        mock_response = MagicMock()
        mock_response.headers = {"Content-Type": "text/html"}
        mock_response.raise_for_status = MagicMock()

        async def iter_bytes() -> AsyncIterator[bytes]:
            yield b"<html></html>"

        mock_response.aiter_bytes = iter_bytes

        with patch("web.services.url_download.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get.return_value = mock_response
            mock_client_class.return_value = mock_client

            result = await download_url("https://example.com/index.html", tmp_path)

        assert result["success"] is False
        assert result["error_code"] == "E0702"

    @pytest.mark.asyncio
    async def test_download_url_rejects_content_length_over_50mb(
        self, tmp_path: Path
    ) -> None:
        from web.services.url_download import download_url

        mock_response = MagicMock()
        mock_response.headers = {
            "Content-Type": "image/jpeg",
            "Content-Length": str(60 * 1024 * 1024),
        }
        mock_response.raise_for_status = MagicMock()

        async def iter_bytes() -> AsyncIterator[bytes]:
            yield b"unused"

        mock_response.aiter_bytes = iter_bytes

        with patch("web.services.url_download.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get.return_value = mock_response
            mock_client_class.return_value = mock_client

            result = await download_url("https://example.com/huge.jpg", tmp_path)

        assert result["success"] is False
        assert result["error_code"] == "E0701"
        assert "50" in result["error"]

    @pytest.mark.asyncio
    async def test_download_url_filename_conflict_appends_sequence(
        self, tmp_path: Path
    ) -> None:
        from web.services.url_download import download_url

        year_dir = tmp_path / str(datetime.now().year) / f"{datetime.now().month:02d}"
        year_dir.mkdir(parents=True)
        (year_dir / "photo.jpg").write_bytes(b"existing")

        mock_response = MagicMock()
        mock_response.headers = {"Content-Type": "image/jpeg"}
        mock_response.raise_for_status = MagicMock()

        async def iter_bytes() -> AsyncIterator[bytes]:
            yield b"new photo"

        mock_response.aiter_bytes = iter_bytes

        with patch("web.services.url_download.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get.return_value = mock_response
            mock_client_class.return_value = mock_client

            result = await download_url("https://example.com/photo.jpg", tmp_path)

        assert result["success"] is True
        assert result["filename"] == "photo_1.jpg"

    @pytest.mark.asyncio
    async def test_download_url_creates_yyyy_mm_subdirectory(
        self, tmp_path: Path
    ) -> None:
        from web.services.url_download import download_url

        mock_response = MagicMock()
        mock_response.headers = {"Content-Type": "image/png"}
        mock_response.raise_for_status = MagicMock()

        async def iter_bytes() -> AsyncIterator[bytes]:
            yield b"png"

        mock_response.aiter_bytes = iter_bytes

        with patch("web.services.url_download.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get.return_value = mock_response
            mock_client_class.return_value = mock_client

            result = await download_url("https://example.com/img.png", tmp_path)

        assert result["success"] is True
        rel_parts = Path(result["path"]).relative_to(tmp_path).parts
        assert str(datetime.now().year) in rel_parts
        assert f"{datetime.now().month:02d}" in rel_parts


class TestDownloadUrls:
    @pytest.mark.asyncio
    async def test_download_urls_partial_failure_continues(
        self, tmp_path: Path
    ) -> None:
        from web.services.url_download import download_urls

        async def fake_download(
            url: str, target_dir: Path, **_: object
        ) -> dict[str, object]:
            if "bad" in url:
                return {
                    "success": False,
                    "url": url,
                    "error": "bad",
                    "error_code": "E0701",
                }
            return {
                "success": True,
                "path": str(target_dir / "ok.txt"),
                "filename": "ok.txt",
                "size": 2,
                "content_type": "text/plain",
            }

        with patch("web.services.url_download.download_url", new=fake_download):
            results = await download_urls(
                [
                    "https://example.com/ok.txt",
                    "https://example.com/bad.txt",
                ],
                tmp_path,
            )

        assert len(results) == 2
        assert results[0]["success"] is True
        assert results[1]["success"] is False

    @pytest.mark.asyncio
    async def test_download_urls_respects_max_concurrent(self, tmp_path: Path) -> None:
        from web.services.url_download import download_urls

        in_flight = 0
        max_seen = 0

        async def fake_download(
            url: str, target_dir: Path, **_: object
        ) -> dict[str, object]:
            nonlocal in_flight, max_seen
            in_flight += 1
            max_seen = max(max_seen, in_flight)
            await asyncio.sleep(0.01)
            in_flight -= 1
            return {
                "success": True,
                "path": str(target_dir / "ok.txt"),
                "filename": "ok.txt",
                "size": 2,
                "content_type": "text/plain",
            }

        with patch("web.services.url_download.download_url", new=fake_download):
            await download_urls(
                [f"https://example.com/{index}.txt" for index in range(6)],
                tmp_path,
                max_concurrent=2,
            )

        assert max_seen <= 2


class TestTimeoutAndAllowlist:
    @pytest.mark.asyncio
    async def test_download_url_timeout_returns_e0701(self, tmp_path: Path) -> None:
        from web.services.url_download import download_url
        import httpx

        with patch("web.services.url_download.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get.side_effect = httpx.TimeoutException("timeout")
            mock_client_class.return_value = mock_client

            result = await download_url("https://example.com/slow.jpg", tmp_path)

        assert result["success"] is False
        assert result["error_code"] == "E0701"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("content_type", "allowed"),
        [
            ("image/jpeg", True),
            ("audio/mpeg", True),
            ("video/mp4", True),
            ("application/pdf", True),
            ("application/zip", True),
            ("text/plain", True),
            ("text/markdown", True),
            ("text/html", False),
            ("application/x-executable", False),
            ("application/javascript", False),
        ],
    )
    async def test_download_url_content_type_allowlist(
        self,
        content_type: str,
        allowed: bool,
        tmp_path: Path,
    ) -> None:
        from web.services.url_download import download_url

        mock_response = MagicMock()
        mock_response.headers = {"Content-Type": content_type}
        mock_response.raise_for_status = MagicMock()

        async def iter_bytes() -> AsyncIterator[bytes]:
            yield b"data"

        mock_response.aiter_bytes = iter_bytes

        with patch("web.services.url_download.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get.return_value = mock_response
            mock_client_class.return_value = mock_client

            result = await download_url(
                f"https://example.com/file.{content_type.split('/')[-1]}",
                tmp_path,
            )

        assert result["success"] is allowed
        if not allowed:
            assert result["error_code"] == "E0702"
