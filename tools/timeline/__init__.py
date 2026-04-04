#!/usr/bin/env python3
"""
Life Index - Timeline Command
输出按时间排列的摘要流

Usage:
    life-index timeline --range 2026-01 2026-03
    life-index timeline --range 2026-01 2026-03 --topic work
"""

from .core import run_timeline

__all__ = ["run_timeline"]
