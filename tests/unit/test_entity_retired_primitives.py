"""Successor tests for removed top-level Entity Graph primitives."""

from __future__ import annotations

import json
import ast
from pathlib import Path

import pytest

from tools.lib.entity_graph import save_entity_graph


def _write_graph(data_dir: Path) -> None:
    save_entity_graph(
        [
            {
                "id": "person-alice",
                "type": "actor",
                "primary_name": "Alice",
                "aliases": [],
                "relationships": [],
            },
            {
                "id": "person-bob",
                "type": "actor",
                "primary_name": "Bob",
                "aliases": [],
                "relationships": [],
            },
        ],
        data_dir / "entity_graph.yaml",
    )


@pytest.mark.parametrize(
    ("argv", "retired_flag", "replacement"),
    [
        (
            ["--seed"],
            "--seed",
            "life-index entity build --from-journals --preview --json",
        ),
        (
            ["--update", "--id", "person-alice", "--add-alias", "A."],
            "--update",
            "life-index entity --add-alias ALIAS --id ENTITY_ID",
        ),
        (
            ["--merge", "person-bob", "--id", "person-bob", "--target-id", "person-alice"],
            "--merge",
            "life-index entity --review --action preview",
        ),
        (
            ["--delete", "--id", "person-bob"],
            "--delete",
            "life-index entity maintain --delete --id ENTITY_ID --preview --json",
        ),
    ],
)
def test_retired_top_level_primitives_return_structured_replacement_error(
    isolated_data_dir: Path,
    capsys: pytest.CaptureFixture[str],
    argv: list[str],
    retired_flag: str,
    replacement: str,
) -> None:
    from tools.entity.__main__ import main

    _write_graph(isolated_data_dir)

    with pytest.raises(SystemExit) as exc:
        main(argv)

    assert exc.value.code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["success"] is False
    assert payload["data"]["retired_flag"] == retired_flag
    assert payload["data"]["replacement_command"] == replacement
    assert payload["error"]["code"] == "ENTITY_PRIMITIVE_REMOVED"
    assert "unrecognized" not in payload["error"]["message"].lower()


def test_seed_write_function_is_removed_but_preview_plan_remains() -> None:
    """Cold-start writes must go through build/batch/review, not legacy seed writes."""
    seed_py = Path(__file__).resolve().parents[2] / "tools" / "entity" / "seed.py"
    module = ast.parse(seed_py.read_text(encoding="utf-8"))
    function_names = {node.name for node in ast.walk(module) if isinstance(node, ast.FunctionDef)}

    assert "seed_entity_graph" not in function_names
    assert "preview_seed_entity_graph" in function_names
