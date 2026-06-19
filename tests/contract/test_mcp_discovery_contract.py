"""Contract tests for the MCP discovery stub (RFC-2026-05-25).

These tests verify that the minimal MCP discovery skeleton:
1. Imports successfully
2. Exposes list_capabilities, describe_tool, invoke_tool
3. Contains no forbidden imports (LLM providers, direct data access,
   dynamic discovery mechanisms)
4. Returns correct shapes from the static capabilities manifest

This is a discovery-only stub; invoke_tool raises NotImplementedError.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MCP_ROOT = REPO_ROOT / "tools" / "mcp_discovery"


# Import and function existence


class TestModuleImports:
    """The mcp_discovery module must be importable and expose the three meta-tools."""

    def test_import_succeeds(self):
        import tools.mcp_discovery  # noqa: F401

    def test_server_module_imports(self):
        from tools.mcp_discovery.server import (
            describe_tool,
            invoke_tool,
            list_capabilities,
        )

        assert callable(list_capabilities)
        assert callable(describe_tool)
        assert callable(invoke_tool)

    def test_list_capabilities_is_callable(self):
        from tools.mcp_discovery.server import list_capabilities

        assert callable(list_capabilities)

    def test_describe_tool_is_callable(self):
        from tools.mcp_discovery.server import describe_tool

        assert callable(describe_tool)

    def test_invoke_tool_is_callable(self):
        from tools.mcp_discovery.server import invoke_tool

        assert callable(invoke_tool)


# Functional contracts


class TestListCapabilities:
    """list_capabilities returns names + one-line descriptions from static manifest."""

    def test_returns_list(self):
        from tools.mcp_discovery.server import list_capabilities

        result = list_capabilities()
        assert isinstance(result, list)

    def test_entries_have_name_and_description(self):
        from tools.mcp_discovery.server import list_capabilities

        result = list_capabilities()
        assert len(result) > 0, "capabilities list must not be empty"
        for entry in result:
            assert "name" in entry, f"Missing 'name' key in entry: {entry}"
            assert "description" in entry, f"Missing 'description' key in entry: {entry}"
            assert isinstance(entry["name"], str)
            assert isinstance(entry["description"], str)

    def test_known_capabilities_present(self):
        """Core CLI verbs must appear in the capability list."""
        from tools.mcp_discovery.server import list_capabilities

        result = list_capabilities()
        names = {entry["name"] for entry in result}
        expected = {
            "write",
            "search",
            "edit",
            "confirm",
            "entity",
            "health",
            "version",
            "journal",
            "index-tree",
        }
        missing = expected - names
        assert not missing, f"Missing expected capabilities: {missing}"


class TestDescribeTool:
    """describe_tool returns manifest entry for known tools, KeyError for unknown."""

    def test_known_tool_returns_entry(self):
        from tools.mcp_discovery.server import describe_tool

        result = describe_tool("write")
        assert isinstance(result, dict)
        assert result.get("name") == "write"
        assert "description" in result

    def test_another_known_tool(self):
        from tools.mcp_discovery.server import describe_tool

        result = describe_tool("search")
        assert result.get("name") == "search"

    def test_unknown_tool_raises_key_error(self):
        from tools.mcp_discovery.server import describe_tool

        with pytest.raises(KeyError):
            describe_tool("nonexistent_tool_xyz")


class TestInvokeTool:
    """invoke_tool exists but raises NotImplementedError (stub only)."""

    def test_raises_not_implemented(self):
        from tools.mcp_discovery.server import invoke_tool

        with pytest.raises(NotImplementedError, match="[Ff]uture|[Ss]tub|[Cc]LI"):
            invoke_tool("write", {"title": "test"})


# Boundary / source-audit tests


DISALLOWED_IMPORTS = {
    "openai",
    "anthropic",
    "sentence_transformers",
    "sentence-transformers",
}

DISALLOWED_DATA_ACCESS = {
    "tools.lib.config",
    "USER_DATA_DIR",
    "Documents/Life-Index",
}

DISALLOWED_DYNAMIC_DISCOVERY = {
    "importlib",
    "glob",
    "os.listdir",
}


def _collect_python_files() -> list[Path]:
    """All .py files under tools/mcp_discovery/."""
    if not MCP_ROOT.exists():
        return []
    return sorted(MCP_ROOT.rglob("*.py"))


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module)
    return imports


class TestBoundaryInvariants:
    """Static source audit: no forbidden imports or data access patterns."""

    def test_no_llm_provider_imports(self):
        offenders: list[str] = []
        for path in _collect_python_files():
            imports = _imported_modules(path)
            found = imports & DISALLOWED_IMPORTS
            if found:
                rel = path.relative_to(REPO_ROOT).as_posix()
                offenders.append(f"{rel}: {sorted(found)}")
        assert offenders == [], f"LLM provider imports found: {offenders}"

    def test_no_direct_data_access(self):
        offenders: list[str] = []
        for path in _collect_python_files():
            content = path.read_text(encoding="utf-8")
            for pattern in DISALLOWED_DATA_ACCESS:
                if pattern in content:
                    rel = path.relative_to(REPO_ROOT).as_posix()
                    offenders.append(f"{rel}: contains '{pattern}'")
        assert offenders == [], f"Direct data access patterns found: {offenders}"

    def test_no_dynamic_discovery_mechanisms(self):
        """No importlib, glob(), or os.listdir for runtime tool scanning."""
        offenders: list[str] = []
        for path in _collect_python_files():
            imports = _imported_modules(path)
            content = path.read_text(encoding="utf-8")
            rel = path.relative_to(REPO_ROOT).as_posix()
            # Check imports
            if "importlib" in imports:
                offenders.append(f"{rel}: imports importlib")
            # Check function calls (glob(, os.listdir)
            if "glob(" in content:
                offenders.append(f"{rel}: calls glob()")
            if "os.listdir" in content:
                offenders.append(f"{rel}: calls os.listdir()")
        assert offenders == [], f"Dynamic discovery mechanisms found: {offenders}"

    def test_capabilities_json_is_valid(self):
        """capabilities.json must be valid JSON with expected structure."""
        cap_file = MCP_ROOT / "capabilities.json"
        assert cap_file.exists(), "capabilities.json must exist"
        data = json.loads(cap_file.read_text(encoding="utf-8"))
        assert isinstance(data, list), "capabilities.json must be a JSON array"
        for entry in data:
            assert "name" in entry
            assert "description" in entry
