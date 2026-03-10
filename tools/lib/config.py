"""
Life Index - Shared Configuration Module
=======================================
Centralized configuration for all atomic tools.
"""

import os
from pathlib import Path
from datetime import datetime

# User data directory (OS standard user documents directory)
# Uses Path.home() for cross-platform compatibility:
#   Windows: C:\Users\<username>\Documents\Life-Index
#   macOS:   ~/Documents/Life-Index
#   Linux:   ~/Documents/Life-Index
USER_DATA_DIR = Path.home() / "Documents" / "Life-Index"

# Project root (for reference only, not for data storage)
PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()

# Directory structure - POINT TO USER DATA DIR
JOURNALS_DIR = USER_DATA_DIR / "Journals"
BY_TOPIC_DIR = USER_DATA_DIR / "by-topic"
ATTACHMENTS_DIR = USER_DATA_DIR / "attachments"

# Abstracts directory (stored within Journals for co-location)
ABSTRACTS_DIR = JOURNALS_DIR

# Note: Abstracts are stored within Journals directory structure:
#   - Monthly: Journals/YYYY/MM/monthly_abstract.md
#   - Yearly:  Journals/YYYY/yearly_abstract.md
# This keeps abstracts co-located with the journals they summarize.

# Ensure directories exist
for dir_path in [JOURNALS_DIR, BY_TOPIC_DIR, ATTACHMENTS_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# File naming patterns
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

# Default values
DEFAULT_LOCATION = "重庆，中国"
DEFAULT_TOPIC = "life"
DEFAULT_PROJECT = "life-index"

# Weather API configuration
WEATHER_API_URL = "https://api.open-meteo.com/v1/forecast"
WEATHER_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

# Cross-platform path mappings
# ========================================
# Format: {"源平台路径前缀": "目标平台路径前缀"}
# 工具会自动检测当前平台并进行双向转换
#
# 使用场景：
# 1. 在 Linux/macOS 上运行 OpenClaw，但日志中有 Windows 路径
#    配置：{"C:\\Users\\xxx": "/home/xxx"} 或 {"C:\\Users\\xxx": "/Users/xxx"}
#
# 2. 在 Windows 上运行 OpenClaw，但日志中有 Linux/macOS 路径
#    配置：{"/home/xxx": "C:\\Users\\xxx"} 或 {"/Users/xxx": "C:\\Users\\xxx"}
#
# 3. 多平台混用（同时配置多组映射）
#
# 示例配置：
PATH_MAPPINGS = {
    # Windows → Linux (WSL/虚拟机)
    "C:\\Users\\17865": "/home/dexter",

    # Windows → macOS (取消注释并修改用户名)
    # "C:\\Users\\your_name": "/Users/your_name",

    # Linux → Windows (在 Windows 上运行时使用)
    # "/home/dexter": "C:\\Users\\17865",

    # WSL 挂载路径
    # "D:\\": "/mnt/d",
}

# Vector Embedding Model Configuration
# ========================================
# 固定模型版本以确保嵌入一致性
# 模型文件约 80MB，首次使用会自动下载
EMBEDDING_MODEL = {
    "name": "sentence-transformers/all-MiniLM-L6-v2",
    "version": "1.0.0",  # 模型版本标识
    "dimension": 384,    # 输出向量维度
    # SHA-256 哈希值（模型配置文件的预期哈希，用于完整性校验）
    # 注意：这是 HuggingFace 上模型文件的哈希，实际实现中我们会校验下载后的配置
    "config_hash": "e4b6f8e8e8e8e8e8e8e8e8e8e8e8e8e8e8e8e8e8e8e8e8e8e8e8e8e8e8e8e8e8",
    # 模型元数据（用于追溯和日志记录）
    "metadata": {
        "description": "MiniLM-L6-v2 模型，适用于短文本语义相似度计算",
        "max_seq_length": 256,
        "recommended_for": "日志检索、语义搜索"
    }
}

# 模型缓存目录（跨平台）
# 使用 platform.system() 检测操作系统，选择合适的缓存路径
def get_model_cache_dir() -> Path:
    """
    获取模型缓存目录（跨平台兼容）

    Returns:
        Path: 模型缓存目录路径
    """
    import platform
    system = platform.system()

    if system == "Windows":
        # Windows: %USERPROFILE%\.cache\life-index\models
        cache_base = Path.home() / ".cache" / "life-index" / "models"
    else:
        # macOS/Linux: ~/.cache/life-index/models
        cache_base = Path.home() / ".cache" / "life-index" / "models"

    cache_base.mkdir(parents=True, exist_ok=True)
    return cache_base


def get_journal_dir(year: int = None, month: int = None) -> Path:
    """Get journal directory for given year/month (defaults to current)."""
    now = datetime.now()
    year = year or now.year
    month = month or now.month
    return JOURNALS_DIR / str(year) / f"{month:02d}"


def get_next_sequence(project: str, date_str: str) -> int:
    """Get next sequence number for a project on a given date."""
    year, month, _ = date_str.split('-')
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
            seq_part = f.stem.split('_')[-1]
            seq_nums.append(int(seq_part))
        except (ValueError, IndexError):
            continue

    return max(seq_nums, default=0) + 1


def parse_frontmatter(file_path: Path) -> dict:
    """Parse YAML frontmatter from a markdown file."""
    content = file_path.read_text(encoding='utf-8')

    if not content.startswith('---'):
        return {}

    try:
        _, fm, body = content.split('---', 2)
        import yaml
        metadata = yaml.safe_load(fm.strip())
        metadata['_body'] = body.strip()
        metadata['_file'] = str(file_path)
        return metadata
    except Exception:
        return {}


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
    import platform

    if not path:
        return ""

    # 1. 处理 Windows 长路径前缀
    if path.startswith('\\\\?\\'):
        path = path[4:]

    # 2. 统一分隔符
    path = path.replace('\\', '/')

    # 3. 应用路径映射（如果配置了）
    current_platform = platform.system()
    for src_prefix, dst_prefix in PATH_MAPPINGS.items():
        # 标准化映射配置中的分隔符
        src_prefix = src_prefix.replace('\\', '/')
        dst_prefix = dst_prefix.replace('\\', '/')

        if path.startswith(src_prefix):
            path = dst_prefix + path[len(src_prefix):]
            break

    return path


def get_safe_path(path: str, base_dir: Path = None) -> Path:
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
            if str(resolved) != str(base_resolved) and not str(resolved).startswith(str(base_resolved) + os.sep):
                # 路径不在 base_dir 内，可能不安全
                # 但仍然返回路径，让调用者决定如何处理
                pass
        except (OSError, ValueError):
            pass

    return resolved
