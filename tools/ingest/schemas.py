"""Schema constants and envelope helpers for the import provider (PRD §5).

Every import command returns a stable JSON envelope with ``schema_version``,
``success``, ``command``, ``data``, and ``error``.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Schema version constants
# ---------------------------------------------------------------------------

ENVELOPE_SCHEMA_VERSION = "import_job.v1"
PLAN_SCHEMA_VERSION = "import_plan.v1"
RUN_SCHEMA_VERSION = "import_run.v1"
STATUS_SCHEMA_VERSION = "import_status.v1"
LEDGER_SCHEMA_VERSION = "import_job_ledger.v1"
ROLLBACK_MANIFEST_SCHEMA_VERSION = "import_rollback_manifest.v1"
ROLLBACK_SCHEMA_VERSION = "import_rollback.v1"

# ---------------------------------------------------------------------------
# Tranche A fixed defaults (PRD §7)
# ---------------------------------------------------------------------------

# sha256("") in hex
_RAW_EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
DEFAULT_NORMALIZED_IMPORT_OPTIONS_HASH = f"sha256:{_RAW_EMPTY_SHA256}"

# sha256("tranche-a:create-only:fail-closed:no-auto-index")
import hashlib as _hl

_DEFAULT_POLICY_INPUT = "tranche-a:create-only:fail-closed:no-auto-index"
DEFAULT_NORMALIZED_WRITE_POLICY_HASH = (
    f"sha256:{_hl.sha256(_DEFAULT_POLICY_INPUT.encode('utf-8')).hexdigest()}"
)

# ---------------------------------------------------------------------------
# Envelope helpers
# ---------------------------------------------------------------------------


def success_envelope(command: str, data: dict[str, Any]) -> dict[str, Any]:
    """Build a success envelope (PRD §5)."""
    return {
        "schema_version": ENVELOPE_SCHEMA_VERSION,
        "success": True,
        "command": command,
        "data": data,
        "error": None,
    }


def error_envelope(
    command: str,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    retryable: bool = False,
) -> dict[str, Any]:
    """Build an error envelope (PRD §5, §11)."""
    return {
        "schema_version": ENVELOPE_SCHEMA_VERSION,
        "success": False,
        "command": command,
        "data": None,
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
            "retryable": retryable,
        },
    }
