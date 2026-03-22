# Phase 4a: LLM Provider + Write Service — TDD Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** LLM Provider abstraction enables automatic metadata extraction from journal content. Write Service orchestrates LLM fill + fallback logic + weather query into a complete data dict, then delegates to `write_journal` core. Writing templates JSON provides 7 presets for quick-start journal entry.

**Architecture:** `web/services/llm_provider.py` defines `LLMProvider` ABC with two concrete providers: `HostAgentProvider` (MVP stub, returns unavailable) and `APIKeyProvider` (httpx async, OpenAI-compatible chat completions). `web/services/write.py` exposes `prepare_journal_data()` which fills empty metadata fields via LLM or fallback, and `write_journal_web()` which wraps the synchronous `tools.write_journal.core.write_journal()`. `web/templates/writing_templates.json` stores 7 preset templates as a JSON array.

**Tech Stack:** Python 3.11+ (abc, asyncio, pathlib, json), httpx (async HTTP), FastAPI (dependency context), pytest + pytest-asyncio (testing)

**Spec Reference:** `docs/web-gui/design-spec.md` v1.4 — §3.3, §3.3.1–§3.3.4, §5.4, §5.4.1–§5.4.2, §5.4.5, §5.6

---

## Phase Scope

| Task | Component | Difficulty | Time Est. |
|:--|:--|:--|:--|
| Task 11a | LLM Provider — `web/services/llm_provider.py` + Write Service — `web/services/write.py` + Templates — `web/templates/writing_templates.json` | Hard | 60 min |

**Dependencies:** Task 11a depends on Phase 1 Task 2 (E07xx error codes in `tools/lib/errors.py`), Phase 1 Task 3 (`web/` directory exists), and Phase 1 Task 4 (`web/app.py` factory). No dependency on Phase 2 or Phase 3. Phase 4b depends on Phase 4a.

## Split Navigation

- Provider: [plan-phase4a1-llm-provider.md](plan-phase4a1-llm-provider.md)
- Write service: [plan-phase4a2-write-service.md](plan-phase4a2-write-service.md)
- Writing templates: [plan-phase4a3-writing-templates.md](plan-phase4a3-writing-templates.md)

> 本文件暂时保留完整 legacy TDD 细节；新的执行入口应优先查看上述 split subplans。

---

## Prerequisites

Before starting, verify Phase 1 is complete:

```bash
python -m pytest tests/unit/test_web_scaffold.py -v   # All Phase 1 tests pass
python -m pytest tests/unit/ -q                        # All tests pass, 0 failures
life-index serve &                                     # Server starts
curl -s http://127.0.0.1:8765/api/health               # {"status":"ok",...}
kill %1
```

Verify E07xx error codes exist:

```bash
python -c "from tools.lib.errors import ErrorCode; print(ErrorCode.LLM_PROVIDER_UNAVAILABLE, ErrorCode.LLM_EXTRACTION_FAILED)"
# Expected: E0703 E0704
```

Read these files (required context):
- `docs/web-gui/design-spec.md` §3.3 — LLM integration strategy, dual provider architecture, interface design
- `docs/web-gui/design-spec.md` §3.3.4 — LLM unavailable fallback strategy (title=content[:20], abstract=content[:100], topic=required)
- `docs/web-gui/design-spec.md` §5.4.1 — Form field smart-fill logic (user input > LLM > fallback)
- `docs/web-gui/design-spec.md` §5.4.2 — Submission flow (collect → LLM fill → attachments → weather → assemble → write)
- `docs/web-gui/design-spec.md` §5.4.5 — Writing templates (7 presets with topic/content/tags)
- `tools/write_journal/core.py` — `write_journal(data, dry_run)` full signature and return structure
- `tools/query_weather/__init__.py` — `geocode_location()` and `query_weather()` signatures
- `tools/lib/errors.py` — `ErrorCode.LLM_PROVIDER_UNAVAILABLE` (E0703), `ErrorCode.LLM_EXTRACTION_FAILED` (E0704)
- `tools/lib/config.py` — `get_default_location()`, `USER_DATA_DIR`, `JOURNALS_DIR`
- `web/app.py` — `create_app()` factory pattern, lazy imports

### Key Data Contracts

**`write_journal(data, dry_run)` — `tools.write_journal.core`:**

```python
# data dict keys:
#   REQUIRED: date (str "YYYY-MM-DD")
#   WORKFLOW-REQUIRED: content (str)
#   OPTIONAL / workflow-filled: title (str), topic (str|list), mood (list), tags (list),
#             people (list), location (str), weather (str), project (str),
#             abstract (str), attachments (list)
#
# Returns:
{
    "success": True,
    "journal_path": "C:/Users/.../Documents/Life-Index/Journals/2026/03/life-index_2026-03-07_001.md",
    "updated_indices": ["by-topic/主题_work.md"],
    "index_status": "complete",           # "complete" | "degraded"
    "side_effects_status": "complete",
    "attachments_processed": [],
    "location_used": "Lagos, Nigeria",
    "weather_used": "晴天 28°C",
    "weather_auto_filled": True,
    "needs_confirmation": False,
    "confirmation_message": "",
    "metrics": {"total_ms": 142.5},
    "error": None,
}

# On failure:
{
    "success": False,
    "error": "缺少必需字段：date",
    # ... other fields with default values
}
```

**`geocode_location(location)` — `tools.query_weather`:**

```python
# Success:
{
    "name": "Lagos",
    "latitude": 6.5244,
    "longitude": 3.3792,
    "country": "Nigeria",
    "admin1": "Lagos",
}

# Failure: None or error response dict with "success": False
```

**`query_weather(latitude, longitude, date, timezone)` — `tools.query_weather`:**

```python
# Success:
{
    "success": True,
    "date": "2026-03-07",
    "location": {"lat": 6.5244, "lon": 3.3792},
    "weather": {
        "code": 0,
        "description": "Clear sky (晴朗)",
        "simple": "晴天",
        "temperature_max": 32.5,
        "temperature_min": 24.1,
        "precipitation": 0.0,
    },
}

# Failure:
{
    "success": False,
    "error": "Weather API request failed",
    # ...
}
```

**LLM `extract_metadata()` return contract:**

```python
# LLM returns a dict with these keys (missing fields = None):
{
    "title": "想念小英雄",          # str | None
    "mood": ["思念", "温暖"],       # list[str] | None
    "tags": ["亲子", "回忆"],       # list[str] | None
    "topic": ["think", "relation"], # list[str] | None — must be from valid set
    "abstract": "100字内摘要...",    # str | None
    "people": ["乐乐"],             # list[str] | None
}
```

**Valid topic values:** `work`, `learn`, `health`, `relation`, `think`, `create`, `life`

---

## Task 11a: LLM Provider + Write Service + Writing Templates

**Files:**
- Create: `web/services/llm_provider.py`
- Create: `web/services/write.py`
- Create: `web/templates/writing_templates.json`
- Test: `tests/unit/test_web_write.py` (create)

**Difficulty:** Hard (~60 min)

**Acceptance Criteria:**
1. `LLMProvider` ABC defines `extract_metadata(content) -> dict` and `is_available() -> bool` as abstract async methods
2. `HostAgentProvider.is_available()` returns `False` (MVP stub — MCP Server not yet implemented)
3. `APIKeyProvider` reads config from env vars `LIFE_INDEX_LLM_API_KEY`, `LIFE_INDEX_LLM_BASE_URL` (default `https://api.openai.com/v1`), `LIFE_INDEX_LLM_MODEL` (default `gpt-4o-mini`)
4. `APIKeyProvider.is_available()` returns `True` only when `LIFE_INDEX_LLM_API_KEY` env var is set and non-empty
5. `APIKeyProvider.extract_metadata()` sends an OpenAI-compatible chat completion request via `httpx.AsyncClient` and parses JSON response
6. `get_provider()` returns the first available provider (HostAgent > APIKey), or `None` if all unavailable
7. `prepare_journal_data(form_data, provider)` fills empty metadata fields via LLM (if provider is not None) or fallback strategy (§3.3.4)
8. `prepare_journal_data()` handles location → weather query flow: if location is provided without weather, geocode + query_weather
9. Fallback when LLM unavailable: `title = content[:20]`, `abstract = content[:100]`, `topic` must already be present (raise error if missing)
10. `write_journal_web(data)` wraps synchronous `write_journal(data)` from `tools.write_journal.core`
11. `writing_templates.json` contains exactly 7 presets: 空白日志, 给乐乐的信, 今日感恩, 工作日志, 学习笔记, 读后感, 健康打卡
12. Each template has keys: `id`, `name`, `topic` (list), `content` (string), `tags` (list)
13. User-provided fields are NEVER overwritten by LLM extraction — user input takes priority
14. LLM extraction failure (network error, invalid JSON) logs warning and falls through to fallback — does not block write

**Subagent Governance:**

- MUST DO: Use `from __future__ import annotations` in all Python files
- MUST DO: Use `pathlib.Path` for all path operations
- MUST DO: Import `write_journal` from `tools.write_journal.core` in `web/services/write.py`
- MUST DO: Import `geocode_location` and `query_weather` from `tools.query_weather` for weather auto-fill
- MUST DO: Import `get_default_location` from `tools.lib.config` for location fallback
- MUST DO: Use `httpx.AsyncClient` for LLM API calls in `APIKeyProvider`
- MUST DO: Parse LLM response as JSON — handle `json.JSONDecodeError` gracefully
- MUST DO: Use error codes `E0703` and `E0704` from `tools.lib.errors.ErrorCode`
- MUST DO: Log all LLM calls and failures via `logging.getLogger(__name__)`
- MUST DO: Validate that LLM-extracted `topic` values are from the valid set (`work`, `learn`, `health`, `relation`, `think`, `create`, `life`)
- MUST DO: Use `class TestXxx:` pattern for all test classes
- MUST DO: Use `@pytest.mark.asyncio` for all async test methods
- MUST DO: Use Chinese text for user-facing error messages and comments
- MUST DO: Keep `prepare_journal_data()` and `write_journal_web()` as async functions
- MUST DO: Run `write_journal()` (synchronous) via `asyncio.to_thread()` or `loop.run_in_executor()` to avoid blocking the event loop
- MUST NOT DO: Access filesystem directly in service code — delegate to `tools/` modules
- MUST NOT DO: Import or create any route/template HTML — that is Phase 4b
- MUST NOT DO: Modify any `tools/` module code
- MUST NOT DO: Hardcode API keys or credentials in source code
- MUST NOT DO: Suppress type errors with `as any`, `@ts-ignore`, or `# type: ignore`
- MUST NOT DO: Use bare `except:` clauses — always catch specific exceptions
- MUST NOT DO: Block the async event loop with synchronous I/O (use `asyncio.to_thread` for `write_journal`)
- MUST NOT DO: Override user-provided fields with LLM-extracted values

**Error Handling:**
- `APIKeyProvider.extract_metadata()` network error (httpx timeout, connection error) → log warning with E0704, return empty dict (fallback to manual)
- `APIKeyProvider.extract_metadata()` invalid JSON response → log warning with E0704, return empty dict
- `APIKeyProvider.is_available()` with no API key → return `False` (not an error)
- `get_provider()` with all providers unavailable → return `None` (not an error — caller uses fallback)
- `prepare_journal_data()` with no LLM and no user-provided topic → raise `ValueError("LLM 不可用时，topic 为必填字段")`
- `prepare_journal_data()` with no content → raise `ValueError("content 为必填字段")`
- `write_journal_web()` delegation failure → propagate error from `write_journal()` return dict
- Weather query failure → log warning, proceed without weather (non-blocking)
- Geocoding failure → log warning, use raw location string, skip weather query

**TDD Steps:**

- [ ] **Step 1: Write the failing tests — LLM Provider**

Create `tests/unit/test_web_write.py`:

```python
"""Tests for Web GUI Write Service — Phase 4a (Task 11a).

Covers LLM Provider abstraction, Write Service, and writing templates.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── LLM Provider Tests ──────────────────────────────────────


class TestLLMProviderABC:
    """LLMProvider ABC defines the expected interface."""

    def test_cannot_instantiate_abc(self) -> None:
        """LLMProvider cannot be instantiated directly."""
        from web.services.llm_provider import LLMProvider

        with pytest.raises(TypeError):
            LLMProvider()  # type: ignore[abstract]

    def test_has_extract_metadata_method(self) -> None:
        """LLMProvider defines extract_metadata as abstract."""
        from web.services.llm_provider import LLMProvider

        assert hasattr(LLMProvider, "extract_metadata")

    def test_has_is_available_method(self) -> None:
        """LLMProvider defines is_available as abstract."""
        from web.services.llm_provider import LLMProvider

        assert hasattr(LLMProvider, "is_available")


class TestHostAgentProvider:
    """HostAgentProvider is an MVP stub that always returns unavailable."""

    @pytest.mark.asyncio
    async def test_is_available_returns_false(self) -> None:
        """HostAgentProvider.is_available() returns False in MVP."""
        from web.services.llm_provider import HostAgentProvider

        provider = HostAgentProvider()
        assert await provider.is_available() is False

    @pytest.mark.asyncio
    async def test_extract_metadata_returns_empty(self) -> None:
        """HostAgentProvider.extract_metadata() returns empty dict."""
        from web.services.llm_provider import HostAgentProvider

        provider = HostAgentProvider()
        result = await provider.extract_metadata("任意内容")
        assert result == {}


class TestAPIKeyProvider:
    """APIKeyProvider reads config from environment variables."""

    @pytest.mark.asyncio
    async def test_is_available_without_key(self) -> None:
        """APIKeyProvider.is_available() returns False when no API key set."""
        from web.services.llm_provider import APIKeyProvider

        with patch.dict(os.environ, {}, clear=True):
            provider = APIKeyProvider()
            assert await provider.is_available() is False

    @pytest.mark.asyncio
    async def test_is_available_with_key(self) -> None:
        """APIKeyProvider.is_available() returns True when API key is set."""
        from web.services.llm_provider import APIKeyProvider

        with patch.dict(os.environ, {"LIFE_INDEX_LLM_API_KEY": "sk-test-key"}):
            provider = APIKeyProvider()
            assert await provider.is_available() is True

    @pytest.mark.asyncio
    async def test_is_available_with_empty_key(self) -> None:
        """APIKeyProvider.is_available() returns False when API key is empty string."""
        from web.services.llm_provider import APIKeyProvider

        with patch.dict(os.environ, {"LIFE_INDEX_LLM_API_KEY": ""}):
            provider = APIKeyProvider()
            assert await provider.is_available() is False

    @pytest.mark.asyncio
    async def test_default_base_url(self) -> None:
        """APIKeyProvider defaults to OpenAI base URL."""
        from web.services.llm_provider import APIKeyProvider

        with patch.dict(os.environ, {"LIFE_INDEX_LLM_API_KEY": "sk-test"}, clear=True):
            provider = APIKeyProvider()
            assert provider.base_url == "https://api.openai.com/v1"

    @pytest.mark.asyncio
    async def test_custom_base_url(self) -> None:
        """APIKeyProvider reads custom base URL from env var."""
        from web.services.llm_provider import APIKeyProvider

        with patch.dict(os.environ, {
            "LIFE_INDEX_LLM_API_KEY": "sk-test",
            "LIFE_INDEX_LLM_BASE_URL": "http://localhost:11434/v1",
        }):
            provider = APIKeyProvider()
            assert provider.base_url == "http://localhost:11434/v1"

    @pytest.mark.asyncio
    async def test_default_model(self) -> None:
        """APIKeyProvider defaults to gpt-4o-mini model."""
        from web.services.llm_provider import APIKeyProvider

        with patch.dict(os.environ, {"LIFE_INDEX_LLM_API_KEY": "sk-test"}, clear=True):
            provider = APIKeyProvider()
            assert provider.model == "gpt-4o-mini"

    @pytest.mark.asyncio
    async def test_custom_model(self) -> None:
        """APIKeyProvider reads custom model from env var."""
        from web.services.llm_provider import APIKeyProvider

        with patch.dict(os.environ, {
            "LIFE_INDEX_LLM_API_KEY": "sk-test",
            "LIFE_INDEX_LLM_MODEL": "deepseek-chat",
        }):
            provider = APIKeyProvider()
            assert provider.model == "deepseek-chat"

    @pytest.mark.asyncio
    async def test_extract_metadata_success(self) -> None:
        """APIKeyProvider.extract_metadata() returns parsed LLM response."""
        from web.services.llm_provider import APIKeyProvider

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "title": "测试标题",
                        "mood": ["专注"],
                        "tags": ["测试"],
                        "topic": ["work"],
                        "abstract": "测试摘要",
                        "people": [],
                    })
                }
            }]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.dict(os.environ, {"LIFE_INDEX_LLM_API_KEY": "sk-test"}):
            provider = APIKeyProvider()

        with patch("web.services.llm_provider.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await provider.extract_metadata("测试日志内容")

        assert result["title"] == "测试标题"
        assert result["mood"] == ["专注"]
        assert result["tags"] == ["测试"]
        assert result["topic"] == ["work"]
        assert result["abstract"] == "测试摘要"

    @pytest.mark.asyncio
    async def test_extract_metadata_invalid_json(self) -> None:
        """APIKeyProvider returns empty dict when LLM returns invalid JSON."""
        from web.services.llm_provider import APIKeyProvider

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{
                "message": {"content": "这不是 JSON"}
            }]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.dict(os.environ, {"LIFE_INDEX_LLM_API_KEY": "sk-test"}):
            provider = APIKeyProvider()

        with patch("web.services.llm_provider.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await provider.extract_metadata("测试内容")

        assert result == {}

    @pytest.mark.asyncio
    async def test_extract_metadata_network_error(self) -> None:
        """APIKeyProvider returns empty dict on network error."""
        import httpx
        from web.services.llm_provider import APIKeyProvider

        with patch.dict(os.environ, {"LIFE_INDEX_LLM_API_KEY": "sk-test"}):
            provider = APIKeyProvider()

        with patch("web.services.llm_provider.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(side_effect=httpx.ConnectError("连接失败"))
            mock_client_cls.return_value = mock_client

            result = await provider.extract_metadata("测试内容")

        assert result == {}

    @pytest.mark.asyncio
    async def test_extract_metadata_filters_invalid_topics(self) -> None:
        """APIKeyProvider filters out invalid topic values from LLM response."""
        from web.services.llm_provider import APIKeyProvider

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "title": "测试",
                        "topic": ["work", "invalid_topic", "learn"],
                        "mood": [],
                        "tags": [],
                        "abstract": "摘要",
                        "people": [],
                    })
                }
            }]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.dict(os.environ, {"LIFE_INDEX_LLM_API_KEY": "sk-test"}):
            provider = APIKeyProvider()

        with patch("web.services.llm_provider.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await provider.extract_metadata("测试内容")

        assert result["topic"] == ["work", "learn"]


class TestGetProvider:
    """get_provider() returns the first available provider or None."""

    @pytest.mark.asyncio
    async def test_returns_none_when_all_unavailable(self) -> None:
        """get_provider() returns None when no providers are available."""
        from web.services.llm_provider import get_provider

        with patch.dict(os.environ, {}, clear=True):
            provider = await get_provider()
            assert provider is None

    @pytest.mark.asyncio
    async def test_returns_api_key_provider_when_configured(self) -> None:
        """get_provider() returns APIKeyProvider when API key is set."""
        from web.services.llm_provider import APIKeyProvider, get_provider

        with patch.dict(os.environ, {"LIFE_INDEX_LLM_API_KEY": "sk-test"}):
            provider = await get_provider()
            assert isinstance(provider, APIKeyProvider)

    @pytest.mark.asyncio
    async def test_host_agent_never_available_in_mvp(self) -> None:
        """HostAgentProvider is never selected in MVP (always unavailable)."""
        from web.services.llm_provider import HostAgentProvider, get_provider

        with patch.dict(os.environ, {"LIFE_INDEX_LLM_API_KEY": "sk-test"}):
            provider = await get_provider()
            assert not isinstance(provider, HostAgentProvider)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/unit/test_web_write.py -k "LLMProvider or HostAgent or APIKey or GetProvider" -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'web.services.llm_provider'`.

- [ ] **Step 3: Implement `web/services/llm_provider.py`**

```python
"""LLM Provider abstraction for metadata extraction.

Defines the LLMProvider ABC and concrete implementations:
- HostAgentProvider: MCP Sampling stub (MVP: always unavailable)
- APIKeyProvider: OpenAI-compatible API via httpx (user-configured)

Per design-spec §3.3, providers are tried in priority order:
HostAgentProvider > APIKeyProvider > None (fallback to manual).

Environment variables for APIKeyProvider:
- LIFE_INDEX_LLM_API_KEY: API key (required for availability)
- LIFE_INDEX_LLM_BASE_URL: API base URL (default: https://api.openai.com/v1)
- LIFE_INDEX_LLM_MODEL: Model name (default: gpt-4o-mini)
"""

from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Any

import httpx

from tools.lib.errors import ErrorCode

logger = logging.getLogger(__name__)

# 合法的 topic 值（来自 AGENTS.md 的 Topic 分类表）
VALID_TOPICS: set[str] = {"work", "learn", "health", "relation", "think", "create", "life"}

# LLM 元数据提炼的 system prompt
EXTRACTION_SYSTEM_PROMPT = """你是 Life Index 日志助手。根据用户提供的日志正文，提炼以下元数据字段。
严格返回 JSON 格式，不要包含任何其他文字。

返回格式：
{
    "title": "简洁的日志标题（10-20字）",
    "mood": ["情绪1", "情绪2"],
    "tags": ["标签1", "标签2", "标签3"],
    "topic": ["主题1"],
    "abstract": "100字以内的摘要",
    "people": ["提及的人物"]
}

topic 必须从以下选项中选择（可多选）：
work（工作）、learn（学习）、health（健康）、relation（关系）、think（思考）、create（创作）、life（生活）

注意事项：
- mood 使用中文情绪词，如"专注"、"充实"、"思念"、"焦虑"等
- tags 使用中文标签，提取正文中的关键主题词
- people 提取正文中提到的人名
- abstract 用中文概括正文核心内容，不超过100字
- 如果某个字段无法从正文中提取，设为 null
"""


class LLMProvider(ABC):
    """元数据提炼的抽象接口。

    所有 LLM Provider 必须实现 extract_metadata() 和 is_available()。
    Per design-spec §3.3.3。
    """

    @abstractmethod
    async def extract_metadata(self, content: str) -> dict[str, Any]:
        """从日志正文中提炼元数据。

        Args:
            content: 日志正文（Markdown 格式）。

        Returns:
            dict with keys: title, mood, tags, topic, abstract, people。
            缺失字段返回 None，调用方使用 fallback 策略。
            提取失败时返回空 dict {}。
        """
        ...

    @abstractmethod
    async def is_available(self) -> bool:
        """检查此 Provider 是否可用。"""
        ...


class HostAgentProvider(LLMProvider):
    """通过 MCP Sampling 借用宿主 Agent 的 LLM 能力。

    前提：Life Index 以 MCP Server 运行，宿主 Agent 声明了 sampling 能力。
    MVP 阶段：is_available() 始终返回 False（等待 MCP Server 化完成）。
    Per design-spec §3.3.1。
    """

    async def extract_metadata(self, content: str) -> dict[str, Any]:
        """MVP 阶段不可用，返回空 dict。"""
        return {}

    async def is_available(self) -> bool:
        """MVP 阶段始终返回 False。"""
        return False


class APIKeyProvider(LLMProvider):
    """用户自配 API key，直接调用 OpenAI-compatible API。

    配置来源（优先级从高到低）：
    1. 环境变量：LIFE_INDEX_LLM_API_KEY、LIFE_INDEX_LLM_BASE_URL、LIFE_INDEX_LLM_MODEL
    2. 代码默认值

    使用 httpx.AsyncClient 异步调用 LLM API。
    Per design-spec §3.3.2。
    """

    def __init__(self) -> None:
        self.api_key: str = os.environ.get("LIFE_INDEX_LLM_API_KEY", "")
        self.base_url: str = os.environ.get(
            "LIFE_INDEX_LLM_BASE_URL", "https://api.openai.com/v1"
        )
        self.model: str = os.environ.get("LIFE_INDEX_LLM_MODEL", "gpt-4o-mini")

    async def is_available(self) -> bool:
        """API key 已配置且非空时返回 True。"""
        return bool(self.api_key)

    async def extract_metadata(self, content: str) -> dict[str, Any]:
        """调用 OpenAI-compatible chat completions API 提炼元数据。

        Args:
            content: 日志正文。

        Returns:
            提炼结果 dict，失败时返回空 dict {}。
        """
        if not self.api_key:
            logger.warning("[%s] API key 未配置，跳过元数据提炼", ErrorCode.LLM_PROVIDER_UNAVAILABLE)
            return {}

        url = f"{self.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": content},
            ],
            "temperature": 0.3,
            "response_format": {"type": "json_object"},
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()

            data = response.json()
            raw_content = data["choices"][0]["message"]["content"]
            metadata = json.loads(raw_content)

            # 验证并过滤 topic 值
            if "topic" in metadata and isinstance(metadata["topic"], list):
                metadata["topic"] = [
                    t for t in metadata["topic"] if t in VALID_TOPICS
                ]

            logger.info("LLM 元数据提炼成功: model=%s", self.model)
            return metadata

        except json.JSONDecodeError as e:
            logger.warning(
                "[%s] LLM 返回的内容不是有效 JSON: %s",
                ErrorCode.LLM_EXTRACTION_FAILED,
                e,
            )
            return {}
        except httpx.HTTPStatusError as e:
            logger.warning(
                "[%s] LLM API 返回错误状态码: %s",
                ErrorCode.LLM_EXTRACTION_FAILED,
                e,
            )
            return {}
        except (httpx.ConnectError, httpx.TimeoutException, httpx.RequestError) as e:
            logger.warning(
                "[%s] LLM API 网络错误: %s",
                ErrorCode.LLM_EXTRACTION_FAILED,
                e,
            )
            return {}
        except (KeyError, IndexError) as e:
            logger.warning(
                "[%s] LLM API 响应格式异常: %s",
                ErrorCode.LLM_EXTRACTION_FAILED,
                e,
            )
            return {}


async def get_provider() -> LLMProvider | None:
    """按优先级返回第一个可用的 LLM Provider。

    优先级: HostAgentProvider > APIKeyProvider > None。
    Per design-spec §3.3。

    Returns:
        可用的 LLMProvider 实例，或 None（全部不可用时）。
    """
    # 优先尝试 HostAgentProvider（MVP 阶段始终不可用）
    host_provider = HostAgentProvider()
    if await host_provider.is_available():
        logger.info("使用 HostAgentProvider（MCP Sampling）")
        return host_provider

    # 其次尝试 APIKeyProvider
    api_provider = APIKeyProvider()
    if await api_provider.is_available():
        logger.info("使用 APIKeyProvider（用户自配 API key）")
        return api_provider

    # 全部不可用
    logger.info("[%s] 所有 LLM Provider 不可用，将使用降级策略", ErrorCode.LLM_PROVIDER_UNAVAILABLE)
    return None
```

- [ ] **Step 4: Run LLM Provider tests to verify they pass**

```bash
python -m pytest tests/unit/test_web_write.py -k "LLMProvider or HostAgent or APIKey or GetProvider" -v
```

Expected: All `TestLLMProviderABC`, `TestHostAgentProvider`, `TestAPIKeyProvider`, `TestGetProvider` tests pass.

- [ ] **Step 5: Write the failing tests — Write Service**

Append to `tests/unit/test_web_write.py`:

```python
# ── Write Service Tests ──────────────────────────────────────


class TestPrepareJournalData:
    """prepare_journal_data() fills metadata via LLM or fallback."""

    @pytest.mark.asyncio
    async def test_user_fields_not_overwritten(self) -> None:
        """User-provided fields are never overwritten by LLM."""
        from web.services.write import prepare_journal_data

        mock_provider = AsyncMock()
        mock_provider.extract_metadata = AsyncMock(return_value={
            "title": "LLM标题",
            "mood": ["LLM情绪"],
            "tags": ["LLM标签"],
            "topic": ["work"],
            "abstract": "LLM摘要",
            "people": ["LLM人物"],
        })

        form_data = {
            "content": "用户正文内容",
            "date": "2026-03-07",
            "title": "用户标题",
            "mood": ["用户情绪"],
            "tags": ["用户标签"],
            "topic": ["think"],
            "people": ["用户人物"],
        }

        result = await prepare_journal_data(form_data, mock_provider)

        assert result["title"] == "用户标题"
        assert result["mood"] == ["用户情绪"]
        assert result["tags"] == ["用户标签"]
        assert result["topic"] == ["think"]
        assert result["people"] == ["用户人物"]

    @pytest.mark.asyncio
    async def test_llm_fills_empty_fields(self) -> None:
        """LLM fills fields that user left empty."""
        from web.services.write import prepare_journal_data

        mock_provider = AsyncMock()
        mock_provider.extract_metadata = AsyncMock(return_value={
            "title": "LLM标题",
            "mood": ["专注"],
            "tags": ["编程"],
            "topic": ["work"],
            "abstract": "LLM生成的摘要",
            "people": ["乐乐"],
        })

        form_data = {
            "content": "今天写了很多代码",
            "date": "2026-03-07",
        }

        result = await prepare_journal_data(form_data, mock_provider)

        assert result["title"] == "LLM标题"
        assert result["mood"] == ["专注"]
        assert result["tags"] == ["编程"]
        assert result["topic"] == ["work"]
        assert result["abstract"] == "LLM生成的摘要"
        assert result["people"] == ["乐乐"]
        assert result["content"] == "今天写了很多代码"
        assert result["date"] == "2026-03-07"

    @pytest.mark.asyncio
    async def test_fallback_without_llm(self) -> None:
        """Without LLM, title and abstract use content truncation."""
        from web.services.write import prepare_journal_data

        content = "这是一段比较长的日志正文内容，用来测试自动截取标题和摘要的功能是否正常工作。" * 5

        form_data = {
            "content": content,
            "date": "2026-03-07",
            "topic": ["work"],  # 必须由用户提供
        }

        result = await prepare_journal_data(form_data, None)

        # title = content[:20]
        assert result["title"] == content[:20]
        # abstract = content[:100]
        assert result["abstract"] == content[:100]
        # 可选字段留空
        assert result["mood"] == []
        assert result["tags"] == []
        assert result["people"] == []

    @pytest.mark.asyncio
    async def test_fallback_without_llm_requires_topic(self) -> None:
        """Without LLM, topic is required — raises ValueError if missing."""
        from web.services.write import prepare_journal_data

        form_data = {
            "content": "日志正文",
            "date": "2026-03-07",
            # topic 未提供
        }

        with pytest.raises(ValueError, match="topic"):
            await prepare_journal_data(form_data, None)

    @pytest.mark.asyncio
    async def test_content_required(self) -> None:
        """content is required — raises ValueError if missing."""
        from web.services.write import prepare_journal_data

        form_data = {
            "date": "2026-03-07",
        }

        with pytest.raises(ValueError, match="content"):
            await prepare_journal_data(form_data, None)

    @pytest.mark.asyncio
    async def test_date_defaults_to_today(self) -> None:
        """date defaults to today if not provided."""
        from datetime import date

        from web.services.write import prepare_journal_data

        form_data = {
            "content": "日志正文",
            "topic": ["work"],
        }

        result = await prepare_journal_data(form_data, None)

        assert result["date"] == date.today().isoformat()

    @pytest.mark.asyncio
    async def test_location_uses_default_when_empty(self) -> None:
        """location falls back to get_default_location() when not provided."""
        from web.services.write import prepare_journal_data

        form_data = {
            "content": "日志正文",
            "date": "2026-03-07",
            "topic": ["work"],
        }

        with patch("web.services.write.get_default_location", return_value="Chongqing, China"):
            result = await prepare_journal_data(form_data, None)

        assert result["location"] == "Chongqing, China"

    @pytest.mark.asyncio
    async def test_llm_extraction_failure_falls_through(self) -> None:
        """LLM extraction failure falls through to fallback gracefully."""
        from web.services.write import prepare_journal_data

        mock_provider = AsyncMock()
        mock_provider.extract_metadata = AsyncMock(return_value={})  # 提取失败返回空

        form_data = {
            "content": "日志正文内容测试",
            "date": "2026-03-07",
            "topic": ["life"],  # 必须由用户提供（LLM 失败时）
        }

        result = await prepare_journal_data(form_data, mock_provider)

        # 降级：title = content[:20], abstract = content[:100]
        assert result["title"] == "日志正文内容测试"[:20]
        assert result["abstract"] == "日志正文内容测试"[:100]

    @pytest.mark.asyncio
    async def test_partial_user_fields_with_llm(self) -> None:
        """User fills some fields, LLM fills the rest."""
        from web.services.write import prepare_journal_data

        mock_provider = AsyncMock()
        mock_provider.extract_metadata = AsyncMock(return_value={
            "title": "LLM标题",
            "mood": ["愉悦"],
            "tags": ["代码"],
            "topic": ["work"],
            "abstract": "LLM摘要",
            "people": [],
        })

        form_data = {
            "content": "写了一天的代码",
            "date": "2026-03-07",
            "title": "我的标题",  # 用户已填 → 保留
            # mood, tags, topic, people 未填 → LLM 填充
        }

        result = await prepare_journal_data(form_data, mock_provider)

        assert result["title"] == "我的标题"  # 用户优先
        assert result["mood"] == ["愉悦"]      # LLM 填充
        assert result["topic"] == ["work"]     # LLM 填充


class TestWriteJournalWeb:
    """write_journal_web() wraps tools.write_journal.core.write_journal()."""

    @pytest.mark.asyncio
    @patch("web.services.write.write_journal")
    async def test_delegates_to_core(self, mock_write: MagicMock) -> None:
        """write_journal_web() calls write_journal from tools."""
        from web.services.write import write_journal_web

        mock_write.return_value = {
            "success": True,
            "journal_path": "/path/to/journal.md",
            "error": None,
        }

        data = {"date": "2026-03-07", "content": "测试正文", "title": "测试"}
        result = await write_journal_web(data)

        mock_write.assert_called_once_with(data, False)
        assert result["success"] is True
        assert result["journal_path"] == "/path/to/journal.md"

    @pytest.mark.asyncio
    @patch("web.services.write.write_journal")
    async def test_dry_run_mode(self, mock_write: MagicMock) -> None:
        """write_journal_web() supports dry_run parameter."""
        from web.services.write import write_journal_web

        mock_write.return_value = {
            "success": True,
            "journal_path": "/path/to/journal.md",
            "content_preview": "---\ntitle: ...",
        }

        data = {"date": "2026-03-07", "content": "测试"}
        result = await write_journal_web(data, dry_run=True)

        mock_write.assert_called_once_with(data, True)
        assert result["success"] is True

    @pytest.mark.asyncio
    @patch("web.services.write.write_journal")
    async def test_propagates_error(self, mock_write: MagicMock) -> None:
        """write_journal_web() propagates error from core write_journal."""
        from web.services.write import write_journal_web

        mock_write.return_value = {
            "success": False,
            "error": "缺少必需字段：date",
        }

        data = {"content": "无日期"}
        result = await write_journal_web(data)

        assert result["success"] is False
        assert "date" in result["error"]
```

- [ ] **Step 6: Run Write Service tests to verify they fail**

```bash
python -m pytest tests/unit/test_web_write.py -k "PrepareJournalData or WriteJournalWeb" -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'web.services.write'`.

- [ ] **Step 7: Implement `web/services/write.py`**

```python
"""Write Service — orchestrates LLM metadata extraction and journal writing.

Handles the submission flow per design-spec §5.4.2:
1. Collect user-filled fields
2. For unfilled fields, call LLM extraction (if provider available)
3. Apply fallback strategy for remaining empty fields (§3.3.4)
4. Handle location → weather query
5. Assemble complete data dict
6. Delegate to tools.write_journal.core.write_journal()

This module does NOT handle attachments or route logic — those are Phase 4b.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date
from typing import Any

from tools.lib.config import get_default_location
from tools.lib.errors import ErrorCode
from tools.write_journal.core import write_journal

logger = logging.getLogger(__name__)

# LLM 可填充的元数据字段
LLM_FILLABLE_FIELDS: list[str] = ["title", "mood", "tags", "topic", "abstract", "people"]


async def prepare_journal_data(
    form_data: dict[str, Any],
    provider: Any | None,
) -> dict[str, Any]:
    """准备完整的日志数据 dict，供 write_journal() 使用。

    处理流程：
    1. 验证必填字段（content）
    2. 设置默认值（date、location）
    3. 对用户未填字段调用 LLM 提炼（如 provider 可用）
    4. 对仍然为空的字段应用降级策略（§3.3.4）

    Args:
        form_data: 用户提交的表单数据。至少包含 content。
        provider: LLMProvider 实例，或 None（无 LLM 可用）。

    Returns:
        完整的 data dict，可直接传给 write_journal()。

    Raises:
        ValueError: content 为空，或无 LLM 时 topic 未提供。
    """
    # ── 验证必填字段 ──
    content = form_data.get("content", "").strip()
    if not content:
        raise ValueError("content 为必填字段")

    # ── 初始化结果 dict ──
    data: dict[str, Any] = {
        "content": content,
        "date": form_data.get("date") or date.today().isoformat(),
    }

    # ── 收集用户已填字段 ──
    user_filled: dict[str, Any] = {}
    for field in LLM_FILLABLE_FIELDS:
        value = form_data.get(field)
        if value:  # 非 None、非空字符串、非空列表
            user_filled[field] = value

    # ── LLM 元数据提炼 ──
    llm_metadata: dict[str, Any] = {}
    if provider is not None:
        # 仅当有未填字段时才调用 LLM
        unfilled = [f for f in LLM_FILLABLE_FIELDS if f not in user_filled]
        if unfilled:
            try:
                llm_metadata = await provider.extract_metadata(content)
                logger.info("LLM 元数据提炼完成，填充字段: %s", list(llm_metadata.keys()))
            except Exception as e:
                logger.warning(
                    "[%s] LLM 元数据提炼异常: %s",
                    ErrorCode.LLM_EXTRACTION_FAILED,
                    e,
                )
                llm_metadata = {}

    # ── 合并字段（用户 > LLM > 降级） ──
    # title
    data["title"] = user_filled.get("title") or llm_metadata.get("title") or content[:20]

    # topic
    user_topic = user_filled.get("topic")
    llm_topic = llm_metadata.get("topic")
    if user_topic:
        data["topic"] = user_topic
    elif llm_topic:
        data["topic"] = llm_topic
    else:
        # 无 LLM 且用户未填 topic → 必填校验
        raise ValueError("LLM 不可用时，topic 为必填字段")

    # abstract
    data["abstract"] = user_filled.get("abstract") or llm_metadata.get("abstract") or content[:100]

    # mood（可选，降级为空列表）
    data["mood"] = user_filled.get("mood") or llm_metadata.get("mood") or []

    # tags（可选，降级为空列表）
    data["tags"] = user_filled.get("tags") or llm_metadata.get("tags") or []

    # people（可选，降级为空列表）
    data["people"] = user_filled.get("people") or llm_metadata.get("people") or []

    # ── 非 LLM 字段 ──
    # location（用户提供 > 默认值）
    data["location"] = form_data.get("location", "").strip() or get_default_location()

    # project（可选）
    if form_data.get("project"):
        data["project"] = form_data["project"]

    # attachments（Phase 4b 处理，此处透传）
    if form_data.get("attachments"):
        data["attachments"] = form_data["attachments"]

    return data


async def write_journal_web(
    data: dict[str, Any],
    dry_run: bool = False,
) -> dict[str, Any]:
    """调用 tools.write_journal.core.write_journal() 写入日志。

    使用 asyncio.to_thread() 避免阻塞事件循环（write_journal 是同步函数）。

    Args:
        data: 完整的日志数据 dict（由 prepare_journal_data() 生成）。
        dry_run: 如果为 True，仅预览不实际写入。

    Returns:
        write_journal() 的返回结果 dict。
    """
    result = await asyncio.to_thread(write_journal, data, dry_run)
    if result.get("success"):
        logger.info("日志写入成功: %s", result.get("journal_path"))
    else:
        logger.warning("日志写入失败: %s", result.get("error"))
    return result
```

- [ ] **Step 8: Run Write Service tests to verify they pass**

```bash
python -m pytest tests/unit/test_web_write.py -k "PrepareJournalData or WriteJournalWeb" -v
```

Expected: All `TestPrepareJournalData` and `TestWriteJournalWeb` tests pass.

- [ ] **Step 9: Write the failing tests — Writing Templates**

Append to `tests/unit/test_web_write.py`:

```python
# ── Writing Templates Tests ──────────────────────────────────


class TestWritingTemplates:
    """writing_templates.json contains 7 presets per design-spec §5.4.5."""

    def _load_templates(self) -> list[dict[str, Any]]:
        """Load and parse writing_templates.json."""
        templates_path = Path(__file__).parent.parent.parent / "web" / "templates" / "writing_templates.json"
        assert templates_path.exists(), f"writing_templates.json not found at {templates_path}"
        with open(templates_path, encoding="utf-8") as f:
            return json.load(f)

    def test_has_seven_templates(self) -> None:
        """writing_templates.json contains exactly 7 templates."""
        templates = self._load_templates()
        assert len(templates) == 7

    def test_all_templates_have_required_keys(self) -> None:
        """Each template has id, name, topic, content, tags."""
        templates = self._load_templates()
        required_keys = {"id", "name", "topic", "content", "tags"}
        for tmpl in templates:
            assert required_keys.issubset(tmpl.keys()), (
                f"Template '{tmpl.get('name', '?')}' missing keys: "
                f"{required_keys - tmpl.keys()}"
            )

    def test_blank_template_first(self) -> None:
        """First template is 空白日志 (blank)."""
        templates = self._load_templates()
        assert templates[0]["id"] == "blank"
        assert templates[0]["name"] == "空白日志"
        assert templates[0]["content"] == ""
        assert templates[0]["topic"] == []

    def test_tuantuan_template(self) -> None:
        """给乐乐的信 template has correct topic and content."""
        templates = self._load_templates()
        tuantuan = next(t for t in templates if t["id"] == "letter-to-tuantuan")
        assert tuantuan["name"] == "给乐乐的信"
        assert "think" in tuantuan["topic"]
        assert "relation" in tuantuan["topic"]
        assert "乐乐" in tuantuan["content"]

    def test_all_ids_unique(self) -> None:
        """All template IDs are unique."""
        templates = self._load_templates()
        ids = [t["id"] for t in templates]
        assert len(ids) == len(set(ids)), f"Duplicate IDs found: {ids}"

    def test_all_topics_valid(self) -> None:
        """All topic values in templates are from the valid set."""
        valid_topics = {"work", "learn", "health", "relation", "think", "create", "life"}
        templates = self._load_templates()
        for tmpl in templates:
            for topic in tmpl["topic"]:
                assert topic in valid_topics, (
                    f"Template '{tmpl['name']}' has invalid topic: '{topic}'"
                )

    def test_template_names_match_spec(self) -> None:
        """Template names match design-spec §5.4.5 exactly."""
        expected_names = [
            "空白日志", "给乐乐的信", "今日感恩", "工作日志",
            "学习笔记", "读后感", "健康打卡",
        ]
        templates = self._load_templates()
        actual_names = [t["name"] for t in templates]
        assert actual_names == expected_names
```

- [ ] **Step 10: Run templates tests to verify they fail**

```bash
python -m pytest tests/unit/test_web_write.py -k "WritingTemplates" -v
```

Expected: FAIL — `AssertionError: writing_templates.json not found`.

- [ ] **Step 11: Create `web/templates/writing_templates.json`**

```json
[
    {
        "id": "blank",
        "name": "空白日志",
        "topic": [],
        "content": "",
        "tags": []
    },
    {
        "id": "letter-to-tuantuan",
        "name": "给乐乐的信",
        "topic": ["think", "relation"],
        "content": "# 亲爱的乐乐\n\n爸爸今天想对你说……\n\n",
        "tags": ["亲子"]
    },
    {
        "id": "gratitude",
        "name": "今日感恩",
        "topic": ["think"],
        "content": "# 今日感恩\n\n今天我感恩的三件事：\n\n1. \n2. \n3. \n\n",
        "tags": ["感恩"]
    },
    {
        "id": "work-log",
        "name": "工作日志",
        "topic": ["work"],
        "content": "# 工作日志\n\n## 今日完成\n\n- \n\n## 遇到的问题\n\n- \n\n## 明日计划\n\n- \n",
        "tags": []
    },
    {
        "id": "study-notes",
        "name": "学习笔记",
        "topic": ["learn"],
        "content": "# 学习笔记\n\n## 今天学了什么\n\n\n\n## 关键收获\n\n\n\n## 还不理解的地方\n\n\n",
        "tags": ["学习"]
    },
    {
        "id": "book-review",
        "name": "读后感",
        "topic": ["learn", "think"],
        "content": "# 读后感\n\n**书名**：\n**作者**：\n\n## 核心观点\n\n\n\n## 我的思考\n\n\n",
        "tags": ["阅读"]
    },
    {
        "id": "health-checkin",
        "name": "健康打卡",
        "topic": ["health"],
        "content": "# 健康打卡\n\n- 睡眠：\n- 运动：\n- 饮食：\n- 身体状况：\n\n",
        "tags": ["健康"]
    }
]
```

- [ ] **Step 12: Run templates tests to verify they pass**

```bash
python -m pytest tests/unit/test_web_write.py -k "WritingTemplates" -v
```

Expected: All `TestWritingTemplates` tests pass.

- [ ] **Step 13: Run all Phase 4a tests**

```bash
python -m pytest tests/unit/test_web_write.py -v
```

Expected: All tests in `TestLLMProviderABC`, `TestHostAgentProvider`, `TestAPIKeyProvider`, `TestGetProvider`, `TestPrepareJournalData`, `TestWriteJournalWeb`, `TestWritingTemplates` pass.

- [ ] **Step 14: Verify existing tests still pass**

```bash
python -m pytest tests/unit/ -q
```

Expected: 0 failures (including all Phase 1 + Phase 2 + Phase 3 tests).

- [ ] **Step 15: Commit**

```bash
git add web/services/llm_provider.py web/services/write.py web/templates/writing_templates.json tests/unit/test_web_write.py
git commit -m "feat(web): add LLM provider abstraction, write service, and writing templates (Phase 4a)"
```

---

## Phase 4a Completion Checklist

Run all checks before declaring Phase 4a complete:

- [ ] **All Phase 4a tests pass:**

```bash
python -m pytest tests/unit/test_web_write.py -v
```

Expected: All tests in `TestLLMProviderABC`, `TestHostAgentProvider`, `TestAPIKeyProvider`, `TestGetProvider`, `TestPrepareJournalData`, `TestWriteJournalWeb`, `TestWritingTemplates` pass.

- [ ] **All existing tests still pass:**

```bash
python -m pytest tests/unit/ -q
```

Expected: 0 failures (including all Phase 1 + Phase 2 + Phase 3 tests).

- [ ] **LLM Provider imports cleanly:**

```bash
python -c "from web.services.llm_provider import LLMProvider, HostAgentProvider, APIKeyProvider, get_provider; print('OK')"
```

Expected: `OK` (no import errors).

- [ ] **Write Service imports cleanly:**

```bash
python -c "from web.services.write import prepare_journal_data, write_journal_web; print('OK')"
```

Expected: `OK` (no import errors).

- [ ] **Writing templates are valid JSON:**

```bash
python -c "import json; data = json.load(open('web/templates/writing_templates.json', encoding='utf-8')); print(f'{len(data)} templates loaded')"
```

Expected: `7 templates loaded`.

- [ ] **Health endpoint still works:**

```bash
life-index serve &
sleep 2
curl -s http://127.0.0.1:8765/api/health | python -m json.tool
kill %1
```

Expected: `{"status": "ok", "version": "..."}`.

- [ ] **Files created:**

```
web/
├── services/
│   ├── stats.py             (existing — Phase 2)
│   ├── journal.py           (existing — Phase 3)
│   ├── search.py            (existing — Phase 3)
│   ├── llm_provider.py      ✅ (created)
│   └── write.py             ✅ (created)
└── templates/
    ├── base.html            (existing)
    ├── dashboard.html       (existing — Phase 2)
    ├── journal.html         (existing — Phase 3)
    ├── search.html          (existing — Phase 3)
    └── writing_templates.json  ✅ (created)

tests/unit/
└── test_web_write.py        ✅ (created)
```

---

## Plan Review Note

After reviewing this plan, dispatch `momus` (plan reviewer) with this file path to validate:
- Acceptance criteria completeness
- TDD step coverage vs. acceptance criteria
- Code correctness and consistency
- Error handling coverage
- Missing edge cases

```
task(subagent_type="momus", prompt="D:\\Loster AI\\Projects\\life-index\\docs\\web-gui\\plan-phase4a-llm-write-service.md")
```
