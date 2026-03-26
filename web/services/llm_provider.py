"""LLM provider abstraction for metadata extraction."""

from __future__ import annotations

import json
import logging
import os
import re
from abc import ABC, abstractmethod
from typing import Any

import httpx

from tools.lib.config import get_llm_config
from tools.lib.errors import ErrorCode

logger = logging.getLogger(__name__)


def _parse_json_object_from_text(text: str) -> dict[str, Any] | None:
    content_text = str(text or "").strip()
    if not content_text:
        return None

    content_text = re.sub(
        r"<think>.*?</think>", "", content_text, flags=re.DOTALL | re.IGNORECASE
    ).strip()

    if content_text.startswith("```"):
        lines = content_text.split("\n")
        content_text = "\n".join(
            lines[1:-1] if lines and lines[-1].strip() == "```" else lines[1:]
        ).strip()

    try:
        parsed = json.loads(content_text)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", content_text, re.DOTALL)
    if not match:
        return None

    try:
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None


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
    "你是 Life Index 日志助手。根据用户提供的日志正文，提炼元数据并严格返回 JSON。\n"
    "\n"
    "## 必填字段（必须全部返回，即使为空）\n"
    "| 字段 | 类型 | 说明 |\n"
    "|------|------|------|\n"
    "| title | string | 日志标题 |\n"
    "| abstract | string | ≤100字的摘要，由正文生成 |\n"
    "| topic | array | 主题分类，从下方 Topic 分类表中选择（必须选择，至少1个） |\n"
    '| mood | array | 心情标签，语义提取1~3个（如 ["开心", "专注"]） |\n'
    "| tags | array | 标签，语义提取关键词（可多个） |\n"
    "| people | array | 相关人物，没有则留空数组 [] |\n"
    '| project | string | 关联项目，没有则留空字符串 "" |\n'
    "\n"
    "## Topic 分类表（必填，至少选1个）\n"
    "| Topic | 含义 | 示例场景 |\n"
    "|-------|------|----------|\n"
    "| work | 工作/职业 | 项目进展、会议、职业发展 |\n"
    "| learn | 学习/成长 | 读书笔记、课程学习、技能提升 |\n"
    "| health | 健康/身体 | 运动、饮食、体检、医疗 |\n"
    "| relation | 关系/社交 | 家人、朋友、社交活动 |\n"
    "| think | 思考/反思 | 人生感悟、决策思考、复盘 |\n"
    "| create | 创作/产出 | 文章、代码、设计作品 |\n"
    "| life | 生活/日常 | 日常琐事、娱乐、购物 |\n"
    "\n"
    "## 返回格式要求\n"
    "- 必须返回标准 JSON 对象\n"
    "- 只返回 JSON，不要包含任何解释或额外文字\n"
    "- topic 必须从上方分类表中选择，不在此表中的值将被过滤掉\n"
    "- mood 最多3个\n"
    "- abstract 不超过100个字\n"
    "- abstract 必须是总结/归纳，不得机械复制正文开头连续句子\n"
    "- title 应简洁，不要直接原样复制全文第一整句，允许提炼\n"
    "- tags 应提炼 3~8 个高信息量关键词\n"
    "- 若正文明显描述项目/开发/代码/设计/产品工作，project 应尽量识别具体项目名"
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
            "temperature": 0.5,
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
            parsed = _parse_json_object_from_text(content_text)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            logger.warning(
                "%s: LLM 返回解析失败: %s", ErrorCode.LLM_EXTRACTION_FAILED, exc
            )
            return {}

        if not isinstance(parsed, dict):
            logger.warning(
                "%s: LLM 未返回可解析 JSON 对象", ErrorCode.LLM_EXTRACTION_FAILED
            )
            return {}

        # Normalize and harden extracted fields
        abstract = str(parsed.get("abstract") or "").strip()
        if abstract:
            abstract = abstract.replace("\n", " ").strip()
            if len(abstract) > 100:
                abstract = abstract[:100].rstrip("，。,. ")
        parsed["abstract"] = abstract

        parsed["title"] = str(parsed.get("title") or "").strip()
        parsed["project"] = str(parsed.get("project") or "").strip()

        for key in ("mood", "tags", "people"):
            value = parsed.get(key)
            if isinstance(value, list):
                parsed[key] = [str(item).strip() for item in value if str(item).strip()]
            elif isinstance(value, str) and value.strip():
                parsed[key] = [value.strip()]
            else:
                parsed[key] = []

        topics = parsed.get("topic")
        if isinstance(topics, list):
            parsed["topic"] = [
                str(topic) for topic in topics if str(topic) in VALID_TOPICS
            ]
        elif isinstance(topics, str) and topics in VALID_TOPICS:
            parsed["topic"] = [topics]
        else:
            parsed["topic"] = []

        return parsed

    async def summarize_search(
        self, query: str, results: list[dict[str, Any]]
    ) -> dict[str, Any]:
        if not await self.is_available() or not query or not results:
            return {}

        # Include ALL results for comprehensive summarization
        compact_results = [
            {
                "title": item.get("title", ""),
                "date": item.get("date", ""),
                "abstract": item.get("abstract", ""),
                "highlight": item.get("highlight", ""),
                "topic": item.get("topic", []),
                "people": item.get("people", []),
                "tags": item.get("tags", []),
                "mood": item.get("mood", []),
            }
            for item in results
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
            "temperature": 1.2,
            "max_tokens": 50000,
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
            parsed = _parse_json_object_from_text(content_text)
        except (httpx.HTTPError, KeyError, IndexError, TypeError, json.JSONDecodeError):
            return {}

        return parsed if isinstance(parsed, dict) else {}


async def get_provider() -> LLMProvider | None:
    providers: list[LLMProvider] = [HostAgentProvider(), APIKeyProvider()]
    for provider in providers:
        if await provider.is_available():
            return provider
    return None
