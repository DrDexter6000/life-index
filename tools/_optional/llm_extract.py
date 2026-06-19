"""
Life Index - LLM Metadata Extraction Module (Optional)
=====================================================
Isolated metadata extraction from journal content.

This module provides synchronous LLM extraction for isolated optional use.
It extracts metadata (title, abstract, topic, mood, tags, people, project) from
raw journal content using an OpenAI-compatible API.

This module is in tools/_optional/ because it depends on LLM API configuration.
Per CHARTER APEX, it must NOT be imported by deterministic tools or default
agent paths.

The prompts and validation logic are SSOT here - Web layer should call this
module, not duplicate the logic.

Optional direct usage:
    from tools._optional.llm_extract import extract_metadata_sync
    from tools.lib.topics import VALID_TOPICS

    result = extract_metadata_sync(content="...")
"""

import json
import re
from typing import Any

import httpx

from ..lib.config import get_llm_config
from ..lib.errors import ErrorCode, LifeIndexError  # noqa: F401
from ..lib.logger import get_logger
from ..lib.topics import VALID_TOPICS

logger = get_logger(__name__)

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


def _parse_json_object_from_text(content_text: str) -> dict[str, Any] | None:
    """Parse JSON object from LLM text output with 3-attempt fallback."""
    if not content_text:
        return None

    content_text = content_text.strip()

    content_text = re.sub(
        r"<thinking>.*?</thinking>", "", content_text, flags=re.DOTALL | re.IGNORECASE
    ).strip()

    content_text = re.sub(
        r"<thinking>.*", "", content_text, flags=re.DOTALL | re.IGNORECASE
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
        pass

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


def _normalize_extracted_fields(parsed: dict[str, Any]) -> dict[str, Any]:
    """Normalize and harden extracted fields from LLM response."""
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
        parsed["topic"] = [str(topic) for topic in topics if str(topic) in VALID_TOPICS]
    elif isinstance(topics, str) and topics in VALID_TOPICS:
        parsed["topic"] = [topics]
    else:
        parsed["topic"] = []

    return parsed


def extract_metadata_sync(content: str, timeout: float = 30.0) -> dict[str, Any]:
    """Extract metadata from journal content using LLM (sync version for CLI).

    Returns empty dict {} if:
    - LLM API not configured (no API key)
    - API call fails
    - Response parsing fails
    """
    config = get_llm_config()
    api_key = config["api_key"]
    base_url = config["base_url"]
    model = config["model"]

    if not api_key:
        logger.debug("LLM API key not configured, returning empty metadata")
        return {}

    if not content or not content.strip():
        logger.warning("Empty content provided for metadata extraction")
        return {}

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": content.strip()},
        ],
        "temperature": 0.5,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                f"{base_url.rstrip('/')}/chat/completions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("%s: LLM request failed: %s", ErrorCode.LLM_EXTRACTION_FAILED, exc)
        return {}

    try:
        response_json = response.json()
        content_text = response_json["choices"][0]["message"]["content"]
        parsed = _parse_json_object_from_text(content_text)
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        logger.warning("%s: LLM response parse failed: %s", ErrorCode.LLM_EXTRACTION_FAILED, exc)
        return {}

    if not isinstance(parsed, dict):
        logger.warning(
            "%s: LLM did not return parseable JSON object",
            ErrorCode.LLM_EXTRACTION_FAILED,
        )
        return {}

    return _normalize_extracted_fields(parsed)


def is_llm_available() -> bool:
    """Check if LLM extraction is available (API key configured)."""
    config = get_llm_config()
    return bool(config["api_key"])


__all__ = [
    "extract_metadata_sync",
    "is_llm_available",
    "VALID_TOPICS",
    "EXTRACTION_SYSTEM_PROMPT",
]
