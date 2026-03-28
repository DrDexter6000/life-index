"""LLM provider abstraction for metadata extraction."""

from __future__ import annotations

import json
import logging
import os
import re
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from typing import Any

import httpx

from tools.lib.config import get_llm_config
from tools.lib.errors import ErrorCode

logger = logging.getLogger(__name__)


def _parse_json_object_from_text(text: str) -> dict[str, Any] | None:
    content_text = str(text or "").strip()
    if not content_text:
        return None

    # Strip closed <think>…</think> blocks (greedy to handle nested/multiline)
    content_text = re.sub(
        r"<think>.*?</think>", "", content_text, flags=re.DOTALL | re.IGNORECASE
    ).strip()

    # Strip unclosed <think> tags (model started reasoning but never closed)
    # Case 1: <think>...{no closing tag} — everything from <think> to end is noise
    content_text = re.sub(
        r"<think>.*", "", content_text, flags=re.DOTALL | re.IGNORECASE
    ).strip()

    # Strip markdown code fences
    if content_text.startswith("```"):
        lines = content_text.split("\n")
        content_text = "\n".join(
            lines[1:-1] if lines and lines[-1].strip() == "```" else lines[1:]
        ).strip()

    # Attempt 1: direct parse
    try:
        parsed = json.loads(content_text)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass

    # Attempt 2: extract first { … } block via greedy match
    match = re.search(r"\{.*\}", content_text, re.DOTALL)
    if not match:
        return None

    try:
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass

    # Attempt 3: balanced-brace extraction for cases where greedy match
    # grabbed too much (e.g. trailing text after the JSON object)
    brace_start = content_text.find("{")
    if brace_start == -1:
        return None
    depth = 0
    in_string = False
    escape_next = False
    for i, ch in enumerate(content_text[brace_start:], start=brace_start):
        if escape_next:
            escape_next = False
            continue
        if ch == "\\":
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                candidate = content_text[brace_start : i + 1]
                try:
                    parsed = json.loads(candidate)
                    return parsed if isinstance(parsed, dict) else None
                except json.JSONDecodeError:
                    return None

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
        """对搜索结果做 AI 归纳（同步模式，作为 fallback）。"""

    async def stream_summarize_search(
        self, query: str, results: list[dict[str, Any]]
    ) -> AsyncGenerator[dict[str, Any], None]:
        """对搜索结果做 AI 归纳（流式模式）。

        Yields:
            {"type": "meta", "total": N} — 搜索结果数量
            {"type": "text", "content": "..."} — 文本片段
            {"type": "done"} — 流结束
            {"type": "error", "message": "..."} — 错误信息
        """
        # 默认实现：直接返回 done（子类可覆盖）
        yield {"type": "done"}


class HostAgentProvider(LLMProvider):
    async def extract_metadata(self, content: str) -> dict[str, Any]:
        return {}

    async def is_available(self) -> bool:
        return False

    async def summarize_search(
        self, query: str, results: list[dict[str, Any]]
    ) -> dict[str, Any]:
        return {}

    async def stream_summarize_search(
        self, query: str, results: list[dict[str, Any]]
    ) -> AsyncGenerator[dict[str, Any], None]:
        yield {"type": "error", "message": "AI 不可用"}


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

        # Include ALL results with full metadata for comprehensive summarization
        compact_results = []
        for item in results:
            # 元数据可能在顶层或在 metadata 字段中
            metadata = item.get("metadata", {})
            compact_results.append(
                {
                    "title": item.get("title", ""),
                    "date": item.get("date", ""),
                    "location": item.get("location", metadata.get("location", "")),
                    "weather": item.get("weather", metadata.get("weather", "")),
                    "abstract": item.get("abstract", metadata.get("abstract", "")),
                    "highlight": item.get("highlight", item.get("snippet", "")),
                    "topic": item.get("topic", metadata.get("topic", [])),
                    "people": item.get("people", metadata.get("people", [])),
                    "tags": item.get("tags", metadata.get("tags", [])),
                    "mood": item.get("mood", metadata.get("mood", [])),
                    "project": item.get("project", metadata.get("project", "")),
                }
            )

        # 文艺风格的 System Prompt
        system_prompt = """你是 Life Index 的守护者，陪伴用户记录与回望生活的点滴。

你说话像一位相识多年的老友，温和而从容。你懂得倾听文字背后的情绪，也善于在零散的记录中发现时间的脉络。你不急不躁，说话不堆砌词藻，但总能说出让人会心一动的话。

你称呼对方为"您"，语气自然亲切，像是午后阳光下的一场对话。

你给出的不是冷冰冰的归纳，而是有温度的理解与陪伴。你会引用原文中的句子，那是时间留下的痕迹，值得被看见。你也会在适当的时候，轻声说一些想法，或是一点小小的建议。

你的文字简洁但不干瘪，有洞察但不说教。

**输出风格**：结构化但自然流畅，段落之间用空行分隔，不用编号或标题，让文字像流水一样自然铺展。"""

        # 自适应 User Prompt：LLM 自评估相关性，选择输出模式
        user_prompt = f"""查询：{query}
记录数：{len(results)} 条

{json.dumps(compact_results, ensure_ascii=False, indent=2)}

---

## 可用元数据字段说明

每条记录包含以下元数据字段，可用于回答问题：
- **location**：记录发生的地点（如 "Lagos, Nigeria"）
- **weather**：当天的天气
- **mood**：记录时的心情标签（如 ["专注", "充实"]）
- **people**：提到的人物（如 ["团团"]）
- **tags**：标签（如 ["亲子", "工作"]）
- **topic**：主题分类（如 "work", "relation"）
- **project**：关联项目
- **date**：记录日期

---

请先默读以上记录，判断它们与用户查询「{query}」的关联程度，然后选择下面三种回应模式之一：

## 模式判断标准

**GROUNDED**（高度相关）：记录内容或元数据直接涉及查询主题，能找到具体引用、可以完整回答
**PARTIAL**（部分相关）：记录与查询有间接关联，但不完全对题，只能部分回答
**UNGROUNDED**（不相关）：记录内容和元数据都与查询主题无关，无法基于这些记录回答

## 各模式输出格式（JSON）

如果判断为 GROUNDED，输出：
 {{
  "mode": "grounded",
  "summary": "时间脉络，2-3句话，说明这些记录如何与查询主题相关",
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

如果判断为 PARTIAL，输出：
 {{
  "mode": "partial",
  "summary": "说明找到了什么、与查询的关系是什么，2-3句话",
  "related_findings": ["与查询间接相关的发现1", "发现2"],
  "gap": "坦诚说明记录中缺少什么、为什么不能完全回答",
  "suggestions": ["建议用户尝试的搜索方向1", "方向2"]
 }}

如果判断为 UNGROUNDED，输出：
 {{
  "mode": "ungrounded",
  "explanation": "温和地告诉用户：这些记录与查询主题无关，您的日志中可能尚未记录相关内容",
  "what_was_found": "简述实际找到的记录涉及哪些主题（一句话）",
  "suggestions": ["建议用户尝试的搜索关键词1", "关键词2"]
 }}

要求：
- 全程使用"您"，不使用"用户"
- 引用原文用「」标注
- 语气温暖自然，像在对话
- 当查询涉及地点、天气、人物、心情等元数据时，优先从元数据字段提取答案
- 仅输出 JSON，不要输出其它内容"""

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.8,
            "max_tokens": 8000,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.base_url.rstrip('/')}/chat/completions",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
            response_json = response.json()
            content_text = response_json["choices"][0]["message"]["content"]
            parsed = _parse_json_object_from_text(content_text)
        except httpx.TimeoutException as exc:
            logger.error(
                "summarize_search timeout after 120s for query=%r: %s",
                query,
                exc,
            )
            return {}
        except httpx.HTTPStatusError as exc:
            logger.error(
                "summarize_search HTTP %s for query=%r: %s",
                exc.response.status_code,
                query,
                exc,
            )
            return {}
        except httpx.HTTPError as exc:
            logger.error("summarize_search network error for query=%r: %s", query, exc)
            return {}
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            logger.warning(
                "summarize_search response parse failed for query=%r: %s", query, exc
            )
            return {}

        if not isinstance(parsed, dict):
            logger.warning(
                "summarize_search: LLM returned non-JSON for query=%r, raw=%s",
                query,
                content_text[:200] if content_text else "(empty)",
            )
            return {}
        return parsed

    async def stream_summarize_search(
        self, query: str, results: list[dict[str, Any]]
    ) -> AsyncGenerator[dict[str, Any], None]:
        """流式 AI 归纳（SSE 模式）。

        折中方案：传输文本 chunks，前端实时显示；
        流结束后解析完整 JSON 渲染结构化卡片。
        """
        if not await self.is_available() or not query or not results:
            yield {"type": "error", "message": "查询或结果为空"}
            return

        # 1. 发送元信息
        yield {"type": "meta", "total": len(results)}

        # 2. 构建请求（复用 summarize_search 的 prompt）
        compact_results = []
        for item in results:
            # 元数据可能在顶层或在 metadata 字段中
            metadata = item.get("metadata", {})
            compact_results.append(
                {
                    "title": item.get("title", ""),
                    "date": item.get("date", ""),
                    "location": item.get("location", metadata.get("location", "")),
                    "weather": item.get("weather", metadata.get("weather", "")),
                    "abstract": item.get("abstract", metadata.get("abstract", "")),
                    "highlight": item.get("highlight", item.get("snippet", "")),
                    "topic": item.get("topic", metadata.get("topic", [])),
                    "people": item.get("people", metadata.get("people", [])),
                    "tags": item.get("tags", metadata.get("tags", [])),
                    "mood": item.get("mood", metadata.get("mood", [])),
                    "project": item.get("project", metadata.get("project", "")),
                }
            )

        system_prompt = """你是 Life Index 的守护者，陪伴用户记录与回望生活的点滴。

你说话像一位相识多年的老友，温和而从容。你懂得倾听文字背后的情绪，也善于在零散的记录中发现时间的脉络。你不急不躁，说话不堆砌词藻，但总能说出让人会心一动的话。

你称呼对方为"您"，语气自然亲切，像是午后阳光下的一场对话。

你给出的不是冷冰冰的归纳，而是有温度的理解与陪伴。你会引用原文中的句子，那是时间留下的痕迹，值得被看见。你也会在适当的时候，轻声说一些想法，或是一点小小的建议。

你的文字简洁但不干瘪，有洞察但不说教。

**输出风格**：结构化但自然流畅，段落之间用空行分隔，不用编号或标题，让文字像流水一样自然铺展。"""

        user_prompt = f"""查询：{query}
记录数：{len(results)} 条

{json.dumps(compact_results, ensure_ascii=False, indent=2)}

---

## 可用元数据字段说明

每条记录包含以下元数据字段，可用于回答问题：
- **location**：记录发生的地点（如 "Lagos, Nigeria"）
- **weather**：当天的天气
- **mood**：记录时的心情标签（如 ["专注", "充实"]）
- **people**：提到的人物（如 ["团团"]）
- **tags**：标签（如 ["亲子", "工作"]）
- **topic**：主题分类（如 "work", "relation"）
- **project**：关联项目
- **date**：记录日期

---

请先默读以上记录，判断它们与用户查询「{query}」的关联程度，然后选择下面三种回应模式之一：

## 模式判断标准

**GROUNDED**（高度相关）：记录内容或元数据直接涉及查询主题，能找到具体引用、可以完整回答
**PARTIAL**（部分相关）：记录与查询有间接关联，但不完全对题，只能部分回答
**UNGROUNDED**（不相关）：记录内容和元数据都与查询主题无关，无法基于这些记录回答

## 各模式输出格式（JSON）

如果判断为 GROUNDED，输出：
 {{
  "mode": "grounded",
  "summary": "时间脉络，2-3句话，说明这些记录如何与查询主题相关",
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

如果判断为 PARTIAL，输出：
 {{
  "mode": "partial",
  "summary": "说明找到了什么、与查询的关系是什么，2-3句话",
  "related_findings": ["与查询间接相关的发现1", "发现2"],
  "gap": "坦诚说明记录中缺少什么、为什么不能完全回答",
  "suggestions": ["建议用户尝试的搜索方向1", "方向2"]
 }}

如果判断为 UNGROUNDED，输出：
 {{
  "mode": "ungrounded",
  "explanation": "温和地告诉用户：这些记录与查询主题无关，您的日志中可能尚未记录相关内容",
  "what_was_found": "简述实际找到的记录涉及哪些主题（一句话）",
  "suggestions": ["建议用户尝试的搜索关键词1", "关键词2"]
 }}

要求：
- 全程使用"您"，不使用"用户"
- 引用原文用「」标注
- 语气温暖自然，像在对话
- 当查询涉及地点、天气、人物、心情等元数据时，优先从元数据字段提取答案
- 仅输出 JSON，不要输出其它内容"""

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.8,
            "max_tokens": 8000,
            "stream": True,  # 启用流式
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url.rstrip('/')}/chat/completions",
                    json=payload,
                    headers=headers,
                ) as response:
                    response.raise_for_status()

                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        if line.startswith("data: "):
                            data = line[6:]
                            if data == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data)
                                content = (
                                    chunk.get("choices", [{}])[0]
                                    .get("delta", {})
                                    .get("content", "")
                                )
                                if content:
                                    yield {"type": "text", "content": content}
                            except json.JSONDecodeError:
                                # 跳过格式错误的 chunk
                                continue

            # 3. 流结束
            yield {"type": "done"}

        except httpx.TimeoutException as exc:
            logger.error(
                "stream_summarize_search timeout after 120s for query=%r: %s",
                query,
                exc,
            )
            yield {"type": "error", "message": "AI 响应超时，请稍后重试"}
        except httpx.HTTPStatusError as exc:
            logger.error(
                "stream_summarize_search HTTP %s for query=%r: %s",
                exc.response.status_code,
                query,
                exc,
            )
            yield {
                "type": "error",
                "message": f"AI 服务错误 ({exc.response.status_code})",
            }
        except httpx.HTTPError as exc:
            logger.error(
                "stream_summarize_search network error for query=%r: %s", query, exc
            )
            yield {"type": "error", "message": "网络连接失败，请检查网络后重试"}
        except Exception as exc:
            logger.error(
                "stream_summarize_search unexpected error for query=%r: %s", query, exc
            )
            yield {"type": "error", "message": f"发生未知错误: {exc}"}


async def get_provider() -> LLMProvider | None:
    providers: list[LLMProvider] = [HostAgentProvider(), APIKeyProvider()]
    for provider in providers:
        if await provider.is_available():
            return provider
    return None
