#!/usr/bin/env python3
"""
Life Index - Metadata Cache Module
L2搜索元数据缓存管理

特性:
- 增量更新：仅处理新增/修改的日志
- 自动初始化：首次使用时自动创建缓存表
- 文件变更检测：使用mtime+size检测文件变更
- 内存缓存：支持内存级缓存加速热点查询
"""

import sqlite3
import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from .config import JOURNALS_DIR, USER_DATA_DIR
from .frontmatter import parse_journal_file
from .path_contract import build_journal_path_fields

# 缓存存储目录
CACHE_DIR = USER_DATA_DIR / ".cache"
METADATA_DB_PATH = CACHE_DIR / "metadata_cache.db"
METADATA_CACHE_REBUILD_HINT = (
    "如发现旧缓存路径格式导致的异常，可执行 `life-index index --rebuild` 进行重建。"
)

# 内存缓存（进程生命周期）
_memory_cache: Dict[str, Any] = {}
_memory_cache_timestamp: float = 0
_memory_cache_ttl: int = 60  # 内存缓存TTL（秒）


def _candidate_cache_keys(file_path: Path) -> List[str]:
    """Return normalized and legacy cache keys for backward compatibility."""
    normalized = build_journal_path_fields(
        file_path, journals_dir=JOURNALS_DIR, user_data_dir=USER_DATA_DIR
    )["path"]
    legacy = str(file_path)

    keys = [normalized]
    if legacy != normalized:
        keys.append(legacy)
    return keys


def init_metadata_cache() -> sqlite3.Connection:
    """初始化元数据缓存数据库"""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(METADATA_DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")  # 启用 WAL 模式提升并发性能
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 创建元数据缓存表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS metadata_cache (
            file_path TEXT PRIMARY KEY,
            date TEXT,
            title TEXT,
            location TEXT,
            weather TEXT,
            topic TEXT,  -- JSON数组
            project TEXT,
            tags TEXT,   -- JSON数组
            mood TEXT,   -- JSON数组
            people TEXT, -- JSON数组
            abstract TEXT,
            links TEXT,  -- JSON数组
            related_entries TEXT,  -- JSON数组
            file_mtime REAL,
            file_size INTEGER,
            cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS entry_relations (
            source_path TEXT NOT NULL,
            target_path TEXT NOT NULL,
            PRIMARY KEY (source_path, target_path)
        )
        """
    )

    _ensure_metadata_cache_columns(conn)

    # 创建索引加速查询
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_metadata_date
        ON metadata_cache(date)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_metadata_topic
        ON metadata_cache(topic)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_metadata_project
        ON metadata_cache(project)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_metadata_location
        ON metadata_cache(location)
    """)

    # 创建缓存状态表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cache_meta (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    conn.commit()
    return conn


def _ensure_metadata_cache_columns(conn: sqlite3.Connection) -> None:
    """Add newly introduced columns for existing cache databases."""
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(metadata_cache)")
    existing_columns = {row[1] for row in cursor.fetchall()}

    if "links" not in existing_columns:
        cursor.execute("ALTER TABLE metadata_cache ADD COLUMN links TEXT")
    if "related_entries" not in existing_columns:
        cursor.execute("ALTER TABLE metadata_cache ADD COLUMN related_entries TEXT")
    conn.commit()


def get_file_signature(file_path: Path) -> Tuple[float, int]:
    """获取文件签名（mtime, size）用于检测变更"""
    try:
        stat = file_path.stat()
        return (stat.st_mtime, stat.st_size)
    except (OSError, IOError):
        return (0, 0)


def is_cache_valid(file_path: Path, cached_mtime: float, cached_size: int) -> bool:
    """检查缓存是否有效（文件未变更）"""
    current_mtime, current_size = get_file_signature(file_path)
    return current_mtime == cached_mtime and current_size == cached_size


def parse_and_cache_journal(
    conn: sqlite3.Connection, file_path: Path
) -> Optional[Dict[str, Any]]:
    """解析日志并更新缓存"""
    try:
        # 解析日志文件
        metadata = parse_journal_file(file_path)
        if not metadata:
            return None

        # 获取文件签名
        mtime, size = get_file_signature(file_path)

        # 提取可过滤字段
        path_fields = build_journal_path_fields(
            file_path, journals_dir=JOURNALS_DIR, user_data_dir=USER_DATA_DIR
        )
        file_path_str = path_fields["path"]
        date = metadata.get("date", "")[:10] if metadata.get("date") else ""
        title = metadata.get("title", "")
        location = metadata.get("location", "")
        weather = metadata.get("weather", "")
        abstract = metadata.get("abstract", "")
        links = json.dumps(metadata.get("links", []), ensure_ascii=False)
        related_entries = json.dumps(
            metadata.get("related_entries", []), ensure_ascii=False
        )

        # 数组字段转为JSON
        topic = json.dumps(metadata.get("topic", []), ensure_ascii=False)
        project = metadata.get("project", "")
        tags = json.dumps(metadata.get("tags", []), ensure_ascii=False)
        mood = json.dumps(metadata.get("mood", []), ensure_ascii=False)
        people = json.dumps(metadata.get("people", []), ensure_ascii=False)

        # 更新缓存
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO metadata_cache
            (file_path, date, title, location, weather, topic, project,
             tags, mood, people, abstract, links, related_entries, file_mtime, file_size)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                file_path_str,
                date,
                title,
                location,
                weather,
                topic,
                project,
                tags,
                mood,
                people,
                abstract,
                links,
                related_entries,
                mtime,
                size,
            ),
        )

        conn.commit()

        return {
            "file_path": file_path_str,
            "rel_path": path_fields["rel_path"],
            "journal_route_path": path_fields["journal_route_path"],
            "date": date,
            "title": title,
            "location": location,
            "weather": weather,
            "topic": json.loads(topic),
            "project": project,
            "tags": json.loads(tags),
            "mood": json.loads(mood),
            "people": json.loads(people),
            "abstract": abstract,
            "links": json.loads(links),
            "related_entries": json.loads(related_entries),
            "metadata": metadata,
        }

    except (IOError, OSError, ValueError):
        return None


def get_cached_metadata(
    conn: sqlite3.Connection, file_path: Path
) -> Optional[Dict[str, Any]]:
    """从缓存获取元数据（如果有效）"""
    cursor = conn.cursor()
    candidate_keys = _candidate_cache_keys(file_path)

    if len(candidate_keys) == 1:
        cursor.execute(
            "SELECT * FROM metadata_cache WHERE file_path = ?", (candidate_keys[0],)
        )
    else:
        cursor.execute(
            "SELECT * FROM metadata_cache WHERE file_path IN (?, ?)",
            (candidate_keys[0], candidate_keys[1]),
        )

    row = cursor.fetchone()
    if row is None:
        return None

    # 检查缓存是否有效
    if not is_cache_valid(file_path, row["file_mtime"], row["file_size"]):
        return None

    # 转换为字典
    normalized_fields = build_journal_path_fields(
        row["file_path"], journals_dir=JOURNALS_DIR, user_data_dir=USER_DATA_DIR
    )
    return {
        "file_path": normalized_fields["path"],
        **normalized_fields,
        "date": row["date"],
        "title": row["title"],
        "location": row["location"],
        "weather": row["weather"],
        "topic": json.loads(row["topic"]) if row["topic"] else [],
        "project": row["project"],
        "tags": json.loads(row["tags"]) if row["tags"] else [],
        "mood": json.loads(row["mood"]) if row["mood"] else [],
        "people": json.loads(row["people"]) if row["people"] else [],
        "abstract": row["abstract"],
        "links": json.loads(row["links"]) if row["links"] else [],
        "related_entries": json.loads(row["related_entries"])
        if row["related_entries"]
        else [],
        "metadata": {
            "date": row["date"],
            "title": row["title"],
            "location": row["location"],
            "weather": row["weather"],
            "topic": json.loads(row["topic"]) if row["topic"] else [],
            "project": row["project"],
            "tags": json.loads(row["tags"]) if row["tags"] else [],
            "mood": json.loads(row["mood"]) if row["mood"] else [],
            "people": json.loads(row["people"]) if row["people"] else [],
            "abstract": row["abstract"],
            "links": json.loads(row["links"]) if row["links"] else [],
            "related_entries": json.loads(row["related_entries"])
            if row["related_entries"]
            else [],
        },
    }


def get_or_update_metadata(
    file_path: Path, conn: Optional[sqlite3.Connection] = None
) -> Optional[Dict[str, Any]]:
    """获取元数据（优先从缓存，缓存未命中则解析并缓存）"""
    close_conn = False
    if conn is None:
        conn = init_metadata_cache()
        close_conn = True

    try:
        # 尝试从缓存获取
        cached = get_cached_metadata(conn, file_path)
        if cached:
            return cached

        # 缓存未命中，解析并缓存
        return parse_and_cache_journal(conn, file_path)

    finally:
        if close_conn:
            conn.close()


def get_all_cached_metadata(
    conn: Optional[sqlite3.Connection] = None,
) -> List[Dict[str, Any]]:
    """获取所有缓存的元数据（用于L2搜索）"""
    close_conn = False
    if conn is None:
        conn = init_metadata_cache()
        close_conn = True

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM metadata_cache")

        results = []
        for row in cursor.fetchall():
            normalized_fields = build_journal_path_fields(
                row["file_path"],
                journals_dir=JOURNALS_DIR,
                user_data_dir=USER_DATA_DIR,
            )
            results.append(
                {
                    "file_path": normalized_fields["path"],
                    **normalized_fields,
                    "date": row["date"],
                    "title": row["title"],
                    "location": row["location"],
                    "weather": row["weather"],
                    "topic": json.loads(row["topic"]) if row["topic"] else [],
                    "project": row["project"],
                    "tags": json.loads(row["tags"]) if row["tags"] else [],
                    "mood": json.loads(row["mood"]) if row["mood"] else [],
                    "people": json.loads(row["people"]) if row["people"] else [],
                    "abstract": row["abstract"],
                    "links": json.loads(row["links"]) if row["links"] else [],
                    "related_entries": json.loads(row["related_entries"])
                    if row["related_entries"]
                    else [],
                    "metadata": {
                        "date": row["date"],
                        "title": row["title"],
                        "location": row["location"],
                        "weather": row["weather"],
                        "topic": json.loads(row["topic"]) if row["topic"] else [],
                        "project": row["project"],
                        "tags": json.loads(row["tags"]) if row["tags"] else [],
                        "mood": json.loads(row["mood"]) if row["mood"] else [],
                        "people": json.loads(row["people"]) if row["people"] else [],
                        "abstract": row["abstract"],
                        "links": json.loads(row["links"]) if row["links"] else [],
                        "related_entries": json.loads(row["related_entries"])
                        if row["related_entries"]
                        else [],
                    },
                }
            )

        return results

    finally:
        if close_conn:
            conn.close()


def invalidate_cache(file_path: Optional[Path] = None) -> None:
    """使缓存失效"""
    conn = init_metadata_cache()
    try:
        cursor = conn.cursor()
        if file_path:
            candidate_keys = _candidate_cache_keys(file_path)
            if len(candidate_keys) == 1:
                cursor.execute(
                    "DELETE FROM metadata_cache WHERE file_path = ?",
                    (candidate_keys[0],),
                )
            else:
                cursor.execute(
                    "DELETE FROM metadata_cache WHERE file_path IN (?, ?)",
                    (candidate_keys[0], candidate_keys[1]),
                )
        else:
            cursor.execute("DELETE FROM metadata_cache")
        conn.commit()
    finally:
        conn.close()


def rebuild_entry_relations(conn: sqlite3.Connection) -> int:
    """Rebuild relation table from cached related_entries metadata."""
    cursor = conn.cursor()
    cursor.execute("DELETE FROM entry_relations")
    cursor.execute("SELECT file_path, related_entries FROM metadata_cache")

    inserted = 0
    for row in cursor.fetchall():
        normalized_fields = build_journal_path_fields(
            row["file_path"], journals_dir=JOURNALS_DIR, user_data_dir=USER_DATA_DIR
        )
        source_rel_path = normalized_fields["rel_path"]
        raw_related_entries = row["related_entries"]
        related_entries = json.loads(raw_related_entries) if raw_related_entries else []
        if not isinstance(related_entries, list):
            continue
        for target_path in related_entries:
            if not isinstance(target_path, str) or not target_path:
                continue
            cursor.execute(
                "INSERT OR REPLACE INTO entry_relations (source_path, target_path) VALUES (?, ?)",
                (source_rel_path, target_path),
            )
            inserted += 1

    conn.commit()
    return inserted


def add_entry_relations(
    conn: sqlite3.Connection, source_rel_path: str, target_paths: List[str]
) -> int:
    """Add incremental relations for a single source entry."""
    cursor = conn.cursor()
    inserted = 0
    seen_targets: set[str] = set()
    for target_path in target_paths:
        if not isinstance(target_path, str):
            continue  # type: ignore[unreachable]
        normalized_target = target_path.strip()
        if not normalized_target or normalized_target in seen_targets:
            continue
        seen_targets.add(normalized_target)
        cursor.execute(
            "INSERT OR REPLACE INTO entry_relations (source_path, target_path) VALUES (?, ?)",
            (source_rel_path, normalized_target),
        )
        inserted += 1
    conn.commit()
    return inserted


def replace_entry_relations(
    conn: sqlite3.Connection, source_rel_path: str, target_paths: List[str]
) -> int:
    """Replace all relations for a single source entry incrementally."""
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM entry_relations WHERE source_path = ?", (source_rel_path,)
    )
    conn.commit()
    return add_entry_relations(conn, source_rel_path, target_paths)


def get_backlinked_by(conn: sqlite3.Connection, target_path: str) -> List[str]:
    """Return rel_paths that point to target_path."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT source_path FROM entry_relations WHERE target_path = ? ORDER BY source_path",
        (target_path,),
    )
    return [row[0] for row in cursor.fetchall()]


def get_cache_stats() -> Dict[str, Any]:
    """获取缓存统计信息"""
    conn = init_metadata_cache()
    try:
        cursor = conn.cursor()

        # 总条目数
        cursor.execute("SELECT COUNT(*) FROM metadata_cache")
        total_entries = cursor.fetchone()[0]

        # 缓存大小
        db_size = METADATA_DB_PATH.stat().st_size if METADATA_DB_PATH.exists() else 0

        # 最后更新时间
        cursor.execute("SELECT MAX(cached_at) FROM metadata_cache")
        last_update = cursor.fetchone()[0]

        return {
            "total_entries": total_entries,
            "db_size_mb": round(db_size / (1024 * 1024), 2),
            "last_update": last_update,
            "cache_path": str(METADATA_DB_PATH),
            "rebuild_hint": METADATA_CACHE_REBUILD_HINT,
        }
    finally:
        conn.close()


def update_cache_for_all_journals(
    progress_callback: Optional[Callable[[int, int, int], None]] = None,
) -> Dict[str, int]:
    """更新所有日志的缓存（用于重建缓存）"""
    conn = init_metadata_cache()
    try:
        updated = 0
        skipped = 0
        errors = 0

        # 遍历所有日志文件
        if JOURNALS_DIR.exists():
            for year_dir in JOURNALS_DIR.iterdir():
                if not year_dir.is_dir() or not year_dir.name.isdigit():
                    continue

                for month_dir in year_dir.iterdir():
                    if not month_dir.is_dir():
                        continue

                    for journal_file in month_dir.glob("*.md"):
                        try:
                            # 检查缓存是否有效
                            cached = get_cached_metadata(conn, journal_file)
                            if cached:
                                skipped += 1
                                continue

                            # 更新缓存
                            result = parse_and_cache_journal(conn, journal_file)
                            if result:
                                updated += 1
                            else:
                                errors += 1

                            if progress_callback:
                                progress_callback(updated, skipped, errors)

                        except (IOError, OSError, ValueError):
                            errors += 1

        return {
            "updated": updated,
            "skipped": skipped,
            "errors": errors,
        }
    finally:
        conn.close()
