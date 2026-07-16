"""Public documentation contracts for the optional Host Agent projection."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_public_docs_describe_the_closed_generic_projection() -> None:
    api = (REPO_ROOT / "docs" / "API.md").read_text(encoding="utf-8")
    architecture = (REPO_ROOT / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
    skill = (REPO_ROOT / "SKILL.md").read_text(encoding="utf-8")

    for method_id in ("health", "journal.get", "search"):
        assert method_id in api
        assert method_id in architecture
    assert "CAPABILITY_REGISTRY" in api
    assert "mcp==1.27.2" in api
    assert "python -m tools.mcp_projection" in api
    assert "generic, removable" in api
    assert "only `.index`" in api
    assert "validation-only tool-call trace" in api
    assert "resolves into or overlaps the\ndata directory" in api
    assert "Codex is the first consumer" in skill
    assert "not yet implemented" not in skill
    assert "tools.mcp_projection" in architecture
    assert "CAPABILITY_REGISTRY" in architecture
    assert "No D5 hand-written newline JSON-RPC server" in architecture
