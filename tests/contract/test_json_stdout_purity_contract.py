"""Contract tests for JSON stdout purity.

JSON-mode CLI output must be directly parseable from stdout. Dependency load
messages belong on stderr or must be suppressed; callers must not have to scan
for the first ``{``.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

WORKTREE_ROOT = Path(__file__).resolve().parents[2]


def _write_chinese_journal(data_dir: Path) -> None:
    journal_dir = data_dir / "Journals" / "2026" / "07"
    journal_dir.mkdir(parents=True, exist_ok=True)
    (journal_dir / "life-index_2026-07-07_001.md").write_text(
        """---
title: 中文搜索测试
date: 2026-07-07
topic: [test]
---

今天记录了中文分词和搜索测试。
""",
        encoding="utf-8",
    )


def _write_noisy_jieba(fake_module_dir: Path) -> None:
    fake_module_dir.mkdir(parents=True, exist_ok=True)
    (fake_module_dir / "jieba.py").write_text(
        """print("FAKE_JIEBA_IMPORT_STDOUT")

def initialize():
    print("FAKE_JIEBA_INITIALIZE_STDOUT")

def cut(text):
    return [text]

def cut_for_search(text):
    return [text]

def load_userdict(path):
    print("FAKE_JIEBA_USERDICT_STDOUT")
""",
        encoding="utf-8",
    )


def test_search_stdout_is_direct_json_when_jieba_loads_noisily(tmp_path: Path) -> None:
    """The search CLI must not leak dependency load banners before JSON."""
    data_dir = tmp_path / "Life-Index"
    fake_module_dir = tmp_path / "fake_jieba"
    _write_chinese_journal(data_dir)
    _write_noisy_jieba(fake_module_dir)

    env = os.environ.copy()
    env["LIFE_INDEX_DATA_DIR"] = str(data_dir)
    env["PYTHONPATH"] = (
        str(fake_module_dir)
        if not env.get("PYTHONPATH")
        else os.pathsep.join([str(fake_module_dir), env["PYTHONPATH"]])
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "tools.search_journals",
            "--query",
            "中文搜索",
            "--level",
            "3",
            "--no-index",
            "--limit",
            "0",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=WORKTREE_ROOT,
        env=env,
        timeout=60,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["success"] is True
    assert "FAKE_JIEBA" not in result.stdout
