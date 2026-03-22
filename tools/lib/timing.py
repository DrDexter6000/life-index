#!/usr/bin/env python3
"""
Life Index - Performance Timing Utility
========================================
Simple timing utility for adding performance metrics to tool outputs.

Usage:
    from lib.timing import Timer

    timer = Timer()

    with timer.measure("weather_query"):
        weather = query_weather(...)

    result["metrics"] = timer.to_dict()
"""

import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Generator, TypeVar, Callable

F = TypeVar("F", bound=Callable[..., Any])


@dataclass
class TimingEntry:
    """A single timing measurement."""

    name: str
    duration_ms: float
    start_time: float = 0.0


class Timer:
    """
    Performance timing utility for collecting execution metrics.

    Example:
        >>> timer = Timer()
        >>> with timer.measure("parse"):
        ...     # parsing logic
        ...     pass
        >>> with timer.measure("write"):
        ...     # writing logic
        ...     pass
        >>> print(timer.to_dict())
        {'parse_ms': 123.4, 'write_ms': 56.7, 'total_ms': 180.1}
    """

    def __init__(self) -> None:
        self._entries: List[TimingEntry] = []
        self._start_time: Optional[float] = None
        self._end_time: Optional[float] = None

    def start(self) -> "Timer":
        """Start the overall timer."""
        self._start_time = time.perf_counter()
        return self

    def stop(self) -> "Timer":
        """Stop the overall timer."""
        self._end_time = time.perf_counter()
        return self

    @contextmanager
    def measure(self, name: str) -> Generator[None, None, None]:
        """Context manager to measure a named operation."""
        start = time.perf_counter()
        try:
            yield
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            self._entries.append(
                TimingEntry(name=name, duration_ms=round(duration_ms, 2), start_time=start)
            )

    def add(self, name: str, duration_ms: float) -> "Timer":
        """Add a timing entry manually."""
        self._entries.append(TimingEntry(name=name, duration_ms=round(duration_ms, 2)))
        return self

    def get(self, name: str) -> Optional[float]:
        """Get duration for a specific operation in ms."""
        for entry in self._entries:
            if entry.name == name:
                return entry.duration_ms
        return None

    @property
    def total_ms(self) -> float:
        """Total duration from start() to stop() in ms."""
        if self._start_time and self._end_time:
            return round((self._end_time - self._start_time) * 1000, 2)
        return 0.0

    def to_dict(self) -> Dict[str, float]:
        """Convert timing entries to a dictionary."""
        result: Dict[str, float] = {}
        for entry in self._entries:
            result[f"{entry.name}_ms"] = entry.duration_ms

        if self._start_time and self._end_time:
            result["total_ms"] = self.total_ms

        return result

    def to_metrics(self) -> Dict[str, Any]:
        """
        Convert to standard metrics format for tool output.

        Returns:
            Dictionary with timing metrics suitable for JSON output.
        """
        metrics: Dict[str, Any] = {
            "timings": self.to_dict(),
            "entries": [{"name": e.name, "duration_ms": e.duration_ms} for e in self._entries],
        }

        if self._start_time and self._end_time:
            metrics["total_ms"] = self.total_ms

        return metrics


# Convenience function for quick timing
def timed(func: F) -> F:
    """
    Decorator to time a function and return metrics.

    Example:
        @timed
        def my_function():
            return {"success": True}

        result = my_function()
        # result["metrics"]["total_ms"] contains timing
    """
    import functools

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        timer = Timer().start()
        try:
            result = func(*args, **kwargs)
            timer.stop()

            if isinstance(result, dict):
                result["metrics"] = timer.to_dict()

            return result
        except Exception:
            timer.stop()
            raise

    return wrapper  # type: ignore[return-value]
