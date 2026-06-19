from __future__ import annotations

from tools.recall import core


def test_deep_mode_stays_deterministic_even_when_legacy_use_llm_true(monkeypatch):
    """Deep recall must not delegate to smart-search LLM orchestration."""

    def fake_search(query, no_semantic=False, env=None):
        return {
            "success": True,
            "merged_results": [{"title": "deterministic"}],
        }

    monkeypatch.setattr(core, "_call_search", fake_search)

    payload = core.run_recall("deep", "python", use_llm=True)

    assert payload["success"] is True
    assert payload["mode"] == "deep"
    assert payload["effective_mode"] == "recall"
    assert payload["source_command"] == "search"
    assert payload["results"] == [{"title": "deterministic"}]
