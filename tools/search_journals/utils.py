#!/usr/bin/env python3
"""
Life Index - Search Journals Tool - Utilities
通用工具函数模块
"""

from typing import Any, Dict, Tuple

# SSOT: 使用 lib/frontmatter 进行 frontmatter 解析
import sys
from pathlib import Path

SEARCH_DIR = Path(__file__).parent
if str(SEARCH_DIR) not in sys.path:
    sys.path.insert(0, str(SEARCH_DIR))

from lib.frontmatter import parse_frontmatter as _parse_frontmatter


def parse_frontmatter(content: str) -> Tuple[Dict[str, Any], str]:
    """解析 YAML frontmatter，返回 (metadata, body)
    
    此函数是 lib.frontmatter.parse_frontmatter 的包装，用于保持向后兼容。
    """
    return _parse_frontmatter(content)
"""
Life Index - Search Journals Tool - Utilities
通用工具函数模块
"""

from typing import Any, Dict, Tuple


def parse_frontmatter(content: str) -> Tuple[Dict[str, Any], str]:
    """解析 YAML frontmatter，返回 (metadata, body)"""
    if not content.startswith("---"):
        return {}, content

    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content

    fm_text = parts[1].strip()
    body = parts[2].strip()

    metadata = {}
    for line in fm_text.split("\n"):
        line = line.strip()
        if ":" in line and not line.startswith("#"):
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()

            # 处理列表格式 [item1, item2]
            if value.startswith("[") and value.endswith("]"):
                value = [
                    v.strip().strip("\"'") for v in value[1:-1].split(",") if v.strip()
                ]

            metadata[key] = value

    return metadata, body
