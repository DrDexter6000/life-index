"""
Life Index - Shared Configuration Module
=========================================
Core configuration loading and accessors.

Configuration Loading Priority:
1. Environment variables: LIFE_INDEX_* (highest)
2. User config file: ~/Documents/Life-Index/.life-index/config.yaml (middle)
3. Code defaults (lowest)

Note: Path definitions moved to paths.py, search config moved to search_config.py
This module re-exports them for backward compatibility.
"""

import os
from pathlib import Path
from typing import Dict, Any

import yaml

from .paths import (
    USER_DATA_DIR,
    PROJECT_ROOT,
    JOURNALS_DIR,
    BY_TOPIC_DIR,
    ATTACHMENTS_DIR,
    ABSTRACTS_DIR,
    CONFIG_DIR,
    CONFIG_FILE,
    ensure_dirs,
    JOURNAL_FILENAME_PATTERN,
    DATE_FORMAT,
    DATETIME_FORMAT,
    JOURNAL_TEMPLATE,
    get_journal_dir,
    get_next_sequence,
    get_path_mappings,
    PATH_MAPPINGS,
    normalize_path,
    get_safe_path,
    get_index_prefixes,
    INDEX_PREFIXES,
)

from .search_config import (
    get_search_config,
    get_search_weights,
    save_search_weights,
    get_search_mode,
    save_search_mode,
    FILE_LOCK_TIMEOUT_DEFAULT,
    FILE_LOCK_TIMEOUT_REBUILD,
    EMBEDDING_MODEL,
    get_model_cache_dir,
)


# =============================================================================
# Configuration Loading (Core)
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


def _get_env_config() -> Dict[str, Any]:
    """Load configuration from environment variables."""
    config: Dict[str, Any] = {}

    # Environment variable mappings
    env_mappings = {
        "LIFE_INDEX_DEFAULT_LOCATION": ("defaults", "location"),
        "LIFE_INDEX_WEATHER_API_URL": ("weather", "api_url"),
        "LIFE_INDEX_WEATHER_TIMEOUT": ("weather", "timeout_seconds"),
        "LIFE_INDEX_SEARCH_LEVEL": ("search", "default_level"),
        "LIFE_INDEX_LOG_LEVEL": ("logging", "level"),
        "LIFE_INDEX_LLM_API_KEY": ("llm", "api_key"),
        "LIFE_INDEX_LLM_BASE_URL": ("llm", "base_url"),
        "LIFE_INDEX_LLM_MODEL": ("llm", "model"),
    }

    for env_var, (section, key) in env_mappings.items():
        value = os.environ.get(env_var)
        if value:
            config.setdefault(section, {})[key] = value

    return config


def _deep_merge(base: Dict, override: Dict) -> Dict:
    """Deep merge two dictionaries."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_user_config() -> Dict[str, Any]:
    """
    Load user configuration with priority:
    1. Config file (highest)
    2. Environment variables
    3. Code defaults (handled by callers)
    """
    # Start with file config, then override with environment variables
    file_config = _load_yaml_config(CONFIG_FILE)
    env_config = _get_env_config()

    return _deep_merge(file_config, env_config)


def reload_user_config() -> Dict[str, Any]:
    """Reload user config from disk/environment and refresh module cache."""
    global USER_CONFIG
    USER_CONFIG = load_user_config()
    return USER_CONFIG


# =============================================================================
# Configuration Instance
# =============================================================================

USER_CONFIG = load_user_config()


# =============================================================================
# Default Values
# =============================================================================


def get_default_location() -> str:
    """Get default location from config or use code default."""
    return (
        USER_CONFIG.get("defaults", {}).get("location")
        or os.environ.get("LIFE_INDEX_DEFAULT_LOCATION")
        or "Chongqing, China"
    )


DEFAULT_LOCATION = get_default_location()


# =============================================================================
# Weather API Configuration
# =============================================================================


def get_weather_config() -> Dict[str, Any]:
    """Get weather API configuration."""
    defaults = {
        "api_url": "https://api.open-meteo.com/v1/forecast",
        "archive_url": "https://archive-api.open-meteo.com/v1/archive",
        "timeout_seconds": 15,
        "allow_skip_on_failure": True,
    }
    return _deep_merge(defaults, USER_CONFIG.get("weather", {}))


WEATHER_API_URL = get_weather_config()["api_url"]
WEATHER_ARCHIVE_URL = get_weather_config()["archive_url"]


# =============================================================================
# LLM Configuration
# =============================================================================


def get_llm_config() -> Dict[str, str]:
    """Get LLM configuration with env > config file > defaults priority."""
    llm_config = USER_CONFIG.get("llm", {})
    api_key_env = os.environ.get("LIFE_INDEX_LLM_API_KEY", "").strip()
    base_url_env = os.environ.get("LIFE_INDEX_LLM_BASE_URL", "").strip()
    model_env = os.environ.get("LIFE_INDEX_LLM_MODEL", "").strip()
    return {
        "api_key": api_key_env or str(llm_config.get("api_key") or "").strip(),
        "base_url": str(
            base_url_env or llm_config.get("base_url") or "https://api.openai.com/v1"
        ).strip(),
        "model": str(model_env or llm_config.get("model") or "gpt-4o-mini").strip(),
    }


def save_llm_config(*, api_key: str, base_url: str, model: str) -> None:
    """Persist LLM configuration into user config.yaml."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    existing = _load_yaml_config(CONFIG_FILE)
    existing["llm"] = {
        "api_key": str(api_key).strip(),
        "base_url": str(base_url).strip(),
        "model": str(model).strip(),
    }
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        yaml.safe_dump(existing, f, allow_unicode=True, sort_keys=False)
    reload_user_config()


def save_default_location(location: str) -> None:
    """Persist default location into user config.yaml."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    existing = _load_yaml_config(CONFIG_FILE)
    defaults = existing.get("defaults", {})
    defaults["location"] = str(location).strip()
    existing["defaults"] = defaults
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        yaml.safe_dump(existing, f, allow_unicode=True, sort_keys=False)
    reload_user_config()


# =============================================================================
# Re-exports for backward compatibility
# =============================================================================

__all__ = [
    # Config loading
    "load_user_config",
    "reload_user_config",
    "USER_CONFIG",
    "_load_yaml_config",
    "_deep_merge",
    # Default values
    "get_default_location",
    "DEFAULT_LOCATION",
    # Weather
    "get_weather_config",
    "WEATHER_API_URL",
    "WEATHER_ARCHIVE_URL",
    # LLM
    "get_llm_config",
    "save_llm_config",
    "save_default_location",
    # Paths (re-exported from paths.py)
    "USER_DATA_DIR",
    "PROJECT_ROOT",
    "JOURNALS_DIR",
    "BY_TOPIC_DIR",
    "ATTACHMENTS_DIR",
    "ABSTRACTS_DIR",
    "CONFIG_DIR",
    "CONFIG_FILE",
    "ensure_dirs",
    "JOURNAL_FILENAME_PATTERN",
    "DATE_FORMAT",
    "DATETIME_FORMAT",
    "JOURNAL_TEMPLATE",
    "get_journal_dir",
    "get_next_sequence",
    "get_path_mappings",
    "PATH_MAPPINGS",
    "normalize_path",
    "get_safe_path",
    "get_index_prefixes",
    "INDEX_PREFIXES",
    # Search config (re-exported from search_config.py)
    "get_search_config",
    "get_search_weights",
    "save_search_weights",
    "get_search_mode",
    "save_search_mode",
    "FILE_LOCK_TIMEOUT_DEFAULT",
    "FILE_LOCK_TIMEOUT_REBUILD",
    "EMBEDDING_MODEL",
    "get_model_cache_dir",
]
