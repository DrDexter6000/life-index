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
from ..lib.paths import get_journals_dir, get_by_topic_dir, get_user_data_dir, resolve_user_data_dir
from ..lib.fragment_notes import (
    boundary_of,
    region_append_separator,
    split_fragment_notes,
    split_suffix_region,
)
from ..lib.frontmatter import (
    _same_value,
    empty_indexable_metadata,
    format_frontmatter,
    frontmatter_rewrite_blocker,
    normalize_indexable_metadata,
    parse_frontmatter,
    parse_journal_file,
    unwritable_frontmatter_key,
)
from ..lib.journal_files import (
    JournalFileKind,
    classify_journal_path,
    display_label,
    is_live_fragment_path,
)
from ..lib.file_lock import FileLock, LockTimeoutError, get_journals_lock_path
from ..lib.errors import ErrorCode, create_error_response
from ..lib.journal_rewrite import (
    OutgoingJournalRefused,
    ensure_replaceable_journal,
    normalize_lf,
    render_frontmatter_block,
    replace_journal_bytes,
    split_journal_bytes,
    verify_outgoing_journal,
)
from ..lib.logger import get_logger
from ..lib.metadata_cache import (
    init_metadata_cache,
    replace_entry_relations,
    upsert_journal_cache_row,
)
from ..lib.search_index import upsert_fts_row
from ..lib.revisions import save_revision_bytes
from ..lib.pending_writes import mark_pending
from ..write_journal.attachments import process_attachments
from ..write_journal.index_updater import refresh_index_b

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


def add_to_index(
    index_file: Path, journal_path: Path, data: Dict[str, Any], body: str = ""
) -> None:
    """添加日志条目到索引文件

    The bracket text is the one display label (title, else first body line,
    else file name); a title is never invented here.
    """
    date_str = data.get("date", "")[:10] if data.get("date") else ""
    indexable = normalize_indexable_metadata(data) or empty_indexable_metadata()
    title = display_label(indexable["title"], body, journal_path)
    try:
        rel_path = os.path.relpath(journal_path, get_journals_dir().parent).replace("\\", "/")
    except ValueError:
        # Cross-drive on Windows: fallback to absolute path
        rel_path = str(journal_path).replace("\\", "/")

    entry = f"- [{date_str}] [{title}]({rel_path})"

    get_by_topic_dir().mkdir(parents=True, exist_ok=True)

    if index_file.exists():
        content = index_file.read_text(encoding="utf-8")
        if entry not in content:
            with open(index_file, "a", encoding="utf-8") as f:
                f.write(entry + "\n")
            logger.debug(f"添加条目到索引：{index_file.name}")
    else:
        # 确定索引类型和名称
        name = index_file.stem.replace("主题_", "").replace("项目_", "").replace("标签_", "")
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
    journal_path: Path, old_data: Dict[str, Any], new_data: Dict[str, Any], body: str = ""
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
            idx_file = get_by_topic_dir() / f"主题_{topic}.md"
            logger.info(f"检测到 topic 变更：{topic} -> 移除")
            if remove_from_index(idx_file, journal_filename):
                updated_indices.append(str(idx_file))

    # 添加到新 topic 索引
    for topic in new_topics:
        if topic:
            idx_file = get_by_topic_dir() / f"主题_{topic}.md"
            logger.info(f"检测到 topic 变更：添加 {topic}")
            add_to_index(idx_file, journal_path, new_data, body)
            if str(idx_file) not in updated_indices:
                updated_indices.append(str(idx_file))

    # 检查 project 变更
    old_project = old_data.get("project", "")
    new_project = new_data.get("project", "")

    if old_project != new_project:
        logger.info(f"检测到 project 变更：{old_project} -> {new_project}")
        # 移除旧 project 索引
        if old_project:
            idx_file = get_by_topic_dir() / f"项目_{old_project}.md"
            if remove_from_index(idx_file, journal_filename):
                if str(idx_file) not in updated_indices:
                    updated_indices.append(str(idx_file))

        # 添加到新 project 索引
        if new_project:
            idx_file = get_by_topic_dir() / f"项目_{new_project}.md"
            add_to_index(idx_file, journal_path, new_data, body)
            if str(idx_file) not in updated_indices:
                updated_indices.append(str(idx_file))

    # 检查 tags 变更
    old_tags = set(_normalize_to_list(old_data.get("tags")))
    new_tags = set(_normalize_to_list(new_data.get("tags")))

    # 移除旧 tag 索引
    for tag in old_tags - new_tags:
        if tag:
            idx_file = get_by_topic_dir() / f"标签_{tag}.md"
            logger.debug(f"检测到 tag 移除：{tag}")
            if remove_from_index(idx_file, journal_filename):
                if str(idx_file) not in updated_indices:
                    updated_indices.append(str(idx_file))

    # 添加新 tag 索引
    for tag in new_tags - old_tags:
        if tag:
            idx_file = get_by_topic_dir() / f"标签_{tag}.md"
            logger.debug(f"检测到 tag 添加：{tag}")
            add_to_index(idx_file, journal_path, new_data, body)
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


def _is_private_key(key: Any) -> bool:
    """Whether a metadata key is an internal ``_``-prefixed string key.

    ``parse_journal_file`` adds such keys itself. A non-string key is never
    private, and this predicate must not raise on one: the rewrite guard runs
    first, but the filter may not depend on that.
    """
    return isinstance(key, str) and key.startswith("_")


def _rewrite_refusal(journal_path: Path, content: str) -> Optional[Dict[str, Any]]:
    """The E0202 envelope when ``content``'s frontmatter cannot be written back."""
    blocker = frontmatter_rewrite_blocker(content)
    if blocker is None:
        return None
    logger.warning(f"frontmatter 无法安全重写（{blocker}）：{journal_path}")
    return create_error_response(
        ErrorCode.FRONTMATTER_INVALID,
        f"Frontmatter cannot be rewritten without loss: {blocker}",
        {"path": str(journal_path), "reason": blocker},
        "Leave the file unchanged and report the file and reason to the user;"
        " do not retry or repair it automatically",
    )


def _no_block_refusal(journal_path: Path) -> Dict[str, Any]:
    """The E0202 envelope when the file has no byte-level frontmatter block."""
    logger.warning(f"文件没有可解析的 frontmatter 区块，拒绝重写：{journal_path}")
    return create_error_response(
        ErrorCode.FRONTMATTER_INVALID,
        "Frontmatter cannot be rewritten without loss: the file has no frontmatter block",
        {"path": str(journal_path), "reason": "no_frontmatter_block"},
        "Leave the file unchanged and report the file and reason to the user;"
        " do not retry or repair it automatically",
    )


def _not_round_trippable_refusal(journal_path: Path) -> Dict[str, Any]:
    """The E0202 envelope when the outgoing file fails its read-back check."""
    logger.warning(f"重写结果无法无损读回（not_round_trippable），拒绝提交：{journal_path}")
    return create_error_response(
        ErrorCode.FRONTMATTER_INVALID,
        "Frontmatter cannot be rewritten without loss: not_round_trippable",
        {"path": str(journal_path), "reason": "not_round_trippable"},
        "Leave the file unchanged and report the file and reason to the user;"
        " do not retry or repair it automatically",
    )


# A new-form fragment's stored identity: a correction is added as a note
# (`fragment note`), these fields and the body are never edited in place.
# `notes_boundary` belongs to the notes machinery, never to a caller's edit.
_FRAGMENT_IDENTITY_FIELDS = (
    "id",
    "kind",
    "ingested_at",
    "schema_version",
    "content",
    "notes_boundary",
)

_FRAGMENT_NOTE_HINT = "a fragment's words are not edited; add a correction with `fragment note`"


def _is_new_form_fragment(journal_path: Path, frontmatter: Dict[str, Any]) -> bool:
    """New-form fragment: fragment by the filename kind rule AND the frontmatter,
    as read inside the lock before the edit, carries ``kind: fragment`` with a
    non-empty ``id``."""
    if classify_journal_path(journal_path) is not JournalFileKind.FRAGMENT:
        return False
    if frontmatter.get("kind") != "fragment":
        return False
    fragment_id = frontmatter.get("id")
    return isinstance(fragment_id, str) and bool(fragment_id.strip())


def _locked_request_refusal(  # noqa: C901 - flat refusal ladder, one branch per rule
    *,
    journal_path: Path,
    frontmatter_updates: Dict[str, Any],
    append_content: Optional[str],
    replace_content: Optional[str],
    journal_is_new_form_fragment: bool,
) -> Optional[Dict[str, Any]]:
    """The refusal (if any) for this request once the locked snapshot is read.

    Fragment protections use the identity read inside the lock, so changing
    ``kind`` / ``id`` in the same call cannot bypass them; legacy journals
    keep the no-content-smuggle rule and the coupled location/weather rule.
    """
    if journal_is_new_form_fragment:
        if replace_content is not None or append_content is not None:
            return _fragment_words_refusal(
                journal_path, "A fragment's own words cannot be replaced or appended"
            )
        blocked_field = next(
            (key for key in _FRAGMENT_IDENTITY_FIELDS if key in frontmatter_updates), None
        )
        if blocked_field is not None:
            return _fragment_words_refusal(
                journal_path,
                f"The '{blocked_field}' field of a fragment cannot be updated",
                field=blocked_field,
            )
        # 新形态 fragment 的 location 修改不再强制同步 weather。
        return None

    if "content" in frontmatter_updates:
        return _content_update_refusal(journal_path, "content")
    if "notes_boundary" in frontmatter_updates:
        return _content_update_refusal(journal_path, "notes_boundary")
    if "id" in frontmatter_updates:
        # The stored entry id is durable: no file — fragment or not — accepts
        # setting, replacing, clearing or removing it through an edit.
        return _content_update_refusal(journal_path, "id")
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
    return None


def _fragment_words_refusal(
    journal_path: Path, what: str, field: Optional[str] = None
) -> Dict[str, Any]:
    """The E0505 envelope when an edit would touch a fragment's own words or identity."""
    details: Dict[str, Any] = {"path": str(journal_path)}
    if field is not None:
        details["field"] = field
    return create_error_response(
        ErrorCode.FRAGMENT_WORDS_IMMUTABLE,
        f"{what}: {_FRAGMENT_NOTE_HINT}",
        details,
        "Leave the fragment's words unchanged; add the correction as a note"
        " with `fragment note`",
    )


def _content_update_refusal(journal_path: Path, key: str = "content") -> Dict[str, Any]:
    """The envelope when ``frontmatter_updates`` tries to smuggle a body change.

    ``notes_boundary`` gets the same refusal: it belongs to the notes
    machinery (`fragment note`), not to a caller's edit.
    """
    return create_error_response(
        ErrorCode.INVALID_INPUT,
        f"The '{key}' key cannot be updated through frontmatter_updates;"
        " body text is changed with --replace-content / --append-content",
        {"path": str(journal_path), "field": key},
        "Use --replace-content or --append-content to change body text",
    )


def _boundary_in_content_refusal(journal_path: Path) -> Dict[str, Any]:
    """The E0001 envelope when supplied content carries the file's boundary."""
    return create_error_response(
        ErrorCode.INVALID_INPUT,
        "supplied content contains the file's notes_boundary value;"
        " the notes region must stay unforgeable",
        {"path": str(journal_path), "field": "content"},
        "Remove the boundary value from the supplied content and retry;"
        " the journal was not changed",
    )


def _invalid_update_key(key: Any) -> bool:
    """Whether a ``frontmatter_updates`` key may never reach the serializer.

    The one shared key rule (:func:`frontmatter.unwritable_frontmatter_key`);
    the outgoing-file check refuses such keys at commit time, this predicate
    refuses them up front.
    """
    return unwritable_frontmatter_key(key)


def _invalid_update_key_refusal(journal_path: Path, key: Any) -> Dict[str, Any]:
    """The E0001 envelope when an update key itself cannot be written."""
    return create_error_response(
        ErrorCode.INVALID_INPUT,
        "frontmatter update keys must be non-empty stripped strings" " without line breaks or ':'",
        {"path": str(journal_path), "field": key if isinstance(key, str) else repr(key)},
        "Fix the field name and retry; the journal was not changed",
    )


def _apply_edit_updates(  # noqa: C901
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
                raw_attachments if isinstance(raw_attachments, list) else [raw_attachments]
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
                        is_absolute = os.path.isabs(source) or source.startswith("/tmp/")
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
            current_entries = [item.strip() for item in current_entries.split(",") if item.strip()]
        elif not isinstance(current_entries, list):
            current_entries = []

        try:
            current_rel_path = os.path.relpath(journal_path, get_user_data_dir()).replace("\\", "/")
        except ValueError:
            current_rel_path = None
        merged_entries: list[str] = []
        seen_entries: set[str] = set()
        for item in current_entries:
            item_str = str(item).strip()
            if not item_str:
                continue
            if current_rel_path and item_str == current_rel_path:
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
            if current_rel_path and item_str == current_rel_path:
                continue
            if not item_str.startswith("Journals/") or not item_str.endswith(".md"):
                continue
            if item_str not in seen_entries:
                merged_entries.append(item_str)
                seen_entries.add(item_str)

        remove_set = {
            str(item).strip() for item in (remove_related_entries or []) if str(item).strip()
        }
        merged_entries = [item for item in merged_entries if item not in remove_set][:10]

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
                try:
                    current_rel_path = os.path.relpath(journal_path, get_user_data_dir()).replace(
                        "\\", "/"
                    )
                except ValueError:
                    current_rel_path = None
                filtered_values: list[str] = []
                seen_values: set[str] = set()
                for item in value:
                    item_str = str(item).strip()
                    if not item_str:
                        continue
                    if not item_str.startswith("Journals/") or not item_str.endswith(".md"):
                        continue
                    if current_rel_path and item_str == current_rel_path:
                        continue
                    if item_str not in seen_values:
                        filtered_values.append(item_str)
                        seen_values.add(item_str)
                value = filtered_values[:10]

            new_frontmatter[key] = value
            if not _same_value(old_value, value):
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
        "metadata_cache_updated": False,
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

        invalid_key = next((key for key in frontmatter_updates if _invalid_update_key(key)), None)
        if invalid_key is not None:
            logger.warning(f"frontmatter 更新键本身不可写入：{invalid_key!r}")
            return _invalid_update_key_refusal(journal_path, invalid_key)

        # ===== 文件锁保护 =====
        # 使用文件锁保护写入操作，防止并发冲突。所有决定这次编辑的读取
        # （重写拒绝检查、fragment 身份、正文）、revision 与替换都发生在
        # 锁内的同一次字节快照上。
        lock = FileLock(get_journals_lock_path(), timeout=30.0)

        try:
            with lock:
                logger.debug("获取文件锁成功")
                raw_bytes = journal_path.read_bytes()
                split = split_journal_bytes(raw_bytes)
                if split is None:
                    return _no_block_refusal(journal_path)
                original_content = raw_bytes.decode("utf-8")
                refusal = _rewrite_refusal(journal_path, original_content)
                if refusal is not None:
                    return refusal
                locked_metadata, locked_body = parse_frontmatter(original_content)
                locked_frontmatter = {
                    k: v for k, v in locked_metadata.items() if not _is_private_key(k)
                }

                # 身份判定用锁内读到的 frontmatter，同一次调用里改 kind/id
                # 也绕不过它。
                journal_is_new_form_fragment = _is_new_form_fragment(
                    journal_path, locked_frontmatter
                )
                refusal = _locked_request_refusal(
                    journal_path=journal_path,
                    frontmatter_updates=frontmatter_updates,
                    append_content=append_content,
                    replace_content=replace_content,
                    journal_is_new_form_fragment=journal_is_new_form_fragment,
                )
                if refusal is not None:
                    return refusal

                # A file with notes: a content edit applies to the original
                # text and keeps the notes region bytes verbatim after it;
                # supplied content containing the boundary is refused (the
                # region must stay unforgeable). Metadata-only edits below
                # never touch the suffix, so the region rides along untouched.
                content_edit_requested = replace_content is not None or append_content is not None
                notes_boundary = boundary_of(locked_frontmatter)
                region_bytes = b""
                if notes_boundary is not None and content_edit_requested:
                    if notes_boundary in (replace_content or "") or notes_boundary in (
                        append_content or ""
                    ):
                        return _boundary_in_content_refusal(journal_path)
                    _original, region_bytes = split_suffix_region(split.suffix, notes_boundary)
                    locked_body = split_fragment_notes(
                        locked_frontmatter, locked_body
                    ).original_text

                old_frontmatter, new_frontmatter, new_body, computed_result = _apply_edit_updates(
                    journal_path=journal_path,
                    current_frontmatter=locked_frontmatter,
                    current_body=locked_body,
                    frontmatter_updates=dict(frontmatter_updates),
                    append_content=append_content,
                    replace_content=replace_content,
                    dry_run=dry_run,
                )
                result.update(computed_result)

                # 正文编辑（legacy journal）写出的正文不含任何 CR：携带
                # 旧正文的文本与调用方提供的文本都经同一个 LF 归一器。
                # 带更正 note 的文件在正文之后按追加规则接回原样的 note
                # 区字节（`fragment note` 的同一条 separator 规则）。
                if content_edit_requested:
                    new_body = normalize_lf(new_body)
                    if region_bytes:
                        separator = region_append_separator(new_body.encode("utf-8"))
                        new_body = (
                            new_body + separator.decode("ascii") + region_bytes.decode("utf-8")
                        )

                # content_modified 恰好在正文字节变化时为真：仅改元数据时
                # 后缀逐字节不变；改正文时与原后缀比较。
                new_body_bytes = new_body.encode("utf-8")
                if replace_content is None and append_content is None:
                    result["content_modified"] = False
                else:
                    result["content_modified"] = (b"\n\n" + new_body_bytes) != split.suffix

                if dry_run:
                    logger.info("模拟运行模式（dry-run）")
                    result["success"] = True
                    result["preview"] = {
                        "frontmatter": format_frontmatter(new_frontmatter),
                        "body_preview": new_body[:200] + "..." if len(new_body) > 200 else new_body,
                    }
                    return result

                metadata_only_edit = replace_content is None and append_content is None
                if metadata_only_edit:
                    new_file_bytes = render_frontmatter_block(new_frontmatter) + split.suffix
                else:
                    new_file_bytes = (
                        render_frontmatter_block(new_frontmatter) + b"\n\n" + new_body_bytes
                    )

                if metadata_only_edit and _same_value(locked_frontmatter, new_frontmatter):
                    # 没有任何字段值变化（类型敏感比较，与提交前核验同一
                    # 规则）、也没有正文操作：成功返回，不重写文件、不保存
                    # revision（revision_path 保持为 None）。后续派生步骤照常
                    # 按当前文件执行，结果字段保持原形状。
                    logger.info("没有任何字段变化，文件未重写")
                else:
                    # 可替换前置检查（符号链接 / 只读）先于 revision 与一切
                    # 写入；拒绝时字节不变、无 revision、无临时文件。
                    ensure_replaceable_journal(journal_path)
                    # 提交前用公共 reader 读回新文件做最后核验；拒绝时
                    # 不保存 revision、不创建临时文件、不替换任何字节。
                    try:
                        verify_outgoing_journal(
                            raw_bytes,
                            new_file_bytes,
                            new_frontmatter,
                            metadata_only=metadata_only_edit,
                            computed_body=None if metadata_only_edit else new_body,
                        )
                    except OutgoingJournalRefused:
                        return _not_round_trippable_refusal(journal_path)

                    # revision 保存原始字节（字节级一致）；失败则日志不被替换。
                    revision_path = save_revision_bytes(journal_path, raw_bytes)
                    result["revision_path"] = str(revision_path)
                    replace_journal_bytes(journal_path, new_file_bytes)
                    logger.info(f"已写入文件：{journal_path.name}")

                if "related_entries" in new_frontmatter or "related_entries" in result["changes"]:
                    metadata_conn = init_metadata_cache()
                    try:
                        try:
                            source_rel_path = os.path.relpath(
                                journal_path, get_user_data_dir()
                            ).replace("\\", "/")
                        except ValueError:
                            source_rel_path = None
                        if source_rel_path:
                            # The shared rule turns whatever the file holds in
                            # this field into ``list[str]``; a malformed value
                            # must not raise after the file is written.
                            indexable = (
                                normalize_indexable_metadata(new_frontmatter)
                                or empty_indexable_metadata()
                            )
                            replace_entry_relations(
                                metadata_conn,
                                source_rel_path,
                                indexable["related_entries"],
                            )
                    finally:
                        metadata_conn.close()

                # 更新索引（如果相关字段变更）
                if any(k in result["changes"] for k in ["topic", "project", "tags"]):
                    logger.info("检测到索引相关字段变更，更新索引...")
                    # 条目方括号标签取原文（带 note 的文件不把 note 区当正文）。
                    label_body = split_fragment_notes(new_frontmatter, new_body).original_text
                    updated = update_indices_for_change(
                        journal_path, old_frontmatter, new_frontmatter, label_body
                    )
                    result["indices_updated"] = updated
                    logger.info(f"已更新 {len(updated)} 个索引文件")

                # 编辑提交后即时写穿该日志的 FTS 行（file → row 与全量重建
                # 同一路径；非阻塞）。写穿成功时不入 pending queue；失败时回退
                # 到 pending queue，由下次搜索 preflight 或 life-index index 恢复。
                # 只有 journals 树中的 live fragment 才允许进入派生存储：
                # digest / derived index / .revisions/ 内的文件一律不写行。
                journal_is_live_fragment = is_live_fragment_path(journal_path, get_journals_dir())

                result["fts_row_updated"] = False
                result["pending_marked"] = False
                result["fts_row"] = {
                    "status": "skipped",
                    "reason": "not_a_live_fragment",
                    "recovery": None,
                }
                if journal_is_live_fragment:

                    def _queue_fts_repair(reason: str) -> None:
                        try:
                            rel_path = str(
                                journal_path.relative_to(resolve_user_data_dir())
                            ).replace("\\", "/")
                            mark_pending(rel_path)
                            logger.info(f"已标记待索引更新: {rel_path}")
                        except Exception as pending_e:
                            logger.warning(f"标记 pending 失败（不影响编辑）：{pending_e}")
                            result["fts_row"] = {
                                "status": "failed",
                                "reason": f"{reason}; pending_queue_failed: {pending_e}",
                                "recovery": "life-index index --rebuild",
                            }
                        else:
                            result["pending_marked"] = True
                            result["fts_row"] = {
                                "status": "failed",
                                "reason": reason,
                                "recovery": "life-index index",
                            }

                    try:
                        upserted_fts_row = upsert_fts_row(journal_path, get_journals_dir())
                    except Exception as e:
                        logger.warning(f"FTS 行写穿失败，回退 pending queue（不影响编辑）：{e}")
                        _queue_fts_repair(f"write_through_failed: {e}")
                    else:
                        if upserted_fts_row is None:
                            # A live fragment always yields a row now; None here
                            # means the write-through did not see a row at all.
                            logger.warning("FTS 行写穿未产出 row，回退 pending queue")
                            _queue_fts_repair("write_through_produced_no_row")
                        else:
                            result["fts_row_updated"] = True
                            if upserted_fts_row.get("unparsable"):
                                # D1: frontmatter did not parse, so the file is
                                # indexed as raw text; this is a complete row,
                                # not a failure and not queued.
                                result["fts_row"] = {
                                    "status": "complete",
                                    "reason": "unparsable_frontmatter_indexed_as_text",
                                    "recovery": None,
                                }
                            else:
                                result["fts_row"] = {
                                    "status": "complete",
                                    "reason": None,
                                    "recovery": None,
                                }

                # 编辑提交后即时更新该日志的元数据缓存行（非阻塞；失败时
                # 由下次搜索的 reconcile 或 index --rebuild 恢复）。缓存只覆盖
                # journals 树中的 live fragment，与 FTS 写穿同一判定。
                if journal_is_live_fragment:
                    try:
                        upserted_row = upsert_journal_cache_row(journal_path, get_journals_dir())
                        if upserted_row is None:
                            raise RuntimeError("metadata cache row upsert produced no row")
                        result["metadata_cache_updated"] = True
                    except Exception as e:
                        result["metadata_cache_updated"] = False
                        logger.warning(f"元数据缓存行更新失败（不影响编辑）：{e}")

                index_b_result = refresh_index_b(False)
                result["index_b_updated"] = index_b_result
                if not index_b_result.get("success"):
                    logger.warning(
                        "Index B refresh failed after edit: %s",
                        index_b_result.get("error") or index_b_result,
                    )

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

    except (IOError, OSError, UnicodeDecodeError) as e:
        # A file whose bytes are not valid UTF-8 cannot be rewritten without
        # corrupting it; refuse with the standard error envelope instead of
        # letting UnicodeDecodeError escape. Whether edit should refuse such
        # files at all is decided elsewhere.
        logger.error(f"文件操作失败：{e}")
        return create_error_response(
            ErrorCode.WRITE_FAILED,
            f"文件操作失败：{e}",
            {"path": str(journal_path)},
            "请检查文件权限或磁盘空间",
        )

    return result


__all__ = ["edit_journal"]
