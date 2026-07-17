#!/usr/bin/env python3
"""Run the fixed public synthetic Core assertion and emit an execution sentinel."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path

import pytest

DEFAULT_TARGET = (
    "tests/contract/test_recall_first_invariants.py::"
    "test_public_blocker_executes_synthetic_core_assertion"
)


@dataclass(eq=False)
class AssertionCounter:
    collected: int = 0
    executed: int = 0
    passed: int = 0
    failed: int = 0
    skipped_nodeids: set[str] = field(default_factory=set)

    def pytest_collection_finish(self, session: pytest.Session) -> None:
        self.collected = len(session.items)

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        if report.skipped:
            self.skipped_nodeids.add(report.nodeid)
        if report.when != "call" or report.skipped:
            return
        self.executed += 1
        if report.passed:
            self.passed += 1
        elif report.failed:
            self.failed += 1


def _write_sentinel(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the public synthetic Core assertion with execution counting."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="Repository root used as pytest rootdir.",
    )
    parser.add_argument(
        "--target",
        default=DEFAULT_TARGET,
        help="Pytest target; the default is the public token-match Core assertion.",
    )
    parser.add_argument(
        "--sentinel",
        type=Path,
        default=None,
        help="Machine-readable JSON output path.",
    )
    args = parser.parse_args(argv)

    root = args.root.resolve()
    sentinel = args.sentinel or root / ".pytest_tmp" / "public-core-assertions.json"
    sentinel.parent.mkdir(parents=True, exist_ok=True)
    counter = AssertionCounter()
    pytest_exit = int(
        pytest.main(
            [
                args.target,
                "-q",
                "--rootdir",
                str(root),
                "--basetemp",
                str(sentinel.parent / "pytest"),
            ],
            plugins=[counter],
        )
    )
    is_green = pytest_exit == 0 and counter.executed > 0 and counter.failed == 0
    payload: dict[str, object] = {
        "schema_version": "life-index.public-core-assertions.v1",
        "target": args.target,
        "core_assertions_collected": counter.collected,
        "core_assertions_executed": counter.executed,
        "core_assertions_passed": counter.passed,
        "core_assertions_failed": counter.failed,
        "core_assertions_skipped": len(counter.skipped_nodeids),
        "pytest_exit_code": pytest_exit,
        "status": "PASS" if is_green else "FAIL",
    }
    _write_sentinel(sentinel, payload)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if is_green else 1


if __name__ == "__main__":
    raise SystemExit(main())
