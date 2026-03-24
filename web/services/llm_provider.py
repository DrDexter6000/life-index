"""LLM provider abstraction for metadata extraction."""

from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Any

import httpx

from tools.lib.config import get_llm_config
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

    @abstractmethod
    async def summarize_search(
        self, query: str, results: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """对搜索结果做 AI 归纳。"""


class HostAgentProvider(LLMProvider):
    async def extract_metadata(self, content: str) -> dict[str, Any]:
        return {}

    async def is_available(self) -> bool:
        return False

    async def summarize_search(
        self, query: str, results: list[dict[str, Any]]
    ) -> dict[str, Any]:
        return {}


class APIKeyProvider(LLMProvider):
    def __init__(self) -> None:
        config = get_llm_config()
        self.api_key = config["api_key"]
        self.base_url = config["base_url"]
        self.model = config["model"]

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

    async def summarize_search(
        self, query: str, results: list[dict[str, Any]]
    ) -> dict[str, Any]:
        if not await self.is_available() or not query or not results:
            return {}

        compact_results = [
            {
                "title": item.get("title", ""),
                "date": item.get("date", ""),
                "abstract": item.get("abstract", ""),
                "highlight": item.get("highlight", ""),
                "topic": item.get("topic", []),
            }
            for item in results[:8]
        ]
        prompt = (
            "请基于以下 Life Index 搜索结果，输出 JSON，格式为 "
            '{"summary": "一句到三句自然语言总结", "key_entries": [{"title": "标题", "date": "日期", "reason": "为什么重要"}], "time_span": "时间跨度"}。'
            "不要输出 JSON 以外的内容。\n"
            f"查询词：{query}\n结果：{json.dumps(compact_results, ensure_ascii=False)}"
        )

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "你是 Life Index 搜索归纳助手。请严格返回 JSON。",
                },
                {"role": "user", "content": prompt},
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
            response_json = response.json()
            content_text = response_json["choices"][0]["message"]["content"]
            parsed = json.loads(content_text)
        except (httpx.HTTPError, KeyError, IndexError, TypeError, json.JSONDecodeError):
            return {}

        return parsed if isinstance(parsed, dict) else {}


async def get_provider() -> LLMProvider | None:
    providers: list[LLMProvider] = [HostAgentProvider(), APIKeyProvider()]
    for provider in providers:
        if await provider.is_available():
            return provider
    return None
