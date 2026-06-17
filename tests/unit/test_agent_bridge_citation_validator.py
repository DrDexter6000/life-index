from __future__ import annotations

from pathlib import Path


def _write_journal(data_dir: Path, rel_path: str, body: str = "body") -> None:
    path = data_dir / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n" "title: Test entry\n" "date: 2026-06-10\n" "---\n\n" f"{body}\n",
        encoding="utf-8",
    )


def test_citation_gate_allows_existing_journal_id(tmp_path, monkeypatch):
    from tools.agent_bridge.citation_validator import validate_citation_gate

    rel_path = "Journals/2026/06/life-index_2026-06-10_001.md"
    _write_journal(tmp_path, rel_path, "grounded content")
    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(tmp_path))

    envelope = {
        "status": "GROUNDED",
        "answer": f"Grounded claim [{rel_path}].",
        "insights": [{"text": "Insight", "evidence_refs": [rel_path]}],
        "evidence_refs": [rel_path],
    }

    result = validate_citation_gate(envelope)

    assert result.ok is True
    assert result.error is None
    assert result.evidence_refs == [rel_path]


def test_citation_gate_rejects_nonexistent_journal_id(tmp_path, monkeypatch):
    from tools.agent_bridge.citation_validator import validate_citation_gate

    rel_path = "Journals/2026/06/missing.md"
    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(tmp_path))

    envelope = {
        "status": "GROUNDED",
        "answer": f"Grounded claim [{rel_path}].",
        "insights": [{"text": "Insight", "evidence_refs": [rel_path]}],
        "evidence_refs": [rel_path],
    }

    result = validate_citation_gate(envelope)

    assert result.ok is False
    assert result.error is not None
    assert "does not exist" in result.error


def test_citation_gate_rejects_zero_citation_grounded(tmp_path, monkeypatch):
    from tools.agent_bridge.citation_validator import validate_citation_gate

    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(tmp_path))
    envelope = {
        "status": "GROUNDED",
        "answer": "Grounded-looking claim.",
        "insights": [],
        "evidence_refs": [],
    }

    result = validate_citation_gate(envelope)

    assert result.ok is False
    assert result.error is not None
    assert "requires at least one" in result.error


def test_citation_gate_rejects_unreferenced_aggregate_claim(tmp_path, monkeypatch):
    from tools.agent_bridge.citation_validator import validate_citation_gate

    rel_path = "Journals/2026/06/life-index_2026-06-10_001.md"
    _write_journal(tmp_path, rel_path)
    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(tmp_path))
    envelope = {
        "status": "GROUNDED",
        "answer": f"One cited claim [{rel_path}]. A second aggregate claim has no citation.",
        "insights": [{"text": "Insight", "evidence_refs": [rel_path]}],
        "evidence_refs": [rel_path],
    }

    result = validate_citation_gate(envelope)

    assert result.ok is False
    assert result.error is not None
    assert "lacks an evidence id" in result.error


def test_citation_gate_rejects_trace_cross_check_mismatch(tmp_path, monkeypatch):
    from tools.agent_bridge.citation_validator import validate_citation_gate

    rel_path = "Journals/2026/06/life-index_2026-06-10_001.md"
    other_path = "Journals/2026/06/life-index_2026-06-11_001.md"
    _write_journal(tmp_path, rel_path)
    _write_journal(tmp_path, other_path)
    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(tmp_path))
    envelope = {
        "status": "GROUNDED",
        "answer": f"Trace-backed claim [{rel_path}].",
        "insights": [{"text": "Insight", "evidence_refs": [rel_path]}],
        "evidence_refs": [rel_path],
    }

    result = validate_citation_gate(envelope, tool_trace_refs=[other_path])

    assert result.ok is False
    assert result.error is not None
    assert "not observed" in result.error


def test_extract_trace_refs_ignores_wildcard_journal_paths():
    from tools.agent_bridge.citation_validator import extract_tool_trace_journal_refs

    messages = [
        {
            "params": {
                "update": {
                    "sessionUpdate": "tool_call",
                    "title": "terminal: ls Journals/2026/03/*.md",
                    "content": "read Journals/2026/03/life-index_2026-03-14_001.md",
                }
            }
        }
    ]

    refs = extract_tool_trace_journal_refs(messages)

    assert refs == ["Journals/2026/03/life-index_2026-03-14_001.md"]
