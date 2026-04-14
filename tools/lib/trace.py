"""Lightweight observability — trace steps embedded in JSON responses."""

from __future__ import annotations

import time
import uuid
from types import TracebackType
from typing import Literal


class TraceStep:
    """Timer and status recorder for a single pipeline step."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.status = "ok"
        self.detail: str | None = None
        self._start: float = 0.0
        self._end: float = 0.0

    def __enter__(self) -> TraceStep:
        self._start = time.monotonic()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> Literal[False]:
        self._end = time.monotonic()
        if exc_type is not None:
            self.status = "error"
            self.detail = str(exc_val)
        return False  # Don't swallow exceptions

    def set_status(self, status: str, detail: str | None = None) -> None:
        self.status = status
        self.detail = detail

    @property
    def duration_ms(self) -> float:
        return round((self._end - self._start) * 1000, 1)

    def to_dict(self) -> dict:
        d: dict = {"step": self.name, "ms": self.duration_ms, "status": self.status}
        if self.detail:
            d["detail"] = self.detail
        return d


class _NoopStep:
    """Null-object step used when tracing is disabled."""

    def __enter__(self) -> _NoopStep:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> Literal[False]:
        return False

    def set_status(self, status: str, detail: str | None = None) -> None:
        pass


class Trace:
    """Operation-level trace container — use as context manager."""

    def __init__(self, command: str, enabled: bool = True) -> None:
        self.command = command
        self.enabled = enabled
        self.trace_id = uuid.uuid4().hex[:8]
        self._steps: list[TraceStep] = []
        self._start: float = 0.0
        self._end: float = 0.0

    def __enter__(self) -> Trace:
        if self.enabled:
            self._start = time.monotonic()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> Literal[False]:
        if self.enabled:
            self._end = time.monotonic()
        return False

    def step(self, name: str) -> TraceStep | _NoopStep:
        if not self.enabled:
            return _NoopStep()
        s = TraceStep(name)
        self._steps.append(s)
        return s

    def to_dict(self) -> dict | None:
        if not self.enabled:
            return None
        return {
            "trace_id": self.trace_id,
            "command": self.command,
            "total_ms": round((self._end - self._start) * 1000, 1),
            "steps": [s.to_dict() for s in self._steps],
        }
