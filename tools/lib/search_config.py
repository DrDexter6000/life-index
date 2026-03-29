"""
Life Index - Search Configuration Module
========================================
Search-specific configuration extracted from config.py.

This module contains all search-related configuration accessors and persistence.
Fully independent - no circular imports with config.py.
"""

import os
from pathlib import Path
from typing import Any, Dict

import yaml

from .paths import (
    CONFIG_DIR,
    CONFIG_FILE,
    _load_yaml_config,
    _deep_merge,
)


# =============================================================================
# Internal: User Config Loader
# =============================================================================


def _get_env_config() -> Dict[str, Any]:
    """Load configuration from environment variables."""
    config: Dict[str, Any] = {}

    env_mappings = {
        "LIFE_INDEX_SEARCH_LEVEL": ("search", "default_level"),
        "LIFE_INDEX_LOG_LEVEL": ("logging", "level"),
    }

    for env_var, (section, key) in env_mappings.items():
        value = os.environ.get(env_var)
        if value:
            config.setdefault(section, {})[key] = value

    return config


def _get_user_config() -> Dict[str, Any]:
    """Load user configuration (local to this module)."""
    file_config = _load_yaml_config(CONFIG_FILE)
    env_config = _get_env_config()
    return _deep_merge(file_config, env_config)


# Local config instance for search module
_SEARCH_USER_CONFIG = _get_user_config()


def _reload_search_config() -> None:
    """Reload search config from disk."""
    global _SEARCH_USER_CONFIG
    _SEARCH_USER_CONFIG = _get_user_config()


# =============================================================================
# Search Configuration Accessors
# =============================================================================


def get_search_config() -> dict[str, Any]:
    """Get search configuration."""
    defaults = {
        "default_level": 3,
        "semantic_weight": 1.0,
        "fts_weight": 1.0,
        "default_limit": 10,
    }
    return _deep_merge(defaults, _SEARCH_USER_CONFIG.get("search", {}))


def get_search_weights() -> tuple[float, float]:
    """Return (fts_weight, semantic_weight) from config."""
    cfg = get_search_config()
    return (
        float(cfg.get("fts_weight", 1.0)),
        float(cfg.get("semantic_weight", 1.0)),
    )


def save_search_weights(fts_weight: float, semantic_weight: float) -> None:
    """Persist search weights into user config.yaml."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    existing = _load_yaml_config(CONFIG_FILE)
    search_cfg = existing.get("search", {})
    search_cfg["fts_weight"] = round(float(fts_weight), 2)
    search_cfg["semantic_weight"] = round(float(semantic_weight), 2)
    existing["search"] = search_cfg

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        yaml.safe_dump(existing, f, allow_unicode=True, sort_keys=False)
    _reload_search_config()


def get_search_mode() -> str:
    """Return search mode from config (strict/balanced/loose)."""
    cfg = get_search_config()
    return str(cfg.get("mode", "balanced"))


def save_search_mode(mode: str) -> None:
    """Persist search mode into user config.yaml."""
    valid_modes = ["strict", "balanced", "loose"]
    if mode not in valid_modes:
        mode = "balanced"
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    existing = _load_yaml_config(CONFIG_FILE)
    search_cfg = existing.get("search", {})
    search_cfg["mode"] = mode
    existing["search"] = search_cfg

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        yaml.safe_dump(existing, f, allow_unicode=True, sort_keys=False)
    _reload_search_config()


# =============================================================================
# File Lock Configuration
# =============================================================================

# 锁超时配置（秒）
FILE_LOCK_TIMEOUT_DEFAULT = 30  # 正常操作（写日志等）
FILE_LOCK_TIMEOUT_REBUILD = 120  # 索引重建（批量操作需要更长时间）


# =============================================================================
# Vector Embedding Model Configuration
# =============================================================================

# 固定模型版本以确保嵌入一致性
# 模型文件约 80MB，首次使用会自动下载
EMBEDDING_MODEL = {
    "name": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    "version": "2.0.0",  # 模型版本标识（递增触发自动重建）
    "dimension": 384,  # 输出向量维度（与旧模型一致）
    # SHA-256 哈希值（模型配置文件的预期哈希，用于完整性校验）
    # 首次部署后填入
    "config_hash": "",
    # 模型元数据（用于追溯和日志记录）
    "metadata": {
        "description": "多语言 MiniLM-L12-v2 模型，支持 50+ 语言的语义相似度计算",
        "max_seq_length": 128,  # 该模型推荐最大序列长度
        "recommended_for": "多语言日志检索、中英文语义搜索",
        "supported_languages": "50+ languages including zh, en, ja, ko, fr, de, es, etc.",
    },
}


def get_model_cache_dir() -> Path:
    """
    获取模型缓存目录（跨平台兼容）

    Returns:
        Path: 模型缓存目录路径
    """
    import platform

    system = platform.system()

    # Check if user specified a custom cache dir
    custom_dir = _SEARCH_USER_CONFIG.get("vector_index", {}).get("cache_dir")
    if custom_dir:
        cache_base = Path(custom_dir)
    elif system == "Windows":
        # Windows: %USERPROFILE%\.cache\life-index\models
        cache_base = Path.home() / ".cache" / "life-index" / "models"
    else:
        # macOS/Linux: ~/.cache/life-index/models
        cache_base = Path.home() / ".cache" / "life-index" / "models"

    cache_base.mkdir(parents=True, exist_ok=True)
    return cache_base


# =============================================================================
# Re-exports
# =============================================================================

__all__ = [
    # Search config
    "get_search_config",
    "get_search_weights",
    "save_search_weights",
    "get_search_mode",
    "save_search_mode",
    # File lock
    "FILE_LOCK_TIMEOUT_DEFAULT",
    "FILE_LOCK_TIMEOUT_REBUILD",
    # Vector model
    "EMBEDDING_MODEL",
    "get_model_cache_dir",
]
