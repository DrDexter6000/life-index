"""
Contract tests: Agent-Native write_journal default-no-LLM behavior.

Verifies that:
1. prepare_journal_metadata with default use_llm (omitted) does not call LLM
2. prepare_journal_metadata with legacy use_llm=True still stays deterministic
3. Importing tools.lib does not trigger llm_extract import
4. VALID_TOPICS is importable from a deterministic module (not llm_extract)
"""

import importlib
import sys
from unittest.mock import patch

import pytest

from tools.write_journal.prepare import prepare_journal_metadata


class TestDefaultNoLLM:
    """prepare_journal_metadata default (use_llm omitted) must not call LLM."""

    def test_default_omitted_does_not_import_optional_llm(self):
        """When use_llm is not passed, tools._optional.llm_extract must not be imported."""
        _before = {k for k in sys.modules if "tools._optional.llm_extract" in k}
        raw = {
            "content": "测试正文",
            "title": "测试标题",
            "topic": "work",
        }
        result = prepare_journal_metadata(raw)
        _after = {k for k in sys.modules if "tools._optional.llm_extract" in k}
        new_modules = _after - _before
        assert len(new_modules) == 0, f"Default path imported optional llm_extract: {new_modules}"
        assert result["field_sources"]["title"] == "user"
        assert result["topic"] == ["work"]

    def test_default_omitted_does_not_call_extract_metadata_sync(self):
        """When use_llm is not passed, extract_metadata_sync must not be called."""
        with patch("tools._optional.llm_extract.extract_metadata_sync") as mock_extract:
            raw = {
                "content": "测试正文",
                "title": "测试标题",
                "topic": "work",
            }
            result = prepare_journal_metadata(raw)
            mock_extract.assert_not_called()
            assert "field_sources" in result

    def test_default_produces_deterministic_output(self):
        """Default path produces deterministic results without any LLM."""
        with patch("tools._optional.llm_extract.extract_metadata_sync") as mock_ext:
            mock_ext.return_value = {
                "title": "AI Title",
                "tags": ["ai-tag"],
            }
            raw = {
                "content": "这是测试内容",
                "title": "User Title",
                "topic": "life",
            }
            result = prepare_journal_metadata(raw)

            assert result["field_sources"]["title"] == "user"
            assert result["field_sources"]["topic"] == "user"
            assert result["llm_status"]["state"] == "disabled"
            mock_ext.assert_not_called()

    def test_legacy_use_llm_true_does_not_import_optional_llm(self):
        """Legacy use_llm=True must not trigger retired tool LLM extraction."""
        _before = {k for k in sys.modules if "tools._optional.llm_extract" in k}
        raw = {
            "content": "测试内容",
            "title": "Manual Title",
            "topic": "life",
        }
        result = prepare_journal_metadata(raw, use_llm=True)
        _after = {k for k in sys.modules if "tools._optional.llm_extract" in k}

        assert _after - _before == set()
        assert result["llm_status"]["state"] == "disabled"
        assert result["field_sources"]["title"] == "user"

    def test_default_no_llm_topic_required(self):
        """When no LLM (default), topic must be provided by user."""
        raw = {"content": "测试内容", "title": "标题"}
        with pytest.raises(ValueError, match="topic"):
            prepare_journal_metadata(raw)


class TestImportIsolation:
    """tools.lib must not import llm_extract by default."""

    def test_lib_init_no_llm_extract_import(self):
        """Importing tools.lib should not bring in llm_extract module."""
        llm_modules_before = {k for k in sys.modules if "llm_extract" in k}
        import tools.lib

        importlib.reload(tools.lib)
        llm_modules_after = {k for k in sys.modules if "llm_extract" in k}
        new_llm_modules = llm_modules_after - llm_modules_before
        assert (
            len(new_llm_modules) == 0
        ), f"tools.lib import triggered llm_extract modules: {new_llm_modules}"


class TestTopicsDeterministic:
    """VALID_TOPICS must be importable from a deterministic module."""

    def test_topics_module_importable(self):
        """tools.lib.topics must exist and export VALID_TOPICS."""
        from tools.lib.topics import VALID_TOPICS

        assert isinstance(VALID_TOPICS, set)
        assert len(VALID_TOPICS) >= 7
        expected = {"work", "learn", "health", "relation", "think", "create", "life"}
        assert expected <= VALID_TOPICS

    def test_prepare_imports_topics_from_deterministic_module(self):
        """prepare.py should import VALID_TOPICS from topics.py, not llm_extract."""
        import inspect
        import tools.write_journal.prepare as prep

        source = inspect.getsource(prep)
        assert (
            "from tools.lib.topics import" in source
        ), "prepare.py must import VALID_TOPICS from tools.lib.topics, not llm_extract"
