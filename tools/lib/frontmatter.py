#!/usr/bin/env python3
"""
Life Index - Frontmatter Utilities
统一 YAML frontmatter 解析/格式化模块（SSOT）

所有工具应使用此模块处理 frontmatter，避免重复实现。
使用 yaml.safe_load 确保完整 YAML 规范支持（多行字符串、嵌套、特殊字符等）。
"""

import mimetypes
import re
import yaml
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Literal, Tuple

# Schema 版本（用于未来格式变更的向后兼容）
SCHEMA_VERSION = 1

# 标准字段顺序（与历史日志保持一致）
FIELD_ORDER = [
    "schema_version",
    "title",
    "date",
    "location",
    "weather",
    "mood",
    "people",
    "tags",
    "project",
    "topic",
    "abstract",
    "links",
    "attachments",
]

# 字段类型定义
LIST_FIELDS = {"mood", "people", "tags", "topic", "links", "attachments"}
STRING_FIELDS = {"title", "date", "location", "weather", "project", "abstract"}


def normalize_attachment_entries(
    attachments: list[Any] | None,
    *,
    mode: Literal["write_input", "stored_metadata"],
) -> list[dict[str, Any]]:
    """Normalize attachment entries for shared write/read handling."""
    normalized: list[dict[str, Any]] = []

    for attachment in attachments or []:
        if mode == "write_input":
            entry = _normalize_attachment_write_input(attachment)
        else:
            entry = _normalize_attachment_stored_metadata(attachment)

        if entry is not None:
            normalized.append(entry)

    return normalized


def _normalize_attachment_write_input(attachment: Any) -> dict[str, Any] | None:
    if isinstance(attachment, str):
        source_path = attachment.strip()
        if not source_path:
            return None
        return {"source_path": source_path, "description": ""}

    if not isinstance(attachment, dict):
        return None

    source_path = str(attachment.get("source_path", "")).strip()
    source_url = str(attachment.get("source_url", "")).strip()
    if not source_path and not source_url:
        return None

    normalized: dict[str, Any] = {"description": str(attachment.get("description", ""))}
    if source_path:
        normalized["source_path"] = source_path
    if source_url:
        normalized["source_url"] = source_url
    if attachment.get("content_type") is not None:
        normalized["content_type"] = str(attachment.get("content_type"))
    size_value = attachment.get("size")
    if size_value is not None:
        normalized["size"] = int(size_value)
    return normalized


def _guess_attachment_content_type(path: str) -> str | None:
    content_type, _ = mimetypes.guess_type(path)
    return content_type


def _normalize_attachment_stored_metadata(attachment: Any) -> dict[str, Any] | None:
    if isinstance(attachment, dict):
        raw_path = str(
            attachment.get("rel_path")
            or attachment.get("path")
            or attachment.get("source_path")
            or ""
        ).strip()
        if not raw_path:
            return None

        return {
            "raw_path": raw_path,
            "path": raw_path,
            "name": str(attachment.get("filename") or Path(raw_path).name),
            "description": str(attachment.get("description", "")),
            "source_url": attachment.get("source_url"),
            "content_type": attachment.get("content_type")
            or _guess_attachment_content_type(raw_path),
            "size": attachment.get("size"),
        }

    raw_path = str(attachment).strip()
    if not raw_path:
        return None

    return {
        "raw_path": raw_path,
        "path": raw_path,
        "name": Path(raw_path).name,
        "description": "",
        "source_url": None,
        "content_type": _guess_attachment_content_type(raw_path),
        "size": None,
    }


def parse_frontmatter(content: str) -> Tuple[Dict[str, Any], str]:
    """
    解析 YAML frontmatter

    Args:
        content: 完整的文件内容

    Returns:
        (metadata_dict, body_content)
    """
    if not content.startswith("---"):
        return {}, content

    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content

    fm_content = parts[1].strip()
    body = parts[2].strip()

    try:
        metadata: Dict[str, Any] = yaml.safe_load(fm_content) or {}
    except yaml.YAMLError:
        metadata, body = _recover_legacy_content_frontmatter(fm_content, body)

    metadata, body = _merge_legacy_content_into_body(metadata, body)

    # yaml.safe_load 会将 ISO 8601 时间戳解析为 datetime 对象。
    # 整个代码库以字符串形式处理日期，转回字符串以保持接口稳定。
    for key, value in metadata.items():
        if isinstance(value, datetime):
            metadata[key] = value.isoformat(timespec="seconds")
        elif isinstance(value, date):
            metadata[key] = value.isoformat()

    return metadata, body


def _recover_legacy_content_frontmatter(
    fm_content: str, body: str
) -> Tuple[Dict[str, Any], str]:
    """Recover metadata/body from legacy malformed `content: "..."` frontmatter."""
    content_match = re.search(r'^content:\s*"', fm_content, re.MULTILINE)
    if not content_match:
        return {}, body

    metadata_prefix = fm_content[: content_match.start()].strip()
    content_block = fm_content[content_match.end() :]

    if content_block.endswith('"'):
        content_block = content_block[:-1]

    try:
        metadata: Dict[str, Any] = yaml.safe_load(metadata_prefix) or {}
    except yaml.YAMLError:
        return {}, body

    recovered_body = content_block.strip()
    trailing_body = body.strip()
    if trailing_body:
        recovered_body = (
            f"{recovered_body}\n\n{trailing_body}" if recovered_body else trailing_body
        )

    return metadata, recovered_body


def _merge_legacy_content_into_body(
    metadata: Dict[str, Any], body: str
) -> Tuple[Dict[str, Any], str]:
    legacy_content = metadata.pop("content", None)
    if not isinstance(legacy_content, str) or not legacy_content.strip():
        return metadata, body

    merged_body = legacy_content.strip()
    trailing_body = body.strip()
    if trailing_body:
        merged_body = f"{merged_body}\n\n{trailing_body}"

    return metadata, merged_body


def parse_journal_file(file_path: Path) -> Dict[str, Any]:
    """
    解析日志文件，返回完整元数据（包含 _body 和 _file）

    Args:
        file_path: 日志文件路径

    Returns:
        包含 frontmatter、正文、文件路径的字典
    """
    try:
        content = file_path.read_text(encoding="utf-8")
        metadata, body = parse_frontmatter(content)

        # 提取标题（第一个 # 标题）
        title_match = re.search(r"^# (.+)$", body, re.MULTILINE)
        metadata["_title"] = title_match.group(1) if title_match else file_path.stem

        # 提取摘要（第一个非空非标题段落）
        abstract_match = re.search(r"\n\n([^#\n].*?)(?=\n\n|\Z)", body, re.DOTALL)
        if abstract_match:
            abstract = abstract_match.group(1).strip()[:100]
            metadata["_abstract"] = (
                abstract + "..." if len(abstract) == 100 else abstract
            )
        else:
            metadata["_abstract"] = "(无摘要)"

        metadata["_body"] = body
        metadata["_file"] = str(file_path)

        return metadata
    except (IOError, OSError, UnicodeDecodeError) as e:
        return {"_error": str(e), "_file": str(file_path)}


def format_frontmatter(data: Dict[str, Any]) -> str:
    """
    格式化 frontmatter 为标准 YAML
    保持字段顺序与历史日志一致
    """
    lines = ["---"]

    # 自动添加 schema_version（如果未提供）
    if "schema_version" not in data:
        lines.append(_format_field("schema_version", SCHEMA_VERSION))

    # 按标准顺序输出已知字段
    for key in FIELD_ORDER:
        if key == "schema_version":
            continue  # 已处理或跳过
        if key in data and data[key] is not None:
            value = data[key]
            lines.append(_format_field(key, value))

    # 输出其他字段
    for key, value in data.items():
        if key not in FIELD_ORDER and not key.startswith("_"):
            lines.append(_format_field(key, value))

    lines.append("---")
    return "\n".join(lines)


def _format_field(key: str, value: Any) -> str:
    """格式化单个字段"""
    import json

    list_like_fields = {"topic", "tags", "mood", "people"}

    if key in list_like_fields and isinstance(value, str):
        # 按逗号分割，确保 "tag1, tag2" 变成 ["tag1", "tag2"]
        value = [item.strip() for item in value.split(",") if item.strip()]

    if isinstance(value, list):
        # 列表使用 JSON 格式
        return f"{key}: {json.dumps(value, ensure_ascii=False)}"
    elif isinstance(value, str):
        # 字符串加引号（除了特定字段）
        if key in ("date",):
            return f"{key}: {value}"
        return f'{key}: "{value}"'
    elif isinstance(value, bool):
        return f"{key}: {str(value).lower()}"
    elif value is None:
        return f"{key}:"
    else:
        return f"{key}: {value}"


def format_journal_content(data: Dict[str, Any]) -> str:
    """
    格式化完整日志内容（frontmatter + 正文）

    Args:
        data: 包含 frontmatter 和 content 的字典

    Returns:
        完整的日志文件内容
    """
    frontmatter_data = {k: v for k, v in data.items() if k != "content"}
    frontmatter = format_frontmatter(frontmatter_data)

    lines = []

    # 标题
    title = data.get("title", "")
    if title:
        lines.append(f"# {title}")
        lines.append("")

    # 正文
    content = data.get("content", "")
    if content:
        # Skip first line if it duplicates the title (strip '#' prefix and whitespace)
        content_lines = content.splitlines()
        skip_first = False
        if title:
            first_non_empty = next(
                (line.strip() for line in content_lines if line.strip()), None
            )
            if first_non_empty:
                # Strip leading '#' and whitespace for comparison
                stripped = first_non_empty.lstrip("#").strip()
                if stripped == title or stripped == f"#{title}":
                    skip_first = True
        if skip_first and len(content_lines) > 1:
            content_lines = content_lines[1:]
        lines.append("\n".join(content_lines))
        lines.append("")

    body = "\n".join(lines)
    return f"{frontmatter}\n\n\n{body}"


def update_frontmatter_fields(
    file_path: Path, updates: Dict[str, Any], dry_run: bool = False
) -> Dict[str, Any]:
    """
    更新日志文件的 frontmatter 字段

    Args:
        file_path: 日志文件路径
        updates: 要更新的字段字典
        dry_run: 是否模拟运行

    Returns:
        包含变更信息的字典
    """
    result: Dict[str, Any] = {
        "success": False,
        "changes": {},
        "error": None,
    }

    try:
        content = file_path.read_text(encoding="utf-8")
        metadata, body = parse_frontmatter(content)

        # 记录变更
        for key, new_value in updates.items():
            old_value = metadata.get(key)
            if old_value != new_value:
                result["changes"][key] = {"old": old_value, "new": new_value}
                metadata[key] = new_value

        if dry_run:
            result["success"] = True
            return result

        # 写入文件
        new_content = format_frontmatter(metadata) + "\n\n" + body
        file_path.write_text(new_content, encoding="utf-8")
        result["success"] = True

    except (IOError, OSError, UnicodeDecodeError) as e:
        result["error"] = str(e)

    return result


def get_required_fields() -> List[str]:
    """获取必需字段列表"""
    return ["title", "date"]


def get_recommended_fields() -> List[str]:
    """获取推荐字段列表"""
    return ["location", "weather", "mood", "people", "abstract", "topic"]


def validate_metadata(metadata: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    验证元数据完整性

    Returns:
        问题列表，每项包含 level, field, message
    """
    issues = []
    required = get_required_fields()

    for field in required:
        if field not in metadata or not metadata[field]:
            issues.append(
                {
                    "level": "error",
                    "field": field,
                    "message": f"缺少必填字段: {field}",
                }
            )

    # 日期格式验证
    if "date" in metadata and metadata["date"]:
        date_str = str(metadata["date"])
        if not re.match(r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2})?$", date_str):
            issues.append(
                {
                    "level": "warning",
                    "field": "date",
                    "message": f"日期格式可能不正确: {date_str}",
                }
            )

    # Schema 版本验证
    schema_version = metadata.get("schema_version")
    if schema_version is not None and schema_version != SCHEMA_VERSION:
        issues.append(
            {
                "level": "warning",
                "field": "schema_version",
                "message": f"Schema 版本不匹配: 文件={schema_version}, 当前={SCHEMA_VERSION}",
            }
        )

    return issues


def get_schema_version() -> int:
    """获取当前 schema 版本"""
    return SCHEMA_VERSION


def migrate_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    迁移元数据到当前 schema 版本

    当读取旧版本 frontmatter 时，自动应用必要的迁移转换。
    这是为未来格式变更准备的迁移框架。

    Args:
        metadata: 从文件解析的元数据

    Returns:
        迁移后的元数据（添加 schema_version 等）
    """
    # 如果没有 schema_version，假设为版本 1（当前版本）
    file_version = metadata.get("schema_version", 1)

    if file_version == SCHEMA_VERSION:
        # 版本匹配，无需迁移
        return metadata

    # 未来版本迁移逻辑将在此处添加
    # 例如：
    # if file_version < 2:
    #     # 版本 1 -> 2 的迁移
    #     metadata = _migrate_v1_to_v2(metadata)
    # if file_version < 3:
    #     # 版本 2 -> 3 的迁移
    #     metadata = _migrate_v2_to_v3(metadata)

    # 更新 schema_version 到当前版本
    metadata["schema_version"] = SCHEMA_VERSION

    return metadata
