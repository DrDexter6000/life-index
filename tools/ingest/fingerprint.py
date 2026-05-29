"""Deterministic fingerprint helpers for the import provider (PRD §7).

All fingerprints use the ``sha256:<hex>`` format.  Inputs are concatenated
with null-byte separators (``\\0``) as specified in the PRD.  Sorted arrays
are joined with commas before inclusion.
"""

from __future__ import annotations

import hashlib


def _sha256_hex(data: str) -> str:
    """Return raw hex SHA-256 of a UTF-8 string."""
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def sha256_hash(data: str) -> str:
    """Return ``sha256:<hex>`` prefixed digest."""
    return f"sha256:{_sha256_hex(data)}"


# ---------------------------------------------------------------------------
# PRD §7: source record fingerprint
# ---------------------------------------------------------------------------


def compute_source_record_fingerprint(
    adapter_id: str,
    adapter_version: str,
    normalized_identity: str,
    content_hash: str,
    metadata_hash: str,
) -> str:
    """Compute source_record_fingerprint from canonical source facts."""
    raw = (
        "life-index.source-record.v1\0"
        + adapter_id
        + "\0"
        + adapter_version
        + "\0"
        + normalized_identity
        + "\0"
        + content_hash
        + "\0"
        + metadata_hash
    )
    return sha256_hash(raw)


# ---------------------------------------------------------------------------
# PRD §7: attachment fingerprint
# ---------------------------------------------------------------------------


def compute_attachment_fingerprint(
    attachment_id: str,
    source_sha256: str,
    target_rel_path: str,
    media_type: str,
    size_bytes: int,
    copy_mode: str,
) -> str:
    """Compute per-attachment fingerprint."""
    raw = (
        "life-index.import-attachment.v1\0"
        + attachment_id
        + "\0"
        + source_sha256
        + "\0"
        + target_rel_path
        + "\0"
        + media_type
        + "\0"
        + str(size_bytes)
        + "\0"
        + copy_mode
    )
    return sha256_hash(raw)


# ---------------------------------------------------------------------------
# PRD §7: proposal fingerprint
# ---------------------------------------------------------------------------


def compute_proposal_fingerprint(
    source_record_fingerprint: str,
    target_rel_path: str,
    title: str,
    date: str,
    topic: str,
    tags: list[str],
    content: str,
    attachment_fingerprints: list[str],
) -> str:
    """Compute per-proposal fingerprint."""
    raw = (
        "life-index.import-proposal.v1\0"
        + source_record_fingerprint
        + "\0"
        + target_rel_path
        + "\0"
        + title
        + "\0"
        + date
        + "\0"
        + topic
        + "\0"
        + ",".join(sorted(tags))
        + "\0"
        + sha256_hash(content)
        + "\0"
        + ",".join(sorted(attachment_fingerprints))
    )
    return sha256_hash(raw)


# ---------------------------------------------------------------------------
# PRD §7: source fingerprint (plan-level)
# ---------------------------------------------------------------------------


def compute_source_fingerprint(
    adapter_id: str,
    adapter_version: str,
    normalized_import_options_hash: str,
    source_record_fingerprints: list[str],
) -> str:
    """Compute plan-level source fingerprint."""
    raw = (
        "life-index.source.v1\0"
        + adapter_id
        + "\0"
        + adapter_version
        + "\0"
        + normalized_import_options_hash
        + "\0"
        + ",".join(sorted(source_record_fingerprints))
    )
    return sha256_hash(raw)


# ---------------------------------------------------------------------------
# PRD §7: plan fingerprint
# ---------------------------------------------------------------------------


def compute_plan_fingerprint(
    schema_version: str,
    source_fingerprint: str,
    proposal_fingerprints: list[str],
    normalized_write_policy_hash: str,
) -> str:
    """Compute plan fingerprint."""
    raw = (
        "life-index.import-plan.v1\0"
        + schema_version
        + "\0"
        + source_fingerprint
        + "\0"
        + ",".join(sorted(proposal_fingerprints))
        + "\0"
        + normalized_write_policy_hash
    )
    return sha256_hash(raw)


# ---------------------------------------------------------------------------
# PRD §7: idempotency key
# ---------------------------------------------------------------------------


def compute_idempotency_key(
    source_fingerprint: str,
    plan_fingerprint: str,
    normalized_target_root_identity: str,
) -> str:
    """Compute idempotency key from source, plan, and target identity."""
    raw = (
        "life-index.import-idempotency.v1\0"
        + source_fingerprint
        + "\0"
        + plan_fingerprint
        + "\0"
        + normalized_target_root_identity
    )
    return sha256_hash(raw)
