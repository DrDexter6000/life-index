#!/usr/bin/env python3
"""
Life Index - Semantic Search Module
RAG 语义检索模块（基于 sqlite-vec）

特性:
- 本地嵌入模型（bge-m3）
- 向量相似度搜索 + 时间衰减排序
- 使用共享 embedding backend 进行推理
"""

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

# 导入配置（使用相对导入）
from .config import (
    JOURNALS_DIR,
    USER_DATA_DIR,
    EMBEDDING_MODEL as EMBEDDING_MODEL_CONFIG,
    get_model_cache_dir,
)
from .frontmatter import parse_frontmatter
from .embedding_backends import SharedEmbeddingModel as EmbeddingModel
from .path_contract import build_journal_path_fields

# 索引存储目录
INDEX_DIR = USER_DATA_DIR / ".index"
VEC_DB_PATH = INDEX_DIR / "journals_vec.db"
CACHE_DIR = get_model_cache_dir()  # 跨平台缓存目录（与 vector_index_simple.py 统一）

# 嵌入模型配置（从 config.py 读取）
EMBEDDING_MODEL = EMBEDDING_MODEL_CONFIG["name"]
EMBEDDING_DIM = EMBEDDING_MODEL_CONFIG["dimension"]


def get_model() -> EmbeddingModel:
    """获取嵌入模型实例"""
    return EmbeddingModel()


def build_embedding_text(
    *,
    title: str | None = None,
    body: str | None = None,
    tags: Any = None,
    topic: Any = None,
) -> str:
    """Build embedding text consistently across incremental and rebuild paths."""
    text_parts: list[str] = []

    if title:
        text_parts.append(title)

    if body:
        text_parts.append(body)

    if tags:
        if isinstance(tags, list):
            text_parts.extend(str(tag) for tag in tags)
        else:
            text_parts.append(str(tags))

    if topic:
        if isinstance(topic, list):
            text_parts.extend(str(item) for item in topic)
        else:
            text_parts.append(str(topic))

    return " ".join(text_parts)


def _load_sqlite_vec_extension(conn: sqlite3.Connection) -> bool:
    """
    加载 sqlite-vec 扩展（跨平台兼容）

    Returns:
        True if loaded successfully
    """
    import platform
    import sys

    try:
        conn.enable_load_extension(True)

        # 根据平台尝试不同的加载方式
        system = platform.system()

        if system == "Windows":
            # Windows: 尝试常见路径
            possible_paths = [
                # 当前目录
                "vec0.dll",
                "vec.dll",
                # Python 包目录
                Path(sys.executable).parent / "Lib" / "site-packages" / "sqlite_vec" / "vec0.dll",
                # 用户数据目录
                USER_DATA_DIR / ".bin" / "vec0.dll",
            ]

            for path in possible_paths:
                try:
                    conn.load_extension(str(path))
                    return True
                except Exception:
                    continue

        elif system == "Darwin":  # macOS
            possible_names = ["vec0.dylib", "libvec.dylib", "vec.dylib", "vec0", "vec"]
            for name in possible_names:
                try:
                    conn.load_extension(name)
                    return True
                except Exception:
                    continue

        else:  # Linux
            possible_names = ["vec0.so", "libvec.so", "vec.so", "vec0", "vec"]
            for name in possible_names:
                try:
                    conn.load_extension(name)
                    return True
                except Exception:
                    continue

        return False

    except Exception:
        return False


def init_vec_db() -> Optional[sqlite3.Connection]:
    """
    初始化向量数据库（sqlite-vec）

    Returns:
        Connection if successful, None if sqlite-vec not available
    """
    INDEX_DIR.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(VEC_DB_PATH))

    # 尝试加载 sqlite-vec 扩展
    if not _load_sqlite_vec_extension(conn):
        conn.close()
        return None

    cursor = conn.cursor()

    # 创建虚拟表（使用 float32 数组存储向量）
    try:
        cursor.execute(f"""
            CREATE VIRTUAL TABLE IF NOT EXISTS journal_vectors USING vec0(
                path TEXT PRIMARY KEY,
                embedding FLOAT[{EMBEDDING_DIM}],
                date TEXT,
                file_hash TEXT
            )
        """)
        conn.commit()
    except Exception as e:
        print(f"Warning: Failed to create vector table: {e}")
        conn.close()
        return None

    return conn


def parse_journal_for_vec(file_path: Path) -> Optional[Tuple[str, str, str]]:
    """
    解析日志文件，提取用于向量化的内容

    Returns:
        (path, combined_text, date) or None
    """
    try:
        content = file_path.read_text(encoding="utf-8")

        if not content.startswith("---"):
            return None

        # 使用 SSOT frontmatter 解析
        metadata, body = parse_frontmatter(content)

        if not metadata:
            return None

        combined_text = build_embedding_text(
            title=metadata.get("title"),
            body=body,
            tags=metadata.get("tags"),
            topic=metadata.get("topic"),
        )

        rel_path = build_journal_path_fields(
            file_path, journals_dir=JOURNALS_DIR, user_data_dir=USER_DATA_DIR
        )["rel_path"]
        date_str = str(metadata.get("date", ""))[:10]

        return (rel_path, combined_text, date_str)

    except Exception:
        return None


def get_file_hash(file_path: Path) -> str:
    """计算文件哈希"""
    try:
        content = file_path.read_bytes()
        return hashlib.md5(content).hexdigest()[:16]
    except Exception:
        return ""


def update_vector_index(incremental: bool = True) -> Dict[str, Any]:
    """
    更新向量索引

    Args:
        incremental: True=仅更新变更，False=全量重建

    Returns:
        {
            "success": bool,
            "added": int,
            "updated": int,
            "removed": int,
            "total": int,
            "auto_rebuild_triggered": bool (optional),
            "error": str (optional)
        }
    """
    result: Dict[str, Any] = {
        "success": False,
        "added": 0,
        "updated": 0,
        "removed": 0,
        "total": 0,
        "auto_rebuild_triggered": False,
        "error": None,
    }

    # Import embedding_backends for version check
    from .embedding_backends import verify_model_integrity, record_model_metadata

    # Check if model version mismatch requires rebuild (Task 1.1.2)
    model_name = str(EMBEDDING_MODEL)
    cache_dir = CACHE_DIR

    integrity_result = verify_model_integrity(model_name, cache_dir)

    if incremental and integrity_result.needs_rebuild:
        # Auto-trigger rebuild on version mismatch
        incremental = False
        result["auto_rebuild_triggered"] = True

        # Extract version info for clear logging
        meta_file = cache_dir / model_name.replace("/", "_") / "model_meta.json"
        if meta_file.exists():
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                old_version = meta.get("version", "unknown")
                new_version = EMBEDDING_MODEL_CONFIG["version"]
                print(
                    f"Embedding model version changed ({old_version} → {new_version}). "
                    f"Auto-rebuilding vector index..."
                )
            except Exception:
                print(f"Auto-rebuilding vector index due to: {integrity_result.message}")
        else:
            print("First-time use. Building initial vector index...")

    # 检查模型是否可用
    model = get_model()
    if not model.load():
        result["error"] = "Embedding model not available"
        return result

    try:
        conn = init_vec_db()
        if conn is None:
            result["error"] = "sqlite-vec extension not available. Vector search disabled."
            return result
        cursor = conn.cursor()

        # 获取已索引的文件
        indexed_files = {}
        try:
            cursor.execute("SELECT path, file_hash FROM journal_vectors")
            for row in cursor.fetchall():
                indexed_files[row[0]] = row[1]
        except Exception:
            pass

        # 扫描所有日志文件
        current_files = set()
        files_to_process = []

        if JOURNALS_DIR.exists():
            for year_dir in JOURNALS_DIR.iterdir():
                if not year_dir.is_dir() or not year_dir.name.isdigit():
                    continue

                for month_dir in year_dir.iterdir():
                    if not month_dir.is_dir():
                        continue

                    for journal_file in month_dir.glob("life-index_*.md"):
                        parsed = parse_journal_for_vec(journal_file)
                        if parsed:
                            rel_path, text, date_str = parsed
                            current_files.add(rel_path)
                            file_hash = get_file_hash(journal_file)

                            if rel_path not in indexed_files:
                                files_to_process.append(
                                    ("add", rel_path, text, date_str, file_hash)
                                )
                            elif indexed_files[rel_path] != file_hash:
                                files_to_process.append(
                                    ("update", rel_path, text, date_str, file_hash)
                                )

        # 找出需要删除的
        files_to_remove = set(indexed_files.keys()) - current_files

        # 如果不是增量模式，清空并重新处理
        if not incremental:
            try:
                cursor.execute("DELETE FROM journal_vectors")
            except Exception:
                pass
            files_to_remove = set()
            files_to_process = [
                ("add", rel_path, text, date_str, file_hash)
                for _, rel_path, text, date_str, file_hash in files_to_process
            ]
            result["removed"] = len(indexed_files)

        # 批量处理（每批 10 个，避免内存问题）
        batch_size = 10
        for i in range(0, len(files_to_process), batch_size):
            batch = files_to_process[i : i + batch_size]

            # 收集文本
            texts = [item[2] for item in batch]

            # 编码为向量
            embeddings = model.encode(texts)

            if not embeddings:
                continue

            # 插入数据库
            for j, (action, rel_path, text, date_str, file_hash) in enumerate(batch):
                if j >= len(embeddings):
                    break

                embedding = embeddings[j]
                embedding_bytes = json.dumps(embedding)

                # 如果是更新，先删除
                if action == "update":
                    try:
                        cursor.execute("DELETE FROM journal_vectors WHERE path = ?", (rel_path,))
                        result["updated"] += 1
                    except Exception:
                        pass
                else:
                    result["added"] += 1

                # 插入新记录
                try:
                    cursor.execute(
                        """
                        INSERT INTO journal_vectors (path, embedding, date, file_hash)
                        VALUES (?, vec_f32(?), ?, ?)
                    """,
                        (rel_path, embedding_bytes, date_str, file_hash),
                    )
                except Exception as e:
                    print(f"Insert error for {rel_path}: {e}")

        # 删除不存在的文件
        for rel_path in files_to_remove:
            try:
                cursor.execute("DELETE FROM journal_vectors WHERE path = ?", (rel_path,))
                result["removed"] += 1
            except Exception:
                pass

        conn.commit()
        conn.close()

        result["total"] = len(current_files)
        result["success"] = True

        # Update model metadata after successful rebuild (Task 1.1.2)
        if result["auto_rebuild_triggered"] or not incremental:
            record_model_metadata(model_name, cache_dir)

    except Exception as e:
        result["error"] = str(e)
        import traceback

        traceback.print_exc()

    return result


def get_stats() -> Dict[str, Any]:
    """获取向量索引统计信息"""
    stats: Dict[str, Any] = {
        "exists": VEC_DB_PATH.exists(),
        "total_vectors": 0,
        "db_size_mb": 0.0,
        "model_loaded": get_model().load(),
    }

    try:
        if VEC_DB_PATH.exists():
            stats["db_size_mb"] = round(VEC_DB_PATH.stat().st_size / (1024 * 1024), 2)

            conn = init_vec_db()
            if conn is not None:
                cursor = conn.cursor()

                try:
                    cursor.execute("SELECT COUNT(*) FROM journal_vectors")
                    stats["total_vectors"] = cursor.fetchone()[0]
                except Exception:
                    pass

                conn.close()

    except Exception:
        pass

    return stats


if __name__ == "__main__":
    # 测试代码
    print("Testing semantic index...")

    print("\nIndex stats:")
    print(json.dumps(get_stats(), indent=2, ensure_ascii=False))

    print("\nUpdating vector index...")
    result = update_vector_index(incremental=False)
    print(json.dumps(result, indent=2, ensure_ascii=False))
