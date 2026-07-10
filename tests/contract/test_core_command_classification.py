"""D0 contracts for exhaustive public-command classification."""

from __future__ import annotations

import ast
import re
from collections.abc import Iterable
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CLI_ENTRYPOINT = REPO_ROOT / "tools" / "__main__.py"
ARCHITECTURE = REPO_ROOT / "docs" / "ARCHITECTURE.md"

BLOCK_NAME = "PUBLIC-COMMAND-CLASSIFICATION"
BLOCK_START = f"<!-- PLATFORM-SSOT:{BLOCK_NAME}:START -->"
BLOCK_END = f"<!-- PLATFORM-SSOT:{BLOCK_NAME}:END -->"
TABLE_HEADER = ("Command", "Classification", "Authority refs")

CORE = "Core"
HOST_OPERATIONS = "Non-Core — Distribution/Host Operations"
LEGACY_ADAPTER = "Legacy External Adapter"
DIRECT_PUBLIC_ROUTES = frozenset({"health", "version"})
CORE_DOMAIN_IDS = frozenset({f"C{number}" for number in range(1, 8)})

CORE_DOMAIN_NAMES = (
    "Canonical journal and attachment mutation",
    "Schema, validation, migration, transaction, locking, and audit",
    "Deterministic indexing, retrieval, freshness, and evidence navigation",
    "Deterministic aggregation and analysis",
    "Entity graph",
    "Integrity, health, backup, restore, and recovery",
    "Deterministic contract and eval verification",
)

EXPECTED_CORE_REFS = {
    "abstract": ("C3",),
    "aggregate": ("C4",),
    "analyze": ("C4",),
    "attachment": ("C3",),
    "backup": ("C6",),
    "confirm": ("C1", "C2"),
    "edit": ("C1", "C2"),
    "entity": ("C5",),
    "entity-graph-eval": ("C5", "C7"),
    "eval": ("C7",),
    "generate-index": ("C3",),
    "health": ("C6",),
    "import": ("C1", "C2"),
    "index": ("C3",),
    "index-tree": ("C3",),
    "journal": ("C3",),
    "maintenance": ("C2", "C6"),
    "migrate": ("C2",),
    "on-this-day": ("C3",),
    "recall": ("C3",),
    "search": ("C3",),
    "smart-search": ("C3",),
    "timeline": ("C3",),
    "trajectory": ("C4",),
    "verify": ("C6",),
    "write": ("C1", "C2"),
}
EXPECTED_HOST_OPERATIONS = frozenset({"bootstrap", "sync-skill", "upgrade", "version"})
EXPECTED_LEGACY_ADAPTERS = frozenset({"weather"})

OWNER_APPROVAL_RULE = (
    "Any new Core domain, non-Core category, or compatibility exception requires "
    "new Human Owner substantive approval."
)
WEATHER_EXCEPTION_RULE = (
    "The optional `weather` Legacy External Adapter is tracked by #166 and cannot "
    "decide canonical journal-write success."
)


def _literal_cmd_map_keys(source: str) -> frozenset[str]:
    tree = ast.parse(source)
    main_nodes = [
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "main"
    ]
    assert len(main_nodes) == 1, "tools.__main__ must define exactly one main function"

    assignments = []
    for node in ast.walk(main_nodes[0]):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if any(isinstance(target, ast.Name) and target.id == "cmd_map" for target in targets):
            assignments.append(node)

    assert len(assignments) == 1, "main must assign cmd_map exactly once"
    value = assignments[0].value
    assert isinstance(value, ast.Dict), "cmd_map must remain a literal dict"

    keys: list[str] = []
    for key in value.keys:
        assert isinstance(key, ast.Constant) and isinstance(
            key.value, str
        ), "cmd_map keys must be literal strings"
        keys.append(key.value)
    assert len(keys) == len(set(keys)), "cmd_map must not contain duplicate literal keys"
    return frozenset(keys)


def _public_routes(source: str) -> frozenset[str]:
    return _literal_cmd_map_keys(source) | DIRECT_PUBLIC_ROUTES


def _named_block(text: str) -> str:
    assert text.count(BLOCK_START) == 1, f"missing or duplicate {BLOCK_START}"
    assert text.count(BLOCK_END) == 1, f"missing or duplicate {BLOCK_END}"
    start = text.index(BLOCK_START) + len(BLOCK_START)
    end = text.index(BLOCK_END, start)
    return text[start:end]


def _table_rows(block: str) -> list[tuple[str, str, str]]:
    table_lines = [line.strip() for line in block.splitlines() if line.strip().startswith("|")]
    assert len(table_lines) >= 2, "classification block must contain a Markdown table"

    rows = [tuple(cell.strip() for cell in line[1:-1].split("|")) for line in table_lines]
    assert rows[0] == TABLE_HEADER, f"classification table header must be {TABLE_HEADER!r}"
    assert len(rows[1]) == 3 and all(
        cell and set(cell) <= {"-", ":"} for cell in rows[1]
    ), "classification table must have a three-column separator"
    data_rows = rows[2:]
    assert all(len(row) == 3 for row in data_rows), "every classification row needs 3 cells"
    return data_rows  # type: ignore[return-value]


def _split_core_refs(value: str) -> tuple[str, ...]:
    refs = tuple(part.strip() for part in value.split(",") if part.strip())
    unknown = set(refs) - CORE_DOMAIN_IDS
    assert refs and not unknown, f"unknown or empty Core authority refs: {sorted(unknown)}"
    return refs


def _validate_public_command_classification(source: str, architecture: str) -> None:
    routes = _public_routes(source)
    block = _named_block(architecture)
    rows = _table_rows(block)

    commands = [row[0] for row in rows]
    duplicates = sorted({command for command in commands if commands.count(command) > 1})
    assert not duplicates, f"duplicate command classification rows: {duplicates}"
    assert set(commands) == routes, (
        f"classification inventory mismatch; missing={sorted(routes - set(commands))}, "
        f"extra={sorted(set(commands) - routes)}"
    )

    by_command = {command: (classification, refs) for command, classification, refs in rows}
    allowed_classifications = {CORE, HOST_OPERATIONS, LEGACY_ADAPTER}
    actual_classifications = {classification for classification, _ in by_command.values()}
    assert actual_classifications <= allowed_classifications, (
        "unratified classification categories: "
        f"{sorted(actual_classifications - allowed_classifications)}"
    )

    core_commands = {
        command for command, (classification, _) in by_command.items() if classification == CORE
    }
    host_commands = {
        command
        for command, (classification, _) in by_command.items()
        if classification == HOST_OPERATIONS
    }
    legacy_commands = {
        command
        for command, (classification, _) in by_command.items()
        if classification == LEGACY_ADAPTER
    }
    assert core_commands == set(EXPECTED_CORE_REFS), "Core command membership drift"
    assert host_commands == EXPECTED_HOST_OPERATIONS, "host-operations membership drift"
    assert legacy_commands == EXPECTED_LEGACY_ADAPTERS, "legacy-adapter membership drift"

    for command, expected_refs in EXPECTED_CORE_REFS.items():
        actual_refs = _split_core_refs(by_command[command][1])
        assert actual_refs == expected_refs, f"Core authority refs drift for {command}"
    for command in EXPECTED_HOST_OPERATIONS:
        assert by_command[command][1] == "Distribution/Host Operations"
    assert by_command["weather"][1] == "#166"

    duplicated_domains = [name for name in CORE_DOMAIN_NAMES if name in architecture]
    assert not duplicated_domains, (
        "docs/ARCHITECTURE.md must reference C1–C7 without duplicating Charter domain "
        f"descriptions: {duplicated_domains}"
    )
    assert WEATHER_EXCEPTION_RULE in block
    assert OWNER_APPROVAL_RULE in block
    assert not re.search(
        r"(?i)non-core[^\n]*(?:bypass|waive|without)[^\n]*human owner",
        block,
    ), "non-Core classifications cannot bypass Human Owner approval"


def _expected_rows() -> list[tuple[str, str, str]]:
    rows = [(command, CORE, ", ".join(refs)) for command, refs in EXPECTED_CORE_REFS.items()]
    rows.extend(
        (command, HOST_OPERATIONS, "Distribution/Host Operations")
        for command in EXPECTED_HOST_OPERATIONS
    )
    rows.append(("weather", LEGACY_ADAPTER, "#166"))
    return sorted(rows)


def _render_future_architecture(
    rows: Iterable[tuple[str, str, str]] | None = None,
    extra_lines: Iterable[str] = (),
) -> str:
    rendered_rows = rows if rows is not None else _expected_rows()
    lines = [
        BLOCK_START,
        "### Public command classification",
        "",
        "| Command | Classification | Authority refs |",
        "|---|---|---|",
        *(
            f"| {command} | {classification} | {refs} |"
            for command, classification, refs in rendered_rows
        ),
        "",
        WEATHER_EXCEPTION_RULE,
        OWNER_APPROVAL_RULE,
        *extra_lines,
        BLOCK_END,
    ]
    return "\n".join(lines)


def _replace_row(
    rows: list[tuple[str, str, str]],
    command: str,
    replacement: tuple[str, str, str],
) -> list[tuple[str, str, str]]:
    return [replacement if row[0] == command else row for row in rows]


def test_ast_public_route_inventory_is_exactly_31_capabilities() -> None:
    routes = _public_routes(CLI_ENTRYPOINT.read_text(encoding="utf-8"))
    assert routes == set(EXPECTED_CORE_REFS) | EXPECTED_HOST_OPERATIONS | EXPECTED_LEGACY_ADAPTERS
    assert len(routes) == 31
    assert {"--version", "-V"}.isdisjoint(routes)


def test_architecture_classification_closes_over_ast_public_routes() -> None:
    _validate_public_command_classification(
        CLI_ENTRYPOINT.read_text(encoding="utf-8"),
        ARCHITECTURE.read_text(encoding="utf-8"),
    )


def test_validator_rejects_new_cmd_map_command_without_mapping() -> None:
    source = CLI_ENTRYPOINT.read_text(encoding="utf-8")
    anchor = "    cmd_map = {\n"
    mutated = source.replace(
        anchor,
        anchor + '        "future-command": "tools.future.__main__",\n',
        1,
    )
    assert mutated != source
    with pytest.raises(AssertionError, match="inventory mismatch"):
        _validate_public_command_classification(mutated, _render_future_architecture())


def test_validator_rejects_missing_direct_route_row() -> None:
    rows = [row for row in _expected_rows() if row[0] != "health"]
    with pytest.raises(AssertionError, match="inventory mismatch"):
        _validate_public_command_classification(
            CLI_ENTRYPOINT.read_text(encoding="utf-8"), _render_future_architecture(rows)
        )


def test_validator_rejects_duplicate_command_row() -> None:
    rows = _expected_rows()
    rows.append(next(row for row in rows if row[0] == "search"))
    with pytest.raises(AssertionError, match="duplicate command"):
        _validate_public_command_classification(
            CLI_ENTRYPOINT.read_text(encoding="utf-8"), _render_future_architecture(rows)
        )


def test_validator_rejects_unknown_core_domain_id() -> None:
    rows = _replace_row(_expected_rows(), "search", ("search", CORE, "C8"))
    with pytest.raises(AssertionError, match="unknown or empty Core authority refs"):
        _validate_public_command_classification(
            CLI_ENTRYPOINT.read_text(encoding="utf-8"), _render_future_architecture(rows)
        )


def test_validator_rejects_weather_reclassified_as_core() -> None:
    rows = _replace_row(_expected_rows(), "weather", ("weather", CORE, "C3"))
    with pytest.raises(AssertionError, match="Core command membership drift"):
        _validate_public_command_classification(
            CLI_ENTRYPOINT.read_text(encoding="utf-8"), _render_future_architecture(rows)
        )


def test_validator_rejects_second_legacy_external_adapter() -> None:
    rows = _replace_row(_expected_rows(), "search", ("search", LEGACY_ADAPTER, "compatibility"))
    with pytest.raises(AssertionError, match="Core command membership drift|legacy-adapter"):
        _validate_public_command_classification(
            CLI_ENTRYPOINT.read_text(encoding="utf-8"), _render_future_architecture(rows)
        )


def test_validator_rejects_unratified_non_core_category() -> None:
    rows = _replace_row(
        _expected_rows(),
        "bootstrap",
        ("bootstrap", "Non-Core — Plugin Operations", "Plugin Operations"),
    )
    with pytest.raises(AssertionError, match="unratified classification categories"):
        _validate_public_command_classification(
            CLI_ENTRYPOINT.read_text(encoding="utf-8"), _render_future_architecture(rows)
        )


def test_validator_rejects_lower_level_domain_description_duplication() -> None:
    architecture = _render_future_architecture(extra_lines=(CORE_DOMAIN_NAMES[0],))
    with pytest.raises(AssertionError, match="without duplicating Charter domain descriptions"):
        _validate_public_command_classification(
            CLI_ENTRYPOINT.read_text(encoding="utf-8"), architecture
        )


def test_validator_rejects_non_core_owner_approval_waiver() -> None:
    architecture = _render_future_architecture(
        extra_lines=("Non-Core classifications may bypass Human Owner substantive approval.",)
    )
    with pytest.raises(AssertionError, match="cannot bypass Human Owner approval"):
        _validate_public_command_classification(
            CLI_ENTRYPOINT.read_text(encoding="utf-8"), architecture
        )
