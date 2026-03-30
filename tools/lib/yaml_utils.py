#!/usr/bin/env python3
"""
Life Index - YAML Configuration Utilities
YAML 配置文件加载与深度合并工具

从 paths.py 和 config.py 提取的公共函数，消除重复代码。
"""

import logging
from pathlib import Path
from typing import Any, Dict

import yaml

logger = logging.getLogger(__name__)


def load_yaml_config(config_path: Path) -> Dict[str, Any]:
    """
    Load configuration from YAML file.

    Args:
        config_path: Path to YAML configuration file

    Returns:
        Dictionary with configuration, or empty dict if file doesn't exist
        or cannot be parsed.
    """
    if not config_path.exists():
        return {}

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except (IOError, OSError, yaml.YAMLError) as e:
        logger.warning("Failed to load YAML config %s: %s", config_path, e)
        return {}


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deep merge two dictionaries.

    Override values take precedence over base values.
    Nested dictionaries are merged recursively.

    Args:
        base: Base dictionary
        override: Override dictionary (higher priority)

    Returns:
        New merged dictionary (does not modify inputs)
    """
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


__all__ = ["load_yaml_config", "deep_merge"]
