"""v1.1.1 observability provenance helper.

Provides a reusable way to attach ``schema_version`` and ``provenance``
fields to an existing JSON-style mapping **without** mutating the caller's
input.  Designed for A1 of the v1.1.1 observability contract milestone.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

SCHEMA_VERSION = "v1.1.1"

VALID_GENERATORS = frozenset(["search", "index", "eval", "entity", "maintenance", "trajectory"])


def _stable_hash(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _get_tool_version() -> str:
    try:
        from tools.__main__ import get_package_version

        return get_package_version()
    except Exception:
        return "dev"


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_provenance_envelope(
    source_data: Dict[str, Any],
    generator: str,
    params: Dict[str, Any],
    generated_at: Optional[str] = None,
    fixture_version: Optional[str] = None,
) -> Dict[str, Any]:
    if generator not in VALID_GENERATORS:
        raise ValueError(
            f"invalid generator '{generator}'; " f"expected one of {sorted(VALID_GENERATORS)}"
        )

    provenance: Dict[str, Any] = {
        "source_hash": _stable_hash(source_data),
        "tool_version": _get_tool_version(),
        "generated_at": generated_at if generated_at is not None else _now_utc_iso(),
        "generator": generator,
        "params_hash": _stable_hash(params),
        "fixture_version": fixture_version,
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "provenance": provenance,
    }
