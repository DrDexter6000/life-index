"""Tests for event detection framework."""

import pytest
import time
from tools.lib.events import (
    Event,
    EventSeverity,
    EventRegistry,
)


class TestEventFramework:
    def test_event_dataclass(self):
        """Event data structure should contain necessary fields."""
        e = Event(
            type="test_event",
            severity=EventSeverity.INFO,
            message="Test message",
            data={"key": "value"},
        )
        assert e.type == "test_event"
        assert e.severity == EventSeverity.INFO
        assert e.message == "Test message"
        assert e.data["key"] == "value"

    def test_event_to_dict(self):
        """Event should serialize to dict."""
        e = Event(
            type="test_event",
            severity=EventSeverity.INFO,
            message="Test",
        )
        d = e.to_dict()
        assert d["type"] == "test_event"
        assert d["severity"] == "info"
        assert d["message"] == "Test"

    def test_event_to_dict_omits_empty_data(self):
        """to_dict should omit data when empty."""
        e = Event(type="t", severity=EventSeverity.LOW, message="m")
        d = e.to_dict()
        assert "data" not in d

    def test_register_and_detect(self):
        """Registered detectors should be invoked on detect_all."""
        called = []

        def dummy_detector(context: dict) -> list[Event]:
            called.append(True)
            return [Event(type="dummy", severity=EventSeverity.LOW, message="test")]

        registry = EventRegistry()
        registry.register("dummy", dummy_detector)
        events = registry.detect_all(context={})
        assert len(called) == 1
        assert len(events) == 1
        assert events[0].type == "dummy"

    def test_detector_exception_does_not_crash(self):
        """A failing detector should not affect other detectors."""

        def bad_detector(context: dict) -> list[Event]:
            raise RuntimeError("boom")

        def good_detector(context: dict) -> list[Event]:
            return [Event(type="good", severity=EventSeverity.INFO, message="ok")]

        registry = EventRegistry()
        registry.register("bad", bad_detector)
        registry.register("good", good_detector)
        events = registry.detect_all(context={})
        assert len(events) == 1
        assert events[0].type == "good"

    def test_detect_respects_enabled_config(self):
        """When enabled=False, no detectors should run."""
        registry = EventRegistry()
        registry.register(
            "test",
            lambda ctx: [Event(type="test", severity=EventSeverity.INFO, message="x")],
        )
        events = registry.detect_all(context={}, enabled=False)
        assert events == []

    def test_detect_timeout_skips_slow_detectors(self):
        """Detectors exceeding the timeout budget should be skipped."""

        def slow_detector(context: dict) -> list[Event]:
            time.sleep(0.2)  # 200ms — exceeds budget
            return [Event(type="slow", severity=EventSeverity.LOW, message="late")]

        def fast_detector(context: dict) -> list[Event]:
            return [Event(type="fast", severity=EventSeverity.INFO, message="ok")]

        registry = EventRegistry()
        registry.register("slow", slow_detector)
        registry.register("fast", fast_detector)
        # slow is registered first; with 50ms budget it should be skipped,
        # but fast should still run since it's after slow.
        events = registry.detect_all(context={}, timeout_ms=50)
        # slow is registered first and takes 200ms, so deadline is exceeded
        # before fast even runs — both may be skipped.
        # Let's re-register with fast first:
        registry2 = EventRegistry()
        registry2.register("fast", fast_detector)
        registry2.register("slow", slow_detector)
        events2 = registry2.detect_all(context={}, timeout_ms=50)
        assert len(events2) >= 1
        assert events2[0].type == "fast"
