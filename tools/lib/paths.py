"""
Life Index - Paths Module
=========================
Path definitions and directory utilities.

This module contains all path-related constants and helpers.
Fully independent - no circular imports with config.py.
"""

import os
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

import yaml


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


# User data directory (OS standard user documents directory)
# Uses Path.home() for cross-platform compatibility:
#   Windows: C:\Users\<username>\Documents\Life-Index
#   macOS:   ~/Documents/Life-Index
#   Linux:   ~/Documents/Life-Index
#
# Can be overridden via LIFE_INDEX_DATA_DIR environment variable (for testing)
USER_DATA_DIR = resolve_user_data_dir()

# Project root (for reference only, not for data storage)
PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()

# Directory structure - POINT TO USER DATA DIR
JOURNALS_DIR = USER_DATA_DIR / "Journals"
BY_TOPIC_DIR = USER_DATA_DIR / "by-topic"
ATTACHMENTS_DIR = USER_DATA_DIR / "attachments"

# Abstracts directory (stored within Journals for co-location)
ABSTRACTS_DIR = JOURNALS_DIR

# Config directory for user configuration
CONFIG_DIR = USER_DATA_DIR / ".life-index"
CONFIG_FILE = CONFIG_DIR / "config.yaml"


def ensure_dirs() -> None:
    """
    确保所有必要的数据目录存在。

    必须在工具的 main() 入口处显式调用，避免 import 时的副作用
    （import 时创建目录会污染测试环境和 CI）。

    各原子工具的 main() 应在执行任何操作前调用此函数。
    """
    for dir_path in [JOURNALS_DIR, BY_TOPIC_DIR, ATTACHMENTS_DIR, CONFIG_DIR]:
        dir_path.mkdir(parents=True, exist_ok=True)


# =============================================================================
# File Naming Patterns
# =============================================================================

JOURNAL_FILENAME_PATTERN = "{project}_{date}_{seq:03d}.md"
DATE_FORMAT = "%Y-%m-%d"
DATETIME_FORMAT = "%Y-%m-%d %H:%M"

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
# Internal Helpers (used by config.py)
# =============================================================================


def _load_yaml_config(config_path: Path) -> Dict[str, Any]:
    """Load configuration from YAML file."""
    if not config_path.exists():
        return {}

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except (IOError, OSError, yaml.YAMLError):
        return {}


def _deep_merge(base: Dict, override: Dict) -> Dict:
    """Deep merge two dictionaries."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


# =============================================================================
# Path Utilities
# =============================================================================


def get_journal_dir(year: Optional[int] = None, month: Optional[int] = None) -> Path:
    """Get journal directory for given year/month (defaults to current)."""
    now = datetime.now()
    year = year or now.year
    month = month or now.month
    return JOURNALS_DIR / str(year) / f"{month:02d}"


def get_next_sequence(project: str, date_str: str) -> int:
    """Get next sequence number for a project on a given date."""
    year, month, _ = date_str.split("-")
    journal_dir = JOURNALS_DIR / year / month

    if not journal_dir.exists():
        return 1

    # Find existing files for this project and date
    pattern = f"{project}_{date_str}_*.md"
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
    user_config = _load_yaml_config(CONFIG_FILE)
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
    user_config = _load_yaml_config(CONFIG_FILE)
    return _deep_merge(defaults, user_config.get("index_prefixes", {}))


# 全局前缀配置实例（延迟加载）
INDEX_PREFIXES = get_index_prefixes()


# =============================================================================
# Re-exports for backward compatibility
# =============================================================================

__all__ = [
    # Paths
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
    # Patterns
    "JOURNAL_FILENAME_PATTERN",
    "DATE_FORMAT",
    "DATETIME_FORMAT",
    "JOURNAL_TEMPLATE",
    # Utilities
    "get_journal_dir",
    "get_next_sequence",
    "get_path_mappings",
    "PATH_MAPPINGS",
    "normalize_path",
    "get_safe_path",
    # Index prefixes
    "get_index_prefixes",
    "INDEX_PREFIXES",
    # Shared helpers (for config.py)
    "_load_yaml_config",
    "_deep_merge",
]
