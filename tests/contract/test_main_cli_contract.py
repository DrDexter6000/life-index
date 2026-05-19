#!/usr/bin/env python3
"""Contract test: unified main CLI help and unknown-command surface.

Verifies:
- `python -m tools --help` exits 0 and prints stable command names
- `python -m tools -h` exits 0 and prints stable command names
- `python -m tools help` exits 0 and prints stable command names
- Unknown command exits non-zero, prints "Unknown command: ...", and prints usage

All invocations use subprocess to test the real CLI surface, not internal
functions.  No user data is read or written.
"""

import subprocess
import sys

# Stable representative subset - not the exhaustive command list.
STABLE_COMMANDS = {
    "write",
    "search",
    "smart-search",
    "aggregate",
    "analyze",
    "health",
    "version",
    "on-this-day",
}


def _invoke(*extra_args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "tools", *extra_args],
        capture_output=True,
        text=True,
        timeout=30,
    )


class TestHelpSurface:
    def test_dash_dash_help_exits_0(self):
        result = _invoke("--help")
        assert result.returncode == 0, (
            f"Expected exit code 0, got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_dash_h_exits_0(self):
        result = _invoke("-h")
        assert result.returncode == 0, (
            f"Expected exit code 0, got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_help_subcommand_exits_0(self):
        result = _invoke("help")
        assert result.returncode == 0, (
            f"Expected exit code 0, got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_help_outputs_stable_commands_dash_dash_help(self):
        result = _invoke("--help")
        stdout = result.stdout
        for cmd in STABLE_COMMANDS:
            assert cmd in stdout, f"Command '{cmd}' not found in --help output"

    def test_help_outputs_stable_commands_dash_h(self):
        result = _invoke("-h")
        stdout = result.stdout
        for cmd in STABLE_COMMANDS:
            assert cmd in stdout, f"Command '{cmd}' not found in -h output"

    def test_help_outputs_stable_commands_help(self):
        result = _invoke("help")
        stdout = result.stdout
        for cmd in STABLE_COMMANDS:
            assert cmd in stdout, f"Command '{cmd}' not found in help output"

    def test_help_outputs_usage_line(self):
        result = _invoke("--help")
        assert "Usage:" in result.stdout

    def test_help_outputs_run_hint(self):
        result = _invoke("--help")
        assert "Run 'life-index <command> --help'" in result.stdout

    def test_help_outputs_python_m_tools_usage_line_dash_dash_help(self):
        result = _invoke("--help")
        assert "python -m tools <command> [options]" in result.stdout

    def test_help_outputs_python_m_tools_usage_line_dash_h(self):
        result = _invoke("-h")
        assert "python -m tools <command> [options]" in result.stdout

    def test_help_outputs_python_m_tools_usage_line_help(self):
        result = _invoke("help")
        assert "python -m tools <command> [options]" in result.stdout

    def test_help_outputs_developer_mode_dash_dash_help(self):
        result = _invoke("--help")
        assert "Developer mode:" in result.stdout

    def test_help_outputs_developer_mode_dash_h(self):
        result = _invoke("-h")
        assert "Developer mode:" in result.stdout

    def test_help_outputs_developer_mode_help(self):
        result = _invoke("help")
        assert "Developer mode:" in result.stdout


class TestNoArgsSurface:
    def test_no_args_exits_non_zero(self):
        result = _invoke()
        assert result.returncode != 0, (
            f"Expected non-zero exit code, got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_no_args_prints_usage(self):
        result = _invoke()
        assert "Usage:" in result.stdout

    def test_no_args_prints_python_m_tools_usage_line(self):
        result = _invoke()
        assert "python -m tools <command> [options]" in result.stdout

    def test_no_args_includes_stable_commands(self):
        result = _invoke()
        stdout = result.stdout
        for cmd in STABLE_COMMANDS:
            assert cmd in stdout, f"Command '{cmd}' not found in no-args output"

    def test_no_args_prints_developer_mode(self):
        result = _invoke()
        assert "Developer mode:" in result.stdout


class TestUnknownCommandSurface:
    def test_unknown_command_exits_non_zero(self):
        result = _invoke("not-a-life-index-command")
        assert result.returncode != 0, (
            f"Expected non-zero exit code, got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_unknown_command_prints_unknown_message(self):
        result = _invoke("not-a-life-index-command")
        assert "Unknown command: not-a-life-index-command" in result.stdout

    def test_unknown_command_prints_usage(self):
        result = _invoke("not-a-life-index-command")
        assert "Usage:" in result.stdout

    def test_unknown_command_includes_stable_commands(self):
        result = _invoke("not-a-life-index-command")
        stdout = result.stdout
        for cmd in STABLE_COMMANDS:
            assert cmd in stdout, f"Command '{cmd}' not found in unknown-command output"
