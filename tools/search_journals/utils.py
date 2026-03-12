#!/usr/bin/env python3
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
