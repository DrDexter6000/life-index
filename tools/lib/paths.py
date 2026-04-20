"""
Life Index - Paths Module
=========================
Path definitions and directory utilities.

This module contains all path-related constants and helpers.
Fully independent - no circular imports with config.py.
"""

import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

from .yaml_utils import load_yaml_config, deep_merge

# =============================================================================
# Path Definitions
# =============================================================================


def resolve_user_data_dir() -> Path:
    """Resolve active user data directory from env override or platform default.

    Priority:
    1. LIFE_INDEX_DATA_DIR environment variable
    2. Path.home()/Documents/Life-Index
    """
    user_data_env = os.environ.get("LIFE_INDEX_DATA_DIR")
    if user_data_env:
        return Path(user_data_env)
    return Path.home() / "Documents" / "Life-Index"


def resolve_journals_dir() -> Path:
    """Resolve active journals directory based on current data-dir resolution."""
    return resolve_user_data_dir() / "Journals"


# ── Stateless Getter System (Round 15) ─────────────────────────────
# No cache — reads env var every time. This prevents stale references
# when tests change LIFE_INDEX_DATA_DIR per-test.

_user_data_dir_cache: Path | None = None  # deprecated: kept for conftest compat, never read


def reset_path_cache() -> None:
    """No-op. Kept for backward compatibility with existing conftest."""
    global _user_data_dir_cache
    _user_data_dir_cache = None


def get_user_data_dir() -> Path:
    """Stateless user data directory. Reads LIFE_INDEX_DATA_DIR env var every call.

    During pytest: crashes immediately if env var is unset, preventing
    any accidental writes to the real ~/Documents/Life-Index/.
    """
    explicit = os.environ.get("LIFE_INDEX_DATA_DIR")
    if explicit:
        return Path(explicit)
    if "pytest" in sys.modules:
        raise RuntimeError(
            "LIFE_INDEX_DATA_DIR not set during pytest — "
            "refusing to use real data dir. "
            "conftest.py must set this env var before importing tool modules."
        )
    return Path.home() / "Documents" / "Life-Index"


def get_journals_dir() -> Path:
    return get_user_data_dir() / "Journals"


def get_index_dir() -> Path:
    return get_user_data_dir() / ".index"


def get_fts_db_path() -> Path:
    return get_index_dir() / "journals_fts.db"


def get_vec_index_path() -> Path:
    return get_index_dir() / "vectors_simple.pkl"


def get_vec_meta_path() -> Path:
    return get_index_dir() / "vectors_simple_meta.json"


def get_cache_dir() -> Path:
    return get_user_data_dir() / ".cache"


def get_metadata_db_path() -> Path:
    return get_cache_dir() / "metadata_cache.db"


def get_by_topic_dir() -> Path:
    return get_user_data_dir() / "by-topic"


def get_attachments_dir() -> Path:
    return get_user_data_dir() / "attachments"


def get_config_dir() -> Path:
    return get_user_data_dir() / ".life-index"


def get_config_file() -> Path:
    return get_config_dir() / "config.yaml"


# User data directory (OS standard user documents directory)
# Uses Path.home() for cross-platform compatibility:
#   Windows: C:\Users\<username>\Documents\Life-Index
#   macOS:   ~/Documents/Life-Index
#   Linux:   ~/Documents/Life-Index
#
# Can be overridden via LIFE_INDEX_DATA_DIR environment variable (for testing)
USER_DATA_DIR = resolve_user_data_dir()  # deprecated: use get_user_data_dir()

# Project root (for reference only, not for data storage)
PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()

# Directory structure - POINT TO USER DATA DIR
JOURNALS_DIR = USER_DATA_DIR / "Journals"  # deprecated: use get_journals_dir()
BY_TOPIC_DIR = USER_DATA_DIR / "by-topic"  # deprecated: use get_by_topic_dir()
ATTACHMENTS_DIR = USER_DATA_DIR / "attachments"  # deprecated: use get_attachments_dir()

# Abstracts directory (stored within Journals for co-location)
ABSTRACTS_DIR = JOURNALS_DIR  # deprecated: use get_journals_dir()

# Config directory for user configuration
CONFIG_DIR = USER_DATA_DIR / ".life-index"  # deprecated: use get_config_dir()
CONFIG_FILE = CONFIG_DIR / "config.yaml"  # deprecated: use get_config_file()


def ensure_dirs() -> None:
    """
    确保所有必要的数据目录存在。

    必须在工具的 main() 入口处显式调用，避免 import 时的副作用
    （import 时创建目录会污染测试环境和 CI）。

    各原子工具的 main() 应在执行任何操作前调用此函数。
    """
    for dir_path in [
        get_journals_dir(),
        get_by_topic_dir(),
        get_attachments_dir(),
        get_config_dir(),
    ]:
        dir_path.mkdir(parents=True, exist_ok=True)


# =============================================================================
# File Naming Patterns
# =============================================================================

JOURNAL_FILENAME_PATTERN = "{project}_{date}_{seq:03d}.md"
DATE_FORMAT = "%Y-%m-%d"
DATETIME_FORMAT = "%Y-%m-%d %H:%M"

# Characters not allowed in filenames (Windows + Unix)
_UNSAFE_FILENAME_CHARS = r'<>:"/\|?*'


def sanitize_filename(name: str, replacement: str = "_") -> str:
    """
    Sanitize a string for use as a filename.

    Replaces characters that are not allowed in filenames on Windows or Unix.

    Args:
        name: The string to sanitize
        replacement: Character to replace unsafe characters with (default: "_")

    Returns:
        Sanitized string safe for use as a filename
    """
    if not name:
        return "unnamed"

    result = name.strip()

    # Replace unsafe characters
    for char in _UNSAFE_FILENAME_CHARS:
        result = result.replace(char, replacement)

    # Collapse multiple replacements into one
    while replacement + replacement in result:
        result = result.replace(replacement + replacement, replacement)

    # Remove leading/trailing replacements
    result = result.strip(replacement)

    return result or "unnamed"


# YAML Frontmatter template
JOURNAL_TEMPLATE = """---
date: {date}
time: {time}
location: {location}
weather: {weather}
topic: {topic}
project: {project}
tags: {tags}
seq: {seq}
---

{content}
"""


# =============================================================================
# Path Utilities
# =============================================================================


def get_journal_dir(year: Optional[int] = None, month: Optional[int] = None) -> Path:
    """Get journal directory for given year/month (defaults to current)."""
    now = datetime.now()
    year = year or now.year
    month = month or now.month
    return get_journals_dir() / str(year) / f"{month:02d}"


def get_next_sequence(project: str, date_str: str) -> int:
    """Get next sequence number for a project on a given date."""
    # Sanitize project name for filesystem safety
    safe_project = sanitize_filename(project)
    year, month, _ = date_str.split("-")
    journal_dir = get_journals_dir() / year / month

    if not journal_dir.exists():
        return 1

    # Find existing files for this project and date
    pattern = f"{safe_project}_{date_str}_*.md"
    existing = list(journal_dir.glob(pattern))

    if not existing:
        return 1

    # Extract sequence numbers
    seq_nums = []
    for f in existing:
        try:
            seq_part = f.stem.split("_")[-1]
            seq_nums.append(int(seq_part))
        except (ValueError, IndexError):
            continue

    return max(seq_nums, default=0) + 1


def get_path_mappings() -> dict[str, str]:
    """Get cross-platform path mappings from config."""
    # Load config directly to avoid circular import
    user_config = load_yaml_config(get_config_file())
    mappings: dict[str, str] = user_config.get("path_mappings", {})
    return mappings


PATH_MAPPINGS = get_path_mappings()


def normalize_path(path: str) -> str:
    """
    标准化路径表示（跨平台兼容）

    功能：
    1. 统一路径分隔符为 '/'
    2. 处理 Windows 长路径前缀（\\\\?\\）
    3. 应用 PATH_MAPPINGS 进行路径转换

    Args:
        path: 原始路径

    Returns:
        标准化后的路径（使用 '/' 分隔符）
    """
    if not path:
        return ""

    # 1. 处理 Windows 长路径前缀
    if path.startswith("\\\\?\\"):
        path = path[4:]

    # 2. 统一分隔符
    path = path.replace("\\", "/")

    # 3. 应用路径映射（如果配置了）
    for src_prefix, dst_prefix in PATH_MAPPINGS.items():
        # 标准化映射配置中的分隔符
        src_prefix = src_prefix.replace("\\", "/")
        dst_prefix = dst_prefix.replace("\\", "/")

        if path.startswith(src_prefix):
            path = dst_prefix + path[len(src_prefix) :]
            break

    return path


def get_safe_path(path: str, base_dir: Optional[Path] = None) -> Optional[Path]:
    """
    获取安全的路径（防止路径遍历攻击）

    Args:
        path: 相对路径或绝对路径
        base_dir: 基础目录（如果 path 是相对路径）

    Returns:
        解析后的 Path 对象，如果路径不安全则返回 None
    """
    if not path:
        return None

    # 转换为 Path 对象
    if Path(path).is_absolute():
        result_path = Path(path)
    elif base_dir:
        result_path = base_dir / path
    else:
        result_path = Path(path)

    # 解析路径（处理 .. 和符号链接）
    try:
        resolved = result_path.resolve()
    except (OSError, ValueError):
        return None

    # 安全检查：确保解析后的路径在预期目录内
    if base_dir:
        try:
            base_resolved = base_dir.resolve()
            # 检查是否是子目录
            if str(resolved) != str(base_resolved) and not str(resolved).startswith(
                str(base_resolved) + os.sep
            ):
                # 路径不在 base_dir 内，不安全
                return None
        except (OSError, ValueError):
            pass

    return resolved


def get_index_prefixes() -> dict[str, str]:
    """
    获取索引文件名前缀配置。

    支持国际化配置，可通过 config.yaml 自定义前缀。
    提供中文（默认）和英文选项。

    Returns:
        {
            "topic": "主题_",      # 或 "topic_"
            "project": "项目_",    # 或 "project_"
            "tag": "标签_",        # 或 "tag_"
        }
    """
    # 默认使用中文前缀
    defaults = {
        "topic": "主题_",
        "project": "项目_",
        "tag": "标签_",
    }

    # 从用户配置合并（如果存在）
    user_config = load_yaml_config(CONFIG_FILE)
    return deep_merge(defaults, user_config.get("index_prefixes", {}))


# 全局前缀配置实例（延迟加载）
INDEX_PREFIXES = get_index_prefixes()


# =============================================================================
# Re-exports for backward compatibility
# =============================================================================

__all__ = [
    # Paths (legacy constants — import-time bindings)
    "USER_DATA_DIR",
    "PROJECT_ROOT",
    "JOURNALS_DIR",
    "BY_TOPIC_DIR",
    "ATTACHMENTS_DIR",
    "ABSTRACTS_DIR",
    "CONFIG_DIR",
    "CONFIG_FILE",
    "resolve_user_data_dir",
    "resolve_journals_dir",
    "ensure_dirs",
    # Lazy Getters (Round 13 Phase 0)
    "reset_path_cache",
    "get_user_data_dir",
    "get_journals_dir",
    "get_index_dir",
    "get_fts_db_path",
    "get_vec_index_path",
    "get_vec_meta_path",
    "get_cache_dir",
    "get_metadata_db_path",
    "get_by_topic_dir",
    "get_attachments_dir",
    "get_config_dir",
    "get_config_file",
    # Patterns
    "JOURNAL_FILENAME_PATTERN",
    "DATE_FORMAT",
    "DATETIME_FORMAT",
    "JOURNAL_TEMPLATE",
    # Utilities
    "get_journal_dir",
    "get_next_sequence",
    "sanitize_filename",
    "get_path_mappings",
    "PATH_MAPPINGS",
    "normalize_path",
    "get_safe_path",
    # Index prefixes
    "get_index_prefixes",
    "INDEX_PREFIXES",
]
