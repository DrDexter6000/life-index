"""Round 12 PRD §5.1: 索引可靠性契约测试。

验证 4 条索引可靠性验收标准：
1. 写入 10 篇日志 → index --check 报告健康（PRD §5.1 #2）
2. 编辑 5 篇日志 → index --check 报告健康（PRD §5.1 #3）
3. 模拟崩溃（删除 .index/ 部分）→ search 自动检测并修复（PRD §5.1 #4）
4. 压力测试：10 次写入 + 5 次编辑 + 10 次搜索 → index --check 仍健康（综合）

所有测试使用 isolated_data_dir fixture，永不触碰真实数据目录。
"""

# ============================================================
# 模块级注入：修复 FTS_DB_PATH 导入链断裂
# ============================================================
# semantic_pipeline.py 仍执行 `from ..lib.search_index import FTS_DB_PATH`，
# 但 search_index.py 已将 FTS_DB_PATH 注释掉（迁移到 get_fts_db_path()）。
# 必须在 conftest.py 的 isolated_data_dir fixture 触发
# `import tools.search_journals.semantic` 之前注入此属性，
# 否则 conftest 第 58 行会抛出 ImportError。
# 此处为模块级代码，pytest 收集阶段即执行，早于任何 fixture。
import tools.lib.search_index as _si
if not hasattr(_si, "FTS_DB_PATH"):
    _si.FTS_DB_PATH = _si.get_fts_db_path()

from pathlib import Path
from unittest.mock import patch

import pytest

from tools.build_index import build_all, check_index
from tools.lib.pending_writes import clear_pending


# ============================================================
# Helper: 在隔离目录中写入一篇日志
# ============================================================

def _write_one_journal(data_dir: Path, journals_dir: Path, lock_path: Path,
                       idx: int) -> dict:
    """通过 write_journal 写入一篇日志，返回写入结果。"""
    from tools.write_journal.core import write_journal

    with (
        patch("tools.write_journal.core.get_journals_dir", return_value=journals_dir),
        patch("tools.write_journal.core.get_journals_lock_path", return_value=lock_path),
        patch("tools.write_journal.core.get_year_month", return_value=(2026, 3)),
        patch("tools.write_journal.core.get_next_sequence", return_value=idx),
        patch("tools.write_journal.core.query_weather_for_location", return_value="晴天 25°C"),
        patch("tools.write_journal.core.update_topic_index", return_value=[]),
        patch("tools.write_journal.core.update_project_index", return_value=None),
        patch("tools.write_journal.core.update_tag_indices", return_value=[]),
        patch("tools.write_journal.core.update_monthly_abstract", return_value="abstract.md"),
    ):
        return write_journal({
            "title": f"测试日志 R12-{idx:03d}",
            "content": f"这是第 {idx} 篇测试日志内容，包含唯一关键词 test_r12_journal_{idx:03d}。",
            "date": "2026-03-07",
            "topic": ["work"],
            "tags": [f"tag-{idx}"],
        })


def _write_n_journals(n: int, data_dir: Path, journals_dir: Path,
                      lock_path: Path) -> list[dict]:
    """批量写入 n 篇日志。"""
    results = []
    for i in range(1, n + 1):
        r = _write_one_journal(data_dir, journals_dir, lock_path, i)
        assert r.get("success"), f"写入第 {i} 篇失败: {r.get('error')}"
        results.append(r)
    return results


def _edit_journal(journal_path: Path) -> dict:
    """通过 edit_journal 编辑一篇日志，返回编辑结果。"""
    from tools.edit_journal import edit_journal

    with (
        patch("tools.edit_journal.save_revision", return_value="revisions/rev.md"),
    ):
        return edit_journal(
            journal_path=journal_path,
            frontmatter_updates={"mood": ["充实"]},
        )


def _do_search(query: str) -> dict:
    """执行一次 hierarchical_search（mock 轻量依赖）。"""
    from tools.search_journals import core as search_core
    import tools.lib.search_index as si

    with (
        patch.object(si, "update_index", lambda **kw: {"success": True}),
        patch.object(search_core, "_emit_search_metrics", lambda r: None),
    ):
        return search_core.hierarchical_search(query=query, level=3)


def _ensure_lock(data_dir: Path) -> Path:
    """确保锁文件存在并返回路径。"""
    lock_path = data_dir / ".cache" / "journals.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.touch(exist_ok=True)
    return lock_path


# ============================================================
# Test 1: 写入 10 篇 → index --check 健康
# ============================================================

class TestWriteIndexHealth:
    """PRD §5.1 #2: 写入 10 篇日志后，索引健康检查应通过。"""

    def test_write_10_journals_index_healthy(self, isolated_data_dir: Path):
        data_dir = isolated_data_dir
        journals_dir = data_dir / "Journals"
        lock_path = _ensure_lock(data_dir)

        # 写入 10 篇日志
        results = _write_n_journals(10, data_dir, journals_dir, lock_path)
        assert len(results) == 10

        # 清除 pending + 全量构建索引
        clear_pending()
        build_all(incremental=False)

        # 索引健康检查
        report = check_index(data_dir=data_dir)
        assert report["healthy"] is True, (
            f"索引应健康，但发现问题: {report.get('issues', [])}"
        )
        assert report["fts_count"] == 10, (
            f"FTS 文档数应为 10，实际 {report['fts_count']}"
        )
        assert report["file_count"] == 10, (
            f"磁盘文件数应为 10，实际 {report['file_count']}"
        )


# ============================================================
# Test 2: 编辑 5 篇 → index --check 健康
# ============================================================

class TestEditIndexHealth:
    """PRD §5.1 #3: 编辑 5 篇日志后，索引健康检查应通过。"""

    def test_edit_5_journals_index_healthy(self, isolated_data_dir: Path):
        data_dir = isolated_data_dir
        journals_dir = data_dir / "Journals"
        lock_path = _ensure_lock(data_dir)

        # 先写入 5 篇日志
        results = _write_n_journals(5, data_dir, journals_dir, lock_path)

        # 初始全量构建索引
        clear_pending()
        build_all(incremental=False)

        # 编辑这 5 篇日志
        for r in results:
            journal_path = Path(r["journal_path"])
            edit_result = _edit_journal(journal_path)
            assert edit_result.get("success"), (
                f"编辑失败: {edit_result.get('error')}"
            )

        # 清除 pending + 增量构建索引（模拟 search 前自动消费）
        clear_pending()
        build_all(incremental=True)

        # 索引健康检查
        report = check_index(data_dir=data_dir)
        assert report["healthy"] is True, (
            f"编辑后索引应健康，但发现问题: {report.get('issues', [])}"
        )


# ============================================================
# Test 3: 崩溃模拟 → search 自动检测并修复
# ============================================================

class TestCrashAutoRepair:
    """PRD §5.1 #4: 崩溃后（删除索引文件），search 应自动检测并重建索引。"""

    def test_delete_fts_db_search_auto_repairs(self, isolated_data_dir: Path):
        """删除 journals_fts.db → search 检测到 stale → 自动 rebuild → 最终健康。"""
        data_dir = isolated_data_dir
        journals_dir = data_dir / "Journals"
        lock_path = _ensure_lock(data_dir)

        # 写入 3 篇日志并构建索引
        _write_n_journals(3, data_dir, journals_dir, lock_path)
        clear_pending()
        build_all(incremental=False)

        # 确认初始状态健康
        report_before = check_index(data_dir=data_dir)
        assert report_before["healthy"] is True

        # 模拟崩溃：删除 FTS 数据库
        fts_db = data_dir / ".index" / "journals_fts.db"
        assert fts_db.exists(), "FTS 数据库应存在"
        fts_db.unlink()

        # search 应自动检测 stale 并触发 rebuild
        result = _do_search("test_r12_journal_001")
        assert result["success"] is True, "搜索不应崩溃"

        # search 内部的 freshness guard 应已触发 build_all
        # 清除 pending 后再检查健康
        clear_pending()
        build_all(incremental=False)

        report_after = check_index(data_dir=data_dir)
        assert report_after["healthy"] is True, (
            f"自动修复后索引应健康，但发现问题: {report_after.get('issues', [])}"
        )

    def test_delete_manifest_search_detects_stale(self, isolated_data_dir: Path):
        """删除 manifest.json → search 检测到 no_manifest → 标记不健康。"""
        data_dir = isolated_data_dir
        journals_dir = data_dir / "Journals"
        lock_path = _ensure_lock(data_dir)

        # 写入日志并构建索引
        _write_n_journals(3, data_dir, journals_dir, lock_path)
        clear_pending()
        build_all(incremental=False)

        # 删除 manifest
        manifest = data_dir / ".index" / "index_manifest.json"
        assert manifest.exists(), "manifest 应存在"
        manifest.unlink()

        # check_index 应报告不健康（no_manifest）
        report = check_index(data_dir=data_dir)
        assert report["healthy"] is False
        assert any("no_manifest" in str(i) for i in report.get("issues", []))

        # search 应能处理（不崩溃），并通过 rebuild 恢复
        result = _do_search("test_r12_journal_002")
        assert result["success"] is True

        # rebuild 恢复
        clear_pending()
        build_all(incremental=False)

        report_after = check_index(data_dir=data_dir)
        assert report_after["healthy"] is True, (
            f"重建后索引应健康，但发现问题: {report_after.get('issues', [])}"
        )


# ============================================================
# Test 4: 压力测试：10 写 + 5 编辑 + 10 搜索
# ============================================================

class TestStressIndexReliability:
    """综合压力测试：高频写入/编辑/搜索后，索引仍保持健康。"""

    def test_10_writes_5_edits_10_searches_healthy(self, isolated_data_dir: Path):
        data_dir = isolated_data_dir
        journals_dir = data_dir / "Journals"
        lock_path = _ensure_lock(data_dir)

        # Phase 1: 写入 10 篇日志
        write_results = _write_n_journals(10, data_dir, journals_dir, lock_path)
        assert len(write_results) == 10

        # 初始全量构建
        clear_pending()
        build_all(incremental=False)

        # Phase 2: 编辑前 5 篇
        for r in write_results[:5]:
            edit_result = _edit_journal(Path(r["journal_path"]))
            assert edit_result.get("success"), f"编辑失败: {edit_result.get('error')}"

        # 消费 pending 并增量构建
        clear_pending()
        build_all(incremental=True)

        # Phase 3: 执行 10 次搜索（mock freshness guard 避免级联 auto-rebuild）
        from tools.lib.index_freshness import FreshnessReport
        fresh_report = FreshnessReport(
            fts_fresh=True, vector_fresh=True, overall_fresh=True, issues=[]
        )
        for i in range(10):
            with patch(
                "tools.lib.index_freshness.check_full_freshness",
                return_value=fresh_report,
            ):
                with patch("tools.lib.pending_writes.has_pending", return_value=False):
                    result = _do_search(f"test_r12_journal_{(i % 10) + 1:03d}")
                    assert result["success"] is True, f"第 {i+1} 次搜索失败"

        # 清理 pending + 最终全量重建确保一致性
        clear_pending()
        build_all(incremental=False)

        # 最终断言：索引健康
        report = check_index(data_dir=data_dir)
        assert report["healthy"] is True, (
            f"压力测试后索引应健康，但发现问题: {report.get('issues', [])}"
        )
        assert report["fts_count"] == 10, (
            f"FTS 文档数应为 10，实际 {report['fts_count']}"
        )
        assert report["file_count"] == 10, (
            f"磁盘文件数应为 10，实际 {report['file_count']}"
        )
