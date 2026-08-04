"""Unit tests for the bounded Windows transient os.replace retry.

These are focused, deterministic fault-injection tests for the narrow retry
added to ``runner._atomic_write_json`` around its ``os.replace`` step. They
never depend on a real file lock: a fake ``os.replace`` raises crafted
``OSError`` values (carrying an explicit ``.winerror``) exactly when the test
wants, and the real ``os.replace`` handles every other call.

The production classifier's ``os.name`` + ``winerror`` semantics are proven by
the direct tests below (which may set ``os.name`` because they do no filesystem
I/O). Every behavioral test that actually drives ``_atomic_write_json`` patches
the classifier instead of mutating the global ``os.name``, so it runs
deterministically on Linux required CI as well as on Windows.

Contract under test (production semantics):

- Only an ``os.replace`` ``OSError`` raised under ``os.name == "nt"`` AND
  carrying ``winerror`` in ``{5, 32}`` is retryable (transient share/access
  locks that race a same-directory atomic replace).
- At most 3 ``os.replace`` attempts; backoff sleeps are exactly ``[0.01, 0.05]``
  (two sleeps, between the three attempts — never after the final attempt).
- On success the existing directory fsync still runs and the result JSON is
  complete with no temp leftover.
- On exhaustion the last ``OSError`` is re-raised as-is and the temp file is
  cleaned up (fail closed, no half-product).
- Non-qualifying errors (``winerror`` not in ``{5, 32}``, no ``winerror``, or
  any failure off-Windows — even ``winerror`` 32) are raised after a single
  attempt with no backoff.
- Errors from mkdir / mkstemp / JSON write / file fsync / directory fsync /
  containment / path validation never enter this retry (they are outside the
  ``os.replace`` call this retry wraps).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

import tools.ingest.runner as runner
from tools.ingest.runner import _atomic_write_json

# ---------------------------------------------------------------------------
# Fault-injection primitives
# ---------------------------------------------------------------------------


def _winerror_oserror(winerror: int, msg: str = "synthetic Windows replace error") -> OSError:
    """An OSError carrying an explicit winerror, portable across platforms.

    The classifier only inspects ``.winerror`` (and ``os.name``), so building
    the error by attribute assignment is exact and avoids any dependency on the
    host OSError constructor shape.
    """
    exc = OSError(msg)
    exc.winerror = winerror
    return exc


class _ReplaceSpy:
    """Wraps the real os.replace; raises a crafted OSError on the first N calls."""

    def __init__(self, *, fail_times: int, winerror: int) -> None:
        self.real = os.replace
        self.fail_times = fail_times
        self.winerror = winerror
        self.calls: list[tuple[Any, Any]] = []

    def __call__(self, src: Any, dst: Any) -> Any:
        self.calls.append((src, dst))
        if len(self.calls) <= self.fail_times:
            raise _winerror_oserror(self.winerror)
        return self.real(src, dst)


class _AlwaysFailReplace:
    """Always raises a crafted OSError (never delegates); records each one."""

    def __init__(self, *, winerror: int) -> None:
        self.winerror = winerror
        self.calls: list[tuple[Any, Any]] = []
        self.raised: list[OSError] = []

    def __call__(self, src: Any, dst: Any) -> None:
        self.calls.append((src, dst))
        exc = _winerror_oserror(self.winerror)
        self.raised.append(exc)
        raise exc


def _temp_leftovers(directory: Path, target_name: str) -> list[str]:
    """Hidden temp names ``.{target}.tmp-*`` produced by _atomic_write_json."""
    prefix = f".{target_name}.tmp-"
    return sorted(p.name for p in directory.iterdir() if p.name.startswith(prefix))


def _transient_when_winerror_5_32(exc: BaseException) -> bool:
    """Behavioral stand-in for the production classifier.

    Confirms exactly the winerror 5/32 OSError as the Windows-transient decision
    the production helper would make under ``os.name == "nt"``. Behavioral
    retry-loop tests patch this onto ``runner._is_windows_transient_replace_error``
    so they never mutate the global ``os.name`` and run deterministically on any
    host; the real ``os.name`` + ``winerror`` semantics are proven by the direct
    classifier tests.
    """
    return isinstance(exc, OSError) and getattr(exc, "winerror", None) in (5, 32)


@pytest.fixture
def _record_sleep(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Replace time.sleep with a recorder so backoff is observed, not waited."""
    slept: list[float] = []
    monkeypatch.setattr("time.sleep", lambda seconds: slept.append(seconds))
    return slept


# ===========================================================================
# Classification helper (deterministic, direct)
# ===========================================================================


@pytest.mark.parametrize("winerror", [5, 32])
def test_classifier_recognizes_windows_transient_winerrors(
    monkeypatch: pytest.MonkeyPatch, winerror: int
) -> None:
    monkeypatch.setattr(runner.os, "name", "nt")
    assert runner._is_windows_transient_replace_error(_winerror_oserror(winerror)) is True


def test_classifier_rejects_non_windows_even_winerror_32(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runner.os, "name", "posix")
    assert runner._is_windows_transient_replace_error(_winerror_oserror(32)) is False


@pytest.mark.parametrize("winerror", [13, 2])
def test_classifier_rejects_permanent_winerrors(
    monkeypatch: pytest.MonkeyPatch, winerror: int
) -> None:
    monkeypatch.setattr(runner.os, "name", "nt")
    assert runner._is_windows_transient_replace_error(_winerror_oserror(winerror)) is False


def test_classifier_rejects_oserror_without_winerror(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runner.os, "name", "nt")
    plain = OSError("plain filesystem error")
    assert runner._is_windows_transient_replace_error(plain) is False


def test_classifier_does_not_swallow_non_oserror(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The classifier is only meaningful for OSError; a non-OSError must never be
    # classified as a retryable transient replace error.
    monkeypatch.setattr(runner.os, "name", "nt")
    assert runner._is_windows_transient_replace_error(RuntimeError("not an os error")) is False


# ===========================================================================
# Behavioral retry-loop tests
#
# These exercise the retry loop given a classifier decision. They patch the
# classifier (not ``os.name``) so they are deterministic on any host; the real
# ``os.name`` + ``winerror`` decision is proven by the direct tests above.
# ===========================================================================


@pytest.mark.parametrize("winerror", [5, 32])
def test_first_transient_replace_failure_then_success(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    winerror: int,
    _record_sleep: list[float],
) -> None:
    monkeypatch.setattr(
        runner, "_is_windows_transient_replace_error", _transient_when_winerror_5_32
    )
    spy = _ReplaceSpy(fail_times=1, winerror=winerror)
    monkeypatch.setattr(runner.os, "replace", spy)

    target = tmp_path / "ledger.json"
    payload = {"schema_version": "import_job_ledger.v1", "jobs": {"a": 1}, "n": 3}

    _atomic_write_json(target, payload)

    # one transient failure, then one success — exactly two attempts
    assert len(spy.calls) == 2
    assert all(spy.calls[i][1] == target for i in range(len(spy.calls)))
    # exactly one backoff (between the two attempts), never after the success
    assert _record_sleep == [0.01]
    # the committed target is complete and parseable, no temp leftover
    assert json.loads(target.read_text("utf-8")) == payload
    assert _temp_leftovers(tmp_path, "ledger.json") == []


# ===========================================================================
# Behavioral: persistent winerror 5 / 32 -> bounded fail (fail closed)
# ===========================================================================


@pytest.mark.parametrize("winerror", [5, 32])
def test_persistent_transient_replace_fails_bounded(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    winerror: int,
    _record_sleep: list[float],
) -> None:
    monkeypatch.setattr(
        runner, "_is_windows_transient_replace_error", _transient_when_winerror_5_32
    )
    failer = _AlwaysFailReplace(winerror=winerror)
    monkeypatch.setattr(runner.os, "replace", failer)

    target = tmp_path / "rollback-manifest.json"
    with pytest.raises(OSError) as excinfo:
        _atomic_write_json(target, {"state": "running"})

    # exactly three attempts; the bubbled object IS the last os.replace-raised
    # exception (identity), not merely a winerror match
    assert len(failer.calls) == 3
    assert excinfo.value is failer.raised[-1]
    assert excinfo.value.winerror == winerror
    # exactly two backoffs (between the three attempts), none after the last
    assert _record_sleep == [0.01, 0.05]
    # fail closed: no target produced, temp cleaned up
    assert not target.exists()
    assert _temp_leftovers(tmp_path, "rollback-manifest.json") == []


# ===========================================================================
# Behavioral: a non-qualifying decision -> no retry (single attempt)
# ===========================================================================


def test_permanent_winerror_no_retry(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    _record_sleep: list[float],
) -> None:
    # winerror 13 is not in {5, 32}: the classifier deems it non-retryable.
    monkeypatch.setattr(
        runner, "_is_windows_transient_replace_error", _transient_when_winerror_5_32
    )
    failer = _AlwaysFailReplace(winerror=13)
    monkeypatch.setattr(runner.os, "replace", failer)

    target = tmp_path / "ledger.json"
    with pytest.raises(OSError) as excinfo:
        _atomic_write_json(target, {"x": 1})

    assert excinfo.value.winerror == 13
    assert len(failer.calls) == 1  # single attempt, no retry
    assert _record_sleep == []  # no backoff
    assert not target.exists()
    assert _temp_leftovers(tmp_path, "ledger.json") == []


def test_plain_oserror_without_winerror_no_retry(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    _record_sleep: list[float],
) -> None:
    monkeypatch.setattr(
        runner, "_is_windows_transient_replace_error", _transient_when_winerror_5_32
    )

    def fail_no_winerror(src: Any, dst: Any) -> None:
        raise OSError("disk full")  # no .winerror attribute at all

    monkeypatch.setattr(runner.os, "replace", fail_no_winerror)

    target = tmp_path / "ledger.json"
    with pytest.raises(OSError, match="disk full"):
        _atomic_write_json(target, {"x": 1})
    assert _record_sleep == []


# ===========================================================================
# Behavioral: happy path writes complete JSON with no temp leftovers
# ===========================================================================


def test_success_writes_complete_json_no_temp_leftovers(tmp_path: Path) -> None:
    target = tmp_path / "rollback-manifest.json"
    payload = {
        "schema_version": "import_rollback_manifest.v1",
        "import_id": "20260615-abcdef",
        "state": "committed",
        "created_files": [{"kind": "journal"}, {"kind": "attachment"}],
        "nested": {"a": [1, 2, 3], "unicode": "照片"},
    }

    _atomic_write_json(target, payload)

    on_disk = json.loads(target.read_text("utf-8"))
    assert on_disk == payload  # complete, byte-faithful JSON
    leftovers = [p.name for p in tmp_path.iterdir() if "tmp" in p.name.lower()]
    assert leftovers == [], f"unexpected temp leftovers: {leftovers}"
