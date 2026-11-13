#!/usr/bin/env python3
"""
Life Index - FTS Update Module
FTS5 索引更新功能

从 search_index.py 提取的索引构建/更新逻辑。

增量扫描以文件 (mtime, size) 签名（fts_file_stats 侧表）判定"未变更"，
只读取新增/变更文件；insert_fts_doc 是 "file → FTS row" 的唯一插入路径，
全量重建与写入/编辑后的单行写穿共用它。

文件只读取一次（bytes）：行内容、file_hash 与签名都从这一次读取派生；
读取前后的签名必须一致才记录签名行，否则行照常写入但不记录签名，
下一次扫描会重新读取该文件。
"""

import hashlib
import logging
import sqlite3
import time as _time_module
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterable

logger = logging.getLogger(__name__)

_REBUILD_MARKER_NAME = ".rebuilding"

from .chinese_tokenizer import segment_for_fts
from .frontmatter import parse_frontmatter
from .journal_files import (
    JournalFileStat,
    fragment_date_from_filename,
    scan_journal_files,
)
from .path_contract import build_journal_path_fields, safe_relative_path

FileSignature = tuple[float, int]


def get_file_hash(file_path: Path) -> str:
    """计算文件内容哈希，用于检测变更"""
    try:
        content = file_path.read_bytes()
        return hashlib.md5(content, usedforsecurity=False).hexdigest()[:16]
    except (OSError, IOError):
        return ""


def _content_hash(raw: bytes) -> str:
    return hashlib.md5(raw, usedforsecurity=False).hexdigest()[:16]


def _normalize_to_str(value: Any) -> str:
    """将值规范化为字符串"""
    if not value:
        return ""
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    return str(value)


def _path_signature(file_path: Path) -> FileSignature | None:
    """The file's own ``(mtime, size)``; ``None`` when it cannot be stat-ed."""
    try:
        stat = file_path.stat()
    except OSError:
        return None
    return (stat.st_mtime, stat.st_size)


def _read_identity(
    file_path: Path,
) -> tuple[tuple[int, int, int], FileSignature] | None:
    """One stat for both the stability identity and the persistent signature.

    Stability uses ``(st_mtime_ns, st_size, st_ino)``: a file replaced by
    another one with the same mtime and size still has a different inode.
    The persistent ``fts_file_stats`` signature stays ``(mtime, size)``.
    """
    try:
        stat = file_path.stat()
    except OSError:
        return None
    identity = (stat.st_mtime_ns, stat.st_size, stat.st_ino)
    return identity, (stat.st_mtime, stat.st_size)


def _require_str(metadata: dict[str, Any], key: str) -> str:
    """Return a metadata scalar as ``str``; an unexpected type is unparsable."""
    value = metadata.get(key, "")
    if value is None:
        return ""
    if not isinstance(value, str):
        raise TypeError(f"field {key!r} must be a string, got {type(value).__name__}")
    return value


def _metadata_text(value: Any) -> str:
    """Normalize an indexed list-or-string field; other types are unparsable."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    raise TypeError(f"field must be a string or list, got {type(value).__name__}")


def _parse_content(
    content: str,
    raw: bytes,
    file_path: Path,
    journals_dir: Path,
    user_data_dir: Path,
    modified_time_ts: float | None,
) -> dict[str, Any] | None:
    """Build an index document from parsed frontmatter; ``None`` when unparsable."""
    try:
        if not content.startswith("---"):
            return None

        # 使用 SSOT frontmatter 解析
        metadata, body = parse_frontmatter(content)
        if not metadata:
            return None

        # 构建可索引文档
        path_fields = build_journal_path_fields(
            file_path, journals_dir=journals_dir, user_data_dir=user_data_dir
        )

        # MD3: Only segment title + content for FTS; metadata columns stay raw.
        # file_hash is computed from the same bytes the row content came from.
        # R11 fix: 'title' stores raw original text (for display),
        # 'title_segmented' stores jieba tokens (for FTS matching).
        raw_title = _require_str(metadata, "title")
        segmented_title = segment_for_fts(raw_title, mode="index")
        segmented_content = segment_for_fts(body, mode="index")

        return {
            "path": path_fields["rel_path"],
            "title": raw_title,
            "title_segmented": segmented_title,
            "content": segmented_content,
            "date": _require_str(metadata, "date")[:10],
            "location": _require_str(metadata, "location"),
            "weather": _require_str(metadata, "weather"),
            "topic": _metadata_text(metadata.get("topic")),
            "project": _require_str(metadata, "project"),
            "tags": _metadata_text(metadata.get("tags")),
            "mood": _metadata_text(metadata.get("mood")),
            "people": _metadata_text(metadata.get("people")),
            "file_hash": _content_hash(raw),
            "modified_time": (
                datetime.fromtimestamp(modified_time_ts).isoformat()
                if modified_time_ts is not None
                else ""
            ),
        }

    except Exception as e:  # noqa: BLE001 - any parse/type failure means raw text
        logger.warning("Failed to parse %s: %s", file_path, e)
        return None


def _raw_document(
    content: str,
    raw: bytes,
    file_path: Path,
    journals_dir: Path,
    user_data_dir: Path,
    modified_time_ts: float | None,
) -> dict[str, Any]:
    """Build a row for a live fragment whose frontmatter did not parse.

    CHARTER §1.11 does not allow a fragment the user can describe with a token
    to be unreachable: the whole file text is segmented into ``content``; every
    metadata column stays empty except ``date``, which falls back to the date
    carried by the canonical fragment filename.
    """
    path_fields = build_journal_path_fields(
        file_path, journals_dir=journals_dir, user_data_dir=user_data_dir
    )
    return {
        "path": path_fields["rel_path"],
        "title": "",
        "title_segmented": "",
        "content": segment_for_fts(content, mode="index"),
        "date": fragment_date_from_filename(file_path) or "",
        "location": "",
        "weather": "",
        "topic": "",
        "project": "",
        "tags": "",
        "mood": "",
        "people": "",
        "file_hash": _content_hash(raw),
        "modified_time": (
            datetime.fromtimestamp(modified_time_ts).isoformat()
            if modified_time_ts is not None
            else ""
        ),
        "unparsable": True,
    }


def read_journal_document(
    file_path: Path, journals_dir: Path, user_data_dir: Path
) -> tuple[dict[str, Any], FileSignature | None, bool]:
    """Read a journal once and derive its row and signature from those bytes.

    Returns ``(document, recorded_signature, unparsable)``. The file is read
    exactly once (``read_bytes``); the row content, ``file_hash`` and
    ``modified_time`` all come from that read. ``OSError`` propagates so the
    caller can treat a transient read failure as "not repaired" instead of
    deleting a valid row.

    Every readable live fragment yields a document. When the frontmatter does
    not parse (no leading ``---``, empty/invalid YAML, a field of an unexpected
    type, bytes that are not valid UTF-8) the document is the raw-text row from
    :func:`_raw_document` and ``unparsable`` is True.

    ``recorded_signature`` is ``None`` unless the stability identity
    ``(st_mtime_ns, st_size, st_ino)`` is unchanged across the read; the next
    scan then re-reads the file. The signature itself stays ``(mtime, size)``.
    """
    before = _read_identity(file_path)
    raw = file_path.read_bytes()
    after = _read_identity(file_path)
    stable = before is not None and after is not None and before[0] == after[0]
    before_signature = before[1] if before is not None else None
    after_signature = after[1] if after is not None else None
    modified_ts = (
        before_signature[0]
        if before_signature is not None
        else (after_signature[0] if after_signature is not None else None)
    )

    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError as e:
        logger.warning("Failed to decode %s as UTF-8: %s", file_path, e)
        content = raw.decode("utf-8", errors="replace")
        doc = None
    else:
        doc = _parse_content(content, raw, file_path, journals_dir, user_data_dir, modified_ts)

    unparsable = doc is None
    if doc is None:
        doc = _raw_document(content, raw, file_path, journals_dir, user_data_dir, modified_ts)

    return doc, (before_signature if stable else None), unparsable


def parse_journal(
    file_path: Path, journals_dir: Path, user_data_dir: Path
) -> dict[str, Any] | None:
    """解析日志文件，提取可索引内容（单次读取）

    Returns ``None`` only when the file cannot be read or its frontmatter does
    not parse; the index itself no longer drops an unparsable live fragment.
    """
    try:
        doc, _signature, unparsable = read_journal_document(file_path, journals_dir, user_data_dir)
    except (OSError, IOError) as e:
        logger.warning("Failed to parse %s: %s", file_path, e)
        return None
    return None if unparsable else doc


def get_indexed_files(conn: sqlite3.Connection) -> dict[str, tuple[str, str]]:
    """获取已索引的文件列表（路径 -> (hash, modified_time)）"""
    cursor = conn.cursor()
    cursor.execute("SELECT path, file_hash, modified_time FROM journals")

    result = {}
    for row in cursor.fetchall():
        result[row[0]] = (row[1], row[2])

    return result


def get_file_stats(conn: sqlite3.Connection) -> dict[str, FileSignature]:
    """获取已记录的文件签名（路径 -> (mtime, size)，来自 fts_file_stats 侧表）。"""
    cursor = conn.cursor()
    cursor.execute("SELECT path, mtime, size FROM fts_file_stats")

    result = {}
    for row in cursor.fetchall():
        result[row[0]] = (row[1], row[2])

    return result


def record_file_signature(
    cursor: sqlite3.Cursor, rel_path: str, signature: FileSignature | None
) -> None:
    """Record (or clear) a file's signature for the next stat-only scan.

    ``signature=None`` means the file changed while it was read; clearing the
    row makes the next scan re-read the file rather than trust stale facts.
    """
    cursor.execute("DELETE FROM fts_file_stats WHERE path = ?", (rel_path,))
    if signature is not None:
        cursor.execute(
            "INSERT OR REPLACE INTO fts_file_stats (path, mtime, size) VALUES (?, ?, ?)",
            (rel_path, signature[0], signature[1]),
        )


def insert_fts_doc(cursor: sqlite3.Cursor, doc: dict[str, Any]) -> None:
    """插入一条 FTS 行（"file → FTS row" 的唯一插入路径）。

    全量重建与写入/编辑后的单行写穿共用本函数，保证两条路径产出的行
    逐列一致（含真实 file_hash 与文件真实 mtime）。
    """
    cursor.execute(
        """
                    INSERT INTO journals (
                        path, title, title_segmented, content, date, location, weather,
                        topic, project, tags, mood, people,
                        file_hash, modified_time
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
        (
            doc["path"],
            doc["title"],
            doc["title_segmented"],
            doc["content"],
            doc["date"],
            doc["location"],
            doc["weather"],
            doc["topic"],
            doc["project"],
            doc["tags"],
            doc["mood"],
            doc["people"],
            doc["file_hash"],
            doc["modified_time"],
        ),
    )


@dataclass(frozen=True, slots=True)
class FtsSignatureReport:
    """Read-only result of comparing live fragments with the FTS index.

    ``current`` is True only when every live fragment has an FTS row and a
    matching ``fts_file_stats`` signature, no row/stat exists for a path that
    is gone, and the pending queue is empty.
    """

    current: bool
    reasons: tuple[str, ...] = ()
    live_files: int = 0
    indexed_rows: int = 0
    stat_rows: int = 0

    def to_dict(self) -> dict[str, Any]:
        # Envelope-safe: cap the reason list, keep the total count.
        return {
            "current": self.current,
            "reasons": list(self.reasons[:20]),
            "reason_count": len(self.reasons),
            "live_files": self.live_files,
            "indexed_rows": self.indexed_rows,
            "stat_rows": self.stat_rows,
        }


def inspect_fts_index(
    conn: sqlite3.Connection,
    journals_dir: Path,
    user_data_dir: Path,
    pending_paths: Iterable[str] = (),
    live: list[JournalFileStat] | None = None,
) -> FtsSignatureReport:
    """Signature check: one directory scan + two indexed reads. Never opens a journal.

    A fragment is current only when it has an FTS row *and* a stats row whose
    ``(mtime, size)`` matches the directory listing. A listing/file mismatch
    is confirmed with one real stat of that file before it counts as changed
    (the metadata cache's ``_row_is_current`` applies the same rule).

    ``live`` is a ``scan_journal_files(journals_dir)`` result the caller
    already holds; passing it avoids a second walk of the tree.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT path FROM journals")
    indexed_rows = {row[0] for row in cursor.fetchall()}
    cursor.execute("SELECT path, mtime, size FROM fts_file_stats")
    recorded_stats: dict[str, FileSignature] = {
        row[0]: (row[1], row[2]) for row in cursor.fetchall()
    }

    if live is None:
        live = scan_journal_files(journals_dir)
    current_paths: set[str] = set()
    reasons: list[str] = []

    for item in live:
        rel_path = safe_relative_path(item.path, user_data_dir)
        current_paths.add(rel_path)
        if rel_path not in indexed_rows:
            reasons.append(f"missing_row: {rel_path}")
            continue
        recorded = recorded_stats.get(rel_path)
        if recorded is None:
            reasons.append(f"missing_signature: {rel_path}")
            continue
        if recorded == (item.mtime, item.size):
            continue
        # The directory listing and the recorded signature disagree. Confirm
        # with one real stat of that file before treating it as changed.
        if _path_signature(item.path) == recorded:
            continue
        reasons.append(f"changed: {rel_path}")

    for rel_path in sorted((indexed_rows | set(recorded_stats)) - current_paths):
        reasons.append(f"vanished: {rel_path}")

    pending = list(pending_paths)
    if pending:
        reasons.append("pending_writes")

    return FtsSignatureReport(
        current=not reasons,
        reasons=tuple(reasons),
        live_files=len(live),
        indexed_rows=len(indexed_rows),
        stat_rows=len(recorded_stats),
    )


def inspect_fts_db(
    fts_db_path: Path,
    journals_dir: Path,
    user_data_dir: Path,
    pending_paths: Iterable[str] = (),
    live: list[JournalFileStat] | None = None,
) -> FtsSignatureReport:
    """Open the FTS database read-only and run :func:`inspect_fts_index`."""
    if not fts_db_path.exists():
        return FtsSignatureReport(current=False, reasons=("no_fts_db",))
    try:
        conn = sqlite3.connect(str(fts_db_path))
    except sqlite3.Error as exc:
        return FtsSignatureReport(current=False, reasons=(f"db_error: {exc}",))
    try:
        return inspect_fts_index(conn, journals_dir, user_data_dir, pending_paths, live)
    except sqlite3.Error as exc:
        return FtsSignatureReport(current=False, reasons=(f"db_error: {exc}",))
    finally:
        conn.close()


def fts_index_is_current() -> bool:
    """Read-only signature check of the configured FTS index (never opens a journal)."""
    from .paths import get_fts_db_path, get_journals_dir, get_user_data_dir
    from .pending_writes import get_pending

    report = inspect_fts_db(
        get_fts_db_path(),
        get_journals_dir(),
        get_user_data_dir(),
        pending_paths=get_pending(),
    )
    return report.current


def _check_rebuild_marker(fts_db_path: Path) -> Path:
    """Remove an orphaned rebuild marker and return its path.

    The caller holds the index lock, so an existing marker cannot belong to a
    live builder for this data directory: whoever wrote it died before removing
    it (including a process killed during the automatic schema-version
    rebuild). Removing it and continuing is safe; the old 300-second age rule
    blocked every repair for five minutes while searches kept stale rows.
    """
    marker = fts_db_path.parent / _REBUILD_MARKER_NAME
    if marker.exists():
        logger.warning("Removing orphaned rebuild marker (index lock held): %s", marker)
        try:
            marker.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("Failed to remove orphaned rebuild marker %s: %s", marker, exc)
    return marker


def _write_rebuild_marker(marker: Path) -> None:
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(f"{_time_module.time()}", encoding="utf-8")


def _remove_rebuild_marker(marker: Path) -> None:
    try:
        marker.unlink(missing_ok=True)
    except OSError as exc:
        logger.warning("Failed to remove rebuild marker %s: %s", marker, exc)


def update_index(
    init_fts_db_func: Callable[[], sqlite3.Connection],
    fts_db_path: Path,
    journals_dir: Path,
    user_data_dir: Path,
    incremental: bool = True,
    force_paths: Iterable[str] | None = None,
    lock_held: bool = False,
) -> dict[str, Any]:
    """
    更新搜索索引

    Args:
        init_fts_db_func: 初始化 FTS 数据库的函数（来自 search_index.init_fts_db）
        fts_db_path: FTS 数据库路径
        journals_dir: 日志目录
        user_data_dir: 用户数据目录
        incremental: True=仅更新变更，False=全量重建
        force_paths: 无论签名是否变化都必须重读的路径（pending 队列快照）
        lock_held: True 表示调用方已持有 index lock（例如 build_all）；默认
            本函数自己获取同一把锁。

    Returns:
        {
            "success": bool,
            "added": int,
            "updated": int,
            "removed": int,
            "total": int,
            "unparsable": int,          # additive: read as raw text (frontmatter did not parse)
            "unparsable_paths": [str],  # additive
            "pending_repaired": [str],  # additive: force_paths actually repaired
            "error": str (optional)
        }
    """
    if lock_held:
        return _update_index_locked(
            init_fts_db_func,
            fts_db_path,
            journals_dir,
            user_data_dir,
            incremental,
            force_paths,
        )

    from .config import FILE_LOCK_TIMEOUT_REBUILD
    from .file_lock import FileLock, get_index_lock_path

    with FileLock(get_index_lock_path(), timeout=FILE_LOCK_TIMEOUT_REBUILD):
        return _update_index_locked(
            init_fts_db_func,
            fts_db_path,
            journals_dir,
            user_data_dir,
            incremental,
            force_paths,
        )


def _update_index_locked(
    init_fts_db_func: Callable[[], sqlite3.Connection],
    fts_db_path: Path,
    journals_dir: Path,
    user_data_dir: Path,
    incremental: bool,
    force_paths: Iterable[str] | None,
) -> dict[str, Any]:
    """Run one scan while the shared index lock is held."""
    forced = set(force_paths or ())
    result: dict[str, Any] = {
        "success": False,
        "added": 0,
        "updated": 0,
        "removed": 0,
        "total": 0,
        "unparsable": 0,
        "unparsable_paths": [],
        "pending_repaired": [],
        "error": None,
    }

    marker: Path | None = None
    marker_written = False

    try:
        if not incremental:
            marker = _check_rebuild_marker(fts_db_path)
            _write_rebuild_marker(marker)
            marker_written = True

        conn = init_fts_db_func()
        try:
            cursor = conn.cursor()

            # 获取当前已索引的文件与已记录的文件签名
            indexed_files = get_indexed_files(conn)
            indexed_stats = get_file_stats(conn)

            # 扫描所有日志文件（仅经 journal_files 枚举；以 (mtime, size)
            # stat-only 判定是否变更——未变更的文件不再被读取或哈希）。
            current_files: set[str] = set()
            files_to_update: list[tuple[str, Path, str]] = []

            if journals_dir.exists():
                for item in scan_journal_files(journals_dir):
                    rel_path = safe_relative_path(item.path, user_data_dir)
                    current_files.add(rel_path)
                    if not incremental:
                        files_to_update.append(("add", item.path, rel_path))
                        continue

                    row_exists = rel_path in indexed_files
                    recorded = indexed_stats.get(rel_path)
                    scanned = (item.mtime, item.size)

                    # R3: a pending path is always re-read, whatever its
                    # signature says. Otherwise R1: a matching signature is
                    # not enough — the FTS row must exist too.
                    if rel_path not in forced:
                        if row_exists and recorded == scanned:
                            continue
                        # A listing/recorded mismatch is confirmed with one
                        # real stat before the file is treated as changed.
                        if (
                            row_exists
                            and recorded is not None
                            and _path_signature(item.path) == recorded
                        ):
                            continue

                    action = "update" if row_exists else "add"
                    files_to_update.append((action, item.path, rel_path))

            # Pending paths that are not live fragments any more: nothing to
            # read (the deletion pass below removes any stale row/stat).
            for rel_path in sorted(forced - current_files):
                logger.debug("Pending path is not a live fragment: %s", rel_path)

            # 找出需要删除的索引（文件已不存在；含孤儿签名行）
            files_to_remove = (set(indexed_files.keys()) | set(indexed_stats)) - current_files
            repaired: list[str] = sorted(
                rel_path for rel_path in files_to_remove if rel_path in forced
            )
            # A forced path that is no longer a live fragment and has no row
            # or signature has nothing left to repair; acknowledge it so it
            # cannot stay queued forever.
            repaired.extend(
                rel_path
                for rel_path in sorted(forced - current_files)
                if rel_path not in indexed_files and rel_path not in indexed_stats
            )

            # 如果不是增量模式，清空所有索引
            if not incremental:
                cursor.execute("DELETE FROM journals")
                cursor.execute("DELETE FROM fts_file_stats")
                result["removed"] = len(indexed_files)
                files_to_remove = set()

            # 执行删除
            for rel_path in files_to_remove:
                cursor.execute("DELETE FROM journals WHERE path = ?", (rel_path,))
                cursor.execute("DELETE FROM fts_file_stats WHERE path = ?", (rel_path,))
                result["removed"] = (result["removed"] or 0) + 1

            # 执行添加/更新
            for action, file_path, rel_path in files_to_update:
                try:
                    doc, signature, unparsable = read_journal_document(
                        file_path, journals_dir, user_data_dir
                    )
                except (OSError, IOError) as e:
                    # Transient read failure: keep whatever row and signature
                    # exist; the file stays not-current and a later scan retries.
                    logger.warning("Failed to read %s: %s", rel_path, e)
                    continue

                if unparsable:
                    # D1: every live fragment has a row. The frontmatter did not
                    # parse, so the row is the segmented full text with empty
                    # metadata; it is current like any other row.
                    result["unparsable"] = (result["unparsable"] or 0) + 1
                    result["unparsable_paths"].append(rel_path)
                    logger.warning(
                        "Journal frontmatter did not parse; indexed as raw text: %s", rel_path
                    )

                # 如果是更新，先删除旧记录
                if not incremental:
                    result["added"] = (result["added"] or 0) + 1
                elif action == "update":
                    cursor.execute("DELETE FROM journals WHERE path = ?", (rel_path,))
                    result["updated"] = (result["updated"] or 0) + 1
                elif rel_path in indexed_files:
                    # A pending/repaired file whose row already exists.
                    cursor.execute("DELETE FROM journals WHERE path = ?", (rel_path,))
                    result["updated"] = (result["updated"] or 0) + 1
                else:
                    result["added"] = (result["added"] or 0) + 1

                insert_fts_doc(cursor, doc)
                # R4: only a stable read may record a signature.
                record_file_signature(cursor, rel_path, signature)
                if rel_path in forced:
                    repaired.append(rel_path)

            conn.commit()

            # 更新总数
            result["total"] = len(current_files)
            result["pending_repaired"] = sorted(set(repaired))
            result["success"] = True
        finally:
            conn.close()

    except (OSError, IOError, sqlite3.Error) as e:
        result["error"] = str(e)
    finally:
        if marker is not None and marker_written:
            _remove_rebuild_marker(marker)

    return result
