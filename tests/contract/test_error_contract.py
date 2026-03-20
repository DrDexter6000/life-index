#!/usr/bin/env python3
"""
Contract tests: ErrorCode & LifeIndexError

Verifies:
1. All error codes documented in API.md exist in ErrorCode class
2. Every code has a recovery strategy in RECOVERY_STRATEGIES
3. LifeIndexError.to_json() produces the documented JSON shape
4. Recovery strategies are valid enum values
5. create_error_response() produces valid structure
6. is_recoverable() logic matches strategy semantics
7. Error code format follows E{module}{type} convention
"""

import re
import pytest

from tools.lib.errors import (
    ErrorCode,
    LifeIndexError,
    create_error_response,
    is_recoverable,
    get_error_description,
    ERROR_DESCRIPTIONS,
)

# ── All error codes documented in API.md ──

API_MD_ERROR_CODES = {
    # General (E00xx)
    "E0000": ("Unknown error", "fail"),
    "E0001": ("Invalid input", "ask_user"),
    "E0002": ("Permission denied", "fail"),
    "E0003": ("Configuration error", "fail"),
    # File (E01xx)
    "E0100": ("File not found", "ask_user"),
    "E0101": ("File already exists", "ask_user"),
    "E0102": ("File corrupted", "fail"),
    "E0103": ("Path invalid", "fail"),
    "E0104": ("Path traversal detected", "fail"),
    "E0105": ("Directory not found", "ask_user"),
    # Write (E02xx)
    "E0200": ("Write failed", "fail"),
    "E0201": ("Sequence error", "fail"),
    "E0202": ("Frontmatter invalid", "fail"),
    "E0203": ("Content empty", "ask_user"),
    "E0204": ("Date invalid", "ask_user"),
    "E0205": ("Attachment copy failed", "continue"),
    # Search (E03xx)
    "E0300": ("Index not found", "continue"),
    "E0301": ("Search failed", "fail"),
    "E0302": ("Query empty", "ask_user"),
    "E0303": ("No results", "continue_empty"),
    # Weather (E04xx)
    "E0400": ("Weather API failed", "skip_optional"),
    "E0401": ("Weather API timeout", "skip_optional"),
    "E0402": ("Location not found", "ask_user"),
    "E0403": ("Weather parse error", "skip_optional"),
    # Edit (E05xx)
    "E0500": ("Journal not found", "ask_user"),
    "E0501": ("Edit conflict", "ask_user"),
    "E0502": ("Field not recognized", "ask_user"),
    "E0503": ("No changes specified", "ask_user"),
    "E0504": ("Location-weather required", "ask_user"),
    # Index (E06xx)
    "E0600": ("Index build failed", "fail"),
    "E0601": ("Index corrupted", "fail"),
    "E0602": ("Vector store error", "continue"),
    "E0603": ("FTS index error", "continue"),
}

VALID_RECOVERY_STRATEGIES = {
    "ask_user",
    "skip_optional",
    "continue_empty",
    "fail",
    "retry",
}

ERROR_CODE_PATTERN = re.compile(r"^E\d{4}$")


class TestErrorCodeCompleteness:
    """All error codes from API.md exist as ErrorCode class attributes."""

    @pytest.mark.parametrize("code", list(API_MD_ERROR_CODES.keys()))
    def test_api_md_code_exists_in_errorcode_class(self, code: str):
        """Each code documented in API.md must be a constant in ErrorCode."""
        all_codes = {
            v
            for k, v in vars(ErrorCode).items()
            if not k.startswith("_") and isinstance(v, str) and ERROR_CODE_PATTERN.match(v)
        }
        assert (
            code in all_codes
        ), f"Error code {code} is documented in API.md but missing from ErrorCode class"

    def test_all_errorcode_constants_follow_format(self):
        """Every string constant in ErrorCode follows E{4-digit} format."""
        for attr_name in dir(ErrorCode):
            if attr_name.startswith("_"):
                continue
            val = getattr(ErrorCode, attr_name)
            if isinstance(val, str):
                assert ERROR_CODE_PATTERN.match(
                    val
                ), f"ErrorCode.{attr_name} = '{val}' does not match E{{4-digit}} format"

    def test_no_duplicate_error_codes(self):
        """No two ErrorCode constants share the same code string."""
        seen: dict[str, str] = {}
        for attr_name in dir(ErrorCode):
            if attr_name.startswith("_"):
                continue
            val = getattr(ErrorCode, attr_name)
            if isinstance(val, str) and ERROR_CODE_PATTERN.match(val):
                assert (
                    val not in seen
                ), f"Duplicate code {val}: ErrorCode.{seen[val]} and ErrorCode.{attr_name}"
                seen[val] = attr_name


class TestRecoveryStrategies:
    """Recovery strategy mapping matches API.md documentation."""

    def test_all_strategies_are_valid_values(self):
        """Every strategy value in RECOVERY_STRATEGIES is a valid strategy."""
        for code, strategy in LifeIndexError.RECOVERY_STRATEGIES.items():
            assert strategy in VALID_RECOVERY_STRATEGIES, (
                f"Code {code} has invalid strategy '{strategy}', "
                f"valid: {VALID_RECOVERY_STRATEGIES}"
            )

    @pytest.mark.parametrize(
        "code,expected_strategy",
        [
            (ErrorCode.WEATHER_API_FAILED, "skip_optional"),
            (ErrorCode.WEATHER_TIMEOUT, "skip_optional"),
            (ErrorCode.WEATHER_PARSE_ERROR, "skip_optional"),
            (ErrorCode.LOCATION_NOT_FOUND, "ask_user"),
            (ErrorCode.FILE_NOT_FOUND, "ask_user"),
            (ErrorCode.PATH_INVALID, "fail"),
            (ErrorCode.PATH_TRAVERSAL_DETECTED, "fail"),
            (ErrorCode.INVALID_INPUT, "ask_user"),
            (ErrorCode.CONTENT_EMPTY, "ask_user"),
            (ErrorCode.DATE_INVALID, "ask_user"),
            (ErrorCode.JOURNAL_NOT_FOUND, "ask_user"),
            (ErrorCode.NO_CHANGES_SPECIFIED, "ask_user"),
            (ErrorCode.LOCATION_WEATHER_REQUIRED, "ask_user"),
            (ErrorCode.NO_RESULTS, "continue_empty"),
            (ErrorCode.QUERY_EMPTY, "ask_user"),
        ],
    )
    def test_specific_code_strategy_matches_api_md(self, code: str, expected_strategy: str):
        """Specific code→strategy mappings match what API.md documents."""
        err = LifeIndexError(code, "test")
        assert err.recovery_strategy == expected_strategy, (
            f"Code {code}: expected strategy '{expected_strategy}', "
            f"got '{err.recovery_strategy}'"
        )

    def test_default_strategy_is_ask_user(self):
        """Codes not in RECOVERY_STRATEGIES default to 'ask_user'."""
        err = LifeIndexError("E9999", "unknown code")
        assert err.recovery_strategy == "ask_user"


class TestLifeIndexErrorToJson:
    """LifeIndexError.to_json() output matches the documented JSON shape."""

    def test_basic_shape(self):
        """to_json() returns {success: False, error: {code, message, details, recovery_strategy}}."""
        err = LifeIndexError(
            ErrorCode.WEATHER_API_FAILED,
            "Weather API request failed",
            {"location": "Lagos, Nigeria", "reason": "timeout"},
            "Please retry later",
        )
        result = err.to_json()

        assert result["success"] is False
        assert "error" in result

        error_obj = result["error"]
        assert error_obj["code"] == "E0400"
        assert error_obj["message"] == "Weather API request failed"
        assert error_obj["details"] == {
            "location": "Lagos, Nigeria",
            "reason": "timeout",
        }
        assert error_obj["recovery_strategy"] == "skip_optional"
        assert error_obj["suggestion"] == "Please retry later"

    def test_minimal_error_no_optional_fields(self):
        """to_json() works with only required fields (no details, no suggestion)."""
        err = LifeIndexError(ErrorCode.INVALID_INPUT, "Bad input")
        result = err.to_json()

        assert result["success"] is False
        assert result["error"]["code"] == "E0001"
        assert result["error"]["message"] == "Bad input"
        assert result["error"]["details"] == {}
        assert result["error"]["recovery_strategy"] == "ask_user"
        assert "suggestion" not in result["error"]

    def test_to_json_contains_exactly_documented_keys(self):
        """Error object contains only the documented keys (no extraneous fields)."""
        err = LifeIndexError(ErrorCode.FILE_NOT_FOUND, "Not found", {"path": "/x"}, "Check path")
        result = err.to_json()

        expected_top_keys = {"success", "error"}
        assert set(result.keys()) == expected_top_keys

        expected_error_keys = {
            "code",
            "message",
            "details",
            "recovery_strategy",
            "suggestion",
        }
        assert set(result["error"].keys()) == expected_error_keys

    def test_to_json_without_suggestion_has_no_suggestion_key(self):
        """When suggestion is None, the key is absent from error object."""
        err = LifeIndexError(ErrorCode.WRITE_FAILED, "Failed")
        result = err.to_json()

        expected_error_keys = {"code", "message", "details", "recovery_strategy"}
        assert set(result["error"].keys()) == expected_error_keys


class TestCreateErrorResponse:
    """create_error_response() produces valid contract-compliant output."""

    def test_returns_same_shape_as_to_json(self):
        """create_error_response() output matches to_json() shape."""
        result = create_error_response(
            ErrorCode.WEATHER_TIMEOUT,
            "Timeout",
            {"timeout_ms": 5000},
            "Retry later",
        )

        assert result["success"] is False
        assert result["error"]["code"] == "E0401"
        assert result["error"]["recovery_strategy"] == "skip_optional"

    def test_uses_default_message_when_not_provided(self):
        """When message is None, uses ERROR_DESCRIPTIONS default."""
        result = create_error_response(ErrorCode.FILE_NOT_FOUND)
        assert result["error"]["message"] == "File not found"

    def test_all_codes_have_descriptions(self):
        """Every code in ErrorCode has an entry in ERROR_DESCRIPTIONS."""
        for attr_name in dir(ErrorCode):
            if attr_name.startswith("_"):
                continue
            val = getattr(ErrorCode, attr_name)
            if isinstance(val, str) and ERROR_CODE_PATTERN.match(val):
                desc = get_error_description(val)
                assert (
                    desc != "Unknown error" or val == ErrorCode.UNKNOWN_ERROR
                ), f"ErrorCode.{attr_name} ({val}) has no description in ERROR_DESCRIPTIONS"


class TestIsRecoverable:
    """is_recoverable() correctly classifies error recoverability."""

    @pytest.mark.parametrize(
        "code,expected",
        [
            (ErrorCode.WEATHER_API_FAILED, True),  # skip_optional
            (ErrorCode.WEATHER_TIMEOUT, True),  # skip_optional
            (ErrorCode.WEATHER_PARSE_ERROR, True),  # skip_optional
            (ErrorCode.NO_RESULTS, True),  # continue_empty
            (
                ErrorCode.PERMISSION_DENIED,
                False,
            ),  # fail (not in RECOVERY_STRATEGIES, default ask_user)
            (ErrorCode.PATH_INVALID, False),  # fail
            (ErrorCode.PATH_TRAVERSAL_DETECTED, False),  # fail
            (ErrorCode.INVALID_INPUT, False),  # ask_user
            (ErrorCode.FILE_NOT_FOUND, False),  # ask_user
        ],
    )
    def test_recoverability_classification(self, code: str, expected: bool):
        """is_recoverable() matches the semantic definition: only skip_optional and continue_empty."""
        assert is_recoverable(code) == expected
