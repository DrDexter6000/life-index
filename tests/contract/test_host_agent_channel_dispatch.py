"""Behavior contracts for the transport-neutral Host Agent dispatcher."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import fields
from pathlib import Path
from typing import Any

import pytest


def _seed_journal(data_dir: Path, *, date: str, seq: str, body: str) -> str:
    year, month, _day = date.split("-")
    journal_path = data_dir / "Journals" / year / month / f"life-index_{date}_{seq}.md"
    journal_path.parent.mkdir(parents=True, exist_ok=True)
    journal_path.write_text(
        f'---\ntitle: "{seq}"\ndate: {date}\ntopic: ["work"]\n---\n{body}\n',
        encoding="utf-8",
    )
    return journal_path.relative_to(data_dir).as_posix()


def _stable_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Remove observability values that are intentionally per invocation."""
    stable = deepcopy(payload)
    stable.pop("events", None)
    stable.pop("_trace", None)
    stable.pop("provenance", None)
    performance = stable.get("performance")
    if isinstance(performance, dict):
        performance.clear()
    return stable


def _search_kwargs(params: object) -> dict[str, Any]:
    return {field.name: getattr(params, field.name) for field in fields(params)}


def test_health_dispatch_matches_the_direct_canonical_application() -> None:
    from tools.__main__ import build_health_payload
    from tools.host_agent_channel.dispatcher import dispatch

    direct = build_health_payload()
    via_dispatcher = dispatch("health", {})

    assert _stable_payload(via_dispatcher) == _stable_payload(direct)


@pytest.mark.parametrize(
    ("selector", "expected_success", "expected_code"),
    [
        ({"path": "Journals/2026/05/life-index_2026-05-28_001.md"}, True, None),
        ({"id": "Journals/2026/05/life-index_2026-05-28_001.md"}, True, None),
        ({"path": "Journals/2026/05/life-index_2026-05-29_001.md"}, False, "JOURNAL_NOT_FOUND"),
        ({"path": "../outside.md"}, False, "JOURNAL_PATH_INVALID"),
    ],
)
def test_journal_get_dispatch_matches_direct_canonical_application(
    isolated_data_dir: Path,
    selector: dict[str, str],
    expected_success: bool,
    expected_code: str | None,
) -> None:
    from tools.host_agent_channel.dispatcher import dispatch
    from tools.journal.__main__ import run_journal_get

    rel_path = _seed_journal(
        isolated_data_dir,
        date="2026-05-28",
        seq="001",
        body="Canonical journal channel entry.",
    )
    resolved_selector = {
        key: (rel_path if value == "Journals/2026/05/life-index_2026-05-28_001.md" else value)
        for key, value in selector.items()
    }

    direct = run_journal_get(**resolved_selector)
    via_dispatcher = dispatch("journal.get", resolved_selector)

    assert via_dispatcher == direct
    assert via_dispatcher["success"] is expected_success
    if expected_code is not None:
        assert via_dispatcher["error"]["code"] == expected_code


@pytest.mark.parametrize("selector", [{}, {"path": "one", "id": "two"}])
def test_journal_get_requires_exactly_one_selector_before_core_execution(
    monkeypatch,
    selector: dict[str, str],
) -> None:
    import tools.host_agent_channel.dispatcher as dispatcher

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("invalid journal selectors reached Core")

    monkeypatch.setattr(dispatcher, "_dispatch_registered", fail_if_called)

    with pytest.raises(dispatcher.InvalidParameters, match="exactly one"):
        dispatcher.dispatch("journal.get", selector)


@pytest.mark.parametrize(
    "params",
    [
        {"query": "needle"},
        {"query": "needle", "limit": 0},
        {"query": "needle", "limit": 1, "offset": 1},
        {"query": "not-present"},
    ],
)
def test_search_dispatch_matches_direct_canonical_application(
    isolated_data_dir: Path,
    params: dict[str, Any],
) -> None:
    from tools.host_agent_channel.dispatcher import dispatch
    from tools.host_agent_channel.registry import SearchParams
    from tools.search_journals.__main__ import run_search

    _seed_journal(
        isolated_data_dir,
        date="2026-05-27",
        seq="001",
        body="needle appears in the first canonical entry.",
    )
    _seed_journal(
        isolated_data_dir,
        date="2026-05-28",
        seq="001",
        body="needle appears in the second canonical entry.",
    )
    typed = SearchParams(**params)

    # Warm the one permitted derived-state refresh, then compare equal inputs.
    run_search(**_search_kwargs(typed))
    direct = run_search(**_search_kwargs(typed))
    via_dispatcher = dispatch("search", params)

    assert _stable_payload(via_dispatcher) == _stable_payload(direct)
    if typed.query == "not-present":
        assert via_dispatcher["success"] is True
        assert via_dispatcher["total_matches"] == 0


@pytest.mark.parametrize(
    "params",
    [
        {"query": "needle", "level": 4},
        {"query": "needle", "level": True},
        {"query": "needle", "year": "2026"},
        {"query": "needle", "month": True},
        {"query": "needle", "limit": -1},
        {"query": "needle", "limit": True},
        {"query": "needle", "offset": -1},
        {"query": "needle", "use_index": "yes"},
        {"query": "needle", "semantic_weight": "1.0"},
    ],
)
def test_search_rejects_invalid_channel_parameters_before_core_execution(
    monkeypatch,
    params: dict[str, Any],
) -> None:
    import tools.host_agent_channel.dispatcher as dispatcher

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("invalid search parameters reached Core")

    monkeypatch.setattr(dispatcher, "_dispatch_registered", fail_if_called)

    with pytest.raises(dispatcher.InvalidParameters):
        dispatcher.dispatch("search", params)


def test_source_safe_search_preserves_metadata_filters_and_relation_context(
    isolated_data_dir: Path,
) -> None:
    """The read channel derives relation evidence from journals, not cache writes."""
    from tools.build_index import build_all
    from tools.host_agent_channel.dispatcher import dispatch
    from tools.search_journals.__main__ import run_search

    target_path = _seed_journal(
        isolated_data_dir,
        date="2026-05-27",
        seq="001",
        body="needle appears in the related target journal.",
    )
    target_file = isolated_data_dir / target_path
    target_file.write_text(
        "---\n"
        'title: "needle target"\n'
        "date: 2026-05-27\n"
        'topic: ["work"]\n'
        "---\n"
        "needle appears in the related target journal.\n",
        encoding="utf-8",
    )
    source_path = isolated_data_dir / "Journals" / "2026" / "05" / "life-index_2026-05-28_001.md"
    source_path.write_text(
        "---\n"
        'title: "needle relation source"\n'
        "date: 2026-05-28\n"
        'topic: ["work"]\n'
        f"related_entries: [{target_path}]\n"
        "---\n"
        "needle appears in the relation source journal.\n",
        encoding="utf-8",
    )
    build_all(incremental=False)

    params = {"query": "needle", "topic": "work"}
    direct = run_search(**params)
    via_dispatcher = dispatch("search", params)

    assert [item["rel_path"] for item in via_dispatcher["l2_results"]] == [
        item["rel_path"] for item in direct["l2_results"]
    ]
    source_rel_path = source_path.relative_to(isolated_data_dir).as_posix()
    direct_l2_source = next(
        item for item in direct["l2_results"] if item["rel_path"] == source_rel_path
    )
    dispatched_l2_source = next(
        item for item in via_dispatcher["l2_results"] if item["rel_path"] == source_rel_path
    )
    direct_target = next(
        item for item in direct["merged_results"] if item["rel_path"] == target_path
    )
    dispatched_target = next(
        item for item in via_dispatcher["merged_results"] if item["rel_path"] == target_path
    )
    direct_source = next(
        item for item in direct["merged_results"] if item["rel_path"] == source_rel_path
    )
    dispatched_source = next(
        item for item in via_dispatcher["merged_results"] if item["rel_path"] == source_rel_path
    )
    assert dispatched_target["topic"] == direct_target["topic"]
    assert dispatched_target["backlinked_by"] == direct_target["backlinked_by"]
    assert dispatched_l2_source["metadata"]["related_entries"] == [target_path]
    assert dispatched_l2_source["metadata"] == direct_l2_source["metadata"]
    assert dispatched_source["related_entries"] == direct_source["related_entries"]
