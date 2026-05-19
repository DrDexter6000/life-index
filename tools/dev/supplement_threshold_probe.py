#!/usr/bin/env python3
"""M09 Supplement Threshold Probe — developer-only diagnostic harness.

Summarizes how the M08 ``_should_supplement`` threshold would classify
keyword-result records across one or more threshold values, **without**
changing public/default search behavior.

This module is deliberately private to ``tools.dev`` and must not be wired
into ``life-index search``, eval baselines, or any public CLI flag.

Usage::

    python -m tools.dev.supplement_threshold_probe \\
        --input records.json \\
        --thresholds 70,76,85 \\
        --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, cast

from tools.search_journals.supplement_policy import _max_fts_score, _should_supplement

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SUPPORTED_OUTCOMES = {"fixed", "regressed", "unchanged", "unknown"}
_PRIVACY_REDACTED_FIELDS = [
    "query",
    "title",
    "content",
    "path",
    "keyword_results",
    "fts_score",
    "relevance",
    "relevance_score",
    "explain",
]


# ---------------------------------------------------------------------------
# Pure function
# ---------------------------------------------------------------------------


def summarize_thresholds(
    records: list[dict[str, Any]],
    *,
    thresholds: list[float],
) -> dict[str, Any]:
    """Classify *records* at each threshold and return aggregate counts.

    Parameters
    ----------
    records:
        List of dicts with shape ``{"id": ..., "keyword_results": [...],
        "semantic_outcome": "fixed"|"regressed"|"unchanged"|"unknown"}``.
    thresholds:
        Positive float values to probe. Must be non-empty and > 0.

    Returns
    -------
    dict with ``"thresholds"`` (keyed by str threshold) and
    ``"total_records"``.  Each bucket contains counts of
    ``would_supplement``, ``would_skip``, ``fixed_candidates``,
    ``regression_risk_candidates``, and ``unknown_score_records``.
    """
    if not thresholds:
        raise ValueError("thresholds must be a non-empty list of positive floats")
    for t in thresholds:
        if t <= 0:
            raise ValueError(f"threshold must be positive, got {t}")

    result: dict[str, Any] = {"thresholds": {}, "total_records": len(records)}

    for threshold in thresholds:
        t_key = str(float(threshold))
        bucket: dict[str, int] = {
            "would_supplement": 0,
            "would_skip": 0,
            "fixed_candidates": 0,
            "regression_risk_candidates": 0,
            "unknown_score_records": 0,
        }

        for record in records:
            kw_results = record.get("keyword_results", [])
            outcome = record.get("semantic_outcome")

            max_fts_score = _max_fts_score(kw_results)
            # Determine if score is unknown (missing or empty keyword_results)
            has_score = (
                bool(kw_results)
                and any(
                    any(k in r for k in ("fts_score", "relevance", "relevance_score"))
                    or (isinstance(r.get("explain"), dict) and "keyword_pipeline" in r["explain"])
                    for r in kw_results
                )
                or max_fts_score > 0.0
            )
            if not has_score:
                bucket["unknown_score_records"] += 1

            # Use M08 helpers for the classification decision
            if _should_supplement(kw_results, max_fts_threshold=threshold):
                bucket["would_supplement"] += 1
                if outcome == "fixed":
                    bucket["fixed_candidates"] += 1
                elif outcome == "regressed":
                    bucket["regression_risk_candidates"] += 1
            else:
                bucket["would_skip"] += 1
                # Even skipped records can be candidates if outcome matches
                if outcome == "fixed":
                    pass  # fixed but strong keyword — not a supplement candidate
                elif outcome == "regressed":
                    pass  # regressed but strong keyword — not a supplement candidate

        result["thresholds"][t_key] = bucket

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="M09 supplement threshold probe (developer-only)",
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to a JSON file or inline JSON string with a 'records' array",
    )
    parser.add_argument(
        "--thresholds",
        required=True,
        help="Comma-separated positive float thresholds, e.g. 70,76,85",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Emit JSON output (default: human-readable, but also JSON)",
    )
    return parser.parse_args(argv)


def _load_records(input_str: str) -> list[dict[str, Any]]:
    """Load records from a file path or inline JSON string."""
    p = Path(input_str)
    if p.is_file():
        raw = p.read_text(encoding="utf-8")
    else:
        raw = input_str

    data = cast(dict[str, Any], json.loads(raw))
    return cast(list[dict[str, Any]], data.get("records", []))


def _parse_thresholds(thresholds_str: str) -> list[float]:
    """Parse comma-separated threshold string into a sorted list of positive floats."""
    parts = thresholds_str.split(",")
    result = []
    for part in parts:
        part = part.strip()
        try:
            val = float(part)
        except (ValueError, TypeError):
            raise ValueError(f"Invalid threshold value: {part!r}") from None
        if val <= 0:
            raise ValueError(f"Threshold must be positive, got {val}")
        result.append(val)
    if not result:
        raise ValueError("thresholds must be non-empty")
    return result


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)

    try:
        records = _load_records(args.input)
        thresholds = _parse_thresholds(args.thresholds)
    except (json.JSONDecodeError, FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    summary = summarize_thresholds(records, thresholds=thresholds)

    # Attach privacy metadata
    summary["privacy"] = {
        "redacted_fields": _PRIVACY_REDACTED_FIELDS,
        "policy": (
            "aggregate counts only; no raw query text, titles, content, paths, "
            "or keyword result objects"
        ),
    }

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
