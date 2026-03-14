#!/usr/bin/env python3
"""
Life Index - Search Journals Tool
分层级检索日志（L1索引→L2元数据→L3内容）

Usage:
    python -m tools.search_journals --query "关键词"
    python -m tools.search_journals --topic work --project LobsterAI
    python -m tools.search_journals --date-from 2026-01-01 --date-to 2026-03-04

Public API:
    from tools.search_journals import hierarchical_search
    result = hierarchical_search(query="深度学习", level=3)
"""

# Public API exports
from .core import hierarchical_search

__all__ = ["hierarchical_search"]
