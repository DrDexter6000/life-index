#!/usr/bin/env python3
"""
Life Index - Frontmatter Utilities
统一 YAML frontmatter 解析/格式化模块（SSOT）。
附件处理和 schema 验证/迁移已提取到 attachment.py 和 schema.py，
本模块保留 re-export 以保证向后兼容。
"""

import json
import re
import yaml
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# --- Re-exports from attachment.py (backward compat) ---
from tools.lib.attachment import normalize_attachment_entries  # noqa: F401

# --- Re-exports from schema.py (backward compat) ---
from tools.lib.schema import (  # noqa: F401
    SCHEMA_VERSION,
    validate_metadata,
    migrate_metadata,
    get_schema_version,
    get_required_fields,
    get_recommended_fields,
)

# 标准字段顺序（与历史日志保持一致）
FIELD_ORDER = [
    "schema_version",
    "title",
    "date",
    "location",
    "weather",
    "mood",
    "entities",
    "people",
    "tags",
    "project",
    "topic",
    "summary",
    "abstract",
    "links",
    "related_entries",
    "attachments",
]

# 字段类型定义
LIST_FIELDS = {
    "mood",
    "entities",
    "people",
    "tags",
    "topic",
    "links",
    "related_entries",
    "attachments",
}
STRING_FIELDS = {
    "title",
    "date",
    "location",
    "weather",
    "project",
    "abstract",
    "summary",
}

# JSON (ensure_ascii=False) leaves some code points raw that YAML's reader
# rejects (DEL, C1 controls, U+FFFE/U+FFFF, lone surrogates) or treats as line
# breaks (U+2028/U+2029).  Escape them so a JSON string literal always stays a
# faithful YAML double-quoted scalar.
_YAML_ESCAPE_REQUIRED = re.compile("[\x7f-\x9f\u2028\u2029\ud800-\udfff\ufffe\uffff]")

# Characters YAML treats as line breaks inside a scalar.
_YAML_LINE_BREAKS = "\n\r\x85\u2028\u2029"

# Marker for "this text cannot be written as a plain YAML scalar".
_NOT_A_PLAIN_SCALAR = object()

# One block-mapping nesting level.
_MAPPING_INDENT = "  "


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

    sections = _split_frontmatter_sections(content)
    if sections is None:
        return {}, content

    fm_content = sections[0].strip()
    body = sections[1].strip()

    try:
        metadata: Dict[str, Any] = yaml.safe_load(fm_content) or {}
    except yaml.YAMLError:
        metadata, body = _recover_legacy_content_frontmatter(fm_content, body)

    metadata, body = _merge_legacy_content_into_body(metadata, body)

    # yaml.safe_load 会将 ISO 8601 时间戳解析为 datetime 对象。
    # 整个代码库以字符串形式处理日期，递归转回字符串以保持接口稳定
    # （顶层与嵌套 mapping/list 都不能向调用方泄漏 datetime）。
    metadata = {key: _normalize_temporal_values(value) for key, value in metadata.items()}

    return metadata, body


def _split_frontmatter_sections(content: str) -> Optional[Tuple[str, str]]:
    """Split the ``---`` fenced block from the body.

    Delimiters are recognised as whole lines (the convention every other
    frontmatter reader in the repository uses), so a field value may contain
    ``---`` without truncating the metadata.  Malformed files that do not use
    whole-line fences keep the historical substring split.
    """
    lines = content.split("\n")
    if lines and lines[0].strip() == "---":
        for index in range(1, len(lines)):
            if lines[index].strip() == "---":
                return "\n".join(lines[1:index]), "\n".join(lines[index + 1 :])

    parts = content.split("---", 2)
    if len(parts) < 3:
        return None
    return parts[1], parts[2]


def _normalize_temporal_values(value: Any) -> Any:
    """Recursively convert YAML dates/timestamps to ISO strings."""
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _normalize_temporal_values(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize_temporal_values(item) for item in value]
    return value


def _recover_legacy_content_frontmatter(fm_content: str, body: str) -> Tuple[Dict[str, Any], str]:
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
        recovered_body = f"{recovered_body}\n\n{trailing_body}" if recovered_body else trailing_body

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
    lines = ["---"]

    # schema_version is always first, whether provided or not
    sv = data.get("schema_version", SCHEMA_VERSION)
    lines.append(_format_field("schema_version", sv))

    # 按标准顺序输出已知字段
    for key in FIELD_ORDER:
        if key == "schema_version":
            continue  # already handled above
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
    list_like_fields = {
        "topic",
        "tags",
        "mood",
        "entities",
        "people",
        "links",
        "related_entries",
    }

    if key in list_like_fields and isinstance(value, str):
        # 按逗号分割，确保 "tag1, tag2" 变成 ["tag1", "tag2"]
        value = [item.strip() for item in value.split(",") if item.strip()]

    if isinstance(value, dict):
        # 映射使用 block-style YAML：可读、保留键序、Unicode 不转义
        return "\n".join(_format_mapping_entry(key, value, ""))
    if isinstance(value, list):
        # 列表使用 JSON 格式
        return f"{key}: {_format_flow_value(value)}"
    elif isinstance(value, str):
        # 字符串加引号（除了 date 字段中本来就能原样解析的值）
        if key in ("date",) and _date_stays_plain(value):
            return f"{key}: {value}"
        return f"{key}: {_quote_yaml_string(value)}"
    elif isinstance(value, bool):
        return f"{key}: {'true' if value else 'false'}"
    elif value is None:
        return f"{key}:"
    elif isinstance(value, float):
        return f"{key}: {_format_float(value)}"
    else:
        return f"{key}: {value}"


def _quote_yaml_string(value: str) -> str:
    """Return a double-quoted YAML scalar for ``value``.

    A JSON string literal with ``ensure_ascii=False`` is already a valid YAML
    double-quoted scalar for ordinary content; only the code points YAML's
    reader cannot carry are rewritten as YAML ``\\uXXXX`` escapes.
    """
    literal = json.dumps(value, ensure_ascii=False)
    return _YAML_ESCAPE_REQUIRED.sub(lambda match: "\\u%04x" % ord(match.group(0)), literal)


def _format_flow_value(value: Any) -> str:
    """Render a value inside an inline flow collection using JSON syntax.

    ``json.dumps`` output is byte-identical for ordinary values, but PyYAML's
    YAML 1.1 resolver reads exponent-only floats (``1e+20``) as strings, so
    floats use ``_format_float`` and collections recurse instead.
    """
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return _quote_yaml_string(value)
    if isinstance(value, float):
        return _format_float(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_format_flow_value(item) for item in value) + "]"
    if isinstance(value, dict):
        entries = (
            f"{_format_flow_key(key)}: {_format_flow_value(item)}" for key, item in value.items()
        )
        return "{" + ", ".join(entries) + "}"
    # Keep the historical TypeError for values JSON cannot represent.
    return json.dumps(value, ensure_ascii=False)


def _format_flow_key(key: Any) -> str:
    """Render a flow-mapping key; JSON always quotes keys."""
    return _quote_yaml_string(key if isinstance(key, str) else str(key))


def _format_float(value: float) -> str:
    """Return a YAML float scalar; inf/nan use YAML's own spellings."""
    if value != value:
        return ".nan"
    if value == float("inf"):
        return ".inf"
    if value == float("-inf"):
        return "-.inf"
    text = repr(value)
    if "e" in text and "." not in text:
        # YAML 1.1 only resolves floats with a decimal point, so "1e+20"
        # would come back as a string.  "1.0e+20" is still the same float.
        text = text.replace("e", ".0e", 1)
    return text


def _load_plain_scalar(text: str) -> Any:
    """Parse ``text`` as a standalone YAML scalar, or return the sentinel.

    A plain scalar is safe to emit only when YAML reads the bare text back as
    exactly the same string.  ``safe_load`` is the authoritative check for
    timestamps, booleans, numbers, sexagesimals and indicator characters.
    """
    if not text or text != text.strip():
        return _NOT_A_PLAIN_SCALAR
    if any(ord(char) < 0x20 or ord(char) == 0x7F for char in text):
        return _NOT_A_PLAIN_SCALAR
    if any(char in _YAML_LINE_BREAKS for char in text):
        return _NOT_A_PLAIN_SCALAR
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError:
        return _NOT_A_PLAIN_SCALAR


def _is_plain_scalar(text: str) -> bool:
    """Whether ``text`` may be written unquoted and still parse back unchanged."""
    return bool(_load_plain_scalar(text) == text)


def _date_stays_plain(text: str) -> bool:
    """Whether an unquoted ``date`` value parses back to the same string."""
    parsed = _load_plain_scalar(text)
    if parsed == text:
        return True
    # parse_frontmatter normalises ISO dates/timestamps back to strings.
    return bool(_normalize_temporal_values(parsed) == text)


def _format_mapping_key(key: Any) -> str:
    """Render a mapping key, quoting it when YAML would resolve it otherwise."""
    if isinstance(key, str):
        return key if _is_plain_scalar(key) else _quote_yaml_string(key)
    return str(key)


def _format_block_scalar(value: Any) -> str:
    """Render a scalar (or inline list) value inside a block mapping."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return value if _is_plain_scalar(value) else _quote_yaml_string(value)
    if isinstance(value, float):
        return _format_float(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, (list, tuple)):
        return _format_flow_value(value)
    return _quote_yaml_string(str(value))


def _format_mapping_entry(key: Any, value: Any, indent: str) -> List[str]:
    """Render one block-mapping entry (recursing into nested mappings)."""
    rendered_key = _format_mapping_key(key)
    if isinstance(value, dict):
        if not value:
            return [f"{indent}{rendered_key}: {{}}"]
        lines = [f"{indent}{rendered_key}:"]
        nested_indent = indent + _MAPPING_INDENT
        for nested_key, nested_value in value.items():
            lines.extend(_format_mapping_entry(nested_key, nested_value, nested_indent))
        return lines
    return [f"{indent}{rendered_key}: {_format_block_scalar(value)}"]


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

    # 正文（100% 保留用户原始内容，不做标题去重）
    content = data.get("content", "")
    if content:
        lines.append(content)
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


def get_summary(fm: Dict[str, Any]) -> Optional[str]:
    """Get summary text, preferring 'summary' over 'abstract'.

    This provides a unified accessor for the journal summary field.
    New entries use 'summary'; old entries may have 'abstract'.
    """
    return fm.get("summary") or fm.get("abstract")
