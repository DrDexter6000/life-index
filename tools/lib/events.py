"""Lightweight event detection framework — piggyback on CLI responses."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Callable

logger = logging.getLogger(__name__)


class EventSeverity(StrEnum):
    """Event severity levels."""

    HIGH = "high"
    INFO = "info"
    LOW = "low"


@dataclass
class Event:
    """A single piggyback event to be returned in CLI JSON responses."""

    type: str
    severity: EventSeverity
    message: str
    data: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "type": self.type,
            "severity": self.severity.value,
            "message": self.message,
        }
        if self.data:
            result["data"] = self.data
        return result


DetectorFunc = Callable[[dict], list[Event]]


class EventRegistry:
    """Isolatable event detector registry."""

    def __init__(self) -> None:
        self._detectors: dict[str, DetectorFunc] = {}

    def register(self, name: str, func: DetectorFunc) -> None:
        self._detectors[name] = func

    def detect_all(
        self,
        context: dict,
        enabled: bool = True,
        timeout_ms: int = 50,
    ) -> list[Event]:
        """Run all registered detectors within the timeout budget.

        Detectors that raise exceptions are silently skipped.
        Once the deadline is exceeded, remaining detectors are skipped.
        """
        if not enabled:
            return []

        events: list[Event] = []
        deadline = time.monotonic() + timeout_ms / 1000

        for name, func in self._detectors.items():
            if time.monotonic() >= deadline:
                logger.debug("Event detection timeout, skipping: %s", name)
                break
            try:
                events.extend(func(context))
            except Exception:
                logger.debug("Event detector '%s' failed", name, exc_info=True)

        return events


# Global registry — convenience aliases
_global_registry = EventRegistry()
register_detector = _global_registry.register
detect_events = _global_registry.detect_all
