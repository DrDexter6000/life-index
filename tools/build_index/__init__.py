#!/usr/bin/env python3
"""
Life Index - Build Index Tool
索引构建工具（FTS + 向量索引）

Usage:
    python -m tools.build_index
    python -m tools.build_index --rebuild

Public API:
    from tools.build_index import build_all
    result = build_all(incremental=True)
"""

from typing import Dict, Any

# 导入配置 (relative imports from parent tools package)
from ..lib.config import get_model_cache_dir, FILE_LOCK_TIMEOUT_REBUILD
from ..lib.search_index import (
    update_index as update_fts_index,
    get_stats as get_fts_stats,
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


def build_all(
    incremental: bool = True, fts_only: bool = False, vec_only: bool = False
) -> Dict[str, Any]:
    """
    构建所有索引

    Args:
        incremental: True=增量更新，False=全量重建
        fts_only: 仅更新 FTS 索引
        vec_only: 仅更新向量索引

    Returns:
        构建结果
    """
    result: Dict[str, Any] = {
        "success": True,
        "fts": None,
        "vector": None,
        "duration_seconds": 0.0,
        "rebuild_hint": "",
    }

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

            # 更新向量索引
            if not fts_only:
                logger.info("Updating vector index...")
                vec_success = False

                # 首先尝试 sqlite-vec
                try:
                    from ..lib.semantic_search import (
                        update_vector_index,
                        get_model,
                    )

                    model = get_model()
                    if model.load():
                        vec_result = update_vector_index(incremental=incremental)
                        if vec_result.get("success"):
                            result["vector"] = vec_result
                            logger.info(
                                f"  ✓ Vector (sqlite-vec): +{vec_result.get('added', 0)} added, "
                                f"~{vec_result.get('updated', 0)} updated"
                            )
                            vec_success = True
                except (ImportError, RuntimeError):
                    pass  # 失败时尝试简单索引

                # 如果 sqlite-vec 失败，使用简单向量索引
                if not vec_success:
                    try:
                        from ..lib.vector_index_simple import (
                            update_vector_index_simple,
                            get_model as get_simple_model,
                        )

                        simple_model = get_simple_model()
                        if simple_model.load():
                            vec_result = update_vector_index_simple(
                                simple_model.encode, incremental=incremental
                            )
                            result["vector"] = vec_result
                            if vec_result.get("success"):
                                logger.info(
                                    f"  ✓ Vector (simple): +{vec_result.get('added', 0)} added, "
                                    f"~{vec_result.get('updated', 0)} updated"
                                )
                            else:
                                logger.warning(
                                    "  ⚠ Vector (simple): "
                                    f"{vec_result.get('error', 'Unknown error')}"
                                )
                        else:
                            logger.info(
                                "  ⚠ Embedding model not available. "
                                "Install: pip install sentence-transformers"
                            )
                    except (RuntimeError, IOError, OSError) as e:
                        logger.error(f"  ✗ Vector error: {e}")
                        result["vector"] = {"success": False, "error": str(e)}

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

    logger.info("\n🧠 Vector Index (Semantic Search):")
    try:
        from ..lib.semantic_search import get_stats as get_vec_stats

        vec_stats = get_vec_stats()
        if vec_stats["exists"] and vec_stats["total_vectors"] > 0:
            logger.info("  Backend: sqlite-vec")
            logger.info("  Exists: Yes")
            logger.info(f"  Vectors: {vec_stats['total_vectors']}")
            logger.info(f"  Size: {vec_stats['db_size_mb']} MB")
            logger.info(
                f"  Model Loaded: {'Yes' if vec_stats['model_loaded'] else 'No'}"
            )
        else:
            # sqlite-vec exists but empty, try simple index
            raise ImportError("sqlite-vec empty, trying simple index")
    except (ImportError, RuntimeError, Exception):
        try:
            from ..lib.vector_index_simple import get_index

            simple_index = get_index()
            simple_stats = simple_index.stats()
            logger.info("  Backend: simple_numpy")
            logger.info(f"  Exists: {'Yes' if simple_stats['exists'] else 'No'}")
            logger.info(f"  Vectors: {simple_stats['total_vectors']}")
            logger.info(f"  Size: {simple_stats['index_size_mb']} MB")
        except (ImportError, RuntimeError):
            logger.info("  Status: Not available")
            logger.info("  Note: Install sentence-transformers for semantic search")

    logger.info("\n💾 Cache Directory:")
    cache_dir = get_model_cache_dir()
    if cache_dir.exists():
        total_size = sum(f.stat().st_size for f in cache_dir.rglob("*") if f.is_file())
        logger.info(f"  Location: {cache_dir}")
        logger.info(f"  Size: {round(total_size / (1024 * 1024), 2)} MB")
    else:
        logger.info("  Not created yet")

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


__all__ = ["build_all", "show_stats"]
