"""Tests for event detection framework."""

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

    def test_detect_timeout_skips_slow_detectors(self, monkeypatch):
        """A detector that runs past the budget stops the detectors after it.

        The clock is the one ``detect_all`` reads, advanced by the slow detector
        itself, so the test does not depend on how fast the machine is.
        """
        import tools.lib.events as events_module

        class FakeClock:
            now = 100.0

            def monotonic(self) -> float:
                return self.now

        clock = FakeClock()
        monkeypatch.setattr(events_module, "time", clock)

        def fast_detector(context: dict) -> list[Event]:
            return [Event(type="fast", severity=EventSeverity.INFO, message="ok")]

        def slow_detector(context: dict) -> list[Event]:
            clock.now += 0.2  # 200 ms: past the 50 ms budget
            return [Event(type="slow", severity=EventSeverity.LOW, message="late")]

        def late_detector(context: dict) -> list[Event]:
            return [Event(type="late", severity=EventSeverity.INFO, message="never")]

        registry = EventRegistry()
        registry.register("fast", fast_detector)
        registry.register("slow", slow_detector)
        registry.register("late", late_detector)

        events = registry.detect_all(context={}, timeout_ms=50)

        assert [event.type for event in events] == ["fast", "slow"]
