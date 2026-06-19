from __future__ import annotations

from pathlib import Path


def _write_journal(
    data_dir: Path,
    *,
    date: str,
    title: str,
    seq: str = "001",
    extra_frontmatter: str = "",
) -> Path:
    year, month, _day = date.split("-")
    journal_dir = data_dir / "Journals" / year / month
    journal_dir.mkdir(parents=True, exist_ok=True)
    path = journal_dir / f"life-index_{date}_{seq}.md"
    lines = ["---", f'title: "{title}"', f"date: {date}"]
    if extra_frontmatter:
        lines.extend(extra_frontmatter.rstrip().splitlines())
    lines.extend(["---", "", f"# {title}", "", "Fixture body"])
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def test_navigate_filters_values_by_month_scope_and_intersects_facets(
    tmp_path: Path, monkeypatch
) -> None:
    from tools.index_tree.core import build_navigate_payload

    data_dir = tmp_path / "Life-Index"
    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(data_dir))

    hit = _write_journal(
        data_dir,
        date="2026-03-14",
        title="AI Work Lagos",
        extra_frontmatter=(
            'project: "Life Index"\n'
            'tags: ["ai", "planning"]\n'
            'location: "Lagos, Nigeria"\n'
            'people: ["Alice"]'
        ),
    )
    _write_journal(
        data_dir,
        date="2026-03-15",
        title="Other AI Lagos",
        extra_frontmatter=(
            'project: "Other"\n' 'tags: ["ai"]\n' 'location: "Lagos, Nigeria"\n' 'people: ["Alice"]'
        ),
    )
    _write_journal(
        data_dir,
        date="2026-04-01",
        title="AI Work London",
        extra_frontmatter=(
            'project: "Life Index"\n'
            'tags: ["ai"]\n'
            'location: "London, United Kingdom"\n'
            'people: ["Alice"]'
        ),
    )

    payload = build_navigate_payload(
        date_from="2026-03",
        date_to="2026-03",
        operations=[
            {
                "type": "facet_value_filter",
                "facet": "location",
                "values": ["Lagos, Nigeria"],
                "match": "any",
            },
            {
                "type": "facet_value_filter",
                "facet": "project",
                "values": ["Life Index"],
                "match": "any",
            },
            {
                "type": "facet_value_filter",
                "facet": "tag",
                "values": ["ai"],
                "match": "any",
            },
        ],
    )

    assert payload["success"] is True
    assert payload["command"] == "index-tree.navigate"
    assert payload["data"]["source"] == "index-b"
    assert payload["data"]["exhaustive"] is True
    assert payload["data"]["count"] == 1
    assert payload["data"]["entries"][0]["path"] == hit.relative_to(data_dir).as_posix()
    assert payload["data"]["entry_pointers"] == [hit.relative_to(data_dir).as_posix()]
    assert ".life-index/index-b/INDEX.md" in payload["data"]["navigation_docs"]
    assert ".life-index/index-b/Journals/2026/03/index.md" in payload["data"]["navigation_docs"]


def test_discover_returns_scoped_facet_value_menu_without_natural_language_inference(
    tmp_path: Path, monkeypatch
) -> None:
    from tools.index_tree.core import build_discover_payload

    data_dir = tmp_path / "Life-Index"
    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(data_dir))

    march_lagos = _write_journal(
        data_dir,
        date="2026-03-14",
        title="March Lagos AI",
        extra_frontmatter=(
            'project: "Life Index"\n' 'tags: ["ai", "planning"]\n' 'location: "Lagos, Nigeria"\n'
        ),
    )
    _write_journal(
        data_dir,
        date="2026-03-15",
        title="March London",
        extra_frontmatter='project: "Other"\ntags: ["travel"]\nlocation: "London, United Kingdom"',
    )
    _write_journal(
        data_dir,
        date="2026-04-01",
        title="April Lagos",
        extra_frontmatter='project: "Life Index"\ntags: ["ai"]\nlocation: "Lagos, Nigeria"',
    )

    payload = build_discover_payload(
        date_from="2026-03",
        date_to="2026-03",
        facets=["location", "project", "tag"],
    )

    assert payload["success"] is True
    assert payload["command"] == "index-tree.discover"
    assert payload["data"]["operation_model"] == "deterministic_navigation.v1"
    assert payload["data"]["exhaustive"] is True
    assert payload["data"]["coverage"]["candidate_count"] == 2
    assert payload["data"]["facets"]["location"]["values"] == [
        {
            "value": "Lagos, Nigeria",
            "count": 1,
            "sample_entry_pointers": [march_lagos.relative_to(data_dir).as_posix()],
        },
        {
            "value": "London, United Kingdom",
            "count": 1,
            "sample_entry_pointers": ["Journals/2026/03/life-index_2026-03-15_001.md"],
        },
    ]
    assert payload["data"]["facets"]["project"]["values"][0]["value"] == "Life Index"
    assert payload["data"]["facets"]["tag"]["values"][0]["value"] == "ai"
    assert payload["data"]["selection_contract"] == (
        "host_agent_selects_values; tool_executes_only"
    )


def test_navigate_exhaustive_result_matches_full_scan(tmp_path: Path, monkeypatch) -> None:
    from tools.index_tree.core import build_navigate_payload

    data_dir = tmp_path / "Life-Index"
    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(data_dir))

    match_a = _write_journal(
        data_dir,
        date="2026-03-10",
        title="Lagos Work A",
        extra_frontmatter='location: "Lagos, Nigeria"\nproject: "Life Index"',
    )
    match_b = _write_journal(
        data_dir,
        date="2026-04-11",
        title="Abuja Work B",
        extra_frontmatter='location: "Abuja, Nigeria"\nproject: "Life Index"',
    )
    _write_journal(
        data_dir,
        date="2026-05-12",
        title="London Work C",
        extra_frontmatter='location: "London, United Kingdom"\nproject: "Life Index"',
    )
    _write_journal(
        data_dir,
        date="2026-04-13",
        title="Abuja Other D",
        extra_frontmatter='location: "Abuja, Nigeria"\nproject: "Other"',
    )

    payload = build_navigate_payload(
        date_from="2026-03",
        date_to="2026-06",
        operations=[
            {
                "type": "facet_value_filter",
                "facet": "location",
                "values": ["Lagos, Nigeria", "Abuja, Nigeria"],
                "match": "any",
            },
            {
                "type": "facet_value_filter",
                "facet": "project",
                "values": ["Life Index"],
                "match": "any",
            },
        ],
    )

    expected = {
        match_a.relative_to(data_dir).as_posix(),
        match_b.relative_to(data_dir).as_posix(),
    }
    assert set(payload["data"]["entry_pointers"]) == expected
    assert payload["data"]["count"] == len(expected)
    assert payload["data"]["coverage"]["candidate_count_before_filters"] == 4
    assert payload["data"]["coverage"]["candidate_count_after_filters"] == 2


def test_navigate_rejects_unknown_operation_without_natural_language_inference(
    tmp_path: Path, monkeypatch
) -> None:
    from tools.index_tree.core import build_navigate_payload

    data_dir = tmp_path / "Life-Index"
    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(data_dir))

    payload = build_navigate_payload(
        date_from="2026-03",
        date_to="2026-03",
        operations=[{"type": "natural_language", "query": "find Nigeria-ish places"}],
    )

    assert payload["success"] is False
    assert payload["errors"][0]["code"] == "INDEX_TREE_NAVIGATE_INVALID_OPERATION"
