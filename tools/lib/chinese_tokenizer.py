"""
Life Index - Chinese Tokenizer Utilities
=======================================
Shared jieba-based Chinese tokenization helpers for FTS indexing and querying.

SSOT: This module is the single source of truth for Chinese segmentation rules.
Both index-time and query-time tokenization must flow through this module to
avoid drift between retrieval pipelines.

Design Decisions (Round 8 Phase 1):
- MD1: Dual mode — index uses jieba.cut() (precise), query uses jieba.cut_for_search()
- MD2: Single function segment_for_fts() with mode param — prevents config drift
- MD3: Only segments CJK characters — English/numbers preserved
- MD4: Stopword filtering is mandatory for query mode, disabled for index mode
- MD6: Entity dict hash tracked in index_meta for staleness detection
"""

from __future__ import annotations

import hashlib
import importlib
import re
import tempfile
import unicodedata
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import yaml


_jieba_initialized = False
_jieba_module: Any | None = None
_entity_dict_loaded: bool = False
_entity_dict_hash: str = ""


# ---------------------------------------------------------------------------
# Chinese Stop Words (MD4: mandatory for query mode)
# ---------------------------------------------------------------------------

CHINESE_STOP_WORDS: frozenset[str] = frozenset(
    {
        # Structural particles (high-frequency, low semantic content)
        "的",
        "了",
        "在",
        "是",
        "我",
        "有",
        "和",
        "就",
        "人",
        "都",
        "一",
        "一个",
        "上",
        "也",
        "很",
        "到",
        "说",
        "要",
        "去",
        "你",
        "会",
        "着",
        "看",
        "好",
        "自己",
        "这",
        # Adverbs / function words
        "那",
        "他",
        "她",
        "它",
        "们",
        "把",
        "被",
        "让",
        "给",
        "从",
        "对",
        "比",
        "跟",
        "向",
        "过",
        # Sentence-final particles (pure tone markers, no semantic content)
        "吗",
        "呢",
        "吧",
        "啊",
        "哦",
        "嗯",
        "呀",
        # Conjunctions that don't carry query intent
        "因为",
        "所以",
        "如果",
        "但是",
        "而且",
        "或者",
        # Measure words / prepositions
        "个",
        "只",
        "些",
        "里",
        "中",
        "后",
        "前",
        "时",
        "能",
        "可以",
        "已经",
        "还",
        "又",
        "再",
        # NOTE (B-4): The following words were REMOVED from stopword list because
        # they carry query intent and their removal was causing recall failures:
        # - 不 (negation intent: 不吃饭, 不喜欢)
        # - 没有 (absence intent: 没有反应, 没有结果)
        # - 怎么 (question intent: 怎么了, 怎么办)
        # - 什么 (question intent: 什么意思, 什么情况)
        # - 这个/那个 (deictic intent: 这个问题, 那个人)
    }
)


def normalize_query(query: str) -> str:
    """Normalize user query text before segmentation.

    Round 8 Phase 3 T3.2:
    - Fullwidth → halfwidth via NFKC
    - Strip common book-title / quote punctuation wrappers
    - Strip leading/trailing punctuation noise
    - Collapse repeated whitespace
    """
    if not query:
        return ""

    normalized = unicodedata.normalize("NFKC", query)
    normalized = normalized.strip()

    if not normalized:
        return ""

    wrapper_chars = "“”‘’「」『』《》〈〉【】（）［］｛｝"
    punctuation_chars = "!！?？,，.。;；:：、…·"

    normalized = normalized.strip(wrapper_chars)
    normalized = normalized.strip(punctuation_chars)
    normalized = re.sub(r"\s+", " ", normalized)

    return normalized.strip()


def is_cjk(char: str) -> bool:
    """Check whether a single character belongs to a CJK ideograph range.

    NOTE: CJK punctuation (U+3000–U+303F) and fullwidth forms (U+FF00–U+FFEF)
    are deliberately excluded — they are punctuation, not content characters
    to be segmented.
    """
    if len(char) != 1:
        return False

    codepoint = ord(char)
    ranges = (
        (0x3400, 0x4DBF),  # CJK Unified Ideographs Extension A
        (0x4E00, 0x9FFF),  # CJK Unified Ideographs
        (0xF900, 0xFAFF),  # CJK Compatibility Ideographs
        (0x20000, 0x2A6DF),  # CJK Unified Ideographs Extension B
        (0x2A700, 0x2B73F),  # CJK Unified Ideographs Extension C
        (0x2B740, 0x2B81F),  # CJK Unified Ideographs Extension D
        (0x2B820, 0x2CEAF),  # CJK Unified Ideographs Extension E
        (0x2CEB0, 0x2EBEF),  # CJK Unified Ideographs Extension F
        (0x30000, 0x3134F),  # CJK Unified Ideographs Extension G
        (0x2F800, 0x2FA1F),  # CJK Compatibility Ideographs Supplement
    )
    return any(start <= codepoint <= end for start, end in ranges)


def _get_jieba_module() -> Any:
    """Import jieba lazily to avoid work during module import."""
    global _jieba_module
    if _jieba_module is None:
        _jieba_module = importlib.import_module("jieba")
    return _jieba_module


def _ensure_jieba_initialized() -> Any:
    """Initialize jieba lazily on first real tokenization use."""
    global _jieba_initialized
    jieba_module = _get_jieba_module()
    if not _jieba_initialized:
        jieba_module.initialize()
        _jieba_initialized = True
    return jieba_module


def _keep_token(token: str) -> bool:
    """Return True when a token contains searchable content.

    At least one alphanumeric or CJK char required.
    """
    stripped = token.strip()
    if not stripped:
        return False
    # Token must contain at least one CJK ideograph or alphanumeric character.
    # This filters out pure-punctuation tokens that jieba may emit.
    return any(is_cjk(char) or char.isalnum() for char in stripped)


# ---------------------------------------------------------------------------
# Entity Dictionary Loading (T1.5)
# ---------------------------------------------------------------------------


def _extract_entity_names(graph_path: Path) -> list[str]:
    """Extract CJK entity names (primary_name + aliases) from entity_graph.yaml.

    Uses raw YAML parsing to avoid validation errors in entity_graph
    (e.g., dangling relationship references).
    """
    if not graph_path.exists():
        return []

    try:
        with graph_path.open("r", encoding="utf-8") as f:
            payload = yaml.safe_load(f) or {}
    except (yaml.YAMLError, OSError):
        return []

    entities = payload.get("entities", [])
    names: list[str] = []
    for entity in entities:
        if not isinstance(entity, dict):
            continue
        primary = entity.get("primary_name", "")
        if primary and len(primary) > 1 and any(is_cjk(c) for c in primary):
            names.append(primary)
        for alias in entity.get("aliases", []):
            if alias and len(alias) > 1 and any(is_cjk(c) for c in alias):
                names.append(alias)

    return names


def load_entity_dict(graph_path: Path | None = None) -> None:
    """Load entity names from entity_graph.yaml into jieba's user dictionary.

    This prevents jieba from splitting entity names like "团团" into "团 团".
    Called lazily on first segmentation use.

    Args:
        graph_path: Path to entity_graph.yaml. If None, uses default location.
    """
    global _entity_dict_loaded, _entity_dict_hash

    if _entity_dict_loaded:
        return

    if graph_path is None:
        from tools.lib.config import USER_DATA_DIR

        graph_path = USER_DATA_DIR / "entity_graph.yaml"

    names = _extract_entity_names(graph_path)

    if not names:
        _entity_dict_loaded = True
        _entity_dict_hash = ""
        return

    # Write names to a temp file in jieba userdict format: word [freq] [tag]
    # We don't specify freq/tag — jieba will auto-calculate.
    jieba_module = _get_jieba_module()
    tmp_path: str = ""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", encoding="utf-8", delete=False
        ) as tmp:
            for name in names:
                tmp.write(f"{name}\n")
            tmp_path = tmp.name

        jieba_module.load_userdict(tmp_path)
    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)

    # B-11: MD5 used for content hashing only, not security
    _entity_dict_hash = hashlib.md5(
        "\n".join(sorted(names)).encode(), usedforsecurity=False
    ).hexdigest()[:12]
    _entity_dict_loaded = True


def get_dict_hash(graph_path: Path | None = None) -> str:
    """Return the hash of the currently loaded entity dictionary.

    Used by index_meta (T1.4) to detect when entity names have changed
    and trigger a rebuild.
    """
    if not _entity_dict_loaded:
        load_entity_dict(graph_path)
    return _entity_dict_hash


def _segment_cjk_text(text: str, mode: str) -> list[str]:
    """Segment a CJK text chunk with jieba in the requested mode."""
    jieba_module = _ensure_jieba_initialized()
    segmented: Iterable[str]
    if mode == "index":
        segmented = jieba_module.cut(text)
    elif mode == "query":
        segmented = jieba_module.cut_for_search(text)
    else:
        raise ValueError("mode must be 'index' or 'query'")

    return [token.strip() for token in segmented if _keep_token(token)]


def _process_text(text: str, mode: str) -> list[str]:
    """Split mixed text into CJK and non-CJK segments and tokenize each."""
    if mode not in {"index", "query"}:
        raise ValueError("mode must be 'index' or 'query'")
    if not text:
        return []

    tokens: list[str] = []
    current_chars: list[str] = []
    current_is_cjk: bool | None = None

    def flush_segment() -> None:
        nonlocal current_chars, current_is_cjk
        if not current_chars:
            return

        segment = "".join(current_chars)
        if current_is_cjk:
            tokens.extend(_segment_cjk_text(segment, mode))
        else:
            tokens.extend(token for token in segment.split() if _keep_token(token))

        current_chars = []
        current_is_cjk = None

    for char in text:
        char_is_cjk = is_cjk(char)
        if current_is_cjk is None or char_is_cjk == current_is_cjk:
            current_chars.append(char)
            current_is_cjk = char_is_cjk
            continue

        flush_segment()
        current_chars.append(char)
        current_is_cjk = char_is_cjk

    flush_segment()
    return tokens


def segment_for_fts(text: str, mode: str = "index") -> str:
    """Segment text into a space-separated token string for FTS5.

    This is the single entry point for both index-time and query-time segmentation.
    Using one function prevents configuration drift (Metis Risk #1).

    Args:
        text: Input text — may contain mixed CJK, English, numbers, punctuation.
        mode: "index" for precise segmentation (jieba.cut),
              "query" for search-optimized segmentation (jieba.cut_for_search).
              Stop word filtering is applied only in query mode (MD4).

    Returns:
        Space-separated token string ready for FTS5 unicode61 tokenizer.
    """
    if not text:
        return ""

    if mode not in ("index", "query"):
        mode = "index"  # Default to safe precise mode

    # Ensure entity dictionary is loaded before segmentation (T1.5)
    load_entity_dict()

    tokens = _process_text(text, mode)

    # MD4: Stop word filtering — query mode only
    if mode == "query" and tokens:
        tokens = [t for t in tokens if t not in CHINESE_STOP_WORDS]

    return " ".join(tokens)


def reset_tokenizer_state() -> None:
    """Reset internal state for testing purposes."""
    global _jieba_initialized, _jieba_module, _entity_dict_loaded, _entity_dict_hash
    _jieba_initialized = False
    _jieba_module = None
    _entity_dict_loaded = False
    _entity_dict_hash = ""


__all__ = [
    "is_cjk",
    "normalize_query",
    "segment_for_fts",
    "_process_text",
    "load_entity_dict",
    "get_dict_hash",
    "CHINESE_STOP_WORDS",
    "reset_tokenizer_state",
]
