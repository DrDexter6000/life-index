#!/usr/bin/env python3

from pathlib import Path


def _write_journal(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_backfill_finds_journals_without_sentiment(isolated_data_dir: Path) -> None:
    from tools.dev.backfill_sentiment import find_journals_without_sentiment

    journal = isolated_data_dir / "Journals" / "2026" / "04" / "a.md"
    _write_journal(journal, '---\ntitle: "x"\ndate: 2026-04-03\n---\n\n# x\n\nbody')

    pending = find_journals_without_sentiment()

    assert journal in pending


def test_backfill_writes_sentiment_to_frontmatter(
    isolated_data_dir: Path, monkeypatch
) -> None:
    import tools.lib.content_analysis as content_analysis
    from tools.dev.backfill_sentiment import backfill_sentiment

    journal = isolated_data_dir / "Journals" / "2026" / "04" / "a.md"
    _write_journal(journal, '---\ntitle: "x"\ndate: 2026-04-03\n---\n\n# x\n\n开心')

    monkeypatch.setattr(
        content_analysis, "generate_sentiment_score", lambda _content: 0.7
    )

    result = backfill_sentiment(dry_run=False, batch_size=10)

    assert result["updated"] == 1
    assert "sentiment_score: 0.7" in journal.read_text(encoding="utf-8")


def test_backfill_dry_run_no_write(isolated_data_dir: Path, monkeypatch) -> None:
    import tools.lib.content_analysis as content_analysis
    from tools.dev.backfill_sentiment import backfill_sentiment

    journal = isolated_data_dir / "Journals" / "2026" / "04" / "a.md"
    original = '---\ntitle: "x"\ndate: 2026-04-03\n---\n\n# x\n\n开心'
    _write_journal(journal, original)

    monkeypatch.setattr(
        content_analysis, "generate_sentiment_score", lambda _content: 0.7
    )

    result = backfill_sentiment(dry_run=True, batch_size=10)

    assert result["updated"] == 0
    assert journal.read_text(encoding="utf-8") == original


def test_backfill_skips_already_scored(isolated_data_dir: Path, monkeypatch) -> None:
    import tools.lib.content_analysis as content_analysis
    from tools.dev.backfill_sentiment import backfill_sentiment

    journal = isolated_data_dir / "Journals" / "2026" / "04" / "a.md"
    _write_journal(
        journal,
        '---\ntitle: "x"\ndate: 2026-04-03\nsentiment_score: 0.4\n---\n\n# x\n\n开心',
    )

    monkeypatch.setattr(
        content_analysis, "generate_sentiment_score", lambda _content: 0.7
    )

    result = backfill_sentiment(dry_run=False, batch_size=10)

    assert result["updated"] == 0
