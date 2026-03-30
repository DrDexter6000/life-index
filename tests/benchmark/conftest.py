"""
Benchmark test fixtures.

Provides synthetic journal data for performance benchmarking.
"""

import sqlite3
import tempfile
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Synthetic journal data generators
# ---------------------------------------------------------------------------


def _make_journals(n: int) -> List[Dict[str, Any]]:
    """Generate n synthetic journal metadata dicts."""
    journals = []
    for i in range(n):
        month = (i % 12) + 1
        day = (i % 28) + 1
        journals.append(
            {
                "path": f"Journals/2026/{month:02d}/life-index_2026-{month:02d}-{day:02d}_{(i % 5) + 1:03d}.md",
                "title": f"Benchmark journal entry {i}",
                "date": f"2026-{month:02d}-{day:02d}",
                "location": "Lagos, Nigeria" if i % 3 == 0 else "Chongqing, China",
                "weather": "晴天 28°C" if i % 2 == 0 else "阴天 22°C",
                "topic": ["work", "learn"][i % 2],
                "project": ["LifeIndex", "Parenting"][i % 2],
                "tags": ["benchmark", "test", f"tag_{i % 10}"],
                "mood": ["专注", "充实"][i % 2],
                "people": ["乐乐"] if i % 4 == 0 else [],
                "abstract": f"This is benchmark journal {i} about daily life and reflections.",
                "content": (
                    f"# Benchmark journal entry {i}\n\n"
                    f"This is a test journal entry for benchmarking purposes. "
                    f"It contains some keywords like 乐乐, LifeIndex, parenting, "
                    f"reflection, and other common terms used in real journals. "
                    f"Entry number {i} is about {'work' if i % 2 == 0 else 'life'}.\n\n"
                    f"Additional content paragraph to make the entry more realistic. "
                    f"Keywords: benchmark, test, performance, search, semantic."
                ),
            }
        )
    return journals


def _build_fts_db(db_path: Path, journals: List[Dict[str, Any]]) -> None:
    """Build a FTS5 database from synthetic journal data."""
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS journals USING fts5(
            path, title, content, date, location, weather,
            topic, project, tags, mood, people,
            tokenize = 'unicode61'
        )
    """
    )
    for j in journals:
        import json

        cursor.execute(
            "INSERT INTO journals(path, title, content, date, location, weather, "
            "topic, project, tags, mood, people) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                j["path"],
                j["title"],
                j["content"],
                j["date"],
                j["location"],
                j["weather"],
                j["topic"] if isinstance(j["topic"], str) else json.dumps(j["topic"]),
                j["project"],
                json.dumps(j["tags"]),
                json.dumps(j["mood"]) if isinstance(j["mood"], list) else j["mood"],
                json.dumps(j["people"]),
            ),
        )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def synthetic_journals_100() -> List[Dict[str, Any]]:
    """100 synthetic journal entries."""
    return _make_journals(100)


@pytest.fixture(scope="session")
def synthetic_journals_500() -> List[Dict[str, Any]]:
    """500 synthetic journal entries."""
    return _make_journals(500)


@pytest.fixture(scope="session")
def fts_db_100(
    synthetic_journals_100: List[Dict[str, Any]],
    tmp_path_factory: pytest.TempPathFactory,
) -> Path:
    """FTS5 database with 100 entries."""
    db_path = tmp_path_factory.mktemp("fts") / "journals_fts_100.db"
    _build_fts_db(db_path, synthetic_journals_100)
    return db_path


@pytest.fixture(scope="session")
def fts_db_500(
    synthetic_journals_500: List[Dict[str, Any]],
    tmp_path_factory: pytest.TempPathFactory,
) -> Path:
    """FTS5 database with 500 entries."""
    db_path = tmp_path_factory.mktemp("fts") / "journals_fts_500.db"
    _build_fts_db(db_path, synthetic_journals_500)
    return db_path


@pytest.fixture(scope="session")
def l2_metadata_100(
    synthetic_journals_100: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """L2 metadata results simulating search_l2_metadata output."""
    return [
        {
            "path": j["path"],
            "title": j["title"],
            "date": j["date"],
            "location": j["location"],
            "weather": j["weather"],
            "topic": j["topic"],
            "project": j["project"],
            "tags": j["tags"],
            "mood": j["mood"],
            "people": j["people"],
            "abstract": j["abstract"],
        }
        for j in synthetic_journals_100
    ]
