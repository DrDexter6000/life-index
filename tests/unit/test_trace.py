"""Tests for observability trace framework."""

import json
import time
import pytest
from tools.lib.trace import Trace


class TestTrace:
    def test_trace_basic_usage(self):
        """Basic usage: create trace, record steps."""
        with Trace("write") as t:
            with t.step("validate"):
                pass
            with t.step("file_write"):
                pass
        result = t.to_dict()
        assert result["command"] == "write"
        assert "trace_id" in result
        assert len(result["trace_id"]) == 8
        assert "total_ms" in result
        assert len(result["steps"]) == 2
        assert result["steps"][0]["step"] == "validate"
        assert result["steps"][0]["status"] == "ok"

    def test_trace_step_records_duration(self):
        """Step should record accurate duration."""
        with Trace("test") as t:
            with t.step("slow_step"):
                time.sleep(0.05)  # 50ms
        step = t.to_dict()["steps"][0]
        assert step["ms"] >= 40
        assert step["ms"] < 200

    def test_trace_step_captures_failure(self):
        """Exception inside step should be recorded as status=error."""
        with Trace("test") as t:
            try:
                with t.step("bad_step"):
                    raise ValueError("boom")
            except ValueError:
                pass
        step = t.to_dict()["steps"][0]
        assert step["status"] == "error"
        assert "boom" in step.get("detail", "")

    def test_trace_step_degraded_status(self):
        """Step can be manually marked as degraded."""
        with Trace("test") as t:
            with t.step("optional") as s:
                s.set_status("degraded", "vector index skipped")
        step = t.to_dict()["steps"][0]
        assert step["status"] == "degraded"
        assert step["detail"] == "vector index skipped"

    def test_trace_total_ms(self):
        """total_ms should approximately equal sum of steps."""
        with Trace("test") as t:
            with t.step("a"):
                time.sleep(0.02)
            with t.step("b"):
                time.sleep(0.02)
        result = t.to_dict()
        assert result["total_ms"] >= 30

    def test_trace_disabled(self):
        """Disabled trace should return None."""
        with Trace("test", enabled=False) as t:
            with t.step("a"):
                pass
        assert t.to_dict() is None

    def test_trace_to_dict_serializable(self):
        """to_dict output should be JSON-serializable."""
        with Trace("write") as t:
            with t.step("validate"):
                pass
        result = t.to_dict()
        json_str = json.dumps(result)
        assert "write" in json_str
