from __future__ import annotations

from pathlib import Path
import yaml


def _write_journal(
    data_dir: Path,
    *,
    date: str,
    title: str,
    seq: str = "001",
    extra_frontmatter: str = "",
    body: str = "Fixture body",
) -> Path:
    year, month, _day = date.split("-")
    journal_dir = data_dir / "Journals" / year / month
    journal_dir.mkdir(parents=True, exist_ok=True)
    path = journal_dir / f"life-index_{date}_{seq}.md"
    lines = ["---", f'title: "{title}"', f"date: {date}"]
    if extra_frontmatter:
        lines.extend(extra_frontmatter.rstrip().splitlines())
    lines.extend(["---", "", f"# {title}", "", body])
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
            'topic: ["work"]\n'
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
            'topic: ["life"]\n'
            'project: "Other"\n'
            'tags: ["ai"]\n'
            'location: "Lagos, Nigeria"\n'
            'people: ["Alice"]'
        ),
    )
    _write_journal(
        data_dir,
        date="2026-04-01",
        title="AI Work London",
        extra_frontmatter=(
            'topic: ["work"]\n'
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
                "facet": "topic",
                "values": ["work"],
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


def test_navigate_rejects_removed_task_facet(tmp_path: Path, monkeypatch) -> None:
    from tools.index_tree.core import build_navigate_payload

    data_dir = tmp_path / "Life-Index"
    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(data_dir))
    _write_journal(
        data_dir,
        date="2026-03-14",
        title="Legacy Task Frontmatter",
        extra_frontmatter='task: ["review"]\ntopic: ["work"]',
    )

    payload = build_navigate_payload(
        date_from="2026-03",
        date_to="2026-03",
        operations=[
            {
                "type": "facet_value_filter",
                "facet": "task",
                "values": ["review"],
                "match": "any",
            }
        ],
    )

    assert payload["success"] is False
    assert payload["errors"][0]["code"] == "INDEX_TREE_NAVIGATE_INVALID_OPERATION"
    assert "task" in payload["errors"][0]["message"]


def test_discover_groups_canonical_facet_aliases_and_reports_raw_values(
    tmp_path: Path, monkeypatch
) -> None:
    from tools.index_tree.core import build_discover_payload

    data_dir = tmp_path / "Life-Index"
    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(data_dir))
    _write_journal(
        data_dir,
        date="2026-03-14",
        title="Canonical Project A",
        extra_frontmatter='project: "Life-Index"\ntags: ["ai"]\ntopic: ["work"]',
    )
    _write_journal(
        data_dir,
        date="2026-03-15",
        title="Canonical Project B",
        extra_frontmatter='project: "Life Index 2.0"\ntags: ["AI"]\ntopic: ["work"]',
    )
    _write_journal(
        data_dir,
        date="2026-03-16",
        title="Canonical Topic Remains Raw",
        extra_frontmatter='project: "Other"\ntopic: ["Life-Index"]',
    )
    (data_dir / "entity_graph.yaml").write_text(
        yaml.safe_dump(
            {
                "entities": [
                    {
                        "id": "project-life-index",
                        "type": "project",
                        "primary_name": "Life Index",
                        "aliases": ["life-index", "Life Index 2.0"],
                    },
                    {
                        "id": "concept-ai",
                        "type": "concept",
                        "primary_name": "AI",
                        "aliases": ["ai"],
                    },
                ]
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    payload = build_discover_payload(
        date_from="2026-03",
        date_to="2026-03",
        facets=["project", "tag", "topic"],
    )

    assert payload["success"] is True
    assert payload["data"]["canonicalization"]["status"] == "active"
    assert payload["data"]["facets"]["project"]["values"][0] == {
        "value": "Life Index",
        "count": 2,
        "sample_entry_pointers": [
            "Journals/2026/03/life-index_2026-03-14_001.md",
            "Journals/2026/03/life-index_2026-03-15_001.md",
        ],
        "raw_values": ["Life Index 2.0", "Life-Index"],
    }
    assert payload["data"]["facets"]["tag"]["values"][0]["value"] == "AI"
    assert payload["data"]["facets"]["tag"]["values"][0]["raw_values"] == ["AI", "ai"]
    assert payload["data"]["facets"]["topic"]["values"] == [
        {
            "value": "work",
            "count": 2,
            "sample_entry_pointers": [
                "Journals/2026/03/life-index_2026-03-14_001.md",
                "Journals/2026/03/life-index_2026-03-15_001.md",
            ],
            "raw_values": ["work"],
        },
        {
            "value": "Life-Index",
            "count": 1,
            "sample_entry_pointers": ["Journals/2026/03/life-index_2026-03-16_001.md"],
            "raw_values": ["Life-Index"],
        },
    ]


def test_navigate_matches_canonicalized_facet_values_and_alias_filter(
    tmp_path: Path, monkeypatch
) -> None:
    from tools.index_tree.core import build_navigate_payload

    data_dir = tmp_path / "Life-Index"
    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(data_dir))
    _write_journal(
        data_dir,
        date="2026-03-14",
        title="Life Index Alias A",
        extra_frontmatter='project: "Life-Index"',
    )
    _write_journal(
        data_dir,
        date="2026-03-15",
        title="Life Index Alias B",
        extra_frontmatter='project: "Life Index 2.0"',
    )
    _write_journal(
        data_dir,
        date="2026-03-16",
        title="Other Project",
        extra_frontmatter='project: "Other"',
    )
    (data_dir / "entity_graph.yaml").write_text(
        yaml.safe_dump(
            {
                "entities": [
                    {
                        "id": "project-life-index",
                        "type": "project",
                        "primary_name": "Life Index",
                        "aliases": ["life-index", "Life Index 2.0"],
                    }
                ]
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    payload = build_navigate_payload(
        date_from="2026-03",
        date_to="2026-03",
        operations=[
            {
                "type": "facet_value_filter",
                "facet": "project",
                "values": ["Life Index"],
                "match": "any",
            }
        ],
    )
    alias_payload = build_navigate_payload(
        date_from="2026-03",
        date_to="2026-03",
        operations=[
            {
                "type": "facet_value_filter",
                "facet": "project",
                "values": ["Life-Index"],
                "match": "any",
            }
        ],
    )
    lower_alias_payload = build_navigate_payload(
        date_from="2026-03",
        date_to="2026-03",
        operations=[
            {
                "type": "facet_value_filter",
                "facet": "project",
                "values": ["life-index"],
                "match": "any",
            }
        ],
    )

    expected = [
        "Journals/2026/03/life-index_2026-03-14_001.md",
        "Journals/2026/03/life-index_2026-03-15_001.md",
    ]
    assert payload["success"] is True
    assert payload["data"]["count"] == 2
    assert payload["data"]["entry_pointers"] == expected
    assert alias_payload["data"]["entry_pointers"] == expected
    assert lower_alias_payload["data"]["entry_pointers"] == expected
    assert payload["data"]["entries"][0]["matched_facets"] == {"project": ["Life Index"]}


def test_discover_invalid_entity_graph_keeps_raw_values_with_diagnostic(
    tmp_path: Path, monkeypatch
) -> None:
    from tools.index_tree.core import build_discover_payload

    data_dir = tmp_path / "Life-Index"
    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(data_dir))
    _write_journal(
        data_dir,
        date="2026-03-14",
        title="Raw Alias A",
        extra_frontmatter='project: "Life-Index"',
    )
    _write_journal(
        data_dir,
        date="2026-03-15",
        title="Raw Alias B",
        extra_frontmatter='project: "Life Index 2.0"',
    )
    (data_dir / "entity_graph.yaml").write_text(
        "entities:\n- id: person-alice\n  type: person\n  primary_name: Alice\n"
        "  relationships:\n  - target: missing\n    relation: knows\n",
        encoding="utf-8",
    )

    payload = build_discover_payload(
        date_from="2026-03",
        date_to="2026-03",
        facets=["project"],
    )

    assert payload["success"] is True
    assert payload["data"]["canonicalization"]["status"] == "disabled"
    assert payload["data"]["canonicalization"]["diagnostics"][0]["code"] == "entity_graph_invalid"
    assert [item["value"] for item in payload["data"]["facets"]["project"]["values"]] == [
        "Life Index 2.0",
        "Life-Index",
    ]


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
            'topic: ["work"]\n'
            'project: "Life Index"\n'
            'tags: ["ai", "planning"]\n'
            'location: "Lagos, Nigeria"\n'
        ),
    )
    _write_journal(
        data_dir,
        date="2026-03-15",
        title="March London",
        extra_frontmatter=(
            'topic: ["life"]\n'
            'project: "Other"\n'
            'tags: ["travel"]\n'
            'location: "London, United Kingdom"'
        ),
    )
    _write_journal(
        data_dir,
        date="2026-04-01",
        title="April Lagos",
        extra_frontmatter=(
            'topic: ["work"]\n'
            'project: "Life Index"\n'
            'tags: ["ai"]\n'
            'location: "Lagos, Nigeria"'
        ),
    )

    payload = build_discover_payload(
        date_from="2026-03",
        date_to="2026-03",
        facets=["location", "project", "tag", "topic"],
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
            "raw_values": ["Lagos, Nigeria"],
        },
        {
            "value": "London, United Kingdom",
            "count": 1,
            "sample_entry_pointers": ["Journals/2026/03/life-index_2026-03-15_001.md"],
            "raw_values": ["London, United Kingdom"],
        },
    ]
    assert payload["data"]["facets"]["project"]["values"][0]["value"] == "Life Index"
    assert payload["data"]["facets"]["tag"]["values"][0]["value"] == "ai"
    assert payload["data"]["facets"]["topic"]["values"] == [
        {
            "value": "life",
            "count": 1,
            "sample_entry_pointers": ["Journals/2026/03/life-index_2026-03-15_001.md"],
            "raw_values": ["life"],
        },
        {
            "value": "work",
            "count": 1,
            "sample_entry_pointers": [march_lagos.relative_to(data_dir).as_posix()],
            "raw_values": ["work"],
        },
    ]
    assert payload["data"]["selection_contract"] == (
        "host_agent_selects_values; tool_executes_only"
    )


def test_discover_content_term_is_explicit_corpus_vocabulary(tmp_path: Path, monkeypatch) -> None:
    from tools.index_tree.core import build_discover_payload

    data_dir = tmp_path / "Life-Index"
    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(data_dir))

    sleep_entry = _write_journal(
        data_dir,
        date="2026-03-14",
        title="睡眠和作息记录",
        body="睡眠记录：作息恢复，晚上睡觉更稳定。",
    )
    _write_journal(
        data_dir,
        date="2026-03-15",
        title="中东局势记录",
        body="中东局势和国际新闻观察。",
    )

    default_payload = build_discover_payload(date_from="2026-03", date_to="2026-03")
    assert "content_term" not in default_payload["data"]["facets"]

    payload = build_discover_payload(
        date_from="2026-03",
        date_to="2026-03",
        facets=["content_term"],
    )

    assert payload["success"] is True
    assert set(payload["data"]["facets"]) == {"content_term"}
    menu = payload["data"]["facets"]["content_term"]
    values = {item["value"]: item for item in menu["values"]}
    for term in ["睡眠", "作息", "睡觉"]:
        assert values[term]["sample_entry_pointers"] == [
            sleep_entry.relative_to(data_dir).as_posix()
        ]
    assert menu["selection_hint"] == (
        "Use content_term values as exact search terms or content_term navigation "
        "filters; they are corpus-observed terms, not synonyms."
    )


def test_navigate_content_term_filter_matches_body_terms_without_inference(
    tmp_path: Path, monkeypatch
) -> None:
    from tools.index_tree.core import build_navigate_payload

    data_dir = tmp_path / "Life-Index"
    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(data_dir))

    hit = _write_journal(
        data_dir,
        date="2026-03-14",
        title="作息记录",
        body="睡眠记录：作息恢复，晚上睡觉更稳定。",
    )
    _write_journal(
        data_dir,
        date="2026-03-15",
        title="中东局势记录",
        body="中东局势和国际新闻观察。",
    )

    payload = build_navigate_payload(
        date_from="2026-03",
        date_to="2026-03",
        operations=[
            {
                "type": "facet_value_filter",
                "facet": "content_term",
                "values": ["睡眠"],
                "match": "any",
            }
        ],
    )

    assert payload["success"] is True
    assert payload["data"]["count"] == 1
    assert payload["data"]["entry_pointers"] == [hit.relative_to(data_dir).as_posix()]
    assert payload["data"]["entries"][0]["matched_facets"] == {"content_term": ["睡眠"]}


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


def test_navigate_entity_neighbors_returns_graph_neighbors_without_facet_interference(
    tmp_path: Path, monkeypatch
) -> None:
    from tools.index_tree.core import build_navigate_payload

    data_dir = tmp_path / "Life-Index"
    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(data_dir))
    _write_journal(
        data_dir,
        date="2026-03-14",
        title="Atlas Work",
        extra_frontmatter='project: "Atlas"\npeople: ["Alice"]\nlocation: "London, United Kingdom"',
    )
    _write_journal(
        data_dir,
        date="2026-03-15",
        title="Home Work",
        extra_frontmatter='project: "Home"\npeople: ["Bob"]\nlocation: "London, United Kingdom"',
    )
    (data_dir / "entity_graph.yaml").write_text(
        yaml.safe_dump(
            {
                "entities": [
                    {
                        "id": "person-alice",
                        "type": "actor",
                        "primary_name": "Alice",
                        "aliases": [],
                        "relationships": [
                            {
                                "target": "project-atlas",
                                "relation": "works_on",
                                "supporting_journal_ids": [
                                    "Journals/2026/03/life-index_2026-03-14_001.md"
                                ],
                            }
                        ],
                    },
                    {
                        "id": "project-atlas",
                        "type": "project",
                        "primary_name": "Atlas",
                        "aliases": [],
                        "relationships": [],
                    },
                    {
                        "id": "person-bob",
                        "type": "actor",
                        "primary_name": "Bob",
                        "aliases": [],
                        "relationships": [],
                    },
                ]
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    payload = build_navigate_payload(
        date_from="2026-03",
        date_to="2026-03",
        operations=[
            {"type": "entity_neighbors", "entity": "Alice", "max_hops": 1},
            {
                "type": "facet_value_filter",
                "facet": "location",
                "values": ["London, United Kingdom"],
                "match": "any",
            },
        ],
    )

    assert payload["success"] is True
    assert payload["data"]["implemented_extensions"] == ["entity_neighbors"]
    assert payload["data"]["entity_neighbors"][0]["resolved_entity"]["id"] == "person-alice"
    assert payload["data"]["entity_neighbors"][0]["neighbors"][0]["entity_id"] == ("project-atlas")
    assert payload["data"]["coverage"]["entity_neighbor_operation_count"] == 1
    assert payload["data"]["coverage"]["facet_filter_count"] == 1
    assert payload["data"]["count"] == 1
    assert payload["data"]["entry_pointers"] == ["Journals/2026/03/life-index_2026-03-14_001.md"]


def test_navigate_rejects_invalid_entity_neighbors_operation(tmp_path: Path, monkeypatch) -> None:
    from tools.index_tree.core import build_navigate_payload

    data_dir = tmp_path / "Life-Index"
    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(data_dir))

    payload = build_navigate_payload(
        operations=[{"type": "entity_neighbors", "entity": "Alice", "max_hops": 0}]
    )

    assert payload["success"] is False
    assert payload["errors"][0]["code"] == "INDEX_TREE_NAVIGATE_INVALID_OPERATION"
    assert "max_hops" in payload["errors"][0]["message"]


def test_navigate_entity_neighbors_invalid_graph_returns_structured_diagnostic(
    tmp_path: Path, monkeypatch
) -> None:
    from tools.index_tree.core import build_navigate_payload

    data_dir = tmp_path / "Life-Index"
    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(data_dir))
    data_dir.mkdir(parents=True)
    (data_dir / "entity_graph.yaml").write_text(
        "entities:\n- id: person-alice\n  type: person\n  primary_name: Alice\n"
        "  relationships:\n  - target: missing\n    relation: works_on\n",
        encoding="utf-8",
    )

    payload = build_navigate_payload(
        operations=[{"type": "entity_neighbors", "entity": "Alice", "max_hops": 1}]
    )

    assert payload["success"] is True
    assert payload["data"]["entity_neighbors"][0]["status"] == "entity_graph_invalid"
    assert payload["data"]["entity_neighbors"][0]["neighbors"] == []
    assert payload["data"]["count"] == 0
