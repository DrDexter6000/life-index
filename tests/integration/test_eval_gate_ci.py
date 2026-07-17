#!/usr/bin/env python3
"""CI integration tests for deterministic eval and public Core assertion wiring.

Quality/noise metrics and private eval remain advisory. Public blocker truth is
owned by the machine-readable synthetic Core assertion sentinel.

This test IS the CI gate's meta-validation: if this test passes, the gate
mechanism is correctly wired. If the gate ever regresses, this test catches it.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
GATE_SCRIPT_PATH = PROJECT_ROOT / "scripts" / "run_eval_gate.sh"
PRE_PUSH_GATE_PATH = PROJECT_ROOT / "scripts" / "pre-push-gate.sh"
ADVISORY_SCRIPT_PATH = PROJECT_ROOT / "scripts" / "run_eval_advisory.sh"


# ── Gate script structure ──


class TestGateScriptStructure:
    """Verify the eval gate script has the required 3-section structure."""

    def test_gate_script_has_three_sections(self) -> None:
        """run_eval_gate.sh must have Section 1/2/3 markers."""
        if not GATE_SCRIPT_PATH.exists():
            pytest.skip("run_eval_gate.sh not found (non-POSIX environment)")

        source = GATE_SCRIPT_PATH.read_text(encoding="utf-8")

        required_sections = ["Section 1", "Section 2", "Section 3"]
        for section in required_sections:
            assert section in source, (
                f"Gate script missing '{section}' marker. "
                f"Found: {[s for s in required_sections if s in source]}"
            )

    def test_section_2_references_public_core_assertion(self) -> None:
        """Section 2 must use the machine-readable public assertion authority."""
        if not GATE_SCRIPT_PATH.exists():
            pytest.skip("run_eval_gate.sh not found (non-POSIX environment)")

        source = GATE_SCRIPT_PATH.read_text(encoding="utf-8")
        assert "run_public_core_assertions.py" in source
        assert "test_golden_rejection" not in source

    def test_section_1_references_eval_infrastructure(self) -> None:
        if not GATE_SCRIPT_PATH.exists():
            pytest.skip("run_eval_gate.sh not found (non-POSIX environment)")

        source = GATE_SCRIPT_PATH.read_text(encoding="utf-8")
        assert "test_eval_metrics.py" in source

    def test_section_3_references_full_regression(self) -> None:
        if not GATE_SCRIPT_PATH.exists():
            pytest.skip("run_eval_gate.sh not found (non-POSIX environment)")

        source = GATE_SCRIPT_PATH.read_text(encoding="utf-8")
        assert "test_eval_provider_retirement.py" in source

    def test_no_continue_on_error(self) -> None:
        """Gate script must NOT use --continue-on-error."""
        if not GATE_SCRIPT_PATH.exists():
            pytest.skip("run_eval_gate.sh not found (non-POSIX environment)")

        source = GATE_SCRIPT_PATH.read_text(encoding="utf-8")
        assert (
            "--continue-on-error" not in source
        ), "Gate script must not use --continue-on-error (violates D15)"

    def test_uses_set_e(self) -> None:
        """Gate script must use 'set -e' for fail-fast behavior."""
        if not GATE_SCRIPT_PATH.exists():
            pytest.skip("run_eval_gate.sh not found (non-POSIX environment)")

        source = GATE_SCRIPT_PATH.read_text(encoding="utf-8")
        assert (
            "set -e" in source or "set -euo pipefail" in source
        ), "Gate script must use 'set -e' or 'set -euo pipefail' for fail-fast"

    def test_blocking_gate_inventory_references_only_existing_test_paths(self) -> None:
        sources = (
            GATE_SCRIPT_PATH.read_text(encoding="utf-8"),
            PRE_PUSH_GATE_PATH.read_text(encoding="utf-8"),
        )
        paths = {
            match
            for source in sources
            for match in re.findall(r"tests/[A-Za-z0-9_./-]+\.py", source)
        }

        missing = sorted(path for path in paths if not (PROJECT_ROOT / path).is_file())
        assert missing == []

    def test_blocking_gate_inventory_excludes_private_quality_eval(self) -> None:
        blocking_sources = (
            GATE_SCRIPT_PATH.read_text(encoding="utf-8"),
            PRE_PUSH_GATE_PATH.read_text(encoding="utf-8"),
            WORKFLOW_PATH.read_text(encoding="utf-8"),
        )
        advisory_paths = (
            "tests/unit/test_eval_gate.py",
            "tests/eval/test_broad_eval_soft_gate.py",
        )

        leaked = [
            path for path in advisory_paths if any(path in source for source in blocking_sources)
        ]
        assert leaked == []

    def test_private_quality_eval_has_an_explicit_advisory_command(self) -> None:
        assert ADVISORY_SCRIPT_PATH.is_file()
        source = ADVISORY_SCRIPT_PATH.read_text(encoding="utf-8")
        assert "tests/unit/test_eval_advisory.py" in source
        assert "tests/unit/test_eval_runner.py" in source
        assert "tests/eval/test_broad_eval_soft_gate.py" in source
        assert "run_public_core_assertions.py" not in source


WORKFLOW_PATH = PROJECT_ROOT / ".github" / "workflows" / "tests.yml"
EXPECTED_DETERMINISTIC_TARGETS = frozenset(
    {
        "tests/unit/test_eval_provider_retirement.py",
        "tests/unit/test_eval_metrics.py",
        "tests/integration/test_eval_gate_ci.py",
        "tests/integration/test_eval_private_inventory.py",
        "tests/eval/test_semantic_report.py",
        "tests/eval/test_eval_compare.py",
        "tests/eval/test_eval_run.py",
        "tests/eval/test_eval_qrels.py",
        "tests/eval/test_eval_export.py",
        "tests/eval/test_eval_serialization.py",
    }
)


def _normalized_test_targets(source: str) -> frozenset[str]:
    return frozenset(re.findall(r"tests/[A-Za-z0-9_./-]+\.py", source))


def test_eval_runner_owns_exact_deterministic_inventory_and_public_sentinel() -> None:
    source = GATE_SCRIPT_PATH.read_text(encoding="utf-8")

    assert _normalized_test_targets(source) == EXPECTED_DETERMINISTIC_TARGETS
    assert source.count("python .github/scripts/run_public_core_assertions.py") == 1
    assert "set -euo pipefail" in source
    assert "|| true" not in source


@pytest.mark.parametrize("surface", [WORKFLOW_PATH, PRE_PUSH_GATE_PATH])
def test_external_gate_surface_delegates_without_duplicate_inventory(
    surface: Path,
) -> None:
    source = surface.read_text(encoding="utf-8")

    assert re.search(r"(?:bash\s+)?scripts/run_eval_gate\.sh(?:\s|$)", source)
    assert _normalized_test_targets(source) == frozenset()


def test_pre_push_records_delegated_runner_failure() -> None:
    source = PRE_PUSH_GATE_PATH.read_text(encoding="utf-8")

    assert re.search(
        r'run_check\s+"search-eval-gate"\s+timeout\s+"\$EVAL_TIMEOUT_SECONDS"\s+'
        r"bash\s+scripts/run_eval_gate\.sh",
        source,
    )
    assert "run_public_core_assertions.py" not in source
    assert 'if [ "${#FAILED_CHECKS[@]}" -eq 0 ]; then' in source
    assert "exit 1" in source
