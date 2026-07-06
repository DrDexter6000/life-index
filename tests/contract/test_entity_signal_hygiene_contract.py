"""Contract tests for Entity Graph signal hygiene."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

from tools.lib.entity_graph import save_entity_graph


def _run_entity_cli(argv: list[str]) -> dict:
    from tools.entity.__main__ import main

    buffer = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = buffer
    try:
        try:
            main(argv)
        except SystemExit as exc:
            assert exc.code in (0, None)
    finally:
        sys.stdout = old_stdout
    return json.loads(buffer.getvalue())


def _capture_entity_help() -> str:
    from tools.entity.__main__ import main

    buffer = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = buffer
    try:
        try:
            main(["--help"])
        except SystemExit as exc:
            assert exc.code == 0
    finally:
        sys.stdout = old_stdout
    return buffer.getvalue()


def _write_minimal_graph(data_dir: Path) -> Path:
    graph_path = data_dir / "entity_graph.yaml"
    save_entity_graph(
        [
            {
                "id": "actor-alice",
                "type": "actor",
                "primary_name": "Alice",
                "attributes": {"kind": "human"},
                "source": "user",
                "status": "confirmed",
                "relationships": [],
            }
        ],
        graph_path,
    )
    return graph_path


def test_read_only_primitives_emit_workflow_hints(isolated_data_dir: Path) -> None:
    """Advanced read-only primitives should point agents back to the workflow gates."""
    _write_minimal_graph(isolated_data_dir)

    expected = {
        ("--check", "--json"): "life-index entity audit --json",
        ("--audit", "--json"): "life-index entity audit --json",
        ("--stats", "--json"): "life-index entity audit --json",
        ("--review", "--json"): "life-index entity audit --json",
    }

    for argv, preferred_command in expected.items():
        payload = _run_entity_cli(list(argv))
        hint = payload["workflow_hint"]
        assert hint["workflow"] in {"audit", "maintain"}
        assert hint["preferred_command"] == preferred_command
        assert "facade" in hint["reason"].lower() or "workflow" in hint["reason"].lower()


def test_audit_marks_zero_reference_entities_as_neutral_facts(
    isolated_data_dir: Path,
) -> None:
    """Zero journal references remain facts, not issues or action advice."""
    _write_minimal_graph(isolated_data_dir)
    journal_dir = isolated_data_dir / "Journals" / "2026" / "07"
    journal_dir.mkdir(parents=True)
    (journal_dir / "life-index_2026-07-01_001.md").write_text(
        "---\ntitle: Test\ndate: 2026-07-01\npeople: []\nentities: []\n---\n\nNo entity refs.\n",
        encoding="utf-8",
    )

    payload = _run_entity_cli(["--audit", "--json"])

    facts = payload["data"]["facts"]
    assert facts["zero_journal_reference_entities"] == ["actor-alice"]
    annotation = payload["data"]["fact_annotations"]["zero_journal_reference_entities"]
    assert annotation["classification"] == "neutral_fact"
    assert annotation["is_issue"] is False
    assert "not an issue" in annotation["message"].lower()
    serialized = json.dumps(payload, ensure_ascii=False).lower()
    assert "archive" not in serialized
    assert "delete" not in serialized


def test_entity_help_uses_single_workflow_vocabulary() -> None:
    """Help should lead with workflow gates and document JSON for all entry points."""
    help_text = _capture_entity_help()

    workflow_pos = help_text.index("Workflow gates")
    advanced_pos = help_text.index("Advanced primitives appendix")
    assert workflow_pos < advanced_pos
    assert "life-index entity build --from-journals --preview --json" in help_text
    assert "life-index entity profile --id ENTITY_ID --json" in help_text
    assert "life-index entity audit --json" in help_text
    assert "life-index entity maintain --normalize --preview --json" in help_text
    assert "--json" in help_text
    assert "Legacy" not in help_text


def test_skill_requires_health_first_for_entity_maintenance() -> None:
    """The host-agent playbook should start entity maintenance from health --json."""
    skill_text = Path("SKILL.md").read_text(encoding="utf-8")

    assert "life-index health --json" in skill_text
    assert "suggested_refresh_step" in skill_text
    assert "实体维护速查" in skill_text
    assert "life-index entity audit --json" in skill_text


def test_skill_links_operational_and_entity_maintenance_playbooks() -> None:
    """Agent-facing maintenance guidance should point to compact playbooks."""
    skill_text = Path("SKILL.md").read_text(encoding="utf-8")
    playbook_path = Path("references/ENTITY_MAINTENANCE_PLAYBOOK.md")

    assert "docs/AGENT_UPDATE_PLAYBOOK.md" in skill_text
    assert "references/ENTITY_MAINTENANCE_PLAYBOOK.md" in skill_text
    assert playbook_path.exists()

    playbook = playbook_path.read_text(encoding="utf-8")
    assert "life-index health --json" in playbook
    assert "life-index entity audit --json" in playbook
    assert "life-index entity --review" in playbook
    assert "life-index entity maintain --normalize --preview --json" in playbook
