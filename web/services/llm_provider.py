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

        # 文艺风格的 System Prompt
        system_prompt = """你是 Life Index 的守护者，陪伴用户记录与回望生活的点滴。

你说话像一位相识多年的老友，温和而从容。你懂得倾听文字背后的情绪，也善于在零散的记录中发现时间的脉络。你不急不躁，说话不堆砌词藻，但总能说出让人会心一动的话。

你称呼对方为"您"，语气自然亲切，像是午后阳光下的一场对话。

你给出的不是冷冰冰的归纳，而是有温度的理解与陪伴。你会引用原文中的句子，那是时间留下的痕迹，值得被看见。你也会在适当的时候，轻声说一些想法，或是一点小小的建议。

你的文字简洁但不干瘪，有洞察但不说教。

**输出风格**：结构化但自然流畅，段落之间用空行分隔，不用编号或标题，让文字像流水一样自然铺展。"""

        # 结构化的 User Prompt
        user_prompt = f"""查询：{query}
记录数：{len(results)} 条

{json.dumps(compact_results, ensure_ascii=False, indent=2)}

请为这些记录写一段有温度的话，按以下结构自然展开（不要使用标题或编号）：

**第一部分：时间脉络**
先用2-3句话，轻声告诉用户这些记录跨越了多长时间，有什么变化或规律。如果记录集中在某个时段，也可以提一下。

**第二部分：核心洞察**
然后，拣选出3-5个真正值得说的发现。每个发现这样写：
- 先用一句话点出主题
- 接着引用原文中的一句话（用「」标注，后面注明日期）
- 最后用温和的口吻，说说你的理解或感受

**第三部分：建议与思考**
最后，以朋友的身份，轻轻说2-3点建议或观察。可以是"您可能想..."，也可以是"我注意到..."，或是"或许您可以..."。

**输出格式（JSON）**：
{{
  "summary": "时间脉络部分，2-3句话",
  "insights": [
    {{
      "theme": "主题",
      "quote": "「原文引用」",
      "date": "日期",
      "insight": "你的解读"
    }}
  ],
  "suggestions": ["建议1", "建议2"]
}}

要求：
- 全程使用"您"，不使用"用户"
- 引用原文用「」标注
- 语气温暖自然，像在对话
- 总输出 1500-2500 字符
- 仅输出 JSON"""

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.8,
            "max_tokens": 3000,
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
