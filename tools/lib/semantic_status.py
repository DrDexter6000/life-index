"""Semantic index status helpers for non-blocking onboarding flows."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from .paths import get_user_data_dir

STATUS_FILENAME = "semantic_index_status.json"
LOG_FILENAME = "semantic_index_build.log"
VALID_STATUSES = {"building", "ready", "disabled", "failed"}


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def get_semantic_status_path(index_dir: Path | None = None) -> Path:
    if index_dir is None:
        index_dir = get_user_data_dir() / ".index"
    return index_dir / STATUS_FILENAME


def write_semantic_status(
    status: str,
    *,
    index_dir: Path | None = None,
    error: str | None = None,
    pid: int | None = None,
    log_path: str | None = None,
) -> dict[str, Any]:
    """Atomically persist semantic index status."""
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid semantic status: {status}")

    if index_dir is None:
        index_dir = get_user_data_dir() / ".index"
    index_dir.mkdir(parents=True, exist_ok=True)

    payload: dict[str, Any] = {
        "schema_version": "semantic_status.v1",
        "status": status,
        "updated_at": _utc_now(),
    }
    if pid is not None:
        payload["pid"] = pid
    if log_path:
        payload["log_path"] = log_path
    if error:
        payload["error"] = error

    status_file = get_semantic_status_path(index_dir)
    fd, tmp_path = tempfile.mkstemp(dir=str(index_dir), prefix=f"{STATUS_FILENAME}.tmp")
    try:
        with open(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        Path(tmp_path).replace(status_file)
    except Exception:
        Path(tmp_path).unlink(missing_ok=True)
        raise
    return payload


def read_semantic_status(index_dir: Path | None = None) -> dict[str, Any] | None:
    status_file = get_semantic_status_path(index_dir)
    if not status_file.exists():
        return None
    try:
        parsed = json.loads(status_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError, TypeError):
        return {"status": "failed", "error": "semantic status file is unreadable"}
    if not isinstance(parsed, dict):
        return {"status": "failed", "error": "semantic status file is not an object"}
    data = cast(dict[str, Any], parsed)
    status = data.get("status")
    if status not in VALID_STATUSES:
        return {"status": "failed", "error": f"invalid semantic status: {status}"}
    return data


def get_semantic_index_status(index_dir: Path | None = None) -> dict[str, Any]:
    """Return honest semantic index state without importing model code."""
    if index_dir is None:
        index_dir = get_user_data_dir() / ".index"

    explicit = read_semantic_status(index_dir)
    if explicit is not None:
        return explicit

    vec_pkl = index_dir / "vectors_simple.pkl"
    matrix = index_dir / "vectors_simple_emb.npz"
    if vec_pkl.exists() or matrix.exists():
        return {"status": "ready", "derived": True}
    return {"status": "disabled", "derived": True}


def start_background_semantic_build(*, incremental: bool) -> dict[str, Any]:
    """Start a detached vector-index build and return immediately."""
    index_dir = get_user_data_dir() / ".index"
    index_dir.mkdir(parents=True, exist_ok=True)
    log_path = index_dir / LOG_FILENAME

    if os.environ.get("LIFE_INDEX_INDEX_FTS_ONLY") == "1":
        return write_semantic_status(
            "disabled",
            index_dir=index_dir,
            log_path=str(log_path),
        )

    write_semantic_status("building", index_dir=index_dir, log_path=str(log_path))

    cmd = [sys.executable, "-m", "tools", "index", "--vec-only", "--json"]
    if not incremental:
        cmd.append("--rebuild")

    env = os.environ.copy()
    env["LIFE_INDEX_SEMANTIC_BACKGROUND"] = "1"
    env.pop("LIFE_INDEX_INDEX_FTS_ONLY", None)

    try:
        log_handle = log_path.open("a", encoding="utf-8")
        log_handle.write(f"\n[{_utc_now()}] starting semantic build: {' '.join(cmd)}\n")
        log_handle.flush()
        kwargs: dict[str, Any] = {
            "stdin": subprocess.DEVNULL,
            "stdout": log_handle,
            "stderr": subprocess.STDOUT,
            "env": env,
        }
        if os.name == "nt":
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(
                subprocess, "DETACHED_PROCESS", 0
            )
        else:
            kwargs["start_new_session"] = True

        proc = subprocess.Popen(cmd, **kwargs)
        log_handle.close()
    except Exception as exc:
        return write_semantic_status(
            "failed",
            index_dir=index_dir,
            error=str(exc),
            log_path=str(log_path),
        )

    return write_semantic_status(
        "building",
        index_dir=index_dir,
        pid=proc.pid,
        log_path=str(log_path),
    )
