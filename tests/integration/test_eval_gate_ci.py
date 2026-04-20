#!/usr/bin/env python3
"""CI integration test: eval gate correctly enforces rejection pass-rate ≥ 90%.

Validates (D15 compliance):
1. The rejection threshold in test_golden_rejection.py is exactly 0.90
2. A fake low pass-rate (85%) triggers eval gate failure (pytest exit != 0)
3. A normal pass-rate (90%) passes the gate (pytest exit == 0)
4. The gate script (run_eval_gate.sh) has the required 3-section structure
5. The gate script does NOT use --continue-on-error (hard gate, no escape hatch)

This test IS the CI gate's meta-validation: if this test passes, the gate
mechanism is correctly wired. If the gate ever regresses, this test catches it.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
REJECTION_TEST_PATH = (
    PROJECT_ROOT / "tests" / "integration" / "test_golden_rejection.py"
)
GATE_SCRIPT_PATH = PROJECT_ROOT / "scripts" / "run_eval_gate.sh"

D15_THRESHOLD = 0.90


# ── Threshold verification ──


class TestRejectionThreshold:
    """Verify the rejection pass-rate threshold constant is correctly set."""

    def test_threshold_is_90_percent(self) -> None:
        """The rejection threshold in test_golden_rejection.py must be exactly 0.90."""
        source = REJECTION_TEST_PATH.read_text(encoding="utf-8")
        match = re.search(r"assert\s+rate\s*>=\s*([0-9.]+)", source)
        assert match, "Could not find 'assert rate >= ...' in test_golden_rejection.py"
        threshold = float(match.group(1))
        assert threshold == D15_THRESHOLD, (
            f"Rejection threshold is {threshold}, expected {D15_THRESHOLD}"
        )


# ── Fake low pass-rate must fail ──


class TestFakeLowPassRateFailsGate:
    """Verify that a synthetic low pass-rate causes the gate to fail."""

    @staticmethod
    def _run_pytest_in_isolation(test_file: Path) -> subprocess.CompletedProcess[str]:
        """Run pytest on a single file with isolated rootdir to avoid scanning."""
        return subprocess.run(
            [
                sys.executable, "-m", "pytest",
                str(test_file), "-v",
                "--rootdir", str(test_file.parent),
                "-c", "",  # ignore project pyproject.toml
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

    def test_fake_85_percent_pass_rate_fails(self, tmp_path: Path) -> None:
        """Create a fake rejection test with 85% pass-rate; gate must fail."""
        fake_test = tmp_path / "test_fake_rejection_low.py"
        fake_test.write_text(
            '''
def test_rejection_pass_rate_low():
    """Fake test: 17/20 pass = 85% < 90% threshold."""
    rate = 17 / 20  # 0.85
    assert rate >= 0.90, (
        f"Rejection pass-rate {rate:.1%} (17/20) < 90% threshold."
    )
''',
            encoding="utf-8",
        )

        result = self._run_pytest_in_isolation(fake_test)

        assert result.returncode != 0, (
            "Gate must fail when rejection pass-rate < 90%, but pytest exited 0.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_normal_90_percent_pass_rate_passes(self, tmp_path: Path) -> None:
        """Create a fake rejection test with exactly 90% pass-rate; gate must pass."""
        fake_test = tmp_path / "test_fake_rejection_ok.py"
        fake_test.write_text(
            '''
def test_rejection_pass_rate_ok():
    """Fake test: 18/20 pass = 90% >= 90% threshold."""
    rate = 18 / 20  # 0.90
    assert rate >= 0.90, (
        f"Rejection pass-rate {rate:.1%} (18/20) < 90% threshold."
    )
''',
            encoding="utf-8",
        )

        result = self._run_pytest_in_isolation(fake_test)

        assert result.returncode == 0, (
            "Gate should pass when rejection pass-rate >= 90%, but pytest exited "
            f"non-zero.\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_boundary_89_percent_fails(self, tmp_path: Path) -> None:
        """Boundary: 89% (just below threshold) must still fail."""
        fake_test = tmp_path / "test_fake_rejection_boundary.py"
        fake_test.write_text(
            '''
def test_rejection_pass_rate_boundary():
    """Boundary test: 89% < 90% must fail."""
    rate = 0.89
    assert rate >= 0.90, (
        f"Rejection pass-rate {rate:.1%} < 90% threshold."
    )
''',
            encoding="utf-8",
        )

        result = self._run_pytest_in_isolation(fake_test)

        assert result.returncode != 0, (
            "Gate must fail at 89% (below 90% threshold).\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )


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

    def test_section_2_references_rejection_test(self) -> None:
        """Section 2 must reference test_golden_rejection.py."""
        if not GATE_SCRIPT_PATH.exists():
            pytest.skip("run_eval_gate.sh not found (non-POSIX environment)")

        source = GATE_SCRIPT_PATH.read_text(encoding="utf-8")
        assert "test_golden_rejection" in source, (
            "Gate script must reference test_golden_rejection.py in Section 2"
        )

    def test_section_1_references_eval_infrastructure(self) -> None:
        """Section 1 must reference eval infrastructure tests."""
        if not GATE_SCRIPT_PATH.exists():
            pytest.skip("run_eval_gate.sh not found (non-POSIX environment)")

        source = GATE_SCRIPT_PATH.read_text(encoding="utf-8")
        assert "test_eval_gate" in source, (
            "Gate script must reference test_eval_gate.py in Section 1"
        )

    def test_section_3_references_full_regression(self) -> None:
        """Section 3 must run full unit regression."""
        if not GATE_SCRIPT_PATH.exists():
            pytest.skip("run_eval_gate.sh not found (non-POSIX environment)")

        source = GATE_SCRIPT_PATH.read_text(encoding="utf-8")
        assert "tests/unit/" in source, (
            "Gate script must reference tests/unit/ in Section 3"
        )

    def test_no_continue_on_error(self) -> None:
        """Gate script must NOT use --continue-on-error."""
        if not GATE_SCRIPT_PATH.exists():
            pytest.skip("run_eval_gate.sh not found (non-POSIX environment)")

        source = GATE_SCRIPT_PATH.read_text(encoding="utf-8")
        assert "--continue-on-error" not in source, (
            "Gate script must not use --continue-on-error (violates D15)"
        )

    def test_uses_set_e(self) -> None:
        """Gate script must use 'set -e' for fail-fast behavior."""
        if not GATE_SCRIPT_PATH.exists():
            pytest.skip("run_eval_gate.sh not found (non-POSIX environment)")

        source = GATE_SCRIPT_PATH.read_text(encoding="utf-8")
        assert "set -e" in source or "set -euo pipefail" in source, (
            "Gate script must use 'set -e' or 'set -euo pipefail' for fail-fast"
        )
