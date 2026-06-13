"""V5a ACP query adapter contract tests.

Covers parse_and_validate (unit), acp_query_adapter (integration via fake agent),
and handoff routing (no openai synthesize when transport==acp).
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
FIXTURE_PATH = Path(__file__).resolve().parent.parent / "fixtures" / "agent_bridge"


# ─── Helpers ──────────────────────────────────────────────────────────


def _valid_grounded_json(allowed_ids=frozenset({"E1", "E2"})) -> str:
    return json.dumps(
        {
            "schema_version": "m35.agent_bridge_query.v0",
            "status": "GROUNDED",
            "answer": "This is a grounded answer.",
            "insights": [
                {"text": "Insight 1", "evidence_refs": ["E1"]},
                {"text": "Insight 2", "evidence_refs": ["E1", "E2"]},
            ],
            "evidence_refs": ["E1", "E2"],
            "gap": None,
            "provenance": {
                "transport": "acp",
                "model": "test",
                "runtime": "test",
                "degraded": False,
            },
            "usage": {"input_tokens": 100, "output_tokens": 50},
        },
        ensure_ascii=False,
    )


def _valid_ungrounded_json() -> str:
    return json.dumps(
        {
            "schema_version": "m35.agent_bridge_query.v0",
            "status": "UNGROUNDED",
            "answer": None,
            "insights": [],
            "evidence_refs": [],
            "gap": "No relevant evidence found.",
            "provenance": {
                "transport": "acp",
                "model": "test",
                "runtime": "test",
                "degraded": False,
            },
            "usage": {"input_tokens": 90, "output_tokens": 40},
        },
        ensure_ascii=False,
    )


def _unknown_evidence_json() -> str:
    return json.dumps(
        {
            "schema_version": "m35.agent_bridge_query.v0",
            "status": "GROUNDED",
            "answer": "Answer citing Z99.",
            "insights": [
                {"text": "Made-up insight", "evidence_refs": ["Z99"]},
            ],
            "evidence_refs": ["Z99"],
            "gap": None,
            "provenance": {
                "transport": "acp",
                "model": "test",
                "runtime": "test",
                "degraded": False,
            },
            "usage": {"input_tokens": 80, "output_tokens": 30},
        },
        ensure_ascii=False,
    )


# ─── Test 1: Strict valid JSON parsing ────────────────────────────────


def test_strict_valid_json_becomes_valid_envelope():
    """Parse strict valid JSON → valid m35.agent_bridge_query.v0 with GROUNDED status."""
    from tools.agent_bridge.acp_query import parse_and_validate

    raw = _valid_grounded_json()
    allowed = frozenset({"E1", "E2"})

    result, error = parse_and_validate(raw, allowed)

    assert error is None, f"Unexpected error: {error}"
    assert result is not None
    assert result["schema_version"] == "m35.agent_bridge_query.v0"
    assert result["status"] == "GROUNDED"
    assert result["answer"] == "This is a grounded answer."
    assert len(result["insights"]) == 2
    assert result["insights"][0]["text"] == "Insight 1"
    assert result["insights"][0]["evidence_refs"] == ["E1"]
    assert result["evidence_refs"] == ["E1", "E2"]
    assert result["gap"] is None


# ─── Test 2: Markdown-fenced JSON repair ──────────────────────────────


def test_markdown_fenced_json_repairs_successfully():
    """JSON inside ```json ... ``` fence repairs to valid envelope."""
    from tools.agent_bridge.acp_query import parse_and_validate

    raw = "```json\n" + _valid_grounded_json() + "\n```"
    allowed = frozenset({"E1", "E2"})

    result, error = parse_and_validate(raw, allowed)

    assert error is None, f"Unexpected error: {error}"
    assert result is not None
    assert result["status"] == "GROUNDED"
    assert result["answer"] == "This is a grounded answer."


# ─── Test 3: Mixed prose rejection ────────────────────────────────────


def test_mixed_prose_rejected_then_repaired():
    """Mixed prose rejected on first attempt, then repair retry succeeds.

    parse_and_validate rejects multi-JSON mixed prose.  The adapter
    then sends a repair prompt; the fake agent (defaulting to valid
    GROUNDED on the retry) produces valid output.  The adapter must
    return the successful retry envelope.
    """
    from tools.agent_bridge.acp_query import (
        QUERY_SCHEMA_VERSION,
        acp_query_adapter,
        parse_and_validate,
    )
    from tools.agent_bridge.config import BrainConfig

    # First, test parse_and_validate directly with mixed prose — must reject
    raw = (
        "Let me help you.\n\n"
        + _valid_grounded_json()
        + "\n\nAlso here's more: "
        + '{"extra": "json"}'
    )
    allowed = frozenset({"E1", "E2"})

    result, error = parse_and_validate(raw, allowed)
    assert result is None, "Mixed prose should be rejected"
    assert (
        error is not None and "Multiple" in error
    ), f"Expected 'Multiple JSON' error, got: {error}"

    # Now integration: full adapter path with MIXED_PROSE_TEST marker.
    # The fake agent emits mixed prose on first turn (rejected), then
    # the repair prompt triggers the default valid GROUNDED response.
    fake_agent = sys.executable
    fake_script = str(FIXTURE_PATH / "fake_acp_agent_query.py")

    cfg = BrainConfig(
        mode="host_agent",
        endpoint=None,
        transport="acp",
        api_key=None,
        model=None,
        data_exposure_ack=True,
        acp_command=[fake_agent, fake_script],
        acp_workdir=str(FIXTURE_PATH),
    )

    scaffold = {
        "evidence_pack": {
            "items": [
                {"document": {"doc_id": "real-entry-1"}, "snippet": "Evidence snippet one."},
                {"document": {"doc_id": "real-entry-2"}, "snippet": "Evidence snippet two."},
            ],
        },
    }

    result = acp_query_adapter("MIXED_PROSE_TEST query", scaffold, cfg)

    # The retry succeeds (fake agent defaults to valid GROUNDED referencing E1)
    assert result["schema_version"] == QUERY_SCHEMA_VERSION
    assert result["status"] == "GROUNDED"
    assert result["provenance"]["degraded"] is False


# ─── Test 4: Unknown evidence ID rejection ────────────────────────────


def test_unknown_evidence_id_rejected():
    """Valid JSON but with unknown evidence IDs → rejected, does NOT become GROUNDED."""
    from tools.agent_bridge.acp_query import parse_and_validate

    raw = _unknown_evidence_json()
    allowed = frozenset({"E1", "E2"})

    result, error = parse_and_validate(raw, allowed)

    assert result is None, "Unknown evidence ID should be rejected"
    assert error is not None
    assert "Z99" in error, f"Error should mention Z99, got: {error}"
    assert "Unknown" in error or "unknown" in error or "evidence" in error.lower()


# ─── Test 5: Short evidence IDs map to real IDs ───────────────────────


def test_short_evidence_ids_map_to_real_ids():
    """Short IDs (E1, E2) map to real journal entry IDs in final evidence_refs."""
    from tools.agent_bridge.acp_query import build_evidence_pack

    scaffold = {
        "evidence_pack": {
            "items": [
                {
                    "document": {"doc_id": "journal-2026-03-04-abc"},
                    "snippet": "First journal entry about life.",
                },
                {
                    "document": {"doc_id": "journal-2026-03-05-def"},
                    "abstract": "Second journal entry about work.",
                },
            ],
        },
    }

    evidence, mapping = build_evidence_pack(scaffold)

    assert "E1" in evidence
    assert "E2" in evidence
    assert mapping["E1"] == "journal-2026-03-04-abc"
    assert mapping["E2"] == "journal-2026-03-05-def"
    assert evidence["E1"]["short_id"] == "E1"
    assert evidence["E2"]["short_id"] == "E2"
    assert "life" in evidence["E1"]["text"]
    assert "work" in evidence["E2"]["text"]


def test_short_evidence_ids_map_from_filtered_results():
    """Evidence from filtered_results also gets short IDs."""
    from tools.agent_bridge.acp_query import build_evidence_pack

    route_path = "D:\\Users\\me\\Life-Index\\Journals\\2026\\06\\result-002.md"
    scaffold = {
        "filtered_results": [
            {"rel_path": "Journals/2026/06/result-001.md", "snippet": "Filtered result one."},
            {"journal_route_path": route_path, "abstract": "Filtered result two."},
        ],
    }

    evidence, mapping = build_evidence_pack(scaffold)

    assert len(evidence) == 2
    assert mapping["E1"] == "Journals/2026/06/result-001.md"
    assert mapping["E2"] == "Journals/2026/06/result-002.md"


# ─── Test 6: UNGROUNDED output accepted ───────────────────────────────


def test_ungrounded_output_accepts_empty_refs():
    """UNGROUNDED with empty refs and non-empty gap accepted as valid."""
    from tools.agent_bridge.acp_query import parse_and_validate

    raw = _valid_ungrounded_json()
    allowed = frozenset({"E1", "E2"})

    result, error = parse_and_validate(raw, allowed)

    assert error is None, f"Unexpected error: {error}"
    assert result is not None
    assert result["status"] == "UNGROUNDED"
    assert result["answer"] is None
    assert result["insights"] == []
    assert result["evidence_refs"] == []
    assert result["gap"] is not None


# ─── Test 7: ACP stream parser uses agent_message_chunk ────────────────


def test_acp_stream_parser_uses_agent_message_chunk():
    """Stream parser collects agent_message_chunk and ignores agent_thought_chunk."""
    from tools.agent_bridge.acp_client import parse_acp_stream

    messages = [
        {
            "jsonrpc": "2.0",
            "method": "session/update",
            "params": {
                "sessionId": "test-session",
                "update": {
                    "content": {"text": "Hello from ACP", "type": "text"},
                    "sessionUpdate": "agent_message_chunk",
                },
            },
        },
        {
            "jsonrpc": "2.0",
            "method": "session/update",
            "params": {
                "sessionId": "test-session",
                "update": {
                    "content": {"text": "This is a thought that should not appear", "type": "text"},
                    "sessionUpdate": "agent_thought_chunk",
                },
            },
        },
        {
            "jsonrpc": "2.0",
            "method": "session/update",
            "params": {
                "sessionId": "test-session",
                "update": {
                    "content": {"text": " More output.", "type": "text"},
                    "sessionUpdate": "agent_message_chunk",
                },
            },
        },
    ]

    result = parse_acp_stream(messages)

    assert "Hello from ACP" in result
    assert "More output" in result
    assert "thought" not in result.lower()


# ─── Test 8: ACP handoff does NOT call openai synthesize ──────────────


def test_acp_handoff_does_not_call_openai_synthesize(monkeypatch):
    """When transport=='acp' and handoff_search is called, client.synthesize is NOT called."""
    import tools.agent_bridge.handoff as handoff_mod
    from tools.agent_bridge.config import BrainConfig

    # Monkeypatch cli_smart_search to avoid subprocess call
    fake_scaffold = {
        "query": "test query",
        "evidence_pack": {
            "items": [
                {"document": {"doc_id": "entry-1"}, "snippet": "Test evidence."},
            ],
        },
    }
    monkeypatch.setattr(handoff_mod, "_cli_smart_search", lambda _q: fake_scaffold)

    # Monkeypatch resolve_brain_config
    fake_agent = sys.executable
    fake_script = str(FIXTURE_PATH / "fake_acp_agent_query.py")
    cfg = BrainConfig(
        mode="host_agent",
        endpoint=None,
        transport="acp",
        api_key=None,
        model=None,
        data_exposure_ack=True,
        acp_command=[fake_agent, fake_script],
        acp_workdir=str(FIXTURE_PATH),
    )
    monkeypatch.setattr(handoff_mod, "resolve_brain_config", lambda: cfg)

    # Monkeypatch resolve_source to return P1 (so it enters the ACP path)
    monkeypatch.setattr(handoff_mod, "resolve_source", lambda _c, in_context_agent=False: "P1")

    # Track whether client.synthesize is called
    synthesize_called = []

    def _fake_synthesize(*_args, **_kwargs):
        synthesize_called.append(True)
        return "SHOULD NOT BE CALLED"

    monkeypatch.setattr("tools.agent_bridge.client.synthesize", _fake_synthesize, raising=False)

    result = handoff_mod.handoff_search("VALID_JSON_TEST query")

    # ACP query adapter returns m35.agent_bridge_query.v0 envelope
    assert result["schema_version"] == "m35.agent_bridge_query.v0"
    assert result["status"] == "GROUNDED"

    # client.synthesize must NOT have been called
    assert len(synthesize_called) == 0, "client.synthesize was called but should NOT have been"


def test_acp_handoff_degrade_does_not_call_openai_synthesize(monkeypatch):
    """When ACP fails in handoff_search, degrade via acp_query module, not client.synthesize."""
    import tools.agent_bridge.handoff as handoff_mod
    from tools.agent_bridge.config import BrainConfig

    # Monkeypatch cli_smart_search
    fake_scaffold = {
        "query": "test query",
        "evidence_pack": {
            "items": [
                {"document": {"doc_id": "entry-1"}, "snippet": "Test evidence."},
            ],
        },
    }
    monkeypatch.setattr(handoff_mod, "_cli_smart_search", lambda _q: fake_scaffold)

    # Config with nonexistent ACP command so adapter fails immediately
    cfg = BrainConfig(
        mode="host_agent",
        endpoint=None,
        transport="acp",
        api_key=None,
        model=None,
        data_exposure_ack=True,
        acp_command=["/nonexistent/path/to/acp-binary"],
        acp_workdir=str(FIXTURE_PATH),
    )
    monkeypatch.setattr(handoff_mod, "resolve_brain_config", lambda: cfg)
    monkeypatch.setattr(handoff_mod, "resolve_source", lambda _c, in_context_agent=False: "P1")

    # Track synthesize calls
    synthesize_called = []

    def _fake_synthesize(*_args, **_kwargs):
        synthesize_called.append(True)
        return "SHOULD NOT BE CALLED"

    monkeypatch.setattr("tools.agent_bridge.client.synthesize", _fake_synthesize, raising=False)

    result = handoff_mod.handoff_search("test query")

    # Should be a degraded m35.agent_bridge_query.v0 envelope
    assert result["schema_version"] == "m35.agent_bridge_query.v0"
    assert result["status"] == "UNGROUNDED"
    assert result["provenance"]["degraded"] is True
    assert (
        len(synthesize_called) == 0
    ), "client.synthesize was called during ACP degradation — must not happen"


# ─── Test 9: Probe contract unchanged ─────────────────────────────────


def test_probe_contract_unchanged():
    """Probe still emits m35.agent_bridge_probe.v0; no scaffold/synthesis/evidence content."""
    from tools.agent_bridge.probe import probe_agent_bridge

    result = probe_agent_bridge(network=False)

    assert result["schema_version"] == "m35.agent_bridge_probe.v0"
    assert result["success"] is True
    assert result["command"] == "agent-bridge probe"
    assert "scaffold" not in result
    assert "synthesis" not in result
    assert "evidence_pack" not in result
    assert result["sends_journal_evidence"] is False


# ─── Additional: build_degraded_result / build_provenance / build_query_prompt ──


def test_build_degraded_result_never_returns_grounded():
    """build_degraded_result always returns UNGROUNDED or PARTIAL, never GROUNDED."""
    from tools.agent_bridge.acp_query import build_degraded_result, build_provenance
    from tools.agent_bridge.config import BrainConfig

    cfg = BrainConfig(
        mode="host_agent",
        endpoint=None,
        transport="acp",
        api_key=None,
        model="test-model",
        data_exposure_ack=True,
    )

    provenance = build_provenance(cfg, degraded=True)
    result = build_degraded_result("UNGROUNDED", "Test gap", provenance)

    assert result["status"] == "UNGROUNDED"
    assert result["answer"] is None
    assert result["insights"] == []
    assert result["evidence_refs"] == []
    assert result["gap"] == "Test gap"
    assert result["provenance"]["degraded"] is True
    assert result["provenance"]["transport"] == "acp"
    assert result["usage"] is None

    # Even if a bad status is passed, it must NEVER return GROUNDED
    result2 = build_degraded_result("GROUNDED", "Should not be grounded", provenance)
    assert result2["status"] != "GROUNDED", "build_degraded_result must never return GROUNDED"


def test_build_query_prompt_includes_allowed_ids():
    """build_query_prompt includes allowed IDs and evidence entries."""
    from tools.agent_bridge.acp_query import build_query_prompt

    evidence = {
        "E1": {"short_id": "E1", "text": "First evidence snippet."},
        "E2": {"short_id": "E2", "text": "Second evidence snippet."},
    }
    allowed = {"E1", "E2"}

    prompt = build_query_prompt("What is the meaning?", evidence, allowed)

    assert "What is the meaning?" in prompt
    assert "E1" in prompt
    assert "E2" in prompt
    assert "First evidence snippet" in prompt
    assert "Second evidence snippet" in prompt
    assert "GROUNDED" in prompt
    assert "PARTIAL" in prompt
    assert "UNGROUNDED" in prompt
    assert "m35.agent_bridge_query.v0" in prompt


def test_parse_and_validate_rejects_empty_string():
    """Empty string is rejected by parse_and_validate."""
    from tools.agent_bridge.acp_query import parse_and_validate

    result, error = parse_and_validate("", frozenset({"E1"}))

    assert result is None
    assert error is not None


def test_parse_and_validate_rejects_invalid_status():
    """Invalid status value is rejected."""
    from tools.agent_bridge.acp_query import parse_and_validate

    raw = json.dumps(
        {
            "schema_version": "m35.agent_bridge_query.v0",
            "status": "HALLUCINATED",
            "answer": "test",
            "insights": [{"text": "t", "evidence_refs": ["E1"]}],
            "evidence_refs": ["E1"],
            "gap": None,
        }
    )
    result, error = parse_and_validate(raw, frozenset({"E1"}))

    assert result is None
    assert error is not None
    assert "HALLUCINATED" in error


def test_parse_and_validate_grounded_requires_answer():
    """GROUNDED with null answer is rejected."""
    from tools.agent_bridge.acp_query import parse_and_validate

    raw = json.dumps(
        {
            "schema_version": "m35.agent_bridge_query.v0",
            "status": "GROUNDED",
            "answer": None,
            "insights": [{"text": "t", "evidence_refs": ["E1"]}],
            "evidence_refs": ["E1"],
            "gap": None,
        }
    )
    result, error = parse_and_validate(raw, frozenset({"E1"}))

    assert result is None
    assert error is not None


def test_build_provenance_uses_cfg_model():
    """build_provenance uses cfg.model when conn_meta has no model."""
    from tools.agent_bridge.acp_query import build_provenance
    from tools.agent_bridge.config import BrainConfig

    cfg = BrainConfig(
        mode="host_agent",
        endpoint=None,
        transport="acp",
        api_key=None,
        model="gpt-4",
        data_exposure_ack=True,
    )

    provenance = build_provenance(cfg, degraded=False)

    assert provenance["transport"] == "acp"
    assert provenance["model"] == "gpt-4"
    assert provenance["degraded"] is False


def test_build_evidence_pack_bounds_to_max():
    """Evidence pack is bounded to _MAX_EVIDENCE_ENTRIES."""
    from tools.agent_bridge.acp_query import build_evidence_pack

    entries = [{"document": {"doc_id": f"entry-{i}"}, "snippet": f"Snippet {i}"} for i in range(20)]
    scaffold = {"evidence_pack": {"items": entries}}

    evidence, mapping = build_evidence_pack(scaffold)

    assert len(evidence) <= 10
    assert len(mapping) <= 10


def test_acp_query_adapter_two_turn_retry_succeeds():
    """Full adapter: first turn invalid, second turn valid → success after retry."""
    from tools.agent_bridge.acp_query import QUERY_SCHEMA_VERSION, acp_query_adapter
    from tools.agent_bridge.config import BrainConfig

    fake_agent = sys.executable
    fake_script = str(FIXTURE_PATH / "fake_acp_agent_query.py")

    cfg = BrainConfig(
        mode="host_agent",
        endpoint=None,
        transport="acp",
        api_key=None,
        model=None,
        data_exposure_ack=True,
        acp_command=[fake_agent, fake_script],
        acp_workdir=str(FIXTURE_PATH),
    )

    scaffold = {
        "evidence_pack": {
            "items": [
                {"document": {"doc_id": "real-entry-1"}, "snippet": "Evidence snippet one."},
                {"document": {"doc_id": "real-entry-2"}, "snippet": "Evidence snippet two."},
            ],
        },
    }

    result = acp_query_adapter("TWO_TURN_TEST query", scaffold, cfg)

    assert result["schema_version"] == QUERY_SCHEMA_VERSION
    assert result["status"] == "GROUNDED"
    assert result["answer"] is not None


def test_acp_query_adapter_with_ungrounded_marker():
    """Full adapter with UNGROUNDED_TEST marker → valid UNGROUNDED envelope."""
    from tools.agent_bridge.acp_query import QUERY_SCHEMA_VERSION, acp_query_adapter
    from tools.agent_bridge.config import BrainConfig

    fake_agent = sys.executable
    fake_script = str(FIXTURE_PATH / "fake_acp_agent_query.py")

    cfg = BrainConfig(
        mode="host_agent",
        endpoint=None,
        transport="acp",
        api_key=None,
        model=None,
        data_exposure_ack=True,
        acp_command=[fake_agent, fake_script],
        acp_workdir=str(FIXTURE_PATH),
    )

    scaffold = {
        "evidence_pack": {
            "items": [
                {"document": {"doc_id": "real-entry-1"}, "snippet": "Evidence snippet one."},
            ],
        },
    }

    result = acp_query_adapter("UNGROUNDED_TEST query", scaffold, cfg)

    assert result["schema_version"] == QUERY_SCHEMA_VERSION
    assert result["status"] == "UNGROUNDED"
    assert result["answer"] is None
    assert result["gap"] is not None


def test_acp_query_adapter_with_fenced_json():
    """Full adapter with FENCED_JSON_TEST → repair succeeds."""
    from tools.agent_bridge.acp_query import QUERY_SCHEMA_VERSION, acp_query_adapter
    from tools.agent_bridge.config import BrainConfig

    fake_agent = sys.executable
    fake_script = str(FIXTURE_PATH / "fake_acp_agent_query.py")

    cfg = BrainConfig(
        mode="host_agent",
        endpoint=None,
        transport="acp",
        api_key=None,
        model=None,
        data_exposure_ack=True,
        acp_command=[fake_agent, fake_script],
        acp_workdir=str(FIXTURE_PATH),
    )

    scaffold = {
        "evidence_pack": {
            "items": [
                {"document": {"doc_id": "real-entry-1"}, "snippet": "Evidence snippet one."},
                {"document": {"doc_id": "real-entry-2"}, "snippet": "Evidence snippet two."},
            ],
        },
    }

    result = acp_query_adapter("FENCED_JSON_TEST query", scaffold, cfg)

    assert result["schema_version"] == QUERY_SCHEMA_VERSION
    assert result["status"] == "GROUNDED"


def test_acp_query_adapter_with_unknown_evidence_rejected_then_repaired():
    """Full adapter with UNKNOWN_EVIDENCE_TEST: rejected, then repair retry succeeds.

    The fake agent emits a GROUNDED response with fabricated Z99 on first
    turn.  parse_and_validate rejects it (unknown evidence ID).  The
    repair prompt triggers the default valid GROUNDED response (E1 only).
    The adapter returns the successful retry envelope.
    """
    from tools.agent_bridge.acp_query import QUERY_SCHEMA_VERSION, acp_query_adapter
    from tools.agent_bridge.config import BrainConfig

    fake_agent = sys.executable
    fake_script = str(FIXTURE_PATH / "fake_acp_agent_query.py")

    cfg = BrainConfig(
        mode="host_agent",
        endpoint=None,
        transport="acp",
        api_key=None,
        model=None,
        data_exposure_ack=True,
        acp_command=[fake_agent, fake_script],
        acp_workdir=str(FIXTURE_PATH),
    )

    scaffold = {
        "evidence_pack": {
            "items": [
                {"document": {"doc_id": "real-entry-1"}, "snippet": "Evidence snippet one."},
            ],
        },
    }

    result = acp_query_adapter("UNKNOWN_EVIDENCE_TEST query", scaffold, cfg)

    assert result["schema_version"] == QUERY_SCHEMA_VERSION
    # The retry succeeds (fake agent defaults to valid GROUNDED with E1)
    assert result["status"] == "GROUNDED"
    assert result["provenance"]["degraded"] is False


# ─── Lead-review regression tests ─────────────────────────────────────


def test_build_evidence_pack_uses_real_smart_search_items():
    """A real smart-search evidence_pack with items maps E1/E2 to journal doc_ids.

    Container keys such as ``items``, ``query_context``, and
    ``semantic_candidates`` must NEVER become evidence IDs.
    """
    from tools.agent_bridge.acp_query import build_evidence_pack

    scaffold = {
        "evidence_pack": {
            "query_context": {
                "query": "team offsite",
                "expanded_query": "team offsite retreat",
            },
            "items": [
                {
                    "document": {
                        "doc_id": "Journals/2026/06/life-index_2026-06-10_001.md",
                        "title": "Team offsite",
                        "date": "2026-06-10",
                    },
                    "snippet": "We discussed the roadmap for Q3.",
                },
                {
                    "document": {
                        "doc_id": "Journals/2026/06/life-index_2026-06-11_001.md",
                        "title": "Follow-up",
                        "date": "2026-06-11",
                    },
                    "snippet": "Action items from the offsite.",
                },
            ],
            "semantic_candidates": [],
        }
    }

    evidence, mapping = build_evidence_pack(scaffold)

    assert mapping["E1"] == "Journals/2026/06/life-index_2026-06-10_001.md"
    assert mapping["E2"] == "Journals/2026/06/life-index_2026-06-11_001.md"
    forbidden = {"items", "query_context", "semantic_candidates"}
    assert not any(v in forbidden for v in mapping.values())
    assert "roadmap" in evidence["E1"]["text"]
    assert "Action items" in evidence["E2"]["text"]


def test_parse_and_validate_rejects_spike_schema_version():
    """Spike-era schema_version values such as v5_spike.answer.v0 must fail."""
    from tools.agent_bridge.acp_query import parse_and_validate

    raw = json.dumps(
        {
            "schema_version": "v5_spike.answer.v0",
            "status": "GROUNDED",
            "answer": "answer",
            "insights": [{"text": "insight", "evidence_refs": ["E1"]}],
            "evidence_refs": ["E1"],
            "gap": None,
        }
    )

    result, error = parse_and_validate(raw, frozenset({"E1"}))

    assert result is None
    assert "v5_spike.answer.v0" in error
    assert "m35.agent_bridge_query.v0" in error


def test_acp_query_adapter_ignores_preexisting_collected_chunks():
    """A reused connection with prior agent_message_chunk output cannot contaminate result."""
    from tools.agent_bridge.acp_query import QUERY_SCHEMA_VERSION, acp_query_adapter
    from tools.agent_bridge.config import BrainConfig

    cfg = BrainConfig(
        mode="host_agent",
        endpoint=None,
        transport="acp",
        api_key=None,
        model=None,
        data_exposure_ack=True,
    )

    prior_text = "PRIOR OUTPUT THAT SHOULD BE IGNORED"
    valid_response = json.dumps(
        {
            "schema_version": "m35.agent_bridge_query.v0",
            "status": "GROUNDED",
            "answer": "Grounded answer from current query.",
            "insights": [{"text": "Insight", "evidence_refs": ["E1"]}],
            "evidence_refs": ["E1"],
            "gap": None,
            "provenance": {
                "transport": "acp",
                "model": "fake",
                "runtime": "fake",
                "degraded": False,
            },
            "usage": {"input_tokens": 10, "output_tokens": 10},
        },
        ensure_ascii=False,
    )

    class FakeConnection:
        session_id = "warm-session"
        collected = [
            {
                "jsonrpc": "2.0",
                "method": "session/update",
                "params": {
                    "sessionId": "warm-session",
                    "update": {
                        "content": {"text": prior_text, "type": "text"},
                        "sessionUpdate": "agent_message_chunk",
                    },
                },
            }
        ]

        def rpc(self, method: str, params: dict | None = None) -> dict:
            self.collected.append(
                {
                    "jsonrpc": "2.0",
                    "method": "session/update",
                    "params": {
                        "sessionId": "warm-session",
                        "update": {
                            "content": {"text": valid_response, "type": "text"},
                            "sessionUpdate": "agent_message_chunk",
                        },
                    },
                }
            )
            return {"jsonrpc": "2.0", "id": 1, "result": {"status": "ok"}}

    scaffold = {
        "evidence_pack": {
            "items": [{"document": {"doc_id": "journal-001"}, "snippet": "Evidence one."}]
        }
    }

    result = acp_query_adapter("warm connection test", scaffold, cfg, connection=FakeConnection())

    assert result["schema_version"] == QUERY_SCHEMA_VERSION
    assert result["status"] == "GROUNDED"
    assert prior_text not in result["answer"]
    assert result["evidence_refs"] == ["journal-001"]


# ─── Lead-review: provenance and usage contract tests ─────────────────


def test_acp_query_adapter_provenance_uses_acp_metadata():
    """Provenance uses runtime from initialize serverInfo and model from session/new."""
    from tools.agent_bridge.acp_query import QUERY_SCHEMA_VERSION, acp_query_adapter
    from tools.agent_bridge.config import BrainConfig

    fake_agent = sys.executable
    fake_script = str(FIXTURE_PATH / "fake_acp_agent_query.py")

    cfg = BrainConfig(
        mode="host_agent",
        endpoint=None,
        transport="acp",
        api_key=None,
        model="cfg-fallback-model",
        data_exposure_ack=True,
        acp_command=[fake_agent, fake_script],
        acp_workdir=str(FIXTURE_PATH),
    )

    scaffold = {
        "evidence_pack": {
            "items": [
                {"document": {"doc_id": "real-entry-1"}, "snippet": "Evidence snippet one."},
            ],
        },
    }

    result = acp_query_adapter("VALID_JSON_TEST query", scaffold, cfg)

    assert result["schema_version"] == QUERY_SCHEMA_VERSION
    assert result["status"] == "GROUNDED"
    assert result["provenance"]["runtime"] == "fake-acp"
    assert result["provenance"]["model"] == "fake-model"
    assert result["provenance"]["degraded"] is False


def test_acp_query_adapter_usage_from_rpc_result():
    """Final envelope usage comes from the ACP session/prompt RPC result, not model JSON."""
    from tools.agent_bridge.acp_query import QUERY_SCHEMA_VERSION, acp_query_adapter
    from tools.agent_bridge.config import BrainConfig

    fake_agent = sys.executable
    fake_script = str(FIXTURE_PATH / "fake_acp_agent_query.py")

    cfg = BrainConfig(
        mode="host_agent",
        endpoint=None,
        transport="acp",
        api_key=None,
        model=None,
        data_exposure_ack=True,
        acp_command=[fake_agent, fake_script],
        acp_workdir=str(FIXTURE_PATH),
    )

    scaffold = {
        "evidence_pack": {
            "items": [
                {"document": {"doc_id": "real-entry-1"}, "snippet": "Evidence snippet one."},
            ],
        },
    }

    result = acp_query_adapter("USAGE_TEST query", scaffold, cfg)

    assert result["schema_version"] == QUERY_SCHEMA_VERSION
    assert result["status"] == "GROUNDED"
    # Model JSON invented 9999 tokens; RPC usage must win.
    assert result["usage"] == {"input_tokens": 7, "output_tokens": 13}


def test_acp_query_adapter_usage_overrides_invalid_model_usage():
    """Invalid model-generated usage is replaced by valid RPC usage without breaking answer."""
    from tools.agent_bridge.acp_query import QUERY_SCHEMA_VERSION, acp_query_adapter
    from tools.agent_bridge.config import BrainConfig

    fake_agent = sys.executable
    fake_script = str(FIXTURE_PATH / "fake_acp_agent_query.py")

    cfg = BrainConfig(
        mode="host_agent",
        endpoint=None,
        transport="acp",
        api_key=None,
        model=None,
        data_exposure_ack=True,
        acp_command=[fake_agent, fake_script],
        acp_workdir=str(FIXTURE_PATH),
    )

    scaffold = {
        "evidence_pack": {
            "items": [
                {"document": {"doc_id": "real-entry-1"}, "snippet": "Evidence snippet one."},
            ],
        },
    }

    result = acp_query_adapter("INVALID_USAGE_TEST query", scaffold, cfg)

    assert result["schema_version"] == QUERY_SCHEMA_VERSION
    assert result["status"] == "GROUNDED"
    assert result["answer"] is not None
    assert result["usage"] == {"input_tokens": 7, "output_tokens": 13}


def test_acp_query_adapter_usage_null_when_rpc_omits_usage():
    """When the RPC result omits usage, the final envelope usage is None."""
    from tools.agent_bridge.acp_query import QUERY_SCHEMA_VERSION, acp_query_adapter
    from tools.agent_bridge.config import BrainConfig

    fake_agent = sys.executable
    fake_script = str(FIXTURE_PATH / "fake_acp_agent_query.py")

    cfg = BrainConfig(
        mode="host_agent",
        endpoint=None,
        transport="acp",
        api_key=None,
        model=None,
        data_exposure_ack=True,
        acp_command=[fake_agent, fake_script],
        acp_workdir=str(FIXTURE_PATH),
    )

    scaffold = {
        "evidence_pack": {
            "items": [
                {"document": {"doc_id": "real-entry-1"}, "snippet": "Evidence snippet one."},
            ],
        },
    }

    result = acp_query_adapter("NO_RPC_USAGE_TEST query", scaffold, cfg)

    assert result["schema_version"] == QUERY_SCHEMA_VERSION
    assert result["status"] == "GROUNDED"
    assert result["usage"] is None


def test_acp_query_adapter_retry_uses_rpc_usage():
    """Retry success also sets usage from the second session/prompt RPC result."""
    from tools.agent_bridge.acp_query import QUERY_SCHEMA_VERSION, acp_query_adapter
    from tools.agent_bridge.config import BrainConfig

    fake_agent = sys.executable
    fake_script = str(FIXTURE_PATH / "fake_acp_agent_query.py")

    cfg = BrainConfig(
        mode="host_agent",
        endpoint=None,
        transport="acp",
        api_key=None,
        model=None,
        data_exposure_ack=True,
        acp_command=[fake_agent, fake_script],
        acp_workdir=str(FIXTURE_PATH),
    )

    scaffold = {
        "evidence_pack": {
            "items": [
                {"document": {"doc_id": "real-entry-1"}, "snippet": "Evidence snippet one."},
                {"document": {"doc_id": "real-entry-2"}, "snippet": "Evidence snippet two."},
            ],
        },
    }

    # TWO_TURN_TEST fails first turn, succeeds on repair. Both RPC responses
    # include authoritative usage metadata, so the final envelope must too.
    result = acp_query_adapter("TWO_TURN_TEST query", scaffold, cfg)

    assert result["schema_version"] == QUERY_SCHEMA_VERSION
    assert result["status"] == "GROUNDED"
    assert result["usage"] == {"input_tokens": 7, "output_tokens": 13}
