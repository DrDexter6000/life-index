#!/usr/bin/env python3
"""
Life Index - Build Index Tool
索引构建工具（FTS only）

Usage:
    python -m tools.build_index
    python -m tools.build_index --rebuild

Public API:
    from tools.build_index import build_all
    result = build_all(incremental=True)
"""

from typing import Dict, Any
from pathlib import Path

# 导入配置 (relative imports from parent tools package)
from ..lib.config import FILE_LOCK_TIMEOUT_REBUILD
from ..lib.paths import get_user_data_dir
from ..lib.search_index import (
    update_index as update_fts_index,
    get_stats as get_fts_stats,
)
from ..lib.index_manifest import (
    IndexManifest,
    write_manifest,
    read_manifest,
    compute_fts_checksum,
)
from ..lib.metadata_cache import (
    get_cache_stats,
    invalidate_cache,
    init_metadata_cache,
    rebuild_entry_relations,
    update_cache_for_all_journals,
)
from ..lib.file_lock import FileLock, LockTimeoutError, get_index_lock_path
from ..lib.errors import ErrorCode, create_error_response
from ..lib.logger import get_logger

# 获取日志器
logger = get_logger("build_index")

SEMANTIC_INDEX_DEPRECATED_NOOP_WARNING = (
    "deprecated_noop: semantic/vector index build options are accepted for compatibility "
    "but ignored; index now builds FTS only."
)


def build_all(
    incremental: bool = True, fts_only: bool = False, vec_only: bool = False
) -> Dict[str, Any]:
    """
    构建所有索引

    Args:
        incremental: True=增量更新，False=全量重建
        fts_only: 兼容参数；索引构建始终只更新 FTS
        vec_only: 废弃兼容参数；接受但不构建向量索引

    Returns:
        构建结果
    """
    result: Dict[str, Any] = {
        "success": True,
        "fts": None,
        "vector": None,
        "duration_seconds": 0.0,
        "rebuild_hint": "",
        "auto_rebuild_triggered": False,  # Task 1.1.2: version mismatch auto-rebuild flag
        "semantic_status": "disabled",
        "warnings": [],
    }
    if vec_only:
        result["warnings"].append(SEMANTIC_INDEX_DEPRECATED_NOOP_WARNING)

    import time

    start_time = time.time()

    # ===== 文件锁保护 =====
    # 使用文件锁保护索引构建，防止并发冲突
    lock = FileLock(get_index_lock_path(), timeout=FILE_LOCK_TIMEOUT_REBUILD)

    try:
        with lock:
            if not incremental:
                invalidate_cache()
                update_cache_for_all_journals()
                relation_conn = init_metadata_cache()
                try:
                    rebuild_entry_relations(relation_conn)
                finally:
                    relation_conn.close()

            # 更新 FTS 索引
            if not vec_only:
                logger.info("Updating FTS index...")
                try:
                    fts_result = update_fts_index(incremental=incremental)
                    result["fts"] = fts_result
                    if fts_result.get("success"):
                        logger.info(
                            f"  ✓ FTS: +{fts_result.get('added', 0)} added, "
                            f"~{fts_result.get('updated', 0)} updated, "
                            f"-{fts_result.get('removed', 0)} removed"
                        )
                    else:
                        logger.warning(f"  ✗ FTS failed: {fts_result.get('error')}")
                        result["success"] = False
                except (RuntimeError, IOError, OSError) as e:
                    logger.error(f"  ✗ FTS error: {e}")
                    result["fts"] = {"success": False, "error": str(e)}
                    result["success"] = False

            # Round 12 Phase 2: Write manifest after FTS completes
            from datetime import datetime as _dt
            from ..lib.paths import get_fts_db_path

            fts_success = (result.get("fts") or {}).get("success", False)
            partial = not fts_success

            if fts_success:
                try:
                    fts_data = result.get("fts") or {}
                    manifest = IndexManifest(
                        fts_count=fts_data.get(
                            "total", fts_data.get("total_documents", fts_data.get("added", 0))
                        ),
                        vector_count=0,
                        file_count=0,  # Will be filled by check_index
                        fts_checksum=compute_fts_checksum(get_fts_db_path()),
                        vector_checksum="",
                        build_timestamp=_dt.now().isoformat(),
                        build_version="2.0.0",
                        partial=partial,
                    )
                    index_dir = get_user_data_dir() / ".index"
                    write_manifest(manifest, index_dir)
                    result["manifest_written"] = True
                    logger.info(f"  ✓ Manifest written (partial={partial})")
                except Exception as e:
                    logger.warning(f"  ⚠ Manifest write failed: {e}")

    except LockTimeoutError as e:
        # 锁超时，返回结构化错误
        return create_error_response(
            ErrorCode.LOCK_TIMEOUT,
            f"无法获取索引锁，请稍后重试: {e}",
            {
                "lock_path": str(get_index_lock_path()),
                "timeout": FILE_LOCK_TIMEOUT_REBUILD,
            },
            "等待几秒后重试，或检查是否有其他进程正在构建索引",
        )

    result["duration_seconds"] = round(time.time() - start_time, 2)
    cache_stats = get_cache_stats()
    result["rebuild_hint"] = cache_stats.get("rebuild_hint", "")
    logger.info(f"Completed in {result['duration_seconds']}s")

    return result


def show_stats() -> None:
    """显示索引统计信息"""
    logger.info("=" * 50)
    logger.info("Life Index - Search Index Statistics")
    logger.info("=" * 50)

    logger.info("\n📚 FTS Index (Full-Text Search):")
    fts_stats = get_fts_stats()
    logger.info(f"  Exists: {'Yes' if fts_stats['exists'] else 'No'}")
    logger.info(f"  Documents: {fts_stats['total_documents']}")
    logger.info(f"  Size: {fts_stats['db_size_mb']} MB")
    if fts_stats["last_updated"]:
        logger.info(f"  Last Updated: {fts_stats['last_updated']}")

    logger.info("\n🔎 Semantic/Vector Index:")
    logger.info("  Status: Disabled (removed from in-tool search/index pipeline)")

    logger.info("\n🗂 Metadata Cache:")
    cache_stats = get_cache_stats()
    logger.info(f"  Entries: {cache_stats['total_entries']}")
    logger.info(f"  Size: {cache_stats['db_size_mb']} MB")
    logger.info(f"  Path: {cache_stats['cache_path']}")
    if cache_stats["last_update"]:
        logger.info(f"  Last Updated: {cache_stats['last_update']}")
    if cache_stats.get("rebuild_hint"):
        logger.info(f"  Hint: {cache_stats['rebuild_hint']}")

    logger.info("=" * 50)


def check_index(data_dir: Path | None = None) -> Dict[str, Any]:
    """Run index consistency check and return structured result.

    This is a read-only operation — it never modifies any index or data file.

    Args:
        data_dir: Root data directory (defaults to USER_DATA_DIR).

    Returns:
        Dict with keys: healthy, fts_count, vector_count, file_count, issues.
        vector_count is retained as a legacy field and is always ignored for health.
    """
    from .diagnostics import check_index_health

    if data_dir is None:
        data_dir = get_user_data_dir()

    report = check_index_health(data_dir)

    # Convert report to JSON-friendly dict
    issues: list[str] = list(report.issues) if not report.consistency_ok else []
    healthy = report.consistency_ok

    healthy = report.fts_ok

    # Round 12 Phase 3: Enhanced check with manifest + freshness
    index_dir = data_dir / ".index"
    manifest = read_manifest(index_dir)

    # Manifest info
    manifest_info: dict[str, object] = {"exists": manifest is not None}
    if manifest is not None:
        manifest_info["fts_count"] = manifest.fts_count
        manifest_info["partial"] = manifest.partial
        if manifest.partial:
            issues.append("partial_build: Last FTS index build was incomplete")
            healthy = False
    else:
        issues.append("no_manifest: No index manifest found, run 'life-index index --rebuild'")
        healthy = False

    # Freshness info
    from ..lib.index_freshness import check_full_freshness

    freshness = check_full_freshness(index_dir)
    if not freshness.overall_fresh:
        healthy = False
        for issue in freshness.issues:
            if issue not in issues:
                issues.append(issue)

    return {
        "healthy": healthy,
        "fts_count": report.fts_count,
        "vector_count": report.vector_count,
        "file_count": report.file_count,
        "manifest": manifest_info,
        "freshness": freshness.to_dict(),
        "issues": issues,
    }


__all__ = ["build_all", "show_stats", "check_index"]
