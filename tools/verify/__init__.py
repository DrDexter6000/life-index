#!/usr/bin/env python3
"""
Life Index - Verify Command
数据完整性校验一等公民命令

Usage:
    life-index verify
    life-index verify --json

Public API:
    from tools.verify import run_verify
    result = run_verify()
"""

from .core import run_verify

__all__ = ["run_verify"]
