"""
Backward-compat re-export shim for llm_extract.

The canonical module is now tools._optional.llm_extract.
This shim exists so that any code still importing from
tools.lib.llm_extract continues to work during migration.

Do NOT add new imports from this module. Use tools._optional.llm_extract
or tools.lib.topics instead.
"""

import warnings
from typing import Any

from tools.lib.topics import VALID_TOPICS  # noqa: F401


# Lazy re-exports for backward compatibility
def __getattr__(name: str) -> Any:
    if name in ("extract_metadata_sync", "is_llm_available", "EXTRACTION_SYSTEM_PROMPT"):
        warnings.warn(
            "tools.lib.llm_extract is deprecated; use tools._optional.llm_extract instead",
            DeprecationWarning,
            stacklevel=2,
        )
        from tools._optional import llm_extract

        return getattr(llm_extract, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [  # noqa: F822
    "extract_metadata_sync",
    "is_llm_available",
    "VALID_TOPICS",
    "EXTRACTION_SYSTEM_PROMPT",
]
