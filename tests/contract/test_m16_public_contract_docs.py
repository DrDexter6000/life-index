#!/usr/bin/env python3
"""M16 contract tests: docs/API.md public JSON contract coverage.

Verifies that docs/API.md documents stable JSON contracts for the eight
public CLI commands (search, smart-search, aggregate, analyze, entity,
timeline, health, generate-index) covering:
- JSON shape / top-level fields
- Field semantics
- Error behavior / error codes or documented deviations
- SLO / performance expectation where applicable
- schema_version policy
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
API_MD = REPO_ROOT / "docs" / "API.md"

# Marker used to locate M16 contract blocks in API.md.
# Each command section must contain a contract block delimited by
# "<!-- M16-CONTRACT: command_name -->" and
# "<!-- /M16-CONTRACT -->".
CONTRACT_START_RE = re.compile(r"<!--\s*M16-CONTRACT:\s*(\S+)\s*-->")
CONTRACT_END_RE = re.compile(r"<!--\s*/M16-CONTRACT\s*-->")

# All eight commands that must have contract blocks.
EIGHT_COMMANDS = [
    "search",
    "smart-search",
    "aggregate",
    "analyze",
    "entity",
    "timeline",
    "health",
    "generate-index",
]

# Required sub-sections within each M16 contract block.
# Each is a regex that must match at least once inside the block.
REQUIRED_SUBSECTIONS = {
    "json_shape": re.compile(
        r"(JSON\s+Shape|顶层字段|Top-Level\s+Fields|返回值字段|"
        r"Response\s+Shape|Output\s+Shape)",
        re.IGNORECASE,
    ),
    "field_semantics": re.compile(
        r"(Field\s+Semantics|字段语义|字段说明|Output\s+Field)",
        re.IGNORECASE,
    ),
    "error_behavior": re.compile(
        r"(Error\s+(Behavior|Behaviour|Codes|Handling)|"
        r"错误(行为|码|处理)|错误码列表|Error\s+Payload|"
        r"deviation|known\s+deviation)",
        re.IGNORECASE,
    ),
    "schema_version_policy": re.compile(
        r"(schema_version|Schema\s+Version\s+Policy|版本策略)",
        re.IGNORECASE,
    ),
}

# SLO is required only for commands that already have documented SLOs.
SLO_COMMANDS = {"search", "smart-search"}
SLO_RE = re.compile(
    r"(SLO|p95|latency|性能|Performance|performance\s+expectation)",
    re.IGNORECASE,
)


def _read_api_md() -> str:
    """Read docs/API.md content."""
    return API_MD.read_text(encoding="utf-8")


def _extract_contract_blocks(text: str) -> dict[str, str]:
    """Extract M16 contract blocks from API.md text.

    Returns dict mapping command name to block content.
    """
    blocks: dict[str, str] = {}
    pos = 0
    while pos < len(text):
        start_match = CONTRACT_START_RE.search(text, pos)
        if not start_match:
            break
        command = start_match.group(1)
        end_match = CONTRACT_END_RE.search(text, start_match.end())
        if not end_match:
            break
        blocks[command] = text[start_match.end() : end_match.start()]
        pos = end_match.end()
    return blocks


class TestM16ContractBlocksExist:
    """Verify all eight commands have M16 contract blocks in API.md."""

    def test_api_md_exists_and_readable(self):
        assert API_MD.is_file(), f"API.md not found at {API_MD}"
        content = _read_api_md()
        assert len(content) > 100, "API.md appears empty"

    def test_all_eight_commands_have_contract_blocks(self):
        content = _read_api_md()
        blocks = _extract_contract_blocks(content)
        missing = [c for c in EIGHT_COMMANDS if c not in blocks]
        assert missing == [], (
            f"Missing M16 contract blocks for: {missing}. "
            f"Found blocks for: {list(blocks.keys())}. "
            f"Each command section in API.md must contain an "
            f"M16-CONTRACT block."
        )

    def test_no_extra_contract_blocks(self):
        content = _read_api_md()
        blocks = _extract_contract_blocks(content)
        extra = [c for c in blocks if c not in EIGHT_COMMANDS]
        assert extra == [], (
            f"Unexpected M16 contract blocks for: {extra}. "
            f"Only the eight commands should have blocks."
        )


class TestM16JsonShapeCoverage:
    """Verify each contract block documents JSON shape / top-level fields."""

    @pytest.mark.parametrize("command", EIGHT_COMMANDS)
    def test_json_shape_documented(self, command: str):
        content = _read_api_md()
        blocks = _extract_contract_blocks(content)
        assert command in blocks, f"No contract block for {command}"
        block = blocks[command]
        assert REQUIRED_SUBSECTIONS["json_shape"].search(block), (
            f"Contract block for '{command}' missing JSON shape / "
            f"top-level fields documentation. Expected a subsection "
            f"matching: {REQUIRED_SUBSECTIONS['json_shape'].pattern}"
        )


class TestM16FieldSemanticsCoverage:
    """Verify each contract block documents field semantics."""

    @pytest.mark.parametrize("command", EIGHT_COMMANDS)
    def test_field_semantics_documented(self, command: str):
        content = _read_api_md()
        blocks = _extract_contract_blocks(content)
        assert command in blocks, f"No contract block for {command}"
        block = blocks[command]
        assert REQUIRED_SUBSECTIONS["field_semantics"].search(block), (
            f"Contract block for '{command}' missing field semantics. "
            f"Expected a subsection matching: "
            f"{REQUIRED_SUBSECTIONS['field_semantics'].pattern}"
        )


class TestM16ErrorBehaviorCoverage:
    """Verify each contract block documents error behavior / codes."""

    @pytest.mark.parametrize("command", EIGHT_COMMANDS)
    def test_error_behavior_documented(self, command: str):
        content = _read_api_md()
        blocks = _extract_contract_blocks(content)
        assert command in blocks, f"No contract block for {command}"
        block = blocks[command]
        assert REQUIRED_SUBSECTIONS["error_behavior"].search(block), (
            f"Contract block for '{command}' missing error behavior / "
            f"error codes documentation. Expected a subsection "
            f"matching: {REQUIRED_SUBSECTIONS['error_behavior'].pattern}"
        )


class TestM16SloCoverage:
    """Verify SLO is documented for commands that have known SLOs."""

    @pytest.mark.parametrize("command", sorted(SLO_COMMANDS))
    def test_slo_documented_where_applicable(self, command: str):
        content = _read_api_md()
        blocks = _extract_contract_blocks(content)
        assert command in blocks, f"No contract block for {command}"
        block = blocks[command]
        assert SLO_RE.search(block), (
            f"Contract block for '{command}' missing SLO / performance "
            f"expectation. Expected a subsection matching: "
            f"{SLO_RE.pattern}"
        )


class TestM16SchemaVersionPolicy:
    """Verify schema_version policy is documented for all commands."""

    @pytest.mark.parametrize("command", EIGHT_COMMANDS)
    def test_schema_version_policy_documented(self, command: str):
        content = _read_api_md()
        blocks = _extract_contract_blocks(content)
        assert command in blocks, f"No contract block for {command}"
        block = blocks[command]
        assert REQUIRED_SUBSECTIONS["schema_version_policy"].search(block), (
            f"Contract block for '{command}' missing schema_version "
            f"policy. Expected text matching: "
            f"{REQUIRED_SUBSECTIONS['schema_version_policy'].pattern}"
        )


class TestM16AnalyzeAliasContract:
    """Verify analyze alias is documented correctly."""

    def test_analyze_alias_documented_in_contract_block(self):
        content = _read_api_md()
        blocks = _extract_contract_blocks(content)
        assert "analyze" in blocks, "No contract block for analyze"
        block = blocks["analyze"]
        # Must state that analyze is an alias for aggregate
        assert re.search(
            r"(alias.*aggregate|aggregate.*alias|" r"command.*[\"']aggregate[\"'])",
            block,
            re.IGNORECASE,
        ), (
            "Analyze contract block must document that it is an alias "
            "for aggregate and emits command='aggregate'."
        )
