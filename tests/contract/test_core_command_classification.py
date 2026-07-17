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
HELP_ALIASES = frozenset({"help", "-h", "--help"})
VERSION_ALIASES = frozenset({"version", "-V", "--version"})
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

CHARTER_CLASSIFICATION_RULES_POINTER = (
    "This table is the exhaustive current 31-route mapping under the Charter-owned\n"
    "C1–C7 and stable non-Core classification rules in `CHARTER.md §1.10`.\n"
    "It maps current routes only; it does not own or duplicate those stable rules."
)
OWNERSHIP_MAPPING_HEADING = "### Public command constitutional ownership/admission mapping"


def _main_function(source: str) -> ast.FunctionDef:
    tree = ast.parse(source)
    main_nodes = [
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "main"
    ]
    assert len(main_nodes) == 1, "tools.__main__ must define exactly one main function"
    return main_nodes[0]


def _literal_cmd_map_keys(source: str) -> frozenset[str]:
    main_node = _main_function(source)

    assignments = []
    for node in ast.walk(main_node):
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


def _literal_collection_values(node: ast.expr) -> frozenset[str]:
    if not isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return frozenset()
    values: list[str] = []
    for element in node.elts:
        if not isinstance(element, ast.Constant) or not isinstance(element.value, str):
            return frozenset()
        values.append(element.value)
    return frozenset(values)


def _positive_subcmd_literals(node: ast.AST) -> frozenset[str]:
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return frozenset()

    if isinstance(node, ast.Compare) and len(node.ops) == len(node.comparators) == 1:
        operator = node.ops[0]
        right = node.comparators[0]
        if isinstance(operator, ast.Eq):
            if (
                isinstance(node.left, ast.Name)
                and node.left.id == "subcmd"
                and isinstance(right, ast.Constant)
                and isinstance(right.value, str)
            ):
                return frozenset({right.value})
            if (
                isinstance(right, ast.Name)
                and right.id == "subcmd"
                and isinstance(node.left, ast.Constant)
                and isinstance(node.left.value, str)
            ):
                return frozenset({node.left.value})
        if isinstance(operator, ast.In) and isinstance(node.left, ast.Name):
            if node.left.id == "subcmd":
                return _literal_collection_values(right)
        return frozenset()

    literals: set[str] = set()
    for child in ast.iter_child_nodes(node):
        literals.update(_positive_subcmd_literals(child))
    return frozenset(literals)


def _is_handled_direct_branch(node: ast.If) -> bool:
    return any(
        not isinstance(statement, ast.Pass)
        and not (
            isinstance(statement, ast.Expr)
            and isinstance(statement.value, ast.Constant)
            and isinstance(statement.value.value, str)
        )
        for statement in node.body
    )


def _is_sys_argv_sequence(node: ast.AST) -> bool:
    if isinstance(node, ast.Subscript):
        node = node.value
    return (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "sys"
        and node.attr == "argv"
    )


def _is_known_help_argv_predicate(node: ast.AST) -> bool:
    if (
        not isinstance(node, ast.Call)
        or not isinstance(node.func, ast.Name)
        or node.func.id != "any"
        or len(node.args) != 1
        or node.keywords
        or not isinstance(node.args[0], ast.GeneratorExp)
    ):
        return False

    generator = node.args[0]
    if len(generator.generators) != 1:
        return False
    comprehension = generator.generators[0]
    if (
        comprehension.is_async
        or comprehension.ifs
        or not isinstance(comprehension.target, ast.Name)
        or not _is_sys_argv_sequence(comprehension.iter)
    ):
        return False

    predicate = generator.elt
    return (
        isinstance(predicate, ast.Compare)
        and len(predicate.ops) == len(predicate.comparators) == 1
        and isinstance(predicate.ops[0], ast.In)
        and isinstance(predicate.left, ast.Name)
        and predicate.left.id == comprehension.target.id
        and _literal_collection_values(predicate.comparators[0]) == HELP_ALIASES
    )


def _is_command_specific_help_guard(node: ast.If) -> bool:
    if not isinstance(node.test, ast.BoolOp) or not isinstance(node.test.op, ast.And):
        return False
    has_route_operand = any(_positive_subcmd_literals(operand) for operand in node.test.values)
    has_independent_help_operand = any(
        not _positive_subcmd_literals(operand) and _is_known_help_argv_predicate(operand)
        for operand in node.test.values
    )
    return has_route_operand and has_independent_help_operand


def _canonical_direct_route(value: str) -> str | None:
    if value in HELP_ALIASES:
        return None
    if value in VERSION_ALIASES:
        return "version"
    return value


def _literal_direct_route_keys(source: str) -> frozenset[str]:
    main_node = _main_function(source)
    routes: set[str] = set()
    for node in ast.walk(main_node):
        if (
            not isinstance(node, ast.If)
            or not _is_handled_direct_branch(node)
            or _is_command_specific_help_guard(node)
        ):
            continue
        for value in _positive_subcmd_literals(node.test):
            route = _canonical_direct_route(value)
            if route is not None:
                routes.add(route)
    return frozenset(routes)


def _public_routes(source: str) -> frozenset[str]:
    return _literal_cmd_map_keys(source) | _literal_direct_route_keys(source)


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
    assert OWNERSHIP_MAPPING_HEADING in block

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
    assert CHARTER_CLASSIFICATION_RULES_POINTER in block
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
        OWNERSHIP_MAPPING_HEADING,
        "",
        "| Command | Classification | Authority refs |",
        "|---|---|---|",
        *(
            f"| {command} | {classification} | {refs} |"
            for command, classification, refs in rendered_rows
        ),
        "",
        CHARTER_CLASSIFICATION_RULES_POINTER,
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
    source = CLI_ENTRYPOINT.read_text(encoding="utf-8")
    routes = _public_routes(source)
    direct_routes = routes - _literal_cmd_map_keys(source)
    assert direct_routes == {"health", "version"}
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


def test_validator_rejects_new_direct_dispatch_route_without_mapping() -> None:
    source = CLI_ENTRYPOINT.read_text(encoding="utf-8")
    anchor = "    # Map subcommands to __main__ module paths\n"
    mutated = source.replace(
        anchor,
        '    if subcmd == "future-direct":\n'
        '        print("future direct route")\n'
        "        return\n\n" + anchor,
        1,
    )
    assert mutated != source
    with pytest.raises(AssertionError, match="inventory mismatch"):
        _validate_public_command_classification(mutated, _render_future_architecture())


def test_validator_rejects_usage_named_direct_handler_without_mapping() -> None:
    source = CLI_ENTRYPOINT.read_text(encoding="utf-8")
    anchor = "    # Map subcommands to __main__ module paths\n"
    mutated = source.replace(
        anchor,
        '    if subcmd == "usage-report":\n'
        "        usage_report()\n"
        "        return\n\n" + anchor,
        1,
    )
    assert mutated != source
    with pytest.raises(AssertionError, match="inventory mismatch"):
        _validate_public_command_classification(mutated, _render_future_architecture())


@pytest.mark.parametrize(
    "condition",
    (
        '"future-left" == subcmd',
        'subcmd in ("future-tuple",)',
        'subcmd in ["future-list"]',
        'subcmd in {"future-set"}',
        'subcmd == "future-negative-help" and "--help" not in sys.argv[2:]',
    ),
)
def test_validator_rejects_supported_positive_direct_route_shapes(condition: str) -> None:
    source = CLI_ENTRYPOINT.read_text(encoding="utf-8")
    anchor = "    # Map subcommands to __main__ module paths\n"
    mutated = source.replace(
        anchor,
        f"    if {condition}:\n"
        '        print("future direct route")\n'
        "        return\n\n" + anchor,
        1,
    )
    assert mutated != source
    with pytest.raises(AssertionError, match="inventory mismatch"):
        _validate_public_command_classification(mutated, _render_future_architecture())


def test_validator_rejects_removed_direct_route_from_source() -> None:
    source = CLI_ENTRYPOINT.read_text(encoding="utf-8")
    handler = (
        "    # Handle health check directly (no submodule import needed)\n"
        '    if subcmd == "health":\n'
    )
    mutated = source.replace(
        handler,
        handler.replace('subcmd == "health"', 'subcmd != "health"'),
        1,
    )
    assert mutated != source
    with pytest.raises(AssertionError, match="inventory mismatch"):
        _validate_public_command_classification(mutated, _render_future_architecture())


def test_validator_accepts_normal_health_handler_without_help_guard() -> None:
    source = CLI_ENTRYPOINT.read_text(encoding="utf-8")
    help_guard = (
        '    if subcmd == "health" and any('
        'arg in ("--help", "-h", "help") for arg in sys.argv[2:]):\n'
        "        print_health_usage()\n"
        "        return\n\n"
    )
    mutated = source.replace(help_guard, "", 1)
    assert mutated != source
    _validate_public_command_classification(mutated, _render_future_architecture())


def test_validator_rejects_unknown_version_alias_as_new_route() -> None:
    source = CLI_ENTRYPOINT.read_text(encoding="utf-8")
    mutated = source.replace(
        'elif subcmd in ("-V", "version"):',
        'elif subcmd in ("-V", "version", "future-version-alias"):',
        1,
    )
    assert mutated != source
    with pytest.raises(AssertionError, match="inventory mismatch"):
        _validate_public_command_classification(mutated, _render_future_architecture())


def test_validator_rejects_unknown_help_alias_as_new_route() -> None:
    source = CLI_ENTRYPOINT.read_text(encoding="utf-8")
    mutated = source.replace(
        'elif subcmd in ("--help", "-h", "help"):',
        'elif subcmd in ("--help", "-h", "help", "future-help-alias"):',
        1,
    )
    assert mutated != source
    with pytest.raises(AssertionError, match="inventory mismatch"):
        _validate_public_command_classification(mutated, _render_future_architecture())


def test_direct_route_discovery_ignores_negative_help_and_string_only_mentions() -> None:
    source = CLI_ENTRYPOINT.read_text(encoding="utf-8")
    anchor = "    # Map subcommands to __main__ module paths\n"
    mutated = source.replace(
        '    """Unified CLI entry point"""',
        '    """Unified CLI entry point mentioning future-docstring only."""',
        1,
    )
    mutated = mutated.replace(
        anchor,
        '    if subcmd != "negative-eq":\n'
        "        pass\n"
        '    if subcmd not in ("negative-in",):\n'
        "        pass\n"
        '    if not (subcmd == "nested-negative"):\n'
        "        pass\n"
        '    if subcmd == "positive-pass-only":\n'
        "        pass\n\n" + anchor,
        1,
    )
    mutated = mutated.replace(
        'print("Usage: life-index <command> [options]")',
        'print("Usage: life-index <command> [options] future-print-only")',
        1,
    )
    assert mutated != source
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
