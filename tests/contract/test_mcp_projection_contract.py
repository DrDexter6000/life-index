"""Contract tests for the removable generic MCP projection."""

from __future__ import annotations

import ast
import asyncio
from dataclasses import fields
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PROJECTION_ROOT = REPO_ROOT / "tools" / "mcp_projection"


def _tool_map(server: Any) -> dict[str, Any]:
    return {tool.name: tool for tool in asyncio.run(server.list_tools())}


def test_projection_exposes_only_registry_tools_with_registry_owned_metadata() -> None:
    from tools.host_agent_channel.registry import CAPABILITY_REGISTRY, projection_annotations
    from tools.mcp_projection.server import create_mcp_server

    server = create_mcp_server()
    tools = _tool_map(server)

    assert set(tools) == set(CAPABILITY_REGISTRY)
    for method_id, capability in CAPABILITY_REGISTRY.items():
        tool = tools[method_id]
        assert tool.description == capability.description
        assert tool.annotations is not None
        assert tool.annotations.model_dump(exclude_none=True) == projection_annotations(capability)
        properties = tool.inputSchema.get("properties", {})
        expected_fields = {field.name: field for field in fields(capability.params_type)}
        assert set(properties) == set(expected_fields)
        for name, definition in expected_fields.items():
            assert properties[name]["description"] == definition.metadata["description"]

    search = CAPABILITY_REGISTRY["search"]
    assert tools["search"].description == search.description
    assert "may refresh only rebuildable `.index` derived state" in search.description


def test_projection_has_no_resources_or_prompts() -> None:
    from tools.mcp_projection.server import create_mcp_server

    server = create_mcp_server()

    assert asyncio.run(server.list_resources()) == []
    assert asyncio.run(server.list_prompts()) == []


def test_mcp_tool_calls_map_to_the_transport_neutral_dispatcher(monkeypatch) -> None:
    import tools.mcp_projection.server as projection

    calls: list[tuple[str, dict[str, Any]]] = []

    def fake_dispatch(method_id: str, params: dict[str, Any]) -> dict[str, Any]:
        calls.append((method_id, params))
        return {"success": True, "method": method_id, "params": params}

    monkeypatch.setattr(projection, "dispatch", fake_dispatch)
    server = projection.create_mcp_server()

    result = asyncio.run(server.call_tool("journal.get", {"id": "Journals/2026/05/x.md"}))

    assert calls == [("journal.get", {"id": "Journals/2026/05/x.md"})]
    assert result


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
