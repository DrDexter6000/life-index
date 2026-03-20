#!/usr/bin/env python3
"""
Life Index - Frontmatter Utilities
统一 YAML frontmatter 解析/格式化模块（SSOT）

所有工具应使用此模块处理 frontmatter，避免重复实现。
使用 yaml.safe_load 确保完整 YAML 规范支持（多行字符串、嵌套、特殊字符等）。
"""

import re
import yaml
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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
        metadata = {}

    # yaml.safe_load 会将 ISO 8601 时间戳解析为 datetime 对象。
    # 整个代码库以字符串形式处理日期，转回字符串以保持接口稳定。
    for key, value in metadata.items():
        if isinstance(value, datetime):
            metadata[key] = value.isoformat(timespec="seconds")
        elif isinstance(value, date):
            metadata[key] = value.isoformat()

    return metadata, body


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
            metadata["_abstract"] = abstract + "..." if len(abstract) == 100 else abstract
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
    import json

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
    frontmatter = format_frontmatter(data)

    lines = []

    # 标题
    title = data.get("title", "")
    if title:
        lines.append(f"# {title}")
        lines.append("")

    # 正文
    content = data.get("content", "")
    if content:
        lines.append(content)
        lines.append("")

    # 附件引用
    attachments = data.get("attachments", [])
    if attachments:
        lines.append("## Attachments")
        for att in attachments:
            if isinstance(att, dict):
                filename = att.get("filename", "")
                rel_path = att.get("rel_path", "")
                description = att.get("description", "")
                path = rel_path or f"../../../attachments/{filename}"
                lines.append(f"- [{filename}]({path}) - {description}")
            elif isinstance(att, str):
                lines.append(f"- [{att}]({att})")
        lines.append("")

    body = "\n".join(lines)
    return f"{frontmatter}\n\n{body}"


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
    result = {
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
