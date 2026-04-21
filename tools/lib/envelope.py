"""
Life Index - Unified Success Envelope
======================================

Provides the canonical success envelope for all Life Index tool outputs.

ADR-018 defines the standard success envelope schema:

    {
        "ok": true,
        "data": { ... },          # tool-specific payload
        "_trace": { ... },        # observability (trace_id, timing, steps)
        "events": [ ... ],        # piggyback event notifications
    }

The error envelope is unchanged — see ``tools/lib/errors.py`` for
``LifeIndexError.to_json()`` which produces ``{success: false, error: {...}}``.

Usage::

    from tools.lib.envelope import success

    return success(
        {"total_entries": 42, "by_type": {...}},
        trace={"trace_id": "a1b2c3d4", "total_ms": 12.3},
        events=[{"type": "index_stale", "severity": "low"}],
    )

When ``_trace`` or ``events`` are omitted they default to ``{}`` and ``[]``
respectively — never ``None``.
"""

from __future__ import annotations

from typing import Any


def success(
    data: dict[str, Any],
    *,
    trace: dict[str, Any] | None = None,
    events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Wrap tool output in the unified success envelope.

    Args:
        data: Tool-specific result payload.  Must be a dict; callers
            should nest scalars or lists inside a dict key.
        trace: Optional observability dict.  Common keys:
            ``trace_id``, ``command``, ``total_ms``, ``steps``.
            Defaults to empty dict when omitted.
        events: Optional list of piggyback event notifications.
            Each event is a dict with at least ``type`` and ``severity``.
            Defaults to empty list when omitted.

    Returns:
        Envelope dict with keys ``ok``, ``data``, ``_trace``, ``events``.
    """
    return {
        "ok": True,
        "data": data,
        "_trace": trace if trace is not None else {},
        "events": events if events is not None else [],
    }
