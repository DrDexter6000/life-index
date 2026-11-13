from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml


def _write_journal(data_dir: Path) -> Path:
    journal = data_dir / "Journals" / "2026" / "03" / "life-index_2026-03-14_001.md"
    journal.parent.mkdir(parents=True, exist_ok=True)
    journal.write_text(
        "\n".join(
            [
                "---",
                'title: "Fallback Work"',
                "date: 2026-03-14",
                'tags: ["fallback"]',
                "---",
                "",
                "# Fallback Work",
                "",
                "fallback body",
            ]
        ),
        encoding="utf-8",
    )
    return journal


def _write_journal_with_frontmatter(
    data_dir: Path,
    *,
    date: str,
    title: str,
    extra_frontmatter: str,
    seq: str = "001",
) -> Path:
    year, month, _day = date.split("-")
    journal = data_dir / "Journals" / year / month / f"life-index_{date}_{seq}.md"
    journal.parent.mkdir(parents=True, exist_ok=True)
    journal.write_text(
        "\n".join(
            [
                "---",
                f'title: "{title}"',
                f"date: {date}",
                *extra_frontmatter.rstrip().splitlines(),
                "---",
                "",
                f"# {title}",
                "",
                "fixture body",
            ]
        ),
        encoding="utf-8",
    )
    return journal


def test_ensure_payload_falls_back_to_journals_when_refresh_fails(tmp_path, monkeypatch):
    from tools.index_tree import materialize

    data_dir = tmp_path / "Life-Index"
    journal = _write_journal(data_dir)
    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(data_dir))

    def _fail_refresh(*args, **kwargs):
        raise RuntimeError("simulated refresh failure")

    monkeypatch.setattr(materialize, "build_materialize_payload", _fail_refresh)

    payload = materialize.build_ensure_payload(date_from="2026-03", date_to="2026-03")

    assert payload["source"] == "journals"
    assert payload["fallback"]["used"] is True
    assert "simulated refresh failure" in payload["fallback"]["reason"]
    assert payload["entry_count"] == 1
    assert payload["entries"][0]["path"] == journal.relative_to(data_dir).as_posix()


def test_ensure_payload_reports_freshness_after_successful_refresh(tmp_path, monkeypatch):
    from tools.index_tree import materialize

    data_dir = tmp_path / "Life-Index"
    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(data_dir))
    _write_journal(data_dir)

    payload = materialize.build_ensure_payload(date_from="2026-03", date_to="2026-03")

    assert payload["source"] == "index-b"
    assert payload["freshness_before"]["fresh"] is False
    assert payload["freshness"]["fresh"] is True
    assert payload["fallback"]["used"] is False


def test_materialize_canonicalizes_entity_graph_aliases_and_records_hash(
    tmp_path: Path, monkeypatch
) -> None:
    from tools.index_tree import materialize

    data_dir = tmp_path / "Life-Index"
    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(data_dir))
    _write_journal_with_frontmatter(
        data_dir,
        date="2026-03-14",
        title="Alias Project A",
        extra_frontmatter='project: "Life-Index"',
    )
    _write_journal_with_frontmatter(
        data_dir,
        date="2026-03-15",
        title="Alias Project B",
        extra_frontmatter='project: "Life Index 2.0"',
    )
    (data_dir / "entity_graph.yaml").write_text(
        yaml.safe_dump(
            {
                "entities": [
                    {
                        "id": "project-life-index",
                        "type": "project",
                        "primary_name": "Life Index",
                        "aliases": ["Life-Index", "Life Index 2.0"],
                    }
                ]
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    payload = materialize.build_materialize_payload(date_from="2026-03", date_to="2026-03")

    month_doc = data_dir / ".life-index" / "index-b" / "Journals" / "2026" / "03" / "index.md"
    manifest = json.loads(
        (data_dir / ".life-index" / "index-b" / "manifest.json").read_text(encoding="utf-8")
    )
    scope = manifest["scopes"]["month:2026-03"]
    assert payload["canonicalization"]["status"] == "active"
    assert scope["canonicalization_hash"]
    assert "| Life Index | 2 |" in month_doc.read_text(encoding="utf-8")
    assert "| Life-Index |" not in month_doc.read_text(encoding="utf-8")
    assert "| Life Index 2.0 |" not in month_doc.read_text(encoding="utf-8")


def test_freshness_marks_scope_stale_when_canonicalization_hash_changes(
    tmp_path: Path, monkeypatch
) -> None:
    from tools.index_tree import materialize

    data_dir = tmp_path / "Life-Index"
    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(data_dir))
    _write_journal_with_frontmatter(
        data_dir,
        date="2026-03-14",
        title="Alias Project",
        extra_frontmatter='project: "Life-Index"',
    )
    (data_dir / "entity_graph.yaml").write_text(
        yaml.safe_dump({"entities": []}, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    materialize.build_materialize_payload(date_from="2026-03", date_to="2026-03")

    (data_dir / "entity_graph.yaml").write_text(
        yaml.safe_dump(
            {
                "entities": [
                    {
                        "id": "project-life-index",
                        "type": "project",
                        "primary_name": "Life Index",
                        "aliases": ["Life-Index"],
                    }
                ]
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    payload = materialize.build_freshness_payload(date_from="2026-03", date_to="2026-03")

    assert payload["fresh"] is False
    assert payload["reasons"]["month:2026-03"] == "canonicalization_hash_mismatch"


# The one date rule for the index-b entry table: a fragment whose frontmatter
# date is missing or malformed is still collected in range and its Entry
# Pointers row shows the day the shared rule gives (file-name day for the
# first three shapes), never the malformed text.
INDEX_B_DATE_SHAPES: dict[str, bytes] = {
    "no_frontmatter": b"no-frontmatter shape body\n",
    "date_digit_run_on": b"---\ntitle: Digit Run On\ndate: 20260311\n---\n\nbody\n",
    "date_list": b"---\ntitle: List Date\ndate: [2026]\n---\n\nbody\n",
    "date_tz_datetime": (
        b"---\ntitle: Tz Datetime\ndate: 2026-03-11T19:43:02+08:00\n---\n\nbody\n"
    ),
}

# The label each shape's row shows: the verbatim title, or (for the file with
# no frontmatter block, whose scan body is empty) the file stem.
INDEX_B_SHAPE_LABELS: dict[str, str] = {
    "no_frontmatter": "{stem}",
    "date_digit_run_on": "Digit Run On",
    "date_list": "List Date",
    "date_tz_datetime": "Tz Datetime",
}


def _write_index_b_shapes(data_dir: Path) -> None:
    month_dir = data_dir / "Journals" / "2026" / "03"
    month_dir.mkdir(parents=True, exist_ok=True)
    for seq, (_shape, payload) in enumerate(sorted(INDEX_B_DATE_SHAPES.items()), start=1):
        (month_dir / f"life-index_2026-03-11_{seq:03d}.md").write_bytes(payload)


@pytest.mark.parametrize("shape", sorted(INDEX_B_DATE_SHAPES))
def test_index_b_entry_table_dates_each_shape_by_the_shared_rule(tmp_path, monkeypatch, shape):
    from tools.index_tree import materialize

    data_dir = tmp_path / "Life-Index"
    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(data_dir))
    _write_index_b_shapes(data_dir)

    payload = materialize.build_materialize_payload(date_from="2026-03", date_to="2026-03")

    assert payload["entry_count"] == 4, shape
    month_doc = data_dir / ".life-index" / "index-b" / "Journals" / "2026" / "03" / "index.md"
    content = month_doc.read_text(encoding="utf-8")
    seq = sorted(INDEX_B_DATE_SHAPES).index(shape) + 1
    stem = f"life-index_2026-03-11_{seq:03d}"
    label = INDEX_B_SHAPE_LABELS[shape].format(stem=stem)
    assert f"| 2026-03-11 | {label} | Journals/2026/03/{stem}.md |" in content, shape


def test_date_range_read_includes_malformed_date_by_filename_day(tmp_path, monkeypatch):
    from tools.index_tree import materialize

    data_dir = tmp_path / "Life-Index"
    month_dir = data_dir / "Journals" / "2026" / "03"
    month_dir.mkdir(parents=True)
    (month_dir / "life-index_2026-03-11_001.md").write_bytes(
        INDEX_B_DATE_SHAPES["date_digit_run_on"]
    )
    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(data_dir))

    def _fail_refresh(*args, **kwargs):
        raise RuntimeError("simulated refresh failure")

    monkeypatch.setattr(materialize, "build_materialize_payload", _fail_refresh)

    payload = materialize.build_ensure_payload(date_from="2026-03", date_to="2026-03")

    assert payload["source"] == "journals"
    assert payload["entry_count"] == 1
    assert payload["entries"][0]["date"] == "2026-03-11"
