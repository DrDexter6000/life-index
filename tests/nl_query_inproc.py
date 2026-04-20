"""In-process query harness for fast regression testing.

Loads bge-m3 model once (lazy, on first query), then provides
fast repeated search calls via direct Python import — no subprocess
overhead, no repeated model cold-start.

Usage:
    from tests.nl_query_inproc import harness
    result = harness.search("重构搜索模块", level=3, explain=True)

The harness wraps `tools.search_journals.core.hierarchical_search`
with module-level reload isolation and model persistence.
"""

from __future__ import annotations

import importlib
import os
import sys
from typing import Any


class InprocHarness:
    """In-process search harness with persistent model loading.

    The bge-m3 model is loaded on first search() call and reused
    for all subsequent calls. This avoids the ~23s cold-start
    penalty per subprocess invocation.
    """

    def __init__(self) -> None:
        self._search_fn: Any = None
        self._loaded = False

    def _ensure_loaded(self) -> None:
        """Lazily import and cache the search function."""
        if self._loaded:
            return

        from tools.search_journals.core import hierarchical_search

        self._search_fn = hierarchical_search
        self._loaded = True

    def search(
        self,
        query: str,
        *,
        level: int = 3,
        explain: bool = False,
        use_index: bool = True,
        semantic: bool = True,
        **kwargs: Any,
    ) -> dict:
        """Execute a search query in-process.

        Args:
            query: Search query string
            level: Search depth (1=index, 2=metadata, 3=full)
            explain: Include score explanations
            use_index: Use FTS index
            semantic: Enable semantic search
            **kwargs: Additional args passed to hierarchical_search

        Returns:
            Search result dict matching CLI JSON structure.
        """
        self._ensure_loaded()
        return self._search_fn(
            query=query,
            level=level,
            explain=explain,
            use_index=use_index,
            semantic=semantic,
            **kwargs,
        )


# Module-level singleton — model loads once, persists for test session
harness = InprocHarness()
