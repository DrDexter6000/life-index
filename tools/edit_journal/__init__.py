#!/usr/bin/env python3
"""
Life Index - Edit Journal Tool
编辑已存在的日志文件，支持 frontmatter 字段修改和正文编辑

Usage:
    python -m tools.edit_journal --journal "Journals/2026/03/life-index_2026-03-05_001.md" \\
        --set-location "Beijing, China" --set-weather "多云"

Public API:
    from tools.edit_journal import edit_journal
    result = edit_journal(journal_path=path, frontmatter_updates={"weather": "晴天"})
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

# 导入配置 (relative imports from parent tools package)
from ..lib.config import JOURNALS_DIR, BY_TOPIC_DIR
from ..lib.frontmatter import (
    parse_journal_file,
    format_frontmatter,
)
from ..lib.file_lock import FileLock, LockTimeoutError, get_journals_lock_path
from ..lib.errors import ErrorCode, create_error_response
from ..lib.logger import get_logger
from ..lib.metadata_cache import init_metadata_cache, replace_entry_relations
from ..lib.revisions import save_revision
from ..write_journal.index_updater import update_vector_index
from ..write_journal.attachments import process_attachments

logger = get_logger(__name__)


def parse_journal(file_path: Path) -> Tuple[Dict[str, Any], str]:
    """
    解析日志文件，返回 (frontmatter_dict, content_body)
    使用 lib/frontmatter 模块实现
    """
    metadata = parse_journal_file(file_path)
    return metadata, metadata.get("_body", "")


# format_frontmatter 已移至 lib/frontmatter 模块


def remove_from_index(index_file: Path, journal_filename: str) -> bool:
    """从索引文件中移除指定日志条目"""
    if not index_file.exists():
        return False

    content = index_file.read_text(encoding="utf-8")
    lines = content.split("\n")

    new_lines = []
    removed = False
    for line in lines:
        if journal_filename in line and line.strip().startswith("- ["):
            removed = True
            logger.debug(f"从索引移除：{journal_filename}")
            continue
        new_lines.append(line)

    if removed:
        index_file.write_text("\n".join(new_lines), encoding="utf-8")
        logger.info(f"已更新索引文件：{index_file.name}")

    return removed


def add_to_index(index_file: Path, journal_path: Path, data: Dict[str, Any]) -> None:
    """添加日志条目到索引文件"""
    date_str = data.get("date", "")[:10] if data.get("date") else ""
    title = data.get("title", "无标题")
    rel_path = os.path.relpath(journal_path, JOURNALS_DIR.parent).replace("\\", "/")

    entry = f"- [{date_str}] [{title}]({rel_path})"

    BY_TOPIC_DIR.mkdir(parents=True, exist_ok=True)

    if index_file.exists():
        content = index_file.read_text(encoding="utf-8")
        if entry not in content:
            with open(index_file, "a", encoding="utf-8") as f:
                f.write(entry + "\n")
            logger.debug(f"添加条目到索引：{index_file.name}")
    else:
        # 确定索引类型和名称
        name = (
            index_file.stem.replace("主题_", "")
            .replace("项目_", "")
            .replace("标签_", "")
        )
        if index_file.stem.startswith("主题_"):
            header = f"# 主题：{name}\n\n"
        elif index_file.stem.startswith("项目_"):
            header = f"# 项目：{name}\n\n"
        elif index_file.stem.startswith("标签_"):
            header = f"# 标签：{name}\n\n"
        else:
            header = f"# {name}\n\n"

        with open(index_file, "w", encoding="utf-8") as f:
            f.write(header + entry + "\n")
        logger.info(f"创建索引文件：{index_file.name}")


def update_indices_for_change(
    journal_path: Path, old_data: Dict[str, Any], new_data: Dict[str, Any]
) -> List[str]:
    """
    根据数据变更更新索引
    返回更新的索引文件列表
    """
    updated_indices = []
    journal_filename = journal_path.name

    # 检查 topic 变更
    old_topics = _normalize_to_list(old_data.get("topic"))
    new_topics = _normalize_to_list(new_data.get("topic"))

    # 移除旧 topic 索引
    for topic in old_topics:
        if topic and topic not in new_topics:
            idx_file = BY_TOPIC_DIR / f"主题_{topic}.md"
            logger.info(f"检测到 topic 变更：{topic} -> 移除")
            if remove_from_index(idx_file, journal_filename):
                updated_indices.append(str(idx_file))

    # 添加到新 topic 索引
    for topic in new_topics:
        if topic:
            idx_file = BY_TOPIC_DIR / f"主题_{topic}.md"
            logger.info(f"检测到 topic 变更：添加 {topic}")
            add_to_index(idx_file, journal_path, new_data)
            if str(idx_file) not in updated_indices:
                updated_indices.append(str(idx_file))

    # 检查 project 变更
    old_project = old_data.get("project", "")
    new_project = new_data.get("project", "")

    if old_project != new_project:
        logger.info(f"检测到 project 变更：{old_project} -> {new_project}")
        # 移除旧 project 索引
        if old_project:
            idx_file = BY_TOPIC_DIR / f"项目_{old_project}.md"
            if remove_from_index(idx_file, journal_filename):
                if str(idx_file) not in updated_indices:
                    updated_indices.append(str(idx_file))

        # 添加到新 project 索引
        if new_project:
            idx_file = BY_TOPIC_DIR / f"项目_{new_project}.md"
            add_to_index(idx_file, journal_path, new_data)
            if str(idx_file) not in updated_indices:
                updated_indices.append(str(idx_file))

    # 检查 tags 变更
    old_tags = set(_normalize_to_list(old_data.get("tags")))
    new_tags = set(_normalize_to_list(new_data.get("tags")))

    # 移除旧 tag 索引
    for tag in old_tags - new_tags:
        if tag:
            idx_file = BY_TOPIC_DIR / f"标签_{tag}.md"
            logger.debug(f"检测到 tag 移除：{tag}")
            if remove_from_index(idx_file, journal_filename):
                if str(idx_file) not in updated_indices:
                    updated_indices.append(str(idx_file))

    # 添加新 tag 索引
    for tag in new_tags - old_tags:
        if tag:
            idx_file = BY_TOPIC_DIR / f"标签_{tag}.md"
            logger.debug(f"检测到 tag 添加：{tag}")
            add_to_index(idx_file, journal_path, new_data)
            if str(idx_file) not in updated_indices:
                updated_indices.append(str(idx_file))

    return updated_indices


def _normalize_to_list(value: Any) -> List[str]:
    """将值规范化为字符串列表"""
    if not value:
        return []
    if isinstance(value, list):
        return [str(v) for v in value if v]
    if isinstance(value, str):
        return [value]
    return []


def _apply_edit_updates(
    *,
    journal_path: Path,
    current_frontmatter: Dict[str, Any],
    current_body: str,
    frontmatter_updates: Dict[str, Any],
    append_content: Optional[str],
    replace_content: Optional[str],
    dry_run: bool,
) -> tuple[Dict[str, Any], Dict[str, Any], str, Dict[str, Any]]:
    result: Dict[str, Any] = {
        "changes": {},
        "content_modified": False,
    }

    old_frontmatter = dict(current_frontmatter)
    old_body = current_body

    # ===== 处理附件更新 =====
    # 如果 frontmatter_updates 包含附件，需要检查是否有需要处理的新附件
    # 已有附件（含 filename/rel_path 或相对路径）直接保留
    # 新附件（含 source_path 且是绝对路径）需要处理
    if "attachments" in frontmatter_updates:
        raw_attachments = frontmatter_updates["attachments"]
        if raw_attachments:
            # 分离已有附件和新附件
            # 附件可能是 dict (已有附件或新上传的) 或 str (已有附件路径)
            existing_attachments: list[dict[str, Any] | str] = []
            new_attachments: list[dict[str, Any] | str] = []

            for att in (
                raw_attachments
                if isinstance(raw_attachments, list)
                else [raw_attachments]
            ):
                if isinstance(att, str):
                    # 字符串：检查是否是相对路径
                    # 相对路径（如 ../../../attachments/...）视为已有附件引用
                    # 绝对路径（如 /tmp/... 或 C:\...）视为新上传的文件
                    if att.startswith("../") or att.startswith("./"):
                        existing_attachments.append(att)
                    else:
                        # 绝对路径，需要处理
                        new_attachments.append({"source_path": att, "description": ""})
                elif isinstance(att, dict):
                    # 检查是否已经是处理过的格式
                    if "filename" in att and "rel_path" in att:
                        # 已经是完整格式，直接保留
                        existing_attachments.append(att)
                    elif "source_path" in att:
                        # 检查 source_path 是否是绝对路径
                        source = att["source_path"]
                        is_absolute = os.path.isabs(source) or source.startswith(
                            "/tmp/"
                        )
                        if is_absolute:
                            # 新上传的附件，需要处理
                            new_attachments.append(att)
                        else:
                            # 相对路径，视为已有附件
                            existing_attachments.append(att)
                    else:
                        # 其他格式，直接保留
                        existing_attachments.append(att)
                else:
                    existing_attachments.append(att)

            # 如果有新附件需要处理
            if new_attachments:
                # 获取日期用于确定附件存储路径
                date_str = None
                if "date" in frontmatter_updates:
                    date_str = frontmatter_updates["date"]
                elif old_frontmatter.get("date"):
                    date_str = old_frontmatter["date"]

                # 解析日期字符串
                if date_str:
                    if isinstance(date_str, str):
                        date_str = date_str[:10]
                    else:
                        date_str = str(date_str)[:10]
                else:
                    date_str = datetime.now().strftime("%Y-%m-%d")

                logger.info(f"处理编辑中的新附件，日期: {date_str}")

                # 调用 CLI 标准附件处理流程
                processed_new = process_attachments(
                    attachments=new_attachments,
                    date_str=date_str,
                    dry_run=dry_run,
                )

                # 合并已有附件和处理后的新附件
                all_attachments = existing_attachments + processed_new
                frontmatter_updates["attachments"] = all_attachments
                logger.info(f"附件处理完成: {len(processed_new)} 个新附件")

                result["attachments_processed"] = len(processed_new)
            else:
                # 只有已有附件，直接使用
                frontmatter_updates["attachments"] = existing_attachments
        else:
            # 空附件列表，表示删除所有附件
            frontmatter_updates["attachments"] = []

    # 应用 frontmatter 更新
    new_frontmatter = dict(old_frontmatter)

    add_related_entries = frontmatter_updates.pop("add_related_entries", None)
    remove_related_entries = frontmatter_updates.pop("remove_related_entries", None)

    if add_related_entries or remove_related_entries:
        current_entries = new_frontmatter.get("related_entries", [])
        if isinstance(current_entries, str):
            current_entries = [
                item.strip() for item in current_entries.split(",") if item.strip()
            ]
        elif not isinstance(current_entries, list):
            current_entries = []

        current_rel_path = os.path.relpath(journal_path, JOURNALS_DIR.parent).replace(
            "\\", "/"
        )
        merged_entries: list[str] = []
        seen_entries: set[str] = set()
        for item in current_entries:
            item_str = str(item).strip()
            if not item_str:
                continue
            if item_str == current_rel_path:
                continue
            if not item_str.startswith("Journals/") or not item_str.endswith(".md"):
                continue
            if item_str not in seen_entries:
                merged_entries.append(item_str)
                seen_entries.add(item_str)

        for item in add_related_entries or []:
            item_str = str(item).strip()
            if not item_str:
                continue
            if item_str == current_rel_path:
                continue
            if not item_str.startswith("Journals/") or not item_str.endswith(".md"):
                continue
            if item_str not in seen_entries:
                merged_entries.append(item_str)
                seen_entries.add(item_str)

        remove_set = {
            str(item).strip()
            for item in (remove_related_entries or [])
            if str(item).strip()
        }
        merged_entries = [item for item in merged_entries if item not in remove_set][
            :10
        ]

        old_related_entries = new_frontmatter.get("related_entries")
        new_frontmatter["related_entries"] = merged_entries
        if old_related_entries != merged_entries:
            result["changes"]["related_entries"] = {
                "old": old_related_entries,
                "new": merged_entries,
            }

    for key, value in frontmatter_updates.items():
        old_value = new_frontmatter.get(key)

        # 特殊处理：空字符串视为删除字段
        if value == "" or value is None:
            if key in new_frontmatter:
                del new_frontmatter[key]
                result["changes"][key] = {"old": old_value, "new": None}
                logger.debug(f"删除字段：{key}")
        else:
            # 特殊处理：list 字段需要确保是数组格式
            list_fields = {
                "topic",
                "mood",
                "tags",
                "people",
                "links",
                "related_entries",
            }
            if key in list_fields and isinstance(value, str):
                # 按逗号分割
                value = [item.strip() for item in value.split(",") if item.strip()]
                logger.debug(f"分割 list 字段：{key} = {value}")

            if key == "related_entries" and isinstance(value, list):
                current_rel_path = os.path.relpath(
                    journal_path, JOURNALS_DIR.parent
                ).replace("\\", "/")
                filtered_values: list[str] = []
                seen_values: set[str] = set()
                for item in value:
                    item_str = str(item).strip()
                    if not item_str:
                        continue
                    if not item_str.startswith("Journals/") or not item_str.endswith(
                        ".md"
                    ):
                        continue
                    if item_str == current_rel_path:
                        continue
                    if item_str not in seen_values:
                        filtered_values.append(item_str)
                        seen_values.add(item_str)
                value = filtered_values[:10]

            new_frontmatter[key] = value
            if old_value != value:
                result["changes"][key] = {"old": old_value, "new": value}
                logger.debug(f"更新字段：{key} = {value}")

    # 处理正文修改
    new_body = old_body
    if replace_content is not None:
        new_body = replace_content
        result["content_modified"] = True
        logger.info("替换正文内容")
    elif append_content is not None:
        if old_body:
            new_body = old_body + "\n\n" + append_content
        else:
            new_body = append_content
        result["content_modified"] = True
        logger.info("追加正文内容")

    return old_frontmatter, new_frontmatter, new_body, result


def edit_journal(
    journal_path: Path,
    frontmatter_updates: Dict[str, Any],
    append_content: Optional[str] = None,
    replace_content: Optional[str] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    编辑日志文件

    Args:
        journal_path: 日志文件路径
        frontmatter_updates: 要更新的 frontmatter 字段
        append_content: 追加到正文的内容
        replace_content: 替换正文的内容（优先级高于 append）
        dry_run: 模拟运行

    Returns:
        {
            "success": bool,
            "journal_path": str,
            "changes": {"field": {"old": val, "new": val}, ...},
            "content_modified": bool,
            "indices_updated": [str],
            "error": str (optional)
        }
    """
    result: Dict[str, Any] = {
        "success": False,
        "journal_path": str(journal_path),
        "revision_path": None,
        "changes": {},
        "content_modified": False,
        "indices_updated": [],
        "error": None,
    }

    try:
        logger.info(f"开始编辑日志：{journal_path.name}")

        if not journal_path.exists():
            logger.error(f"日志文件不存在：{journal_path}")
            return create_error_response(
                ErrorCode.JOURNAL_NOT_FOUND,
                f"日志文件不存在：{journal_path}",
                {"path": str(journal_path)},
                "请检查文件路径是否正确",
            )

        if not frontmatter_updates and not append_content and not replace_content:
            logger.warning("未指定任何修改")
            return create_error_response(
                ErrorCode.NO_CHANGES_SPECIFIED,
                "未指定任何修改内容",
                None,
                "请使用 --set-*, --append-content 或 --replace-content 指定修改",
            )

        if "location" in frontmatter_updates:
            weather_value = frontmatter_updates.get("weather")
            if not isinstance(weather_value, str) or not weather_value.strip():
                logger.warning("修改地点时缺少同步天气")
                return create_error_response(
                    ErrorCode.LOCATION_WEATHER_REQUIRED,
                    "修改地点时，必须同时更新天气",
                    {"required_fields": ["location", "weather"]},
                    "请先查询新地点的天气；如果 query_weather 失败，可手动提供天气后再一起修改",
                )

        compute_updates = lambda current_frontmatter, current_body: _apply_edit_updates(
            journal_path=journal_path,
            current_frontmatter=current_frontmatter,
            current_body=current_body,
            frontmatter_updates=dict(frontmatter_updates),
            append_content=append_content,
            replace_content=replace_content,
            dry_run=dry_run,
        )

        metadata = parse_journal_file(journal_path)
        initial_frontmatter = {
            k: v for k, v in metadata.items() if not k.startswith("_")
        }
        initial_body = metadata.get("_body", "")

        old_frontmatter, new_frontmatter, new_body, computed_result = compute_updates(
            initial_frontmatter, initial_body
        )
        result.update(computed_result)

        if dry_run:
            logger.info("模拟运行模式（dry-run）")
            result["success"] = True
            result["preview"] = {
                "frontmatter": format_frontmatter(new_frontmatter),
                "body_preview": new_body[:200] + "..."
                if len(new_body) > 200
                else new_body,
            }
            return result

        # ===== 文件锁保护 =====
        # 使用文件锁保护写入操作，防止并发冲突
        lock = FileLock(get_journals_lock_path(), timeout=30.0)

        try:
            with lock:
                logger.debug("获取文件锁成功")
                original_content = journal_path.read_text(encoding="utf-8")
                locked_metadata = parse_journal_file(journal_path)
                locked_frontmatter = {
                    k: v for k, v in locked_metadata.items() if not k.startswith("_")
                }
                locked_body = locked_metadata.get("_body", "")
                old_frontmatter, new_frontmatter, new_body, computed_result = (
                    compute_updates(locked_frontmatter, locked_body)
                )
                result.update(computed_result)
                revision_path = save_revision(journal_path, original_content)
                result["revision_path"] = str(revision_path)
                # 写入文件
                new_content = format_frontmatter(new_frontmatter) + "\n\n\n" + new_body
                journal_path.write_text(new_content, encoding="utf-8")
                logger.info(f"已写入文件：{journal_path.name}")

                if (
                    "related_entries" in new_frontmatter
                    or "related_entries" in result["changes"]
                ):
                    metadata_conn = init_metadata_cache()
                    try:
                        source_rel_path = os.path.relpath(
                            journal_path, JOURNALS_DIR.parent
                        ).replace("\\", "/")
                        replace_entry_relations(
                            metadata_conn,
                            source_rel_path,
                            new_frontmatter.get("related_entries", []),
                        )
                    finally:
                        metadata_conn.close()

                # 更新索引（如果相关字段变更）
                if any(k in result["changes"] for k in ["topic", "project", "tags"]):
                    logger.info("检测到索引相关字段变更，更新索引...")
                    updated = update_indices_for_change(
                        journal_path, old_frontmatter, new_frontmatter
                    )
                    result["indices_updated"] = updated
                    logger.info(f"已更新 {len(updated)} 个索引文件")

                # 更新向量索引（如果内容相关字段变更）
                content_fields_changed = result["content_modified"] or any(
                    k in result["changes"] for k in ["title", "tags", "topic"]
                )
                if content_fields_changed:
                    try:
                        # 构建更新数据（合并旧的和新的 frontmatter）
                        update_data = dict(new_frontmatter)
                        update_data["content"] = new_body
                        vector_updated = update_vector_index(journal_path, update_data)
                        if vector_updated:
                            logger.info("向量索引已同步更新")
                            result["vector_index_updated"] = True
                    except Exception as e:
                        logger.warning(f"向量索引更新失败（不影响编辑）：{e}")

        except LockTimeoutError as e:
            # 锁超时，返回结构化错误
            logger.error(f"文件锁超时：{e}")
            return create_error_response(
                ErrorCode.LOCK_TIMEOUT,
                f"无法获取写入锁，请稍后重试：{e}",
                {"lock_path": str(get_journals_lock_path()), "timeout": 30.0},
                "等待几秒后重试，或检查是否有其他进程正在编辑",
            )

        result["success"] = True
        logger.info(f"编辑完成：{journal_path.name}")

    except (IOError, OSError) as e:
        logger.error(f"文件操作失败：{e}")
        return create_error_response(
            ErrorCode.WRITE_FAILED,
            f"文件操作失败：{e}",
            {"path": str(journal_path)},
            "请检查文件权限或磁盘空间",
        )

    return result


__all__ = ["edit_journal"]
