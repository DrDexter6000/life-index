from __future__ import annotations

from pathlib import Path


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
