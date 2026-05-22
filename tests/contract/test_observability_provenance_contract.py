"""Contract tests for v1.1.1 provenance helper (A1).

Validates the reusable provenance envelope that later JSON-generating
commands will consume.  No CLI wiring is tested here.
"""

import copy
import json
from datetime import datetime

import pytest


def _import_observability():
    from tools.lib.observability import build_provenance_envelope

    return build_provenance_envelope


class TestProvenanceEnvelopeSchema:
    """Top-level schema_version + provenance field contract."""

    def test_schema_version_is_v111(self):
        build = _import_observability()
        result = build(
            source_data={"k": "v"},
            generator="search",
            params={"query": "test"},
        )
        assert result["schema_version"] == "v1.1.1"

    def test_provenance_key_exists(self):
        build = _import_observability()
        result = build(
            source_data={"k": "v"},
            generator="search",
            params={"query": "test"},
        )
        assert "provenance" in result

    def test_provenance_has_all_required_fields(self):
        build = _import_observability()
        result = build(
            source_data={"k": "v"},
            generator="search",
            params={"query": "test"},
        )
        prov = result["provenance"]
        required = [
            "source_hash",
            "tool_version",
            "generated_at",
            "generator",
            "params_hash",
            "fixture_version",
        ]
        for field in required:
            assert field in prov, f"missing field: {field}"


class TestSourceHash:
    """source_hash: stable SHA-256 for semantically identical inputs."""

    def test_stable_for_same_input(self):
        build = _import_observability()
        data = {"entries": ["a", "b", "c"]}
        r1 = build(source_data=data, generator="search", params={})
        r2 = build(source_data=data, generator="search", params={})
        assert r1["provenance"]["source_hash"] == r2["provenance"]["source_hash"]

    def test_differs_for_different_input(self):
        build = _import_observability()
        r1 = build(source_data={"x": 1}, generator="search", params={})
        r2 = build(source_data={"x": 2}, generator="search", params={})
        assert r1["provenance"]["source_hash"] != r2["provenance"]["source_hash"]

    def test_prefix_sha256(self):
        build = _import_observability()
        result = build(source_data={}, generator="search", params={})
        assert result["provenance"]["source_hash"].startswith("sha256:")

    def test_json_serialization_order_stability(self):
        build = _import_observability()
        data1 = {"a": 1, "b": 2}
        data2 = {"b": 2, "a": 1}
        r1 = build(source_data=data1, generator="search", params={})
        r2 = build(source_data=data2, generator="search", params={})
        assert r1["provenance"]["source_hash"] == r2["provenance"]["source_hash"]


class TestParamsHash:
    """params_hash: stable hash for command parameters."""

    def test_stable_for_same_params(self):
        build = _import_observability()
        params = {"query": "hello", "level": 3}
        r1 = build(source_data={}, generator="search", params=params)
        r2 = build(source_data={}, generator="search", params=params)
        assert r1["provenance"]["params_hash"] == r2["provenance"]["params_hash"]

    def test_differs_for_different_params(self):
        build = _import_observability()
        r1 = build(source_data={}, generator="search", params={"q": "a"})
        r2 = build(source_data={}, generator="search", params={"q": "b"})
        assert r1["provenance"]["params_hash"] != r2["provenance"]["params_hash"]

    def test_prefix_sha256(self):
        build = _import_observability()
        result = build(source_data={}, generator="search", params={})
        assert result["provenance"]["params_hash"].startswith("sha256:")


class TestGeneratedAt:
    """generated_at: ISO 8601 UTC, testable without wall-clock flakiness."""

    def test_iso8601_utc_format(self):
        build = _import_observability()
        result = build(source_data={}, generator="search", params={})
        ts = result["provenance"]["generated_at"]
        parsed = datetime.fromisoformat(ts)
        assert parsed.tzinfo is not None

    def test_utc_timezone(self):
        build = _import_observability()
        result = build(source_data={}, generator="search", params={})
        ts = result["provenance"]["generated_at"]
        assert ts.endswith("+00:00") or ts.endswith("Z")

    def test_accepts_override_for_determinism(self):
        build = _import_observability()
        fixed_ts = "2026-01-01T00:00:00+00:00"
        result = build(
            source_data={},
            generator="search",
            params={},
            generated_at=fixed_ts,
        )
        assert result["provenance"]["generated_at"] == fixed_ts


class TestGeneratorEnum:
    """generator: validate against the planned enum family."""

    VALID_GENERATORS = [
        "search",
        "index",
        "eval",
        "entity",
        "maintenance",
        "trajectory",
    ]

    @pytest.mark.parametrize("gen", VALID_GENERATORS)
    def test_valid_generators_accepted(self, gen):
        build = _import_observability()
        result = build(source_data={}, generator=gen, params={})
        assert result["provenance"]["generator"] == gen

    def test_invalid_generator_rejected(self):
        build = _import_observability()
        with pytest.raises(ValueError):
            build(source_data={}, generator="invalid_tool", params={})


class TestToolVersion:
    """tool_version: sourced from existing project version mechanism."""

    def test_tool_version_is_string(self):
        build = _import_observability()
        result = build(source_data={}, generator="search", params={})
        assert isinstance(result["provenance"]["tool_version"], str)

    def test_tool_version_not_empty(self):
        build = _import_observability()
        result = build(source_data={}, generator="search", params={})
        assert len(result["provenance"]["tool_version"]) > 0


class TestFixtureVersion:
    """fixture_version: null by default, set only for eval."""

    def test_default_null(self):
        build = _import_observability()
        result = build(source_data={}, generator="search", params={})
        assert result["provenance"]["fixture_version"] is None

    def test_can_be_set(self):
        build = _import_observability()
        result = build(
            source_data={},
            generator="eval",
            params={},
            fixture_version="2026-05-22",
        )
        assert result["provenance"]["fixture_version"] == "2026-05-22"


class TestInputImmutability:
    """Helper must not mutate caller's input."""

    def test_source_data_not_mutated(self):
        build = _import_observability()
        original = {"key": "value", "nested": [1, 2, 3]}
        frozen = copy.deepcopy(original)
        build(source_data=original, generator="search", params={})
        assert original == frozen

    def test_params_not_mutated(self):
        build = _import_observability()
        original = {"query": "test", "level": 3}
        frozen = copy.deepcopy(original)
        build(source_data={}, generator="search", params=original)
        assert original == frozen

    def test_result_independent_of_input_mutation(self):
        build = _import_observability()
        data = {"k": "v"}
        result = build(source_data=data, generator="search", params={})
        data["k"] = "mutated"
        result2 = build(source_data={"k": "v"}, generator="search", params={})
        assert result["provenance"]["source_hash"] == result2["provenance"]["source_hash"]


class TestJsonSerializable:
    """Entire result must be JSON-serializable."""

    def test_json_round_trip(self):
        build = _import_observability()
        result = build(
            source_data={"entries": [1, 2]},
            generator="index",
            params={"rebuild": False},
        )
        serialized = json.dumps(result)
        deserialized = json.loads(serialized)
        assert deserialized == result
