#!/usr/bin/env python3

from tools.lib.related_candidates import suggest_related_entries


def test_suggest_related_entries_prefers_same_people_project_topic() -> None:
    current = {
        "path": "Journals/2026/04/current.md",
        "date": "2026-04-03",
        "topic": ["work"],
        "people": ["Alice"],
        "project": "Life-Index",
        "tags": ["search", "ranking"],
    }
    entries = [
        {
            "rel_path": "Journals/2026/04/high.md",
            "date": "2026-04-01",
            "title": "High",
            "abstract": "High match",
            "topic": ["work"],
            "people": ["Alice"],
            "project": "Life-Index",
            "tags": ["search", "ranking"],
            "related_entries": [],
        },
        {
            "rel_path": "Journals/2026/04/low.md",
            "date": "2026-01-01",
            "title": "Low",
            "abstract": "Low match",
            "topic": ["life"],
            "people": ["Bob"],
            "project": "Other",
            "tags": ["misc"],
            "related_entries": [],
        },
    ]

    candidates = suggest_related_entries(current, entries, max_candidates=5)

    assert candidates[0]["rel_path"] == "Journals/2026/04/high.md"
    assert candidates[0]["score"] > 0
    assert any(reason["type"] == "same_people" for reason in candidates[0]["reasons"])
    assert any(reason["type"] == "same_project" for reason in candidates[0]["reasons"])


def test_suggest_related_entries_skips_self_and_existing_relations() -> None:
    current = {
        "path": "Journals/2026/04/current.md",
        "date": "2026-04-03",
        "topic": ["work"],
        "people": ["Alice"],
        "project": "Life-Index",
        "tags": ["search", "ranking"],
        "related_entries": ["Journals/2026/04/already.md"],
    }
    entries = [
        {
            "rel_path": "Journals/2026/04/current.md",
            "date": "2026-04-03",
            "title": "Self",
            "abstract": "Self",
            "topic": ["work"],
            "people": ["Alice"],
            "project": "Life-Index",
            "tags": ["search", "ranking"],
            "related_entries": [],
        },
        {
            "rel_path": "Journals/2026/04/already.md",
            "date": "2026-04-02",
            "title": "Already linked",
            "abstract": "Already linked",
            "topic": ["work"],
            "people": ["Alice"],
            "project": "Life-Index",
            "tags": ["search", "ranking"],
            "related_entries": [],
        },
    ]

    candidates = suggest_related_entries(current, entries, max_candidates=5)

    assert candidates == []


def test_suggest_related_entries_includes_structured_reasons_and_human_summary() -> (
    None
):
    current = {
        "path": "Journals/2026/04/current.md",
        "date": "2026-04-03",
        "topic": ["work"],
        "people": ["Alice"],
        "project": "Life-Index",
        "tags": ["search", "ranking"],
    }
    entries = [
        {
            "rel_path": "Journals/2026/04/high.md",
            "date": "2026-04-01",
            "title": "High",
            "abstract": "High match",
            "topic": ["work"],
            "people": ["Alice"],
            "project": "Life-Index",
            "tags": ["search", "ranking"],
            "related_entries": [],
        }
    ]

    candidates = suggest_related_entries(current, entries, max_candidates=5)

    assert candidates[0]["match_reason"]
    assert candidates[0]["reasons"]
    assert candidates[0]["score_breakdown"]
    assert candidates[0]["score"] == sum(
        item["score"] for item in candidates[0]["score_breakdown"]
    )


def test_suggest_related_entries_assigns_stable_candidate_ids() -> None:
    current = {
        "path": "Journals/2026/04/current.md",
        "date": "2026-04-03",
        "topic": ["work"],
        "people": ["Alice"],
        "project": "Life-Index",
        "tags": ["search", "ranking"],
    }
    entries = [
        {
            "rel_path": "Journals/2026/04/a.md",
            "date": "2026-04-01",
            "title": "A",
            "abstract": "A match",
            "topic": ["work"],
            "people": ["Alice"],
            "project": "Life-Index",
            "tags": ["search", "ranking"],
            "related_entries": [],
        },
        {
            "rel_path": "Journals/2026/04/b.md",
            "date": "2026-04-02",
            "title": "B",
            "abstract": "B match",
            "topic": ["work"],
            "people": ["Alice"],
            "project": "Life-Index",
            "tags": ["search", "ranking"],
            "related_entries": [],
        },
    ]

    candidates = suggest_related_entries(current, entries, max_candidates=5)

    assert [candidate["candidate_id"] for candidate in candidates] == [1, 2]
