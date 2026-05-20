#!/usr/bin/env python3
"""PAS-2 API Contract Alignment Tests.

Verifies that docs/API.md is aligned with current CLI implementation truth
for schema_version policy, search parameters, and error codes.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
API_MD = REPO_ROOT / "docs" / "API.md"
ERRORS_PY = REPO_ROOT / "tools" / "lib" / "errors.py"
URL_DOWNLOAD_PY = REPO_ROOT / "tools" / "lib" / "url_download.py"
SEARCH_CONSTANTS_PY = REPO_ROOT / "tools" / "lib" / "search_constants.py"

# Commands that emit dict-shaped JSON with top-level schema_version per PAS-1.
DICT_SHAPED_COMMANDS = [
    "search",
    "smart-search",
    "aggregate",
    "analyze",
    "entity",
    "timeline",
    "health",
]


def _read_api_md() -> str:
    return API_MD.read_text(encoding="utf-8")


def _read_errors_py() -> str:
    return ERRORS_PY.read_text(encoding="utf-8")


def _read_url_download_py() -> str:
    return URL_DOWNLOAD_PY.read_text(encoding="utf-8")


def _read_search_constants_py() -> str:
    return SEARCH_CONSTANTS_PY.read_text(encoding="utf-8")


def _max_results_default() -> str:
    text = _read_search_constants_py()
    match = re.search(r"MAX_RESULTS_DEFAULT:\s*int\s*=\s*(\d+)", text)
    assert match is not None, "MAX_RESULTS_DEFAULT not found in search_constants.py"
    return match.group(1)


def _extract_contract_block(text: str, command: str) -> str | None:
    start_re = re.compile(rf"<!--\s*M16-CONTRACT:\s*{re.escape(command)}\s*-->")
    end_re = re.compile(r"<!--\s*/M16-CONTRACT\s*-->")
    start_match = start_re.search(text)
    if not start_match:
        return None
    end_match = end_re.search(text, start_match.end())
    if not end_match:
        return None
    return text[start_match.end() : end_match.start()]


# =============================================================================
# 1. schema_version policy
# =============================================================================


class TestSchemaVersionPolicyNotStale:
    """M16 dict-shaped commands must not document a 'no top-level schema_version' policy."""

    @pytest.mark.parametrize("command", DICT_SHAPED_COMMANDS)
    def test_no_stale_no_schema_version_text(self, command: str):
        content = _read_api_md()
        block = _extract_contract_block(content, command)
        assert block is not None, f"Missing M16 contract block for {command}"
        stale_patterns = [
            r"does\s+not\s+emit\s+a?\s*top-level\s+`?schema_version`?",
            r"no\s+top-level\s+`?schema_version`?",
            r"lacks\s+a?\s*top-level\s+`?schema_version`?",
            r"absence\s+of\s+a?\s*top-level\s+`?schema_version`?",
        ]
        for pattern in stale_patterns:
            assert not re.search(pattern, block, re.IGNORECASE), (
                f"Contract block for '{command}' contains stale "
                f"'no top-level schema_version' text matching /{pattern}/i"
            )

    @pytest.mark.parametrize("command", DICT_SHAPED_COMMANDS)
    def test_dict_shaped_command_emits_schema_version(self, command: str):
        content = _read_api_md()
        block = _extract_contract_block(content, command)
        assert block is not None, f"Missing M16 contract block for {command}"
        assert re.search(
            r"emits\s+a?\s*top-level\s+`?schema_version`?",
            block,
            re.IGNORECASE,
        ), (
            f"Contract block for '{command}' must document that it "
            f"emits a top-level schema_version field"
        )


# =============================================================================
# 2. Search parameter alignment
# =============================================================================


class TestSearchParameterDocsAlignment:
    """docs/API.md search_journals parameter table must match CLI help truth."""

    def _get_search_params_section(self) -> str:
        content = _read_api_md()
        # Find the search_journals parameter table
        marker = "## search_journals"
        idx = content.find(marker)
        assert idx != -1, "search_journals section not found in API.md"
        # Grab a chunk large enough to contain the parameter table
        chunk = content[idx : idx + 8000]
        return chunk

    def test_no_semantic_is_documented_not_semantic_flag(self):
        chunk = self._get_search_params_section()
        # API.md must NOT document `semantic` as a flag defaulting to false
        # (old drift); it must document `--no-semantic` or state semantic is on by default.
        lines = [line.strip() for line in chunk.splitlines()]
        for line in lines:
            if (
                line.startswith("|")
                and "semantic" in line.lower()
                and "no-semantic" not in line.lower()
            ):
                # If this line says "semantic | flag | ❌ | false" that's the old drift
                if re.search(
                    r"\|\s*semantic\s*\|\s*flag\s*\|\s*.*false",
                    line,
                    re.IGNORECASE,
                ):
                    pytest.fail(
                        f"API.md still documents 'semantic' as a flag defaulting to false: {line}"
                    )

    def test_no_index_is_documented_not_use_index_flag(self):
        chunk = self._get_search_params_section()
        lines = [line.strip() for line in chunk.splitlines()]
        for line in lines:
            if (
                line.startswith("|")
                and "use-index" in line.lower()
                and "no-index" not in line.lower()
            ):
                if re.search(
                    r"\|\s*use-index\s*\|\s*flag\s*\|\s*.*false",
                    line,
                    re.IGNORECASE,
                ):
                    pytest.fail(
                        f"API.md still documents 'use-index' as a flag defaulting to false: {line}"
                    )

    def test_semantic_weight_default_is_1_0(self):
        chunk = self._get_search_params_section()
        assert re.search(
            r"semantic-weight\s*\|\s*float\s*\|[^|]*\|\s*1\.0",
            chunk,
            re.IGNORECASE,
        ), "API.md must document semantic-weight default as 1.0 (was 0.4)"

    def test_fts_weight_default_is_1_0(self):
        chunk = self._get_search_params_section()
        assert re.search(
            r"fts-weight\s*\|\s*float\s*\|[^|]*\|\s*1\.0",
            chunk,
            re.IGNORECASE,
        ), "API.md must document fts-weight default as 1.0 (was 0.6)"

    def test_undocumented_search_params_present(self):
        chunk = self._get_search_params_section()
        required_params = [
            "semantic-policy",
            "read-top",
            "explain",
            "diagnose",
            "diagnose-days",
        ]
        missing = []
        for param in required_params:
            if param not in chunk.lower():
                missing.append(param)
        assert missing == [], f"API.md search_journals section missing documented params: {missing}"

    def test_limit_default_matches_search_constant(self):
        chunk = self._get_search_params_section()
        expected = _max_results_default()
        assert re.search(
            rf"--limit\s*\|\s*int\s*\|[^|]*\|\s*{re.escape(expected)}",
            chunk,
            re.IGNORECASE,
        ), (
            "API.md must document the effective --limit default from "
            f"MAX_RESULTS_DEFAULT ({expected})"
        )


# =============================================================================
# 3. Error-code family coverage
# =============================================================================


class TestErrorCodeFamilyCoverage:
    """Error-code classification tables must cover production-used families."""

    def test_e07xx_row_present_in_classification_table(self):
        content = _read_api_md()
        # The high-level classification table is near line ~80 (~2300 chars in)
        table_chunk = content[:3000]
        assert re.search(
            r"\|\s*Web\s*\|\s*E07xx\s*\|",
            table_chunk,
            re.IGNORECASE,
        ), "API.md high-level error-code classification table missing E07xx Web row"

    def test_e0005_e0006_present_in_general_error_table(self):
        content = _read_api_md()
        # General error table (E00xx)
        general_match = re.search(
            r"### 通用错误 \(E00xx\).*?(?=### |## |$)",
            content,
            re.DOTALL,
        )
        assert general_match, "General error (E00xx) table not found"
        general_block = general_match.group(0)
        assert "E0005" in general_block, "E0005 missing from general error table"
        assert "E0006" in general_block, "E0006 missing from general error table"

    def test_e07xx_codes_present_in_detailed_table(self):
        content = _read_api_md()
        errors_py = _read_errors_py()
        # Extract all E07xx codes defined in errors.py
        e07_codes = re.findall(r"E07\d{2}", errors_py)
        assert e07_codes, "No E07xx codes found in errors.py"
        # They must appear somewhere in API.md error-code tables
        missing = [c for c in e07_codes if c not in content]
        assert missing == [], f"E07xx codes defined in errors.py but missing from API.md: {missing}"


# =============================================================================
# 4. E08xx implement-or-remove
# =============================================================================


class TestE08xxNotFalselyDocumented:
    """E08xx must not be silently documented as implemented if code does not emit them."""

    def test_e08xx_not_in_errors_py(self):
        errors_py = _read_errors_py()
        e08_codes = re.findall(r"E08\d{2}", errors_py)
        assert (
            e08_codes == []
        ), f"E08xx codes found in errors.py but task says they are not implemented: {e08_codes}"

    def test_e08xx_not_in_runtime_code(self):
        """E08xx must not appear in tools/ runtime code as emitted error codes."""
        tools_dir = REPO_ROOT / "tools"
        found = []
        for path in tools_dir.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            codes = set(re.findall(r"E08\d{2}", text))
            for c in codes:
                found.append(f"{path.relative_to(REPO_ROOT)}: {c}")
        assert found == [], f"E08xx codes found in tools/ runtime code: {found}"

    def test_e08xx_not_documented_as_implemented(self):
        content = _read_api_md()
        # If E08xx is mentioned, it must be explicitly marked reserved/unimplemented/deferred,
        # not listed in an implemented-code table.
        e08_matches = list(re.finditer(r"E08\d{2}", content))
        if not e08_matches:
            return  # Already clean
        # For each E08xx mention, verify it is in a reserved/deferred context
        for m in e08_matches:
            start = max(0, m.start() - 200)
            end = min(len(content), m.end() + 200)
            context = content[start:end].lower()
            allowed_contexts = [
                "reserved",
                "unimplemented",
                "deferred",
                "not implemented",
                "placeholder",
                "future",
            ]
            assert any(word in context for word in allowed_contexts), (
                f"E08xx code {m.group(0)} at position {m.start()} is documented "
                f"without a reserved/unimplemented/deferred marker. Context:\n{content[start:end]}"
            )
