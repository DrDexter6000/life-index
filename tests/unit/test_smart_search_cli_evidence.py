"""CLI tests for smart-search --include-evidence flag (R2C3).

Tests argparse wiring and output shape without running full search pipeline.
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))


def _mock_orch_search(query, include_evidence=False, **kwargs):
    """Mock orchestrator.search() returning evidence only when flag set."""
    result = {
        "success": True,
        "query": query,
        "rewritten_query": query,
        "filtered_results": [{"title": "mock", "path": "mock.md"}],
        "summary": "",
        "citations": [],
        "agent_decisions": [],
        "agent_unavailable": True,
        "performance": {"total_time_ms": 10.0},
    }
    if include_evidence:
        result["evidence_pack"] = {
            "query_context": {"query": query},
            "items": [{"document": {"title": "mock"}, "scores": {"source": "fts"}}],
            "semantic_candidates": [],
            "total_available": 1,
            "has_more": False,
            "no_confident_match": False,
        }
        result["performance"]["evidence_build_ms"] = 1.5
    return result


def _make_mock_orch():
    """Create mock orchestrator with search side_effect."""
    orch = MagicMock()
    orch.search.side_effect = _mock_orch_search
    return orch


def test_cli_include_evidence_flag_parsed():
    """--include-evidence is recognized and passed through to search()."""
    with patch("sys.argv", ["smart-search", "--query", "test", "--include-evidence"]):
        with patch(
            "tools.search_journals.orchestrator.SmartSearchOrchestrator",
            return_value=_make_mock_orch(),
        ) as MockCls:
            with patch("tools.smart_search.__main__._try_init_llm", return_value=None):
                with patch("builtins.print"):
                    from tools.smart_search.__main__ import main

                    try:
                        main()
                    except SystemExit as e:
                        assert e.code == 0
            instance = MockCls.return_value
            call_kwargs = instance.search.call_args
    assert call_kwargs.kwargs.get("include_evidence") is True


def test_cli_default_no_evidence():
    """Without --include-evidence, output has no evidence_pack key."""
    captured = []
    with patch("sys.argv", ["smart-search", "--query", "test"]):
        with patch(
            "tools.search_journals.orchestrator.SmartSearchOrchestrator",
            return_value=_make_mock_orch(),
        ):
            with patch("tools.smart_search.__main__._try_init_llm", return_value=None):
                with patch(
                    "builtins.print",
                    side_effect=lambda *a, **kw: captured.append(a[0]) if a else None,
                ):
                    from tools.smart_search.__main__ import main

                    try:
                        main()
                    except SystemExit:
                        pass
    result = json.loads(captured[0])
    assert "evidence_pack" not in result


def test_cli_include_evidence_adds_pack():
    """With --include-evidence, output includes evidence_pack."""
    captured = []
    with patch("sys.argv", ["smart-search", "--query", "test", "--include-evidence"]):
        with patch(
            "tools.search_journals.orchestrator.SmartSearchOrchestrator",
            return_value=_make_mock_orch(),
        ):
            with patch("tools.smart_search.__main__._try_init_llm", return_value=None):
                with patch(
                    "builtins.print",
                    side_effect=lambda *a, **kw: captured.append(a[0]) if a else None,
                ):
                    from tools.smart_search.__main__ import main

                    try:
                        main()
                    except SystemExit:
                        pass
    result = json.loads(captured[0])
    assert "evidence_pack" in result
    assert "items" in result["evidence_pack"]


def test_cli_help_includes_evidence_flag():
    """--include-evidence appears in CLI help text."""
    captured = []
    with patch("sys.argv", ["smart-search", "--help"]):
        with patch("sys.stdout.write", side_effect=lambda text: captured.append(text)):
            from tools.smart_search.__main__ import main

            try:
                main()
            except SystemExit as e:
                assert e.code == 0

    help_text = "".join(captured)
    assert "--include-evidence" in help_text
    assert "evidence pack" in help_text.lower()


# ---------------------------------------------------------------------------
# R2D1: --synthesize CLI tests
# ---------------------------------------------------------------------------


def _mock_orch_search_with_synthesis(query, include_evidence=False, synthesize=False):
    """Mock orchestrator.search() returning answer when synthesize=True."""
    result = {
        "success": True,
        "query": query,
        "rewritten_query": query,
        "filtered_results": [{"title": "mock", "path": "mock.md"}],
        "summary": "",
        "citations": [],
        "agent_decisions": [],
        "agent_unavailable": False,
        "performance": {"total_time_ms": 10.0},
    }
    if synthesize:
        result["answer"] = {
            "answer_text": "Mock answer based on evidence.",
            "citations": ["mock.md"],
            "confidence": "medium",
            "confidence_reason": "Answer supported by retrieved results without evidence pack.",
            "limitations": [],
            "evidence_summary": "",
        }
        result["performance"]["synthesis_ms"] = 50.0
    if include_evidence:
        result["evidence_pack"] = {
            "query_context": {"query": query},
            "items": [{"document": {"title": "mock"}, "scores": {"source": "fts"}}],
            "semantic_candidates": [],
            "total_available": 1,
            "has_more": False,
            "no_confident_match": False,
        }
        result["performance"]["evidence_build_ms"] = 1.5
    return result


def _make_mock_orch_with_synthesis():
    """Create mock orchestrator with search side_effect supporting synthesize."""
    orch = MagicMock()
    orch.search.side_effect = _mock_orch_search_with_synthesis
    return orch


def test_cli_synthesize_flag_parsed():
    """--synthesize is recognized and passed through to search()."""
    with patch("sys.argv", ["smart-search", "--query", "test", "--synthesize"]):
        with patch(
            "tools.search_journals.orchestrator.SmartSearchOrchestrator",
            return_value=_make_mock_orch_with_synthesis(),
        ) as MockCls:
            with patch("tools.smart_search.__main__._try_init_llm", return_value=None):
                with patch("builtins.print"):
                    from tools.smart_search.__main__ import main

                    try:
                        main()
                    except SystemExit as e:
                        assert e.code == 0
            instance = MockCls.return_value
            call_kwargs = instance.search.call_args
    assert call_kwargs.kwargs.get("synthesize") is True


def test_cli_default_no_answer():
    """Without --synthesize, output has no answer key."""
    captured = []
    with patch("sys.argv", ["smart-search", "--query", "test"]):
        with patch(
            "tools.search_journals.orchestrator.SmartSearchOrchestrator",
            return_value=_make_mock_orch_with_synthesis(),
        ):
            with patch("tools.smart_search.__main__._try_init_llm", return_value=None):
                with patch(
                    "builtins.print",
                    side_effect=lambda *a, **kw: captured.append(a[0]) if a else None,
                ):
                    from tools.smart_search.__main__ import main

                    try:
                        main()
                    except SystemExit:
                        pass
    result = json.loads(captured[0])
    assert "answer" not in result


def test_cli_help_includes_synthesize_flag():
    """--synthesize appears in CLI help text."""
    captured = []
    with patch("sys.argv", ["smart-search", "--help"]):
        with patch("sys.stdout.write", side_effect=lambda text: captured.append(text)):
            from tools.smart_search.__main__ import main

            try:
                main()
            except SystemExit as e:
                assert e.code == 0

    help_text = "".join(captured)
    assert "--synthesize" in help_text


# ---------------------------------------------------------------------------
# R2D3: Answer transparency CLI tests
# ---------------------------------------------------------------------------


def test_cli_synthesize_output_includes_transparency_fields():
    """--synthesize output includes confidence_reason, limitations, evidence_summary."""
    captured = []
    with patch("sys.argv", ["smart-search", "--query", "test", "--synthesize"]):
        with patch(
            "tools.search_journals.orchestrator.SmartSearchOrchestrator",
            return_value=_make_mock_orch_with_synthesis(),
        ):
            with patch("tools.smart_search.__main__._try_init_llm", return_value=None):
                with patch(
                    "builtins.print",
                    side_effect=lambda *a, **kw: captured.append(a[0]) if a else None,
                ):
                    from tools.smart_search.__main__ import main

                    try:
                        main()
                    except SystemExit:
                        pass
    result = json.loads(captured[0])
    assert "answer" in result
    answer = result["answer"]
    assert "confidence_reason" in answer
    assert "limitations" in answer
    assert "evidence_summary" in answer
    assert isinstance(answer["limitations"], list)


# ---------------------------------------------------------------------------
# R2J: Evidence Pack Diagnostics CLI tests
# ---------------------------------------------------------------------------

_VALID_OUTCOMES = ("ok", "weak_results", "no_confident_match", "zero_results")


def _mock_orch_search_with_diagnostics(query, include_evidence=False, **kwargs):
    """Mock orchestrator.search() with diagnostics in evidence_pack."""
    result = {
        "success": True,
        "query": query,
        "rewritten_query": query,
        "filtered_results": [{"title": "mock", "path": "mock.md"}],
        "summary": "",
        "citations": [],
        "agent_decisions": [],
        "agent_unavailable": True,
        "performance": {"total_time_ms": 10.0},
    }
    if include_evidence:
        result["evidence_pack"] = {
            "query_context": {"query": query},
            "items": [{"document": {"title": "mock"}, "scores": {"source": "fts"}}],
            "semantic_candidates": [],
            "total_available": 1,
            "has_more": False,
            "no_confident_match": False,
            "diagnostics": {
                "retrieval_outcome": "ok",
                "outcome_reason": "confident_results_present",
            },
        }
        result["performance"]["evidence_build_ms"] = 1.5
    return result


def _make_mock_orch_with_diagnostics():
    """Create mock orchestrator with diagnostics-aware search."""
    orch = MagicMock()
    orch.search.side_effect = _mock_orch_search_with_diagnostics
    return orch


def test_cli_evidence_includes_diagnostics():
    """--include-evidence output includes evidence_pack.diagnostics."""
    captured = []
    with patch("sys.argv", ["smart-search", "--query", "test", "--include-evidence"]):
        with patch(
            "tools.search_journals.orchestrator.SmartSearchOrchestrator",
            return_value=_make_mock_orch_with_diagnostics(),
        ):
            with patch("tools.smart_search.__main__._try_init_llm", return_value=None):
                with patch(
                    "builtins.print",
                    side_effect=lambda *a, **kw: captured.append(a[0]) if a else None,
                ):
                    from tools.smart_search.__main__ import main

                    try:
                        main()
                    except SystemExit:
                        pass
    result = json.loads(captured[0])
    assert "evidence_pack" in result
    assert "diagnostics" in result["evidence_pack"]
    diag = result["evidence_pack"]["diagnostics"]
    assert diag["retrieval_outcome"] in _VALID_OUTCOMES
    assert isinstance(diag.get("outcome_reason"), str)
    # notes/suggestions conditionally present (omitted when empty)
    if "notes" in diag:
        assert isinstance(diag["notes"], list)
    if "suggestions" in diag:
        assert isinstance(diag["suggestions"], list)


def test_cli_default_no_diagnostics():
    """Default output has no evidence_pack, hence no diagnostics."""
    captured = []
    with patch("sys.argv", ["smart-search", "--query", "test"]):
        with patch(
            "tools.search_journals.orchestrator.SmartSearchOrchestrator",
            return_value=_make_mock_orch_with_diagnostics(),
        ):
            with patch("tools.smart_search.__main__._try_init_llm", return_value=None):
                with patch(
                    "builtins.print",
                    side_effect=lambda *a, **kw: captured.append(a[0]) if a else None,
                ):
                    from tools.smart_search.__main__ import main

                    try:
                        main()
                    except SystemExit:
                        pass
    result = json.loads(captured[0])
    assert "evidence_pack" not in result


# ---------------------------------------------------------------------------
# S1O: LLM config alignment tests
# ---------------------------------------------------------------------------


def _clear_llm_env(monkeypatch):
    """Clear all LLM-related env vars to ensure test isolation."""
    for key in [
        "OPENAI_API_KEY",
        "LLM_API_KEY",
        "OPENAI_BASE_URL",
        "LLM_BASE_URL",
        "LLM_MODEL",
        "LIFE_INDEX_LLM_API_KEY",
        "LIFE_INDEX_LLM_BASE_URL",
        "LIFE_INDEX_LLM_MODEL",
    ]:
        monkeypatch.delenv(key, raising=False)


def test_resolve_llm_config_life_index_env(monkeypatch):
    """LIFE_INDEX_LLM_* env vars are used when OPENAI_*/LLM_* are absent."""
    _clear_llm_env(monkeypatch)
    monkeypatch.setattr("tools.lib.config.USER_CONFIG", {})
    monkeypatch.setenv("LIFE_INDEX_LLM_API_KEY", "li-key")
    monkeypatch.setenv("LIFE_INDEX_LLM_BASE_URL", "https://li.example/v1")
    monkeypatch.setenv("LIFE_INDEX_LLM_MODEL", "li-model")

    from tools.smart_search.__main__ import _resolve_llm_config

    api_key, base_url, model = _resolve_llm_config()
    assert api_key == "li-key"
    assert base_url == "https://li.example/v1"
    assert model == "li-model"


def test_resolve_llm_config_openai_env_overrides_life_index(monkeypatch):
    """OPENAI_API_KEY selects legacy path; Life Index config is ignored."""
    _clear_llm_env(monkeypatch)
    monkeypatch.setattr("tools.lib.config.USER_CONFIG", {})
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.setenv("LIFE_INDEX_LLM_API_KEY", "li-key")
    monkeypatch.setenv("LIFE_INDEX_LLM_BASE_URL", "https://li.example/v1")
    monkeypatch.setenv("LIFE_INDEX_LLM_MODEL", "li-model")

    from tools.smart_search.__main__ import _resolve_llm_config

    api_key, base_url, model = _resolve_llm_config()
    assert api_key == "openai-key"
    assert base_url is None
    assert model == "gpt-4o-mini"


def test_resolve_llm_config_llm_env_overrides_life_index(monkeypatch):
    """LLM_API_KEY selects legacy path; Life Index config is ignored."""
    _clear_llm_env(monkeypatch)
    monkeypatch.setattr("tools.lib.config.USER_CONFIG", {})
    monkeypatch.setenv("LLM_API_KEY", "llm-key")
    monkeypatch.setenv("LIFE_INDEX_LLM_API_KEY", "li-key")
    monkeypatch.setenv("LIFE_INDEX_LLM_BASE_URL", "https://li.example/v1")
    monkeypatch.setenv("LIFE_INDEX_LLM_MODEL", "li-model")

    from tools.smart_search.__main__ import _resolve_llm_config

    api_key, base_url, model = _resolve_llm_config()
    assert api_key == "llm-key"
    assert base_url is None
    assert model == "gpt-4o-mini"


def test_resolve_llm_config_config_file_fallback(monkeypatch):
    """Config file values are used when no env vars are set."""
    _clear_llm_env(monkeypatch)
    monkeypatch.setattr(
        "tools.lib.config.USER_CONFIG",
        {
            "llm": {
                "api_key": "cfg-key",
                "base_url": "https://cfg.example/v1",
                "model": "cfg-model",
            }
        },
    )

    from tools.smart_search.__main__ import _resolve_llm_config

    api_key, base_url, model = _resolve_llm_config()
    assert api_key == "cfg-key"
    assert base_url == "https://cfg.example/v1"
    assert model == "cfg-model"


def test_resolve_llm_config_no_key_returns_none(monkeypatch):
    """Missing key returns None for api_key."""
    _clear_llm_env(monkeypatch)
    monkeypatch.setattr("tools.lib.config.USER_CONFIG", {})

    from tools.smart_search.__main__ import _resolve_llm_config

    api_key, base_url, model = _resolve_llm_config()
    assert api_key is None
    assert model == "gpt-4o-mini"


def test_try_init_llm_returns_none_without_key(monkeypatch):
    """_try_init_llm returns None when no API key is available."""
    _clear_llm_env(monkeypatch)
    monkeypatch.setattr("tools.lib.config.USER_CONFIG", {})

    from tools.smart_search.__main__ import _try_init_llm

    assert _try_init_llm() is None


def test_try_init_llm_returns_client_with_life_index_key(monkeypatch):
    """_try_init_llm initializes client with LIFE_INDEX_LLM_API_KEY."""
    _clear_llm_env(monkeypatch)
    monkeypatch.setattr("tools.lib.config.USER_CONFIG", {})
    monkeypatch.setenv("LIFE_INDEX_LLM_API_KEY", "test-li-key")
    monkeypatch.setenv("LIFE_INDEX_LLM_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setenv("LIFE_INDEX_LLM_MODEL", "gpt-4o-mini")

    from tools.smart_search.__main__ import _try_init_llm

    client = _try_init_llm()
    assert client is not None
    assert client._model == "gpt-4o-mini"


def test_try_init_llm_openai_key_still_works(monkeypatch):
    """Existing OPENAI_API_KEY path is preserved."""
    _clear_llm_env(monkeypatch)
    monkeypatch.setattr("tools.lib.config.USER_CONFIG", {})
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

    from tools.smart_search.__main__ import _try_init_llm

    client = _try_init_llm()
    assert client is not None


def test_resolve_llm_config_legacy_key_no_cross_contamination(monkeypatch):
    """Legacy API key + Life Index base_url/model: only legacy env/default used."""
    _clear_llm_env(monkeypatch)
    monkeypatch.setattr(
        "tools.lib.config.USER_CONFIG",
        {
            "llm": {
                "api_key": "cfg-key",
                "base_url": "https://cfg.example/v1",
                "model": "cfg-model",
            }
        },
    )
    monkeypatch.setenv("OPENAI_API_KEY", "legacy-key")
    monkeypatch.setenv("LIFE_INDEX_LLM_BASE_URL", "https://li.example/v1")
    monkeypatch.setenv("LIFE_INDEX_LLM_MODEL", "li-model")

    from tools.smart_search.__main__ import _resolve_llm_config

    api_key, base_url, model = _resolve_llm_config()
    assert api_key == "legacy-key"
    assert base_url is None
    assert model == "gpt-4o-mini"


def test_resolve_llm_config_legacy_key_with_own_base_url(monkeypatch):
    """Legacy API key + OPENAI_BASE_URL: legacy base_url is used."""
    _clear_llm_env(monkeypatch)
    monkeypatch.setattr("tools.lib.config.USER_CONFIG", {})
    monkeypatch.setenv("OPENAI_API_KEY", "legacy-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://legacy.example/v1")
    monkeypatch.setenv("LIFE_INDEX_LLM_BASE_URL", "https://li.example/v1")

    from tools.smart_search.__main__ import _resolve_llm_config

    api_key, base_url, model = _resolve_llm_config()
    assert api_key == "legacy-key"
    assert base_url == "https://legacy.example/v1"


def test_resolve_llm_config_legacy_key_llm_model_env(monkeypatch):
    """Legacy API key + LLM_MODEL env: LLM_MODEL is honored."""
    _clear_llm_env(monkeypatch)
    monkeypatch.setattr("tools.lib.config.USER_CONFIG", {})
    monkeypatch.setenv("LLM_API_KEY", "legacy-key")
    monkeypatch.setenv("LLM_MODEL", "legacy-model")
    monkeypatch.setenv("LIFE_INDEX_LLM_MODEL", "li-model")

    from tools.smart_search.__main__ import _resolve_llm_config

    api_key, base_url, model = _resolve_llm_config()
    assert api_key == "legacy-key"
    assert model == "legacy-model"


def test_resolve_llm_config_no_legacy_key_uses_life_index(monkeypatch):
    """No legacy key: Life Index env/config provides all three fields atomically."""
    _clear_llm_env(monkeypatch)
    monkeypatch.setattr(
        "tools.lib.config.USER_CONFIG",
        {
            "llm": {
                "api_key": "cfg-key",
                "base_url": "https://cfg.example/v1",
                "model": "cfg-model",
            }
        },
    )

    from tools.smart_search.__main__ import _resolve_llm_config

    api_key, base_url, model = _resolve_llm_config()
    assert api_key == "cfg-key"
    assert base_url == "https://cfg.example/v1"
    assert model == "cfg-model"


def test_resolve_llm_config_llm_base_url_fallback_in_legacy(monkeypatch):
    """LLM_API_KEY + LLM_BASE_URL (not OPENAI_BASE_URL) works in legacy path."""
    _clear_llm_env(monkeypatch)
    monkeypatch.setattr("tools.lib.config.USER_CONFIG", {})
    monkeypatch.setenv("LLM_API_KEY", "legacy-key")
    monkeypatch.setenv("LLM_BASE_URL", "https://llm-legacy.example/v1")

    from tools.smart_search.__main__ import _resolve_llm_config

    api_key, base_url, model = _resolve_llm_config()
    assert api_key == "legacy-key"
    assert base_url == "https://llm-legacy.example/v1"
