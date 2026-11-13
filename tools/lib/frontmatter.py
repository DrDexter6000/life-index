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
from tools.lib.journal_files import fragment_date_from_filename

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


class _RecursiveFrontmatterError(ValueError):
    """A frontmatter collection refers to itself (a recursive YAML alias)."""


def parse_frontmatter(content: str) -> Tuple[Dict[str, Any], str]:
    """
    解析 YAML frontmatter

    Args:
        content: 完整的文件内容

    Returns:
        (metadata_dict, body_content)

    The root of the YAML document must be a mapping. A document whose root is a
    list or a scalar carries no metadata fields, so it reads exactly like a file
    without frontmatter: ``({}, body)``. A recursive structure (``&a [*a]``) is
    unreadable in the same way. Every reader may therefore assume a dict without
    guarding the type itself.
    """
    metadata, body, _unreadable = _read_frontmatter(content)
    return metadata, body


def frontmatter_is_unreadable(content: str) -> bool:
    """Whether a present ``---`` block holds no readable mapping.

    True for a list or scalar root, a YAML error the legacy-content recovery
    cannot turn into a mapping, and a recursive structure. A file without a
    ``---`` block and an empty block (``---\\n---``) are readable (they simply
    carry no fields). A rewriter refuses such a file through
    :func:`frontmatter_rewrite_blocker`, which reports this as ``"unreadable"``.
    """
    _metadata, _body, unreadable = _read_frontmatter(content)
    return unreadable


def frontmatter_rewrite_blocker(content: str) -> Optional[str]:
    """Reason an existing file's frontmatter cannot be written back, or ``None``.

    A tool that rewrites an existing frontmatter first proves it can write it
    back. Two reason codes block a rewrite:

    - ``"unreadable"``: a present block has no readable mapping root, so
      ``parse_frontmatter`` reads it as no fields and a rewrite would delete the
      user's YAML text.
    - ``"not_round_trippable"``: the block is readable, but serializing the
      parsed mapping and parsing the result does not give back what the
      serializer is meant to write for it (:func:`_rewrite_form`): a non-string
      key, ``!!set``, ``!!pairs``, a ``_``-prefixed key, ...

    A file without a ``---`` block and an empty block are rewritable, as is a
    file whose YAML would merely be laid out differently after a rewrite. The
    comparison is on parsed values, including their types, and uses the same
    parser as every reader.

    The check fails safe: if the serializer and :func:`_rewrite_form` ever
    disagree, the answer is a refusal, never a lossy rewrite.
    """
    metadata, body, unreadable = _read_frontmatter(content)
    if unreadable:
        return "unreadable"

    try:
        rendered = format_frontmatter(metadata)
        rewritten, _rewritten_body = parse_frontmatter(f"{rendered}\n\n{body}")
        same = _same_value(rewritten, _rewrite_form(metadata))
    except Exception:  # noqa: BLE001 - the serializer must never make a rewriter crash
        return "not_round_trippable"

    return None if same else "not_round_trippable"


def _rewrite_form(metadata: Dict[Any, Any]) -> Dict[Any, Any]:
    """The mapping ``format_frontmatter()`` is meant to write for ``metadata``.

    The serializer normalizes three things on purpose, and none of them loses
    a value: it always writes ``schema_version``; it leaves out a known field
    whose value is null (every reader treats that as absent); and it writes a
    string in a list field as the list of its comma-separated items. Everything
    else must come back exactly.
    """
    form: Dict[Any, Any] = {}
    for key, value in metadata.items():
        if value is None and key != "schema_version" and key in FIELD_ORDER:
            continue
        if key in _LIST_LIKE_FIELDS and isinstance(value, str):
            value = _split_list_text(value)
        form[key] = value
    form.setdefault("schema_version", SCHEMA_VERSION)
    return form


def _same_value(left: Any, right: Any) -> bool:
    """Equality that also compares types (``1``, ``1.0`` and ``True`` differ)."""
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(
            _same_value(left[key], right[key]) for key in left
        )
    if isinstance(left, (list, tuple)):
        return len(left) == len(right) and all(_same_value(a, b) for a, b in zip(left, right))
    return bool(left == right)


def _read_frontmatter(content: str) -> Tuple[Dict[str, Any], str, bool]:
    """The one parser behind ``parse_frontmatter`` and ``frontmatter_is_unreadable``."""
    if not content.startswith("---"):
        return {}, content, False

    sections = _split_frontmatter_sections(content)
    if sections is None:
        return {}, content, False

    fm_content = sections[0].strip()
    body = sections[1].strip()

    try:
        # Only an absent document (``None``) reads as an empty mapping. A
        # falsy root that is not a mapping (``false``, ``0``, ``[]``, ``""``)
        # is text the user wrote: it is unreadable, never "no fields".
        metadata: Any = yaml.safe_load(fm_content)
        if metadata is None:
            metadata = {}
    except (yaml.YAMLError, ValueError):
        # PyYAML raises a plain ValueError (not a YAMLError) for an impossible
        # timestamp such as ``date: 2026-99-99``.
        recovered, body = _recover_legacy_content_frontmatter(fm_content, body)
        if recovered is None:
            return {}, body, True
        metadata = recovered
    except RecursionError:
        return {}, body, True

    if not isinstance(metadata, dict):
        return {}, body, True

    metadata, body = _merge_legacy_content_into_body(metadata, body)

    # yaml.safe_load 会将 ISO 8601 时间戳解析为 datetime 对象。
    # 整个代码库以字符串形式处理日期，递归转回字符串以保持接口稳定
    # （顶层与嵌套 mapping/list 都不能向调用方泄漏 datetime）。同一次遍历
    # 还替换 lone surrogate（SQLite/UTF-8 无法编码）并拒绝递归结构。
    try:
        metadata = {
            _normalize_string_key(key): _normalize_temporal_values(value)
            for key, value in metadata.items()
        }
    except (_RecursiveFrontmatterError, RecursionError):
        return {}, body, True

    return metadata, body, False


# The fields every derived per-fragment store (FTS row, metadata cache) may
# index. ``normalize_indexable_metadata`` guarantees the type of each one.
INDEXABLE_SCALAR_FIELDS = (
    "title",
    "date",
    "location",
    "weather",
    "project",
    "abstract",
)
INDEXABLE_LIST_FIELDS = (
    "topic",
    "tags",
    "mood",
    "people",
    "links",
    "related_entries",
)


# ASCII digits and hyphens only; no calendar check.
_DATE_TEXT_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")

# Every collection type ``yaml.safe_load`` can build: mappings, sequences,
# ``!!pairs`` / ``!!omap`` (lists of tuples) and ``!!set``.
_COLLECTION_TYPES = (dict, list, tuple, set, frozenset)


def _leaf_text(value: Any) -> str:
    """Text of one scalar leaf: never raises, always UTF-8 encodable."""
    if value is None:
        return ""
    if isinstance(value, str):
        return _replace_lone_surrogates(value)
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    try:
        return _replace_lone_surrogates(str(value))
    except ValueError:
        # An integer too long for decimal conversion (``0xfff...``).
        return hex(value) if isinstance(value, int) else ""
    except Exception:  # noqa: BLE001 - a leaf must never raise
        return ""


def _collection_children(value: Any) -> List[Tuple[str, Any]]:
    """``(prefix, child)`` pairs of one collection, in a deterministic order."""
    if isinstance(value, dict):
        return [(f"{_leaf_text(key)}: ", item) for key, item in value.items()]
    if isinstance(value, (set, frozenset)):
        # A set has no order of its own, and its iteration order changes with
        # the process hash seed: sort by type name and text.
        keyed = [((type(item).__name__, _leaf_text(item)), item) for item in value]
        return [("", item) for _key, item in sorted(keyed, key=lambda pair: pair[0])]
    return [("", item) for item in value]


def _flatten_indexable_text(value: Any) -> str:
    """Deterministic depth-first text of a collection value.

    A mapping renders as ``key: value`` pairs, any other collection as its
    items, joined with ``", "``; every scalar leaf stays searchable at any
    depth. The walk is iterative, so depth cannot exhaust the stack, and a
    collection that contains itself renders as nothing at the point of the
    recursive reference. Never raises.
    """
    if not isinstance(value, _COLLECTION_TYPES):
        return _leaf_text(value)

    pieces: List[str] = []
    on_path = {id(value)}
    # One frame per open collection: [children iterator, id, is_first_child].
    stack: List[List[Any]] = [[iter(_collection_children(value)), id(value), True]]
    while stack:
        frame = stack[-1]
        try:
            prefix, child = next(frame[0])
        except StopIteration:
            on_path.discard(frame[1])
            stack.pop()
            continue
        if not frame[2]:
            pieces.append(", ")
        frame[2] = False
        pieces.append(prefix)
        if isinstance(child, _COLLECTION_TYPES):
            if id(child) in on_path:
                continue
            on_path.add(id(child))
            stack.append([iter(_collection_children(child)), id(child), True])
        else:
            pieces.append(_leaf_text(child))
    return "".join(pieces)


def _indexable_scalar_text(value: Any) -> str:
    """Text of a scalar field: a mapping or list becomes its flattened text."""
    return _flatten_indexable_text(value)


def _indexable_list(value: Any) -> List[str]:
    """Normalize a list field to ``list[str]``.

    A list keeps one text per item; a mapping/list item becomes its flattened
    text. A scalar becomes a one-item list, and a mapping at field level becomes
    a one-item list holding its flattened text.
    """
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [_indexable_scalar_text(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted(_indexable_scalar_text(item) for item in value)
    return [_indexable_scalar_text(value)]


def empty_indexable_metadata() -> Dict[str, Any]:
    """The indexable fields of a fragment whose frontmatter did not parse."""
    indexable: Dict[str, Any] = {key: "" for key in INDEXABLE_SCALAR_FIELDS}
    indexable.update({key: [] for key in INDEXABLE_LIST_FIELDS})
    return indexable


def normalize_indexable_metadata(metadata: Any) -> Optional[Dict[str, Any]]:
    """Return the indexable fields of ``metadata`` with guaranteed types.

    ``metadata`` is whatever :func:`parse_frontmatter` returned. A derived
    store may index only what this function returns:

    - the root must be a mapping, and not empty; that is the *only* reason this
      function returns ``None``;
    - scalar fields (:data:`INDEXABLE_SCALAR_FIELDS`) are text: ``None`` reads
      as ``""``, a string stays, a number or boolean becomes its text; a
      mapping or list becomes its flattened text;
    - list fields (:data:`INDEXABLE_LIST_FIELDS`) are ``list[str]``: ``None``
      becomes ``[]``, a scalar becomes a one-item list, a list keeps one text
      per item; a mapping/list item becomes its flattened text, and a mapping
      at field level becomes a one-item list holding its flattened text;
    - every other key is ignored.

    Flattened text is deterministic and never raises: depth-first, a mapping
    renders as ``key: value`` pairs, a list as its items, joined with ``", "``;
    non-string keys use ``str()``. Returns ``None`` only when the frontmatter
    is unparsable; the caller then treats the fragment like one without
    frontmatter (FTS: raw-text row; metadata cache: empty row). This is one rule
    for both stores — never duplicate it.
    """
    if not isinstance(metadata, dict) or not metadata:
        return None

    indexable: Dict[str, Any] = {}
    for key in INDEXABLE_SCALAR_FIELDS:
        indexable[key] = _indexable_scalar_text(metadata.get(key))

    for key in INDEXABLE_LIST_FIELDS:
        indexable[key] = _indexable_list(metadata.get(key))

    return indexable


def indexable_date(indexable: Dict[str, Any], file_path: Path) -> str:
    """The one date rule for every fragment reader (FTS, cache, fallback, timeline).

    The first 10 characters of the normalized ``date`` text when they have the
    shape ``YYYY-MM-DD`` (digits and hyphens; no calendar check), otherwise the
    date carried by the canonical fragment filename, otherwise ``""``. Values
    such as ``20260311`` or ``[2026]`` therefore never occupy the date column
    with text no date-range query can match.
    """
    date_text = str(indexable.get("date") or "")[:10]
    if _DATE_TEXT_RE.match(date_text):
        return date_text
    return fragment_date_from_filename(file_path) or ""


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


_LONE_SURROGATE_RE = re.compile("[\ud800-\udfff]")


def _replace_lone_surrogates(text: str) -> str:
    """Replace lone surrogates with U+FFFD; cheap fast path for ordinary text."""
    if text.isascii():
        return text
    return _LONE_SURROGATE_RE.sub("\ufffd", text)


def _normalize_string_key(key: Any) -> Any:
    """Replace lone surrogates in a string mapping key; other keys stay as-is."""
    if isinstance(key, str):
        return _replace_lone_surrogates(key)
    return key


def _normalize_temporal_values(value: Any, seen: Optional[set] = None) -> Any:
    """Recursively convert YAML dates to ISO strings, make strings UTF-8 safe.

    A recursive collection raises :class:`_RecursiveFrontmatterError`, which
    ``_read_frontmatter`` turns into "unreadable" instead of letting the YAML
    alias recurse forever.
    """
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        return _replace_lone_surrogates(value)
    if isinstance(value, dict):
        if seen is None:
            seen = set()
        if id(value) in seen:
            raise _RecursiveFrontmatterError("recursive frontmatter mapping")
        seen.add(id(value))
        try:
            return {
                _normalize_string_key(key): _normalize_temporal_values(item, seen)
                for key, item in value.items()
            }
        finally:
            seen.discard(id(value))
    if isinstance(value, (list, tuple, set, frozenset)):
        # ``!!pairs`` / ``!!omap`` build tuples and ``!!set`` builds a set; a
        # string or a recursive reference can hide inside any of them.
        if seen is None:
            seen = set()
        if id(value) in seen:
            raise _RecursiveFrontmatterError("recursive frontmatter collection")
        seen.add(id(value))
        try:
            return type(value)(_normalize_temporal_values(item, seen) for item in value)
        finally:
            seen.discard(id(value))
    return value


def _recover_legacy_content_frontmatter(
    fm_content: str, body: str
) -> Tuple[Optional[Dict[str, Any]], str]:
    """Recover metadata/body from legacy malformed `content: "..."` frontmatter.

    Returns ``None`` as the metadata when no mapping can be recovered; the
    caller then treats the frontmatter as unreadable.
    """
    content_match = re.search(r'^content:\s*"', fm_content, re.MULTILINE)
    if not content_match:
        return None, body

    metadata_prefix = fm_content[: content_match.start()].strip()
    content_block = fm_content[content_match.end() :]

    if content_block.endswith('"'):
        content_block = content_block[:-1]

    try:
        metadata: Any = yaml.safe_load(metadata_prefix)
        if metadata is None:
            metadata = {}
    except (yaml.YAMLError, ValueError):
        return None, body
    if not isinstance(metadata, dict):
        return None, body

    recovered_body = content_block.strip()
    trailing_body = body.strip()
    if trailing_body:
        recovered_body = f"{recovered_body}\n\n{trailing_body}" if recovered_body else trailing_body

    return metadata, recovered_body


def _merge_legacy_content_into_body(
    metadata: Dict[str, Any], body: str
) -> Tuple[Dict[str, Any], str]:
    legacy_content = metadata.get("content")
    if not isinstance(legacy_content, str):
        # Not the legacy shape: ``content`` stays an ordinary key, so a tool
        # that rewrites the frontmatter writes it back instead of dropping it.
        return metadata, body
    del metadata["content"]
    if not legacy_content.strip():
        return metadata, body

    # The text came through YAML and may hold an escaped lone surrogate.
    merged_body = _replace_lone_surrogates(legacy_content.strip())
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


# Fields the serializer writes as lists: a string value becomes the list of its
# comma-separated items ("tag1, tag2" -> ["tag1", "tag2"]).
_LIST_LIKE_FIELDS = frozenset(
    {"topic", "tags", "mood", "entities", "people", "links", "related_entries"}
)


def _split_list_text(value: str) -> List[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _format_field(key: str, value: Any) -> str:
    """格式化单个字段"""
    if key in _LIST_LIKE_FIELDS and isinstance(value, str):
        value = _split_list_text(value)

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
        blocker = frontmatter_rewrite_blocker(content)
        if blocker is not None:
            result["error"] = f"frontmatter rewrite blocked ({blocker})"
            return result
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
