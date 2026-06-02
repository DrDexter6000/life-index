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

import datetime
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from .paths import get_cache_dir, get_metadata_db_path, get_journals_dir, get_user_data_dir
from .frontmatter import parse_journal_file
from .path_contract import build_journal_path_fields

CACHE_VERSION_SCHEMA_VERSION = "v1.1.1"

# 缓存存储目录 (deprecated: use getters)
CACHE_DIR = get_cache_dir()  # deprecated: use get_cache_dir()
METADATA_DB_PATH = get_metadata_db_path()  # deprecated: use get_metadata_db_path()
USER_DATA_DIR = get_user_data_dir()  # deprecated: use get_user_data_dir()
JOURNALS_DIR = get_journals_dir()  # deprecated: use get_journals_dir()
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
        file_path, journals_dir=get_journals_dir(), user_data_dir=get_user_data_dir()
    )["path"]
    legacy = str(file_path)

    keys = [normalized]
    if legacy != normalized:
        keys.append(legacy)
    return keys


def init_metadata_cache() -> sqlite3.Connection:
    """初始化元数据缓存数据库"""
    get_cache_dir().mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(get_metadata_db_path()))
    conn.execute("PRAGMA journal_mode=WAL")  # 启用 WAL 模式提升并发性能
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 创建元数据缓存表
    cursor.execute(
        """
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
    """
    )

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
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_metadata_date
        ON metadata_cache(date)
    """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_metadata_topic
        ON metadata_cache(topic)
    """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_metadata_project
        ON metadata_cache(project)
    """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_metadata_location
        ON metadata_cache(location)
    """
    )

    # 创建缓存状态表
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS cache_meta (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """
    )

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
    if "word_count" not in existing_columns:
        cursor.execute("ALTER TABLE metadata_cache ADD COLUMN word_count INTEGER")
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


def parse_and_cache_journal(conn: sqlite3.Connection, file_path: Path) -> Optional[Dict[str, Any]]:
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
            file_path, journals_dir=get_journals_dir(), user_data_dir=get_user_data_dir()
        )
        file_path_str = path_fields["path"]
        date = metadata.get("date", "")[:10] if metadata.get("date") else ""
        title = metadata.get("title", "")
        location = metadata.get("location", "")
        weather = metadata.get("weather", "")
        abstract = metadata.get("abstract", "")
        links = json.dumps(metadata.get("links", []), ensure_ascii=False)
        related_entries = json.dumps(metadata.get("related_entries", []), ensure_ascii=False)

        # 数组字段转为JSON
        topic = json.dumps(metadata.get("topic", []), ensure_ascii=False)
        project = metadata.get("project", "")
        tags = json.dumps(metadata.get("tags", []), ensure_ascii=False)
        mood = json.dumps(metadata.get("mood", []), ensure_ascii=False)
        people = json.dumps(metadata.get("people", []), ensure_ascii=False)

        # 计算字数（基于正文，不含 frontmatter）
        word_count = len(metadata.get("_body", "").split())

        # 更新缓存
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO metadata_cache
            (file_path, date, title, location, weather, topic, project,
             tags, mood, people, abstract, links, related_entries,
             word_count, file_mtime, file_size)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                word_count,
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
            "word_count": word_count,
            "metadata": {**metadata, "word_count": word_count},
        }

    except (IOError, OSError, ValueError):
        return None


def get_cached_metadata(conn: sqlite3.Connection, file_path: Path) -> Optional[Dict[str, Any]]:
    """从缓存获取元数据（如果有效）"""
    cursor = conn.cursor()
    candidate_keys = _candidate_cache_keys(file_path)

    if len(candidate_keys) == 1:
        cursor.execute("SELECT * FROM metadata_cache WHERE file_path = ?", (candidate_keys[0],))
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
        row["file_path"], journals_dir=get_journals_dir(), user_data_dir=get_user_data_dir()
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
        "related_entries": json.loads(row["related_entries"]) if row["related_entries"] else [],
        "word_count": row["word_count"] if row["word_count"] is not None else 0,
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
            "related_entries": json.loads(row["related_entries"]) if row["related_entries"] else [],
            "word_count": row["word_count"] if row["word_count"] is not None else 0,
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
                journals_dir=get_journals_dir(),
                user_data_dir=get_user_data_dir(),
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
                    "related_entries": (
                        json.loads(row["related_entries"]) if row["related_entries"] else []
                    ),
                    "word_count": row["word_count"] if row["word_count"] is not None else 0,
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
                        "related_entries": (
                            json.loads(row["related_entries"]) if row["related_entries"] else []
                        ),
                        "word_count": row["word_count"] if row["word_count"] is not None else 0,
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
            row["file_path"], journals_dir=get_journals_dir(), user_data_dir=get_user_data_dir()
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
    cursor.execute("DELETE FROM entry_relations WHERE source_path = ?", (source_rel_path,))
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
        db_size = get_metadata_db_path().stat().st_size if get_metadata_db_path().exists() else 0

        # 最后更新时间
        cursor.execute("SELECT MAX(cached_at) FROM metadata_cache")
        last_update = cursor.fetchone()[0]

        return {
            "total_entries": total_entries,
            "db_size_mb": round(db_size / (1024 * 1024), 2),
            "last_update": last_update,
            "cache_path": str(get_metadata_db_path()),
            "rebuild_hint": METADATA_CACHE_REBUILD_HINT,
        }
    finally:
        conn.close()


# ============================================================
# Cache Version Sidecar (v1.1.1)
# ============================================================


def _get_tool_version() -> str:
    try:
        from importlib.metadata import PackageNotFoundError, version as package_version

        return package_version("life-index")
    except PackageNotFoundError:
        pass
    try:
        bootstrap = Path(__file__).parent.parent.parent / "bootstrap-manifest.json"
        if bootstrap.exists():
            data = json.loads(bootstrap.read_text(encoding="utf-8"))
            v = data.get("repo_version")
            if isinstance(v, str) and v:
                return v
    except (OSError, ValueError, json.JSONDecodeError):
        pass
    return "dev"


def get_cache_version_dir() -> Path:
    return get_user_data_dir() / ".life-index" / "cache"


def get_cache_version_path() -> Path:
    return get_cache_version_dir() / "_version.json"


def _compute_source_hash() -> str:
    journals_dir = get_journals_dir()
    sha = hashlib.sha256()
    if journals_dir.exists():
        for journal_file in sorted(journals_dir.rglob("*.md")):
            try:
                sha.update(journal_file.read_bytes())
            except (IOError, OSError):
                continue
    for meta_file in sorted(get_user_data_dir().glob("entity_graph.yaml")):
        try:
            sha.update(meta_file.read_bytes())
        except (IOError, OSError):
            continue
    return f"sha256:{sha.hexdigest()}"


def write_cache_version(
    source_hash: str = "",
    invalidation_reason: str = "",
    from_version: str = "",
) -> Dict[str, Any]:
    version_dir = get_cache_version_dir()
    version_dir.mkdir(parents=True, exist_ok=True)

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    if not source_hash:
        source_hash = _compute_source_hash()

    existing = read_cache_version()
    invalidation_history: list = []
    if existing:
        invalidation_history = list(existing.get("invalidation_history", []))
    if invalidation_reason:
        invalidation_history.append(
            {
                "at": now_iso,
                "reason": invalidation_reason,
                "from_version": from_version,
            }
        )

    data: Dict[str, Any] = {
        "schema_version": CACHE_VERSION_SCHEMA_VERSION,
        "tool_version": _get_tool_version(),
        "created_at": now_iso,
        "source_hash": source_hash,
        "invalidation_history": invalidation_history,
    }

    version_path = get_cache_version_path()
    version_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return data


def read_cache_version() -> Optional[Dict[str, Any]]:
    version_path = get_cache_version_path()
    if not version_path.exists():
        return None
    try:
        data = json.loads(version_path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
        return None
    except (json.JSONDecodeError, OSError):
        return None


def evaluate_cache_state(
    data_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    current_hash = _compute_source_hash() if data_dir is None else "unknown"
    stored = read_cache_version() if data_dir is None else None

    if data_dir is not None:
        version_path = data_dir / ".life-index" / "cache" / "_version.json"
        if version_path.exists():
            try:
                stored = json.loads(version_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                stored = None

    exists = stored is not None
    version_match = False
    hash_match = False
    would_rebuild = not exists

    if exists and stored:
        version_match = stored.get("schema_version") == CACHE_VERSION_SCHEMA_VERSION
        stored_hash = stored.get("source_hash", "")
        hash_match = stored_hash == current_hash
        if not version_match or not hash_match:
            would_rebuild = True

    reasons: List[str] = []
    if not exists:
        reasons.append("no_existing_version")
    elif not version_match:
        reasons.append("schema_version_mismatch")
    elif not hash_match:
        reasons.append("source_hash_mismatch")

    return {
        "exists": exists,
        "stored_schema_version": stored.get("schema_version") if stored else None,
        "stored_source_hash": stored.get("source_hash") if stored else None,
        "current_schema_version": CACHE_VERSION_SCHEMA_VERSION,
        "version_match": version_match,
        "hash_match": hash_match,
        "would_rebuild": would_rebuild,
        "reasons": reasons,
    }


def run_cache_audit() -> Dict[str, Any]:
    stored = read_cache_version()
    version_exists = stored is not None
    status = "missing"

    if stored:
        current_hash = _compute_source_hash()
        version_match = stored.get("schema_version") == CACHE_VERSION_SCHEMA_VERSION
        hash_match = stored.get("source_hash") == current_hash
        if version_match and hash_match:
            status = "valid"
        elif version_match and not hash_match:
            status = "stale"
        else:
            status = "incompatible"

    return {
        "success": True,
        "cache_audit": {
            "version_exists": version_exists,
            "status": status,
            "json": True,
        },
    }


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
        if get_journals_dir().exists():
            for year_dir in get_journals_dir().iterdir():
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
