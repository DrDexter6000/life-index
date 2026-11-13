"""FTS index freshness for the L3 retrieval fallback.

The L3 fallback (full-corpus content scan when FTS recall looks low) may only
be skipped when the FTS index is known to cover every live fragment. That is
decided by the same per-fragment ``(mtime, size)`` signature check the search
preflight and ``life-index index`` use: every live fragment needs an FTS row
and a matching recorded signature, and no row/signature may describe a file
that is gone.

The previous rule compared the newest journal mtime against
``index_meta.last_updated``. It could report "fresh" for an outside change
that kept the timestamp tick, for a missing row whose file was older than the
last scan, or for a deleted file; it also treated a missing ``last_updated``
as stale, which the write-through used to change on every write. Both are
gone; ``fts_update.inspect_fts_index`` is the single signature rule.
"""

from __future__ import annotations


def index_is_current() -> bool:
    """Whether the FTS index covers every live fragment (read-only check)."""
    from .fts_update import fts_index_is_current

    return fts_index_is_current()
