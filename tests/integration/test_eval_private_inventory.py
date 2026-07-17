from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def test_private_corpus_runner_is_excluded_from_blocking_inventories() -> None:
    blocking_paths = (
        PROJECT_ROOT / "scripts" / "run_eval_gate.sh",
        PROJECT_ROOT / "scripts" / "pre-push-gate.sh",
        PROJECT_ROOT / ".github" / "workflows" / "tests.yml",
    )

    leaks = [
        path
        for path in blocking_paths
        if "tests/unit/test_eval_runner.py" in path.read_text(encoding="utf-8")
    ]
    assert leaks == []
