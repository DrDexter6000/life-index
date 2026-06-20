from __future__ import annotations

import json
from pathlib import Path

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
