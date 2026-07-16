"""Contract tests for the removable generic MCP projection."""

from __future__ import annotations

import ast
import asyncio
from dataclasses import fields
from hashlib import sha256
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PROJECTION_ROOT = REPO_ROOT / "tools" / "mcp_projection"
MCP_SDK_VERSION = "1.27.2"


@pytest.fixture
def optional_mcp_sdk() -> None:
    """Skip only the runtime projection checks without the pinned optional SDK."""
    try:
        installed_version = version("mcp")
    except PackageNotFoundError:
        pytest.skip(f"requires optional mcp=={MCP_SDK_VERSION}")
    if installed_version != MCP_SDK_VERSION:
        pytest.skip(f"requires optional mcp=={MCP_SDK_VERSION}; found mcp=={installed_version}")


def _tool_map(server: Any) -> dict[str, Any]:
    return {tool.name: tool for tool in asyncio.run(server.list_tools())}


def _seed_journal(data_dir: Path) -> str:
    journal_path = data_dir / "Journals" / "2026" / "05" / "life-index_2026-05-28_001.md"
    journal_path.parent.mkdir(parents=True, exist_ok=True)
    journal_path.write_text(
        "---\n"
        'title: "bounded projection entry"\n'
        "date: 2026-05-28\n"
        'topic: ["work"]\n'
        "---\n"
        "needle is present in this journal.\n",
        encoding="utf-8",
    )
    return journal_path.relative_to(data_dir).as_posix()


def _snapshot(root: Path) -> dict[str, str]:
    snapshot: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        snapshot[f"{relative}/" if path.is_dir() else relative] = (
            "directory" if path.is_dir() else sha256(path.read_bytes()).hexdigest()
        )
    return snapshot


def _non_index_snapshot(snapshot: dict[str, str]) -> dict[str, str]:
    return {
        path: value
        for path, value in snapshot.items()
        if path != ".index/" and not path.startswith(".index/")
    }


@pytest.mark.usefixtures("optional_mcp_sdk")
def test_projection_exposes_only_registry_tools_with_registry_owned_metadata() -> None:
    from tools.host_agent_channel.registry import CAPABILITY_REGISTRY, projection_annotations
    from tools.mcp_projection.server import create_mcp_server

    server = create_mcp_server()
    tools = _tool_map(server)

    expected_annotations = {
        "health": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": CAPABILITY_REGISTRY["health"].idempotent,
            "openWorldHint": False,
        },
        "journal.get": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": CAPABILITY_REGISTRY["journal.get"].idempotent,
            "openWorldHint": False,
        },
        "search": {
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": CAPABILITY_REGISTRY["search"].idempotent,
            "openWorldHint": False,
        },
    }

    assert set(tools) == {"health", "journal.get", "search"}
    for method_id, capability in CAPABILITY_REGISTRY.items():
        tool = tools[method_id]
        assert tool.description == capability.description
        assert tool.annotations is not None
        assert tool.annotations.model_dump(exclude_none=True) == expected_annotations[method_id]
        assert projection_annotations(capability) == expected_annotations[method_id]
        properties = tool.inputSchema.get("properties", {})
        expected_fields = {field.name: field for field in fields(capability.params_type)}
        assert set(properties) == set(expected_fields)
        for name, definition in expected_fields.items():
            assert properties[name]["description"] == definition.metadata["description"]

    search = CAPABILITY_REGISTRY["search"]
    assert tools["search"].description == search.description
    assert "may refresh only rebuildable `.index` derived state" in search.description


@pytest.mark.usefixtures("optional_mcp_sdk")
def test_mcp_read_tools_never_create_or_append_validation_trace(
    isolated_data_dir: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tools.mcp_projection.server import create_mcp_server

    journal_path = _seed_journal(isolated_data_dir)
    before = _snapshot(isolated_data_dir)
    trace_path = tmp_path / "external-trace" / "tool-calls.jsonl"
    monkeypatch.setenv("LIFE_INDEX_VALIDATION_MODE", "1")
    monkeypatch.setenv("LIFE_INDEX_TOOL_CALL_LOG", str(trace_path))
    server = create_mcp_server()

    assert asyncio.run(server.call_tool("health", {}))
    assert _snapshot(isolated_data_dir) == before
    assert not trace_path.exists(), "MCP health must not create an external dispatcher trace."

    trace_path.parent.mkdir()
    trace_before = b"pre-existing direct validation evidence\n"
    trace_path.write_bytes(trace_before)

    assert asyncio.run(server.call_tool("journal.get", {"path": journal_path}))
    assert _snapshot(isolated_data_dir) == before
    assert trace_path.read_bytes() == trace_before


@pytest.mark.usefixtures("optional_mcp_sdk")
def test_mcp_search_can_refresh_only_index_and_never_validation_trace(
    isolated_data_dir: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tools.mcp_projection.server import create_mcp_server

    _seed_journal(isolated_data_dir)
    trace_path = tmp_path / "external-trace" / "tool-calls.jsonl"
    trace_path.parent.mkdir()
    trace_before = b"pre-existing direct validation evidence\n"
    trace_path.write_bytes(trace_before)
    monkeypatch.setenv("LIFE_INDEX_VALIDATION_MODE", "1")
    monkeypatch.setenv("LIFE_INDEX_TOOL_CALL_LOG", str(trace_path))
    before = _snapshot(isolated_data_dir)

    server = create_mcp_server()
    assert asyncio.run(server.call_tool("search", {"query": "needle"}))

    after = _snapshot(isolated_data_dir)
    assert _non_index_snapshot(after) == _non_index_snapshot(before)
    changed_paths = {
        path for path in set(before) | set(after) if before.get(path) != after.get(path)
    }
    assert changed_paths
    assert all(path == ".index/" or path.startswith(".index/") for path in changed_paths)
    assert trace_path.read_bytes() == trace_before


@pytest.mark.usefixtures("optional_mcp_sdk")
def test_projection_has_no_resources_or_prompts() -> None:
    from tools.mcp_projection.server import create_mcp_server

    server = create_mcp_server()

    assert asyncio.run(server.list_resources()) == []
    assert asyncio.run(server.list_prompts()) == []


@pytest.mark.usefixtures("optional_mcp_sdk")
def test_mcp_tool_calls_map_to_the_transport_neutral_dispatcher(monkeypatch) -> None:
    import tools.mcp_projection.server as projection

    calls: list[tuple[str, dict[str, Any], bool]] = []

    def fake_dispatch(
        method_id: str,
        params: dict[str, Any],
        *,
        emit_validation_trace: bool = True,
    ) -> dict[str, Any]:
        calls.append((method_id, params, emit_validation_trace))
        return {"success": True, "method": method_id, "params": params}

    monkeypatch.setattr(projection, "dispatch", fake_dispatch)
    server = projection.create_mcp_server()

    result = asyncio.run(server.call_tool("journal.get", {"id": "Journals/2026/05/x.md"}))

    assert calls == [("journal.get", {"id": "Journals/2026/05/x.md"}, False)]
    assert result


@pytest.mark.usefixtures("optional_mcp_sdk")
def test_projection_rejects_a_forbidden_tool_before_dispatch(monkeypatch) -> None:
    import tools.mcp_projection.server as projection

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("forbidden MCP tool reached dispatcher")

    monkeypatch.setattr(projection, "dispatch", fail_if_called)
    server = projection.create_mcp_server()

    with pytest.raises(Exception, match="Unknown tool"):
        asyncio.run(server.call_tool("write", {"title": "must not run"}))


def test_projection_source_has_no_broad_discovery_or_d5_transport() -> None:
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(PROJECTION_ROOT.rglob("*.py"))
    )

    for forbidden in (
        "mcp_discovery",
        "capabilities.json",
        "list_capabilities",
        "jsonrpc",
        "stdin.readline",
        "subprocess",
        "shell",
        "provider",
        "LLM",
        "Codex",
    ):
        assert forbidden not in source
    assert 'transport="stdio"' in source


def test_projection_does_not_import_mcp_until_a_projection_entrypoint_runs() -> None:
    source = (PROJECTION_ROOT / "server.py").read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(PROJECTION_ROOT / "server.py"))

    top_level_imports = [
        node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))
    ]

    assert all(
        not (
            isinstance(node, ast.ImportFrom)
            and node.module is not None
            and node.module.startswith("mcp")
        )
        for node in top_level_imports
    )
