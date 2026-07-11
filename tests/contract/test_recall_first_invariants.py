"""Public CLI contracts for recall-first retrieval truthfulness."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
_SANDBOX_MARKER = ".synthetic-d1-a-sandbox"


def _make_synthetic_data_dir(tmp_path: Path) -> Path:
    data_dir = tmp_path / "Life-Index"
    (data_dir / "Journals" / "2026" / "01").mkdir(parents=True)
    (data_dir / _SANDBOX_MARKER).write_text("synthetic only\n", encoding="utf-8")
    return data_dir


def _assert_synthetic_data_dir(data_dir: Path) -> None:
    """Fail closed before any behavior run can target configured user data."""
    resolved = data_dir.resolve()
    configured = os.environ.get("LIFE_INDEX_DATA_DIR")
    if configured and resolved == Path(configured).expanduser().resolve():
        raise AssertionError("refusing to run recall contract against configured data")
    default_data_dir = (Path.home() / "Documents" / "Life-Index").resolve()
    if resolved == default_data_dir:
        raise AssertionError("refusing to run recall contract against default user data")
    if not (resolved / _SANDBOX_MARKER).is_file():
        raise AssertionError("synthetic sandbox marker is missing")


def _write_journal(data_dir: Path, *, sequence: int, title: str, content: str) -> str:
    rel_path = f"Journals/2026/01/life-index_2026-01-01_{sequence:03d}.md"
    journal_path = data_dir / rel_path
    journal_path.write_text(
        "---\n"
        f"title: {title}\n"
        "date: 2026-01-01\n"
        "topic:\n"
        "  - synthetic\n"
        "tags: []\n"
        "people: []\n"
        "---\n\n"
        f"{content}\n",
        encoding="utf-8",
    )
    return rel_path


def _run_search(data_dir: Path, query: str, *extra_args: str) -> dict:
    _assert_synthetic_data_dir(data_dir)
    env = {
        **os.environ,
        "LIFE_INDEX_DATA_DIR": str(data_dir),
        "LIFE_INDEX_NOISE_GATE": "1",
    }
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "tools.search_journals",
            "--query",
            query,
            "--no-index",
            *extra_args,
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert proc.returncode == 0, f"search failed: {proc.stderr}"
    return json.loads(proc.stdout)


def test_default_search_keeps_all_synthetic_token_matches_despite_noise_label(
    tmp_path: Path,
) -> None:
    data_dir = _make_synthetic_data_dir(tmp_path)
    expected_path = _write_journal(
        data_dir,
        sequence=1,
        title="Synthetic 菜谱推荐 note",
        content="A neutral fixture containing the exact token 菜谱推荐 for retrieval.",
    )

    result = _run_search(data_dir, "菜谱推荐")

    assert result["total_matches"] == 1
    returned_path = Path(result["merged_results"][0]["path"]).as_posix()
    assert returned_path.endswith(expected_path)


def test_default_limit_only_changes_presentation_and_limit_zero_exposes_all_matches(
    tmp_path: Path,
) -> None:
    data_dir = _make_synthetic_data_dir(tmp_path)
    for sequence in range(1, 24):
        _write_journal(
            data_dir,
            sequence=sequence,
            title=f"Synthetic recalltoken note {sequence}",
            content=f"Neutral fixture {sequence} contains recalltoken.",
        )

    limited = _run_search(data_dir, "recalltoken")
    unlimited = _run_search(data_dir, "recalltoken", "--limit", "0")

    assert len(limited["merged_results"]) == 20
    assert len(unlimited["merged_results"]) == 23
    assert limited["total_matches"] == unlimited["total_matches"] == 23
    assert limited["has_more"] is True
    assert unlimited["has_more"] is False
