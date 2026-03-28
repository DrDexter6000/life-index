#!/usr/bin/env python3
"""
Life Index - Semantic Search Module
RAG 语义检索模块（基于 sqlite-vec）

特性:
- 本地嵌入模型（多语言 MiniLM，~420MB）
- 向量相似度搜索 + 时间衰减排序
- 使用 fastembed (ONNX Runtime) 进行推理
"""

import sqlite3
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING
import sys

if TYPE_CHECKING:
    from fastembed import TextEmbedding

# 导入配置
sys.path.insert(0, str(Path(__file__).parent))
from config import (
    JOURNALS_DIR,
    USER_DATA_DIR,
    EMBEDDING_MODEL as EMBEDDING_MODEL_CONFIG,
    get_model_cache_dir,
)
from path_contract import build_journal_path_fields

# 索引存储目录
INDEX_DIR = USER_DATA_DIR / ".index"
VEC_DB_PATH = INDEX_DIR / "journals_vec.db"
CACHE_DIR = get_model_cache_dir()  # 跨平台缓存目录（与 vector_index_simple.py 统一）

# 嵌入模型配置（从 config.py 读取）
EMBEDDING_MODEL = EMBEDDING_MODEL_CONFIG["name"]
EMBEDDING_DIM = EMBEDDING_MODEL_CONFIG["dimension"]


class EmbeddingModel:
    """嵌入模型管理器（单例模式）"""

    _instance: Optional["EmbeddingModel"] = None
    _model: Optional["TextEmbedding"] = None

    def __new__(cls) -> "EmbeddingModel":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def load(self) -> bool:
        """加载嵌入模型，返回是否成功"""
        if self._model is not None:
            return True

        try:
            from fastembed import TextEmbedding

            print(f"Loading embedding model: {EMBEDDING_MODEL}...")
            CACHE_DIR.mkdir(parents=True, exist_ok=True)

            self._model = TextEmbedding(EMBEDDING_MODEL, cache_dir=str(CACHE_DIR))
            print("Model loaded successfully.")
            return True

        except Exception as e:
            print(f"Warning: Failed to load embedding model: {e}")
            return False

    def encode(self, texts: List[str]) -> List[List[float]]:
        """编码文本为向量"""
        if not self.load():
            return []

        if self._model is None:
            return []

        try:
            # fastembed 返回 generator，需要转换为 list
            embeddings = list(self._model.embed(texts))
            # Convert numpy arrays to lists
            return [list(e) for e in embeddings]
        except Exception as e:
            print(f"Encoding error: {e}")
            return []


def get_model() -> EmbeddingModel:
    """获取嵌入模型实例"""
    return EmbeddingModel()


def _load_sqlite_vec_extension(conn: sqlite3.Connection) -> bool:
    """
    加载 sqlite-vec 扩展（跨平台兼容）

    Returns:
        True if loaded successfully
    """
    import platform

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
                Path(sys.executable).parent
                / "Lib"
                / "site-packages"
                / "sqlite_vec"
                / "vec0.dll",
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

        parts = content.split("---", 2)
        if len(parts) < 3:
            return None

        fm_text = parts[1].strip()
        body = parts[2].strip()

        # 解析 frontmatter
        metadata: Dict[str, Any] = {}
        for line in fm_text.split("\n"):
            line = line.strip()
            if ":" in line and not line.startswith("#"):
                key, raw_value = line.split(":", 1)
                key = key.strip()
                value_str = raw_value.strip()

                if value_str.startswith("[") and value_str.endswith("]"):
                    value: Any = [
                        v.strip().strip("\"'")
                        for v in value_str[1:-1].split(",")
                        if v.strip()
                    ]
                else:
                    value = value_str

                metadata[key] = value

        # 组合用于向量化的文本（标题 + 正文 + 标签）
        text_parts = []

        if metadata.get("title"):
            text_parts.append(metadata["title"])

        text_parts.append(body[:1000])  # 限制正文长度，避免过长

        if metadata.get("tags"):
            tags = metadata["tags"]
            if isinstance(tags, list):
                text_parts.extend(tags)
            else:
                text_parts.append(tags)

        if metadata.get("topic"):
            topic = metadata["topic"]
            if isinstance(topic, list):
                text_parts.extend(topic)
            else:
                text_parts.append(topic)

        combined_text = " ".join(text_parts)

        rel_path = build_journal_path_fields(
            file_path, journals_dir=JOURNALS_DIR, user_data_dir=USER_DATA_DIR
        )["rel_path"]
        date_str = metadata.get("date", "")[:10]

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
            "error": str (optional)
        }
    """
    result: Dict[str, Any] = {
        "success": False,
        "added": 0,
        "updated": 0,
        "removed": 0,
        "total": 0,
        "error": None,
    }

    # 检查模型是否可用
    model = get_model()
    if not model.load():
        result["error"] = "Embedding model not available"
        return result

    try:
        conn = init_vec_db()
        if conn is None:
            result["error"] = (
                "sqlite-vec extension not available. Vector search disabled."
            )
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
            # 重新收集所有文件
            files_to_process = []
            for action, rel_path, text, date_str, file_hash in files_to_process:
                if action in ("add", "update"):
                    files_to_process.append(
                        ("add", rel_path, text, date_str, file_hash)
                    )
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
                        cursor.execute(
                            "DELETE FROM journal_vectors WHERE path = ?", (rel_path,)
                        )
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
                cursor.execute(
                    "DELETE FROM journal_vectors WHERE path = ?", (rel_path,)
                )
                result["removed"] += 1
            except Exception:
                pass

        conn.commit()
        conn.close()

        result["total"] = len(current_files)
        result["success"] = True

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
