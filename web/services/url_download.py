"""URL download service for Web GUI attachments."""

import asyncio
from pathlib import Path
from typing import Any

import httpx

from tools.lib.url_download import download_url


async def download_urls(
    urls: list[str],
    target_dir: Path,
    *,
    date_str: str | None = None,
    max_concurrent: int = 3,
) -> list[dict[str, Any]]:
    semaphore = asyncio.Semaphore(max_concurrent)

    async def _download(url: str) -> dict[str, Any]:
        async with semaphore:
            return await download_url(url, target_dir, date_str=date_str)

    return list(await asyncio.gather(*[_download(url) for url in urls]))
