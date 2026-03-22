"""LLM provider abstraction for metadata extraction."""

from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Any

import httpx

from tools.lib.errors import ErrorCode

logger = logging.getLogger(__name__)

VALID_TOPICS: set[str] = {
    "work",
    "learn",
    "health",
    "relation",
    "think",
    "create",
    "life",
}

EXTRACTION_SYSTEM_PROMPT = (
    """你是 Life Index 日志助手。根据用户提供的日志正文，提炼元数据并严格返回 JSON。"""
)


class LLMProvider(ABC):
    @abstractmethod
    async def extract_metadata(self, content: str) -> dict[str, Any]:
        """从日志正文中提炼元数据。"""

    @abstractmethod
    async def is_available(self) -> bool:
        """检查 Provider 是否可用。"""


class HostAgentProvider(LLMProvider):
    async def extract_metadata(self, content: str) -> dict[str, Any]:
        return {}

    async def is_available(self) -> bool:
        return False


class APIKeyProvider(LLMProvider):
    def __init__(self) -> None:
        self.api_key = os.getenv("LIFE_INDEX_LLM_API_KEY", "").strip()
        self.base_url = os.getenv(
            "LIFE_INDEX_LLM_BASE_URL", "https://api.openai.com/v1"
        ).strip()
        self.model = os.getenv("LIFE_INDEX_LLM_MODEL", "gpt-4o-mini").strip()

    async def is_available(self) -> bool:
        return bool(self.api_key)

    async def extract_metadata(self, content: str) -> dict[str, Any]:
        if not await self.is_available():
            return {}

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": content},
            ],
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url.rstrip('/')}/chat/completions",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("%s: LLM 请求失败: %s", ErrorCode.LLM_EXTRACTION_FAILED, exc)
            return {}

        try:
            response_json = response.json()
            content_text = response_json["choices"][0]["message"]["content"]
            parsed = json.loads(content_text)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            logger.warning(
                "%s: LLM 返回解析失败: %s", ErrorCode.LLM_EXTRACTION_FAILED, exc
            )
            return {}

        topics = parsed.get("topic")
        if isinstance(topics, list):
            parsed["topic"] = [
                str(topic) for topic in topics if str(topic) in VALID_TOPICS
            ]

        return parsed if isinstance(parsed, dict) else {}


async def get_provider() -> LLMProvider | None:
    providers: list[LLMProvider] = [HostAgentProvider(), APIKeyProvider()]
    for provider in providers:
        if await provider.is_available():
            return provider
    return None
