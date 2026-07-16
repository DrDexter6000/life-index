"""Filesystem authority contracts for the Host Agent channel."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path


def _seed_data(data_dir: Path) -> str:
    journal = data_dir / "Journals" / "2026" / "05" / "life-index_2026-05-28_001.md"
    journal.parent.mkdir(parents=True, exist_ok=True)
    journal.write_text(
        "---\n"
        'title: "bounded channel entry"\n'
        "date: 2026-05-28\n"
        'topic: ["work"]\n'
        "attachments: [attachments/proof.txt]\n"
        "---\n"
        "needle is present in this journal.\n",
        encoding="utf-8",
    )
    attachments = data_dir / "attachments"
    attachments.mkdir()
    (attachments / "proof.txt").write_text("attachment source", encoding="utf-8")
    (data_dir / "entity_graph.yaml").write_text("entities: []\n", encoding="utf-8")
    return journal.relative_to(data_dir).as_posix()


def _snapshot(root: Path) -> dict[str, str]:
    """Capture both directory topology and exact file content."""
    snapshot: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_dir():
            snapshot[f"{relative}/"] = "directory"
        else:
            snapshot[relative] = sha256(path.read_bytes()).hexdigest()
    return snapshot


def _non_index_snapshot(snapshot: dict[str, str]) -> dict[str, str]:
    return {
        path: value
        for path, value in snapshot.items()
        if path != ".index/" and not path.startswith(".index/")
    }


def test_health_and_journal_get_are_physically_read_only(isolated_data_dir: Path) -> None:
    from tools.host_agent_channel.dispatcher import dispatch

    journal_path = _seed_data(isolated_data_dir)
    before = _snapshot(isolated_data_dir)

    assert dispatch("health", {})["success"] is True
    assert dispatch("journal.get", {"path": journal_path})["success"] is True

    assert _snapshot(isolated_data_dir) == before


def test_search_can_change_only_the_rebuildable_index_directory(isolated_data_dir: Path) -> None:
    from tools.host_agent_channel.dispatcher import dispatch

    _seed_data(isolated_data_dir)
    before = _snapshot(isolated_data_dir)

    assert dispatch("search", {"query": "needle"})["success"] is True

    after = _snapshot(isolated_data_dir)
    assert _non_index_snapshot(after) == _non_index_snapshot(before)
    changed_paths = {
        path for path in set(before) | set(after) if before.get(path) != after.get(path)
    }
    assert changed_paths
    assert all(path == ".index/" or path.startswith(".index/") for path in changed_paths)


def test_search_keeps_validation_trace_outside_the_data_boundary(
    isolated_data_dir: Path,
    tmp_path: Path,
    monkeypatch,
) -> None:
    """The opt-in control trace is sanitized and never becomes source-data state."""
    from tools.host_agent_channel.dispatcher import dispatch

    trace_path = tmp_path / "projection-trace" / "tool-calls.jsonl"
    assert not trace_path.is_relative_to(isolated_data_dir)
    monkeypatch.setenv("LIFE_INDEX_VALIDATION_MODE", "1")
    monkeypatch.setenv("LIFE_INDEX_TOOL_CALL_LOG", str(trace_path))

    _seed_data(isolated_data_dir)
    before = _snapshot(isolated_data_dir)

    assert dispatch("search", {"query": "needle"})["success"] is True

    after = _snapshot(isolated_data_dir)
    assert _non_index_snapshot(after) == _non_index_snapshot(before)
    assert trace_path.is_file()
    records = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 1
    assert records[0]["tool"] == "search"
    assert records[0]["success"] is True
    assert set(records[0]["result"]) == {
        "total_available",
        "total_found",
        "total_matches",
        "has_more",
    }
    serialized = json.dumps(records[0], ensure_ascii=False)
    assert "content" not in serialized
    assert "metadata" not in serialized


def test_search_suppresses_validation_trace_inside_the_data_boundary(
    isolated_data_dir: Path,
    monkeypatch,
) -> None:
    """A caller cannot redirect source-safe trace evidence into user data."""
    from tools.host_agent_channel.dispatcher import dispatch

    trace_path = isolated_data_dir / "projection-trace" / "tool-calls.jsonl"
    monkeypatch.setenv("LIFE_INDEX_VALIDATION_MODE", "1")
    monkeypatch.setenv("LIFE_INDEX_TOOL_CALL_LOG", str(trace_path))

    _seed_data(isolated_data_dir)
    before = _snapshot(isolated_data_dir)

    assert dispatch("search", {"query": "needle"})["success"] is True

    after = _snapshot(isolated_data_dir)
    assert _non_index_snapshot(after) == _non_index_snapshot(before)
    assert not trace_path.exists()
