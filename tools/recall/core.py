#!/usr/bin/env python3
"""
Life Index - Recall Module Core Logic

L3 module that consumes L2 search/smart-search through subprocess delegation.
Provides three search modes: default (pure FTS), recall (hybrid), deep (deterministic recall).

Mirrors the on_this_day subprocess pattern — never imports L2 internals directly.
"""

import json
import os
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional

SCHEMA_VERSION = "gbrain.recall.v1"


def _error_result(
    code: str,
    message: str,
    details: Optional[Dict[str, Any]] = None,
    recovery_strategy: str = "ask_user",
) -> Dict[str, Any]:
    """Build a structured error result."""
    err: Dict[str, Any] = {
        "code": code,
        "message": message,
        "details": details if details is not None else {},
        "recovery_strategy": recovery_strategy,
    }
    return {
        "success": False,
        "schema_version": SCHEMA_VERSION,
        "mode": None,
        "effective_mode": None,
        "query": None,
        "results": [],
        "source_command": None,
        "error": err,
    }


def _call_search(
    query: str,
    no_semantic: bool = False,
    env: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Invoke L2 search CLI via subprocess and return parsed JSON."""
    cmd = [sys.executable, "-m", "tools", "search", "--query", query]
    if no_semantic:
        cmd.append("--no-semantic")

    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )

    try:
        payload = json.loads(proc.stdout)
    except (json.JSONDecodeError, TypeError) as exc:
        return {
            "success": False,
            "error": f"search output not valid JSON: {exc}",
        }
    if not isinstance(payload, dict):
        return {
            "success": False,
            "error": "search output JSON was not an object",
        }
    return payload


def _extract_results(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract result list from L2 search output.

    L2 search returns 'merged_results'; smart-search returns 'filtered_results'.
    """
    if "merged_results" in payload:
        return list(payload["merged_results"])
    if "filtered_results" in payload:
        return list(payload["filtered_results"])
    return []


def run_recall(
    mode: str,
    query: str,
    use_llm: bool = False,
) -> Dict[str, Any]:
    """
    Execute recall search across three modes.

    Args:
        mode: Search mode — 'default', 'recall', or 'deep'.
        query: Search query string.
        use_llm: Legacy compatibility parameter; ignored. Tools are deterministic.

    Returns:
        Structured JSON result with schema_version, mode, effective_mode,
        results, source_command, and error fields.
    """
    t0 = time.monotonic()

    # Validate mode
    valid_modes = {"default", "recall", "deep"}
    if mode not in valid_modes:
        return _error_result(
            "E2501",
            f"Invalid mode: '{mode}'. Must be one of: {', '.join(sorted(valid_modes))}.",
        )

    # Validate query
    if not query or not query.strip():
        return _error_result(
            "E2502",
            "Query must not be empty.",
            recovery_strategy="ask_user",
        )

    # Preserve LIFE_INDEX_DATA_DIR for subprocess
    env = None
    data_dir = os.environ.get("LIFE_INDEX_DATA_DIR")
    if data_dir:
        env = os.environ.copy()

    effective_mode = mode
    source_command = ""
    stderr_warning = ""
    l2_payload: Dict[str, Any] = {}

    if mode == "default":
        # Pure FTS — no semantic search
        l2_payload = _call_search(query, no_semantic=True, env=env)
        source_command = "search --no-semantic"
        # Legacy use_llm is ignored in default mode.

    elif mode == "recall":
        # Default hybrid search (FTS + semantic fallback)
        l2_payload = _call_search(query, no_semantic=False, env=env)
        source_command = "search"
        # Legacy use_llm is ignored in recall mode.

    elif mode == "deep":
        # Deep mode no longer invokes in-tool LLM orchestration. Keep the mode
        # accepted for compatibility, but execute the deterministic recall path.
        l2_payload = _call_search(query, no_semantic=False, env=env)
        source_command = "search"
        effective_mode = "recall"
        stderr_warning = "recall: deep mode uses deterministic recall; in-tool LLM is retired."

    # Check L2 payload success
    if not l2_payload.get("success", False):
        err_msg = l2_payload.get("error", "unknown L2 error")
        if isinstance(err_msg, dict):
            err_msg = err_msg.get("message", str(err_msg))
        return _error_result(
            "E2503",
            f"L2 {source_command} failed: {err_msg}",
            {"source_command": source_command},
            recovery_strategy="retry",
        )

    # Extract results from L2 payload
    results = _extract_results(l2_payload)

    elapsed_ms = int((time.monotonic() - t0) * 1000)

    result: Dict[str, Any] = {
        "success": True,
        "schema_version": SCHEMA_VERSION,
        "mode": mode,
        "effective_mode": effective_mode,
        "query": query,
        "results": results,
        "source_command": source_command,
        "performance": {
            "total_time_ms": elapsed_ms,
        },
        "error": None,
    }

    # Emit stderr warning if degradation occurred
    if stderr_warning:
        print(stderr_warning, file=sys.stderr)

    return result
