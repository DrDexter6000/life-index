#!/usr/bin/env python3
"""
Life Index - Write Journal Tool - Utilities
通用工具函数模块
"""

import os
import platform
import re
from datetime import datetime
from typing import Tuple

from ..lib.config import PATH_MAPPINGS
from ..lib.paths import get_journals_dir


def get_year_month(date_str: str) -> Tuple[int, int]:
    """从日期字符串提取年和月"""
    dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    return dt.year, dt.month


def convert_path_for_platform(source_path: str) -> str:
    """
    跨平台路径转换（双向）- 启发式 + 配置映射

    优先使用启发式自动检测常见跨平台场景（如 WSL），
    然后回退到用户配置的 PATH_MAPPINGS。

    支持场景：
    - Windows ↔ WSL: C:\\Users\\xxx ↔ /mnt/c/Users/xxx
    - 用户自定义映射（通过 config.yaml）

    Args:
        source_path: 原始路径

    Returns:
        转换后的路径（如果匹配），否则返回原路径
    """
    if not source_path:
        return source_path

    current_system = platform.system()  # 'Windows', 'Linux', 'Darwin' (macOS)

    # ========== 启发式 1: Windows 路径在 Linux/WSL 环境 ==========
    # 检测: Linux + 路径以盘符开头 (如 C:\... 或 C:/...)
    if current_system == "Linux":
        win_match = re.match(r"^([A-Za-z]):[/\\](.*)$", source_path)
        if win_match:
            drive, rest = win_match.groups()
            # 转换: C:\Users\... → /mnt/c/Users/...
            normalized_rest = rest.replace("\\", "/")
            wsl_path = f"/mnt/{drive.lower()}/{normalized_rest}"

            # 保守策略: 只有转换后的路径确实存在时才使用
            if os.path.exists(wsl_path):
                return wsl_path

    # ========== 启发式 2: WSL 路径在 Windows 环境 ==========
    # 检测: Windows + 路径以 /mnt/x/ 开头
    if current_system == "Windows":
        wsl_match = re.match(r"^/mnt/([a-z])/(.*)$", source_path)
        if wsl_match:
            drive, rest = wsl_match.groups()
            # 转换: /mnt/c/Users/... → C:\Users\...
            normalized_rest = rest.replace("/", "\\")
            win_path = f"{drive.upper()}:\\{normalized_rest}"

            # 保守策略: 只有转换后的路径确实存在时才使用
            if os.path.exists(win_path):
                return win_path

    # ========== 回退: 用户配置的 PATH_MAPPINGS ==========
    if PATH_MAPPINGS:
        normalized_source = source_path.replace("\\", "/")

        for from_prefix, to_prefix in PATH_MAPPINGS.items():
            normalized_from = from_prefix.replace("\\", "/")
            normalized_to = to_prefix.replace("\\", "/")

            if normalized_source.lower().startswith(normalized_from.lower()):
                converted = normalized_to + normalized_source[len(normalized_from) :]
                if current_system == "Windows":
                    converted = converted.replace("/", "\\")
                return converted

    # 无匹配，返回原路径
    return source_path


def generate_filename(date_str: str, sequence: int = 1) -> str:
    """生成日志文件名: life-index_YYYY-MM-DD_XXX.md"""
    date_part = date_str[:10]  # YYYY-MM-DD
    return f"life-index_{date_part}_{sequence:03d}.md"


def get_next_sequence(date_str: str) -> int:
    """获取指定日期的下一个序列号"""
    year, month = get_year_month(date_str)
    month_dir = get_journals_dir() / str(year) / f"{month:02d}"

    if not month_dir.exists():
        return 1

    date_part = date_str[:10]
    pattern = f"life-index_{date_part}_*.md"
    existing = list(month_dir.glob(pattern))

    if not existing:
        return 1

    # 提取最大序列号
    max_seq = 0
    for f in existing:
        match = re.search(rf"life-index_{date_part}_(\d+)\.md$", f.name)
        if match:
            max_seq = max(max_seq, int(match.group(1)))

    return max_seq + 1
