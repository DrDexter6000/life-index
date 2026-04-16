#!/usr/bin/env python3
"""
Life Index - Write Journal Tool - Index Updater
索引更新模块
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..lib.config import JOURNALS_DIR, BY_TOPIC_DIR, get_index_prefixes
from ..lib.errors import ErrorCode, create_error_response
from ..lib.frontmatter import get_summary


def _build_entry(data: Dict[str, Any], journal_path: Path) -> str:
    """Build a by-topic entry line with optional summary."""
    date_str = data.get("date", "")[:10]
    title = data.get("title", "无标题")
    rel_path = os.path.relpath(journal_path, JOURNALS_DIR.parent).replace("\\", "/")
    summary = get_summary(data) or ""
    if summary:
        return f"- [{date_str}] [{title}]({rel_path}) — {summary}"
    return f"- [{date_str}] [{title}]({rel_path})"


def _sanitize_index_name(value: str) -> str:
    text = str(value or "").strip()
    return text.replace("/", "_").replace("\\", "_")


def sanitize_index_name(value: str) -> str:
    """Public SSOT helper for index-safe topic/project/tag names."""
    return _sanitize_index_name(value)


def build_index_filename(kind: str, value: str) -> str:
    prefixes = get_index_prefixes()
    default_prefixes = {"topic": "主题_", "project": "项目_", "tag": "标签_"}
    prefix = prefixes.get(kind, default_prefixes[kind])
    safe_value = sanitize_index_name(value)
    return f"{prefix}{safe_value}.md"


def update_topic_index(
    topic: Any, journal_path: Path, data: Dict[str, Any]
) -> List[Path]:
    """更新主题索引文件 - 支持单个主题或主题列表"""
    if not topic:
        return []

    # 统一处理为列表
    if isinstance(topic, str):
        topics = [topic]
    elif isinstance(topic, list):
        topics = topic
    else:
        return []

    entry = _build_entry(data, journal_path)

    updated = []
    for t in topics:
        if not t:
            continue
        BY_TOPIC_DIR.mkdir(parents=True, exist_ok=True)
        index_file = BY_TOPIC_DIR / build_index_filename("topic", str(t))

        if index_file.exists():
            content = index_file.read_text(encoding="utf-8")
            if entry not in content:
                with open(index_file, "a", encoding="utf-8") as f:
                    f.write(entry + "\n")
        else:
            with open(index_file, "w", encoding="utf-8") as f:
                f.write(f"# 主题: {t}\n\n")
                f.write(entry + "\n")

        updated.append(index_file)

    return updated


def update_project_index(
    project: str, journal_path: Path, data: Dict[str, Any]
) -> Optional[Path]:
    """更新项目索引文件"""
    if not project:
        return None

    # 获取可配置的前缀
    BY_TOPIC_DIR.mkdir(parents=True, exist_ok=True)
    index_file = BY_TOPIC_DIR / build_index_filename("project", project)

    entry = _build_entry(data, journal_path)

    if index_file.exists():
        content = index_file.read_text(encoding="utf-8")
        if entry not in content:
            with open(index_file, "a", encoding="utf-8") as f:
                f.write(entry + "\n")
    else:
        with open(index_file, "w", encoding="utf-8") as f:
            f.write(f"# 项目: {project}\n\n")
            f.write(entry + "\n")

    return index_file


def update_tag_indices(
    tags: List[str], journal_path: Path, data: Dict[str, Any]
) -> List[Path]:
    """更新标签索引文件"""
    updated = []

    # 获取可配置的前缀
    for tag in tags:
        if not tag:
            continue

        BY_TOPIC_DIR.mkdir(parents=True, exist_ok=True)
        index_file = BY_TOPIC_DIR / build_index_filename("tag", str(tag))

        entry = _build_entry(data, journal_path)

        if index_file.exists():
            content = index_file.read_text(encoding="utf-8")
            if entry not in content:
                with open(index_file, "a", encoding="utf-8") as f:
                    f.write(entry + "\n")
        else:
            with open(index_file, "w", encoding="utf-8") as f:
                f.write(f"# 标签: {tag}\n\n")
                f.write(entry + "\n")

        updated.append(index_file)

    return updated


def update_index(year: int, month: int, dry_run: bool = False) -> Dict[str, Any]:
    """
    Update index tree after journal write.

    Touches 3 files:
    1. index_YYYY-MM.md — monthly index
    2. index_YYYY.md — yearly index
    3. INDEX.md — root anchor

    Args:
        year: Year
        month: Month
        dry_run: Preview mode

    Returns:
        {
            "success": bool,
            "monthly_index": dict,
            "yearly_index": dict,
            "root_index": dict,
        }
    """
    from ..generate_index import (
        generate_monthly_index,
        generate_yearly_index,
        generate_root_index,
    )

    result: Dict[str, Any] = {"success": True}

    try:
        # 1. Monthly index
        monthly = generate_monthly_index(year=year, month=month, dry_run=dry_run)
        result["monthly_index"] = monthly

        # 2. Yearly index
        yearly = generate_yearly_index(year=year, dry_run=dry_run)
        result["yearly_index"] = yearly

        # 3. Root index
        root = generate_root_index(dry_run=dry_run)
        result["root_index"] = root

        # Mark degraded if any layer failed
        if not all(
            r.get("success", False) for r in [monthly, yearly, root] if r is not None
        ):
            result["success"] = False

    except Exception as e:
        result["success"] = False
        result.update(
            create_error_response(
                ErrorCode.INDEX_BUILD_FAILED,
                f"Index tree update failed: {e}",
                {"year": year, "month": month},
                "Index update is non-blocking; next write or rebuild will retry",
            )
        )

    return result


# Backward-compatible alias
update_monthly_abstract = update_index


def update_fts_index(journal_path: Path, data: Dict[str, Any]) -> bool:
    """写入后同步更新 FTS 索引（Write-Through）

    直接从内存中的 data 构建单条 FTS 文档并插入，无需重新读取文件。
    幂等：若 rel_path 已存在则先删除再插入。

    Args:
        journal_path: 日志文件最终路径（用于计算 rel_path）
        data: 日志数据（包含 title, content, date, tags, topic 等）

    Returns:
        True 如果更新成功，False 如果失败（不影响主流程）
    """
    try:
        from ..lib.search_index import init_fts_db, write_index_meta
        from ..lib.chinese_tokenizer import segment_for_fts
        from ..lib.config import JOURNALS_DIR, USER_DATA_DIR
        from ..lib.path_contract import build_journal_path_fields
        from datetime import datetime

        def _norm(value: Any) -> str:
            if not value:
                return ""
            if isinstance(value, list):
                return ", ".join(str(v) for v in value)
            return str(value)

        path_fields = build_journal_path_fields(
            journal_path, journals_dir=JOURNALS_DIR, user_data_dir=USER_DATA_DIR
        )
        rel_path = path_fields["rel_path"]

        # Segment title + body using same pipeline as full index build
        segmented_title = segment_for_fts(data.get("title", ""), mode="index")
        segmented_content = segment_for_fts(data.get("content", ""), mode="index")

        conn = init_fts_db()
        cursor = conn.cursor()

        # Idempotent: remove existing entry if present
        cursor.execute("DELETE FROM journals WHERE path = ?", (rel_path,))

        cursor.execute(
            """INSERT INTO journals (path, title, content, date, location, weather,
                                    topic, project, tags, mood, people, file_hash, modified_time)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                rel_path,
                segmented_title,
                segmented_content,
                str(data.get("date", ""))[:10],
                data.get("location", ""),
                data.get("weather", ""),
                _norm(data.get("topic")),
                data.get("project", ""),
                _norm(data.get("tags")),
                _norm(data.get("mood")),
                _norm(data.get("people")),
                "",  # file_hash: will be corrected on next incremental scan
                datetime.now().isoformat(),
            ),
        )

        # Refresh last_updated in index_meta
        write_index_meta(conn)

        conn.commit()
        conn.close()

        return True

    except Exception as e:
        # FTS update failure should not block journal write
        print(f"Warning: Failed to update FTS index: {e}")
        return False


def update_vector_index(journal_path: Path, data: Dict[str, Any]) -> bool:
    """
    写入后同步更新向量索引（Write-Through）

    Args:
        journal_path: 日志文件路径
        data: 日志数据（包含 title, content, abstract, tags, topic 等）

    Returns:
        True 如果更新成功，False 如果失败（不影响主流程）
    """
    try:
        from ..lib.vector_index_simple import get_model, get_index
        from ..lib.config import USER_DATA_DIR
        from ..lib.semantic_search import build_embedding_text

        model = get_model()
        if not model.load():
            return False

        embed_text = build_embedding_text(
            title=data.get("title"),
            body=data.get("content"),
            tags=data.get("tags"),
            topic=data.get("topic"),
        ).strip()
        if not embed_text:
            return False

        # 生成嵌入向量
        embeddings = model.encode([embed_text])
        if not embeddings:
            return False

        # 计算相对路径
        try:
            rel_path = str(journal_path.relative_to(USER_DATA_DIR)).replace("\\", "/")
        except ValueError:
            rel_path = str(journal_path).replace("\\", "/")

        # 更新索引
        index = get_index()
        date_str = str(data.get("date", ""))[:10]

        # 计算文件哈希用于后续增量更新检测
        import hashlib

        try:
            file_content = journal_path.read_bytes()
            file_hash = hashlib.md5(file_content).hexdigest()[:16]
        except Exception:
            file_hash = ""

        index.add(rel_path, embeddings[0], date_str, file_hash)
        index.commit()

        return True

    except (ImportError, OSError, IOError, RuntimeError) as e:
        # 向量索引更新失败不应阻塞日志写入
        # 日志会在下次 cron 全量重建时补上
        print(f"Warning: Failed to update vector index: {e}")
        return False
