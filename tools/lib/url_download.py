from __future__ import annotations

from datetime import datetime
import mimetypes
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024


def _normalize_url(url: str) -> str:
    stripped = url.strip()
    if stripped.startswith("http://"):
        return "https://" + stripped[len("http://") :]
    return stripped


def _guess_filename(url: str) -> str:
    name = Path(urlparse(url).path).name
    return name or "downloaded-attachment"


def _infer_content_type(filename: str, content_type: str) -> str:
    normalized = content_type.split(";")[0].strip().lower()
    if normalized:
        return normalized
    guessed, _ = mimetypes.guess_type(filename)
    return (guessed or "").lower()


def _dated_target_dir(target_dir: Path, date_str: str | None = None) -> Path:
    if date_str:
        try:
            dt = datetime.fromisoformat(str(date_str).replace("Z", "+00:00"))
        except ValueError:
            dt = datetime.strptime(str(date_str)[:10], "%Y-%m-%d")
    else:
        dt = datetime.now()
    return target_dir / str(dt.year) / f"{dt.month:02d}"


def _dedupe_filename(target_dir: Path, filename: str) -> str:
    candidate = target_dir / filename
    if not candidate.exists():
        return filename

    path = Path(filename)
    stem = path.stem or "downloaded-attachment"
    suffix = path.suffix
    index = 1
    while True:
        numbered = f"{stem}_{index}{suffix}"
        if not (target_dir / numbered).exists():
            return numbered
        index += 1


def _is_allowed_content_type(content_type: str) -> bool:
    lowered = content_type.lower()
    return (
        lowered.startswith("image/")
        or lowered.startswith("audio/")
        or lowered.startswith("video/")
        or lowered
        in {"application/pdf", "application/zip", "text/plain", "text/markdown"}
    )


async def download_url(
    url: str,
    target_dir: Path,
    *,
    date_str: str | None = None,
    timeout: float = 30.0,
) -> dict[str, Any]:
    normalized_url = _normalize_url(url)
    dated_dir = _dated_target_dir(target_dir, date_str=date_str)
    dated_dir.mkdir(parents=True, exist_ok=True)

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
            response = await client.get(normalized_url)
            response.raise_for_status()

            raw_filename = _guess_filename(normalized_url)
            content_type = _infer_content_type(
                raw_filename, str(response.headers.get("Content-Type", ""))
            )
            if not _is_allowed_content_type(content_type):
                return {
                    "success": False,
                    "url": normalized_url,
                    "error": f"Content-Type {content_type or 'unknown'} rejected",
                    "error_code": "E0702",
                }

            content_length = response.headers.get("Content-Length")
            if content_length:
                try:
                    if int(content_length) > MAX_FILE_SIZE_BYTES:
                        return {
                            "success": False,
                            "url": normalized_url,
                            "error": "文件大小超过 50MB 限制",
                            "error_code": "E0701",
                        }
                except ValueError:
                    pass

            filename = _dedupe_filename(dated_dir, raw_filename)
            output_path = dated_dir / filename
            total_size = 0
            with output_path.open("wb") as file_obj:
                async for chunk in response.aiter_bytes():
                    total_size += len(chunk)
                    if total_size > MAX_FILE_SIZE_BYTES:
                        file_obj.close()
                        output_path.unlink(missing_ok=True)
                        return {
                            "success": False,
                            "url": normalized_url,
                            "error": "文件大小超过 50MB 限制",
                            "error_code": "E0701",
                        }
                    file_obj.write(chunk)
    except Exception as exc:
        return {
            "success": False,
            "url": normalized_url,
            "error": str(exc),
            "error_code": "E0701",
        }

    return {
        "success": True,
        "path": str(output_path),
        "filename": filename,
        "size": total_size,
        "content_type": content_type,
    }


async def download_urls(
    urls: list[str],
    target_dir: Path,
    *,
    date_str: str | None = None,
    max_concurrent: int = 3,
) -> list[dict[str, Any]]:
    import asyncio

    semaphore = asyncio.Semaphore(max_concurrent)

    async def _download(url: str) -> dict[str, Any]:
        async with semaphore:
            return await download_url(url, target_dir, date_str=date_str)

    return list(await asyncio.gather(*[_download(url) for url in urls]))
