#!/usr/bin/env python3
"""The Life Index local gate: one command, one verdict.

This module owns the complete inventory of checks that guard a push. Nothing
else may list them: the native pre-push hook delegates here
(``--from-hook``), and the online backstop
(``.github/workflows/backstop.yml``) runs the same static inventory through
``--fast`` on a clean hosted machine without ever blocking a push.

Modes::

    python scripts/gate.py                      # full gate on HEAD
    python scripts/gate.py --fast               # static checks only, no tests
    python scripts/gate.py --base A --head B    # explicit outgoing range
    python scripts/gate.py --no-linux           # skip the WSL Linux leg (loud)
    python scripts/gate.py --list               # print the inventory, in order
    python scripts/gate.py --setup-linux        # create/refresh the WSL env
    python scripts/gate.py --from-hook [REMOTE [URL]]   # gate a push (stdin)
    python scripts/gate.py --install-hook       # install the native pre-push hook
    python scripts/gate.py --check-hook         # is the gate's hook installed?

The checks always run on the *committed* candidate (a detached worktree of
the resolved SHA), never on the working tree. The two public-diff scans run
once for **every commit the push would add**, so a file that is added in one
outgoing commit and deleted in a later one is still scanned. Every process
that runs candidate code gets one sanitized environment: nothing inherited
that starts with LIFE_INDEX_/PYTHON/PYTEST_/COVERAGE_/COV_CORE_/PIP_/
PRE_COMMIT_/GIT_ (and no VIRTUAL_ENV), a forced synthetic data directory, a
throwaway HOME, and the candidate on PYTHONPATH. Each test leg fingerprints
the real home's default data directory (stat only) before and after.
Standard library only.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib
import xml.etree.ElementTree as ET
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
# Built from parts so the literal never appears in a public added line.
REPORT_DIR = REPO_ROOT / ("." + "agent-reports") / "gate"

ZERO_SHA = "0" * 40
MAIN_BRANCH_REF = "refs/heads/main"
# The empty tree: the scan base of a root commit, which has no first parent.
EMPTY_TREE_SHA = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"

PER_TEST_TIMEOUT = 600  # seconds per test; mirrors the retired workflows
LEG_TIMEOUT = int(os.environ.get("GATE_LEG_TIMEOUT", "5400"))
CHECK_TIMEOUT = int(os.environ.get("GATE_CHECK_TIMEOUT", "1800"))
PROBE_TIMEOUT = 120

REQUIRED_TOOLS = (
    "black",
    "flake8",
    "mypy",
    "bandit",
    "pytest",
    "pytest_cov",
    "pytest_timeout",
)

# The WSL side of the Linux leg. The gate never creates or updates this
# environment; --setup-linux does, and it is the only mode that downloads.
# "$HOME", not "~": these land inside double quotes in bash, where a tilde
# does not expand.
WSL_BASE = "$HOME/.cache/life-index-gate"
WSL_VENV = f"{WSL_BASE}/venv-py311"
WSL_HASH_FILE = f"{WSL_BASE}/py311-deps.sha256"
# Per-run work directories live here: on disk, and not under a dot-directory.
WSL_WORK_PARENT = "/var/tmp"
SETUP_HINT = "python scripts/gate.py --setup-linux"

# The extra packages --setup-linux installs on top of ``.[dev]``; they are
# part of the hashed environment description. The project itself is then
# uninstalled: the shared environment keeps only dependencies, and a gate
# run points ``PYTHONPATH`` at the clone it is testing instead of mutating
# the shared install.
WSL_EXTRA_PLUGINS = ("pytest", "pytest-cov", "pytest-timeout", "bandit")

# Variables a sanitized child never inherits: anything that could redirect
# data access (LIFE_INDEX_*), imports (PYTHON*), pytest/coverage behavior,
# pip configuration, a stale hook context, or Git's own environment (GIT_*:
# Git exports GIT_DIR/GIT_PREFIX to the pre-push hook, and a test that runs
# git in a temporary directory would otherwise act on the pushing worktree's
# real repository instead).
SANITIZED_PREFIXES = (
    "LIFE_INDEX_",
    "PYTHON",
    "PYTEST_",
    "COVERAGE_",
    "COV_CORE_",
    "PIP_",
    "PRE_COMMIT_",
    "GIT_",
)
SANITIZED_EXACT = {"VIRTUAL_ENV"}

# The native pre-push hook, written by --install-hook. Recognized by the
# marker line so --check-hook can compare content and --install-hook can
# refuse to overwrite a hook it did not write.
HOOK_MARKER = "# life-index-gate pre-push hook (managed by scripts/gate.py)"
HOOK_TEMPLATE = (
    "#!/bin/sh\n"
    f"{HOOK_MARKER}\n"
    "# Written by scripts/gate.py --install-hook; edits are overwritten by --force.\n"
    "# Forwards Git's stdin push records to the gate; see docs/CI_HARD_CHECKS.md.\n"
    'toplevel="$(git rev-parse --show-toplevel)" || exit 1\n'
    'exec python "$toplevel/scripts/gate.py" --from-hook "$@"\n'
)


# ── The two execution seams (unit tests replace these) ──────────────────────


@dataclass(frozen=True)
class ProcResult:
    """One finished subprocess."""

    returncode: int
    stdout: str = ""
    stderr: str = ""
    detail: str = ""  # e.g. "timed out after 5400s"


def _kill_tree(proc: subprocess.Popen) -> None:
    """Best-effort tree kill. Windows: taskkill /T /F. Posix: the child only
    (no process-group kill); the WSL pytest is separately wrapped in
    ``timeout --kill-after`` inside the leg script."""
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(proc.pid)],
            capture_output=True,
            check=False,
        )
    else:
        try:
            proc.kill()
        except OSError:
            pass


def run_process(
    argv: Sequence[object],
    *,
    cwd: Path | str | None = None,
    env: dict[str, str] | None = None,
    timeout: int | None = None,
    capture: bool = True,
) -> ProcResult:
    """Run one subprocess.

    Every external command the gate spawns goes through this seam, so the
    unit tests can replace subprocess execution with a recorder. On timeout
    the whole process tree is killed (best effort) before returning.
    """
    command = [str(part) for part in argv]
    try:
        proc = subprocess.Popen(
            command,
            cwd=None if cwd is None else str(cwd),
            env=env,
            stdout=subprocess.PIPE if capture else None,
            stderr=subprocess.PIPE if capture else None,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError:
        return ProcResult(127, detail=f"command not found: {command[0]}")
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_tree(proc)
        try:
            out, err = proc.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            out, err = "", ""
        return ProcResult(
            124,
            out or "",
            err or "",
            detail=f"timed out after {timeout}s",
        )
    if capture:
        return ProcResult(proc.returncode, out or "", err or "")
    return ProcResult(proc.returncode)


def wsl_command(args: Sequence[str]) -> list[str]:
    """Build the wsl.exe command line for one exec-form command.

    This is the single WSL seam: everything that touches WSL goes through
    this builder, so unit tests can replace it. ``--exec`` bypasses the
    default shell so argv reaches the target command verbatim.
    """
    return ["wsl.exe", "--exec", *args]


def run_wsl(
    args: Sequence[str],
    *,
    timeout: int | None = None,
    capture: bool = True,
) -> ProcResult:
    """Run one command inside WSL through the single seam."""
    return run_process(wsl_command(args), timeout=timeout, capture=capture)


# ── Git helpers (all through the run_process seam) ──────────────────────────


def git(
    *args: str,
    cwd: Path | None = None,
    timeout: int | None = None,
) -> ProcResult:
    return run_process(["git", *args], cwd=cwd or REPO_ROOT, timeout=timeout)


def resolve_full_sha(ref: str) -> str | None:
    proc = git("rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def is_ancestor(ancestor: str, descendant: str) -> bool:
    return git("merge-base", "--is-ancestor", ancestor, descendant).returncode == 0


def first_parent(sha: str) -> str:
    """The commit's first parent, or the empty tree for a root commit."""
    proc = git("rev-parse", "--verify", "--quiet", f"{sha}^")
    if proc.returncode == 0 and proc.stdout.strip():
        return proc.stdout.strip()
    return EMPTY_TREE_SHA


def rev_list_outgoing(head: str, not_refs: Sequence[str]) -> list[str] | None:
    """Commits reachable from ``head`` but not from ``not_refs``, oldest
    first. Returns None when git fails."""
    proc = git("rev-list", "--reverse", head, "--not", *not_refs)
    if proc.returncode != 0:
        return None
    return [line for line in proc.stdout.splitlines() if line.strip()]


def git_common_dir() -> Path | None:
    proc = git("rev-parse", "--git-common-dir")
    if proc.returncode != 0:
        return None
    raw = proc.stdout.strip()
    if not raw:
        return None
    path = Path(raw)
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


# ── Push records (C1): every ref being pushed ───────────────────────────────


@dataclass(frozen=True)
class PushRecord:
    local_ref: str
    local_sha: str
    remote_ref: str
    remote_sha: str

    @property
    def is_deletion(self) -> bool:
        return self.local_sha == ZERO_SHA

    @property
    def is_new_remote_ref(self) -> bool:
        return self.remote_sha == ZERO_SHA


def parse_push_records(text: str) -> list[PushRecord]:
    """Parse Git's pre-push stdin: one ``<local ref> <local sha> <remote
    ref> <remote sha>`` record per line."""
    records: list[PushRecord] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) != 4:
            raise ValueError(f"malformed pre-push record: {line!r}")
        records.append(PushRecord(*parts))
    return records


def push_record_outgoing(
    records: Sequence[PushRecord], remote_name: str | None
) -> tuple[list[str], str]:
    """The union of commits the given push records would publish, oldest
    first (C2/F3). A record with a known remote SHA excludes that commit;
    a new remote ref excludes everything on the remote's tracking refs."""
    merged: list[str] = []
    for record in records:
        if record.is_new_remote_ref:
            not_refs = [f"--remotes={remote_name or 'origin'}"]
        else:
            not_refs = [record.remote_sha]
        commits = rev_list_outgoing(record.local_sha, not_refs)
        if commits is None:
            return [], (
                f"cannot list outgoing commits for {record.local_ref}; " "fetch the remote first"
            )
        for commit in commits:
            if commit not in merged:
                merged.append(commit)
    return merged, ""


# ── The inventory (D1): this module, and nothing else, lists the checks ─────


@dataclass(frozen=True)
class Check:
    key: str
    label: str
    argv: tuple[str, ...]


def static_checks(commits: Sequence[str]) -> tuple[Check, ...]:
    """The ordered static inventory, run inside the exported candidate.

    The two diff-scan entries are markers: the stage runs each script once
    per outgoing commit with ``--base`` set to that commit's first parent,
    so every change that is published in history is scanned, not just the
    tip's cumulative diff (see ``scan_check``).
    """
    py = sys.executable
    del commits  # the commit list is dynamic; kept in the signature for --list
    return (
        Check(
            "static:black",
            "black --check --diff tools/",
            (py, "-m", "black", "--check", "--diff", "tools/"),
        ),
        Check(
            "static:flake8",
            "flake8 tools/",
            (
                py,
                "-m",
                "flake8",
                "tools/",
                "--count",
                "--max-complexity=40",
                "--max-line-length=100",
                "--show-source",
                "--statistics",
            ),
        ),
        Check(
            "static:mypy",
            "mypy tools/",
            (py, "-m", "mypy", "tools/", "--ignore-missing-imports"),
        ),
        Check(
            "static:bandit",
            "bandit -r tools/",
            (py, "-m", "bandit", "-r", "tools/", "-ll", "-c", "pyproject.toml"),
        ),
        Check(
            "static:doc-sync",
            "check_doc_sync.py",
            (py, ".github/scripts/check_doc_sync.py"),
        ),
        Check(
            "static:l2-no-llm",
            "check_l2_no_llm.py",
            (py, ".github/scripts/check_l2_no_llm.py"),
        ),
        Check(
            "static:public-diff-names",
            "check_public_diff_names.py per outgoing commit",
            (py, ".github/scripts/check_public_diff_names.py", "--per-commit"),
        ),
        Check(
            "static:public-surface-allowlist",
            "check_public_surface_allowlist.py per outgoing commit",
            (py, ".github/scripts/check_public_surface_allowlist.py", "--per-commit"),
        ),
        Check(
            "static:skill-mirror",
            "sync_skill_artifacts.py --check",
            (py, "scripts/sync_skill_artifacts.py", "--check"),
        ),
    )


def scan_check(script: str, commit: str, parent: str) -> list[str]:
    """The argv of one public-diff scan for one outgoing commit."""
    return [
        sys.executable,
        f".github/scripts/{script}",
        "--base",
        parent,
        "--head",
        commit,
    ]


def sentinel_check() -> Check:
    return Check(
        "sentinel",
        "run_public_core_assertions.py",
        (sys.executable, ".github/scripts/run_public_core_assertions.py"),
    )


def pytest_argv(junit: Path, basetemp: Path, *, coverage: bool) -> list[str]:
    argv = [sys.executable, "-m", "pytest", "tests", f"--timeout={PER_TEST_TIMEOUT}"]
    if coverage:
        argv += ["--cov=tools", "--cov-report=term-missing"]
    argv += [f"--basetemp={basetemp}", f"--junitxml={junit}"]
    return argv


# ── junit XML: leg counts are read from the file, never from console text ───


def junit_totals(root: ET.Element) -> dict[str, int]:
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))

    def total(attribute: str) -> int:
        return sum(int(suite.get(attribute) or 0) for suite in suites)

    tests = total("tests")
    errors = total("errors")
    failures = total("failures")
    skipped = total("skipped")
    return {
        "tests": tests,
        "errors": errors,
        "failures": failures,
        "skipped": skipped,
        "passed": max(tests - errors - failures - skipped, 0),
    }


def parse_junit(path: Path) -> dict[str, int] | None:
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError):
        return None
    return junit_totals(root)


# The same computation, embedded into the Linux leg's bash script through a
# quoted heredoc (literal text, real newlines) so the WSL side reports
# counts without copying files back over /mnt.
LEG_RESULT_CODE = (
    "import json, sys\n"
    "import xml.etree.ElementTree as ET\n"
    "root = ET.parse(sys.argv[1]).getroot()\n"
    'suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))\n'
    "def total(attr):\n"
    "    return sum(int(s.get(attr) or 0) for s in suites)\n"
    't = total("tests"); e = total("errors"); f = total("failures"); sk = total("skipped")\n'
    'print("GATE-LEG-RESULT " + json.dumps({\n'
    '    "tests": t, "errors": e, "failures": f, "skipped": sk,\n'
    '    "passed": max(t - e - f - sk, 0)}))\n'
)

RESULT_PREFIX = "GATE-LEG-RESULT "
PYTHON_PREFIX = "GATE-LEG-PYTHON "
TRIPWIRE_PREFIX = "GATE-TRIPWIRE "

# The real-data tripwire fingerprint: file count plus a hash over each
# file's size and mtime. It only ever stats files - it never opens one and
# never prints a name. Embedded into the Linux leg through a quoted heredoc;
# ``fingerprint_tree`` below is the native-leg twin and a unit test pins the
# two implementations against each other.
TRIPWIRE_CODE = (
    "import hashlib, os, sys\n"
    "from collections import deque\n"
    "def fingerprint(root):\n"
    "    if not os.path.isdir(root):\n"
    '        return "absent"\n'
    "    digest = hashlib.sha256()\n"
    "    pending = deque([root])\n"
    "    count = 0\n"
    "    while pending:\n"
    "        current = pending.popleft()\n"
    "        try:\n"
    "            children = sorted(os.scandir(current), key=lambda entry: entry.name)\n"
    "        except OSError:\n"
    '            digest.update(b"E")\n'
    "            continue\n"
    "        for child in children:\n"
    "            try:\n"
    "                info = child.stat(follow_symlinks=False)\n"
    "            except OSError:\n"
    '                digest.update(b"e")\n'
    "                continue\n"
    "            if child.is_dir(follow_symlinks=False):\n"
    "                pending.append(child.path)\n"
    "            else:\n"
    "                count += 1\n"
    '                digest.update(f"{info.st_size}:{int(info.st_mtime)}\\n".encode())\n'
    '    return f"files={count}:{digest.hexdigest()[:32]}"\n'
    "print(fingerprint(sys.argv[1]))\n"
)


def real_data_root() -> Path:
    """The real user's default data directory, read before any sanitization.

    The tripwire watches this directory (stat only) while tests run.
    """
    home = os.environ.get("USERPROFILE") or os.environ.get("HOME") or str(Path.home())
    return Path(home) / "Documents" / "Life-Index"


def fingerprint_tree(path: Path) -> str:
    """Native-leg twin of TRIPWIRE_CODE: count + hash of (size, mtime)."""
    if not path.is_dir():
        return "absent"
    digest = hashlib.sha256()
    pending: deque[Path] = deque([path])
    count = 0
    while pending:
        current = pending.popleft()
        try:
            children = sorted(os.scandir(current), key=lambda entry: entry.name)
        except OSError:
            digest.update(b"E")
            continue
        for child in children:
            try:
                info = child.stat(follow_symlinks=False)
            except OSError:
                digest.update(b"e")
                continue
            if child.is_dir(follow_symlinks=False):
                pending.append(Path(child.path))
            else:
                count += 1
                digest.update(f"{info.st_size}:{int(info.st_mtime)}\n".encode())
    return f"files={count}:{digest.hexdigest()[:32]}"


# ── Test legs ────────────────────────────────────────────────────────────────


@dataclass
class LegResult:
    platform: str
    python_version: str = ""
    ran: bool = False
    passed: bool = False
    tests: int | None = None
    passed_count: int | None = None
    failed_count: int | None = None
    skipped_count: int | None = None
    detail: str = ""
    log_path: Path | None = None
    duration: float = 0.0
    tripwire: str = ""


def sanitized_env(
    home_dir: Path,
    data_dir: Path,
    pythonpath: Path,
    coverage_file: Path | None = None,
) -> dict[str, str]:
    """One sanitized environment for every process that runs candidate code.

    Start from the caller's environment; drop everything that could
    redirect data access, imports, pytest/coverage behavior, pip
    configuration, or a stale hook context; then force the throwaway home,
    the synthetic data directory, UTF-8 and the candidate on PYTHONPATH.
    """
    env = {
        name: value
        for name, value in os.environ.items()
        if not name.startswith(SANITIZED_PREFIXES) and name not in SANITIZED_EXACT
    }
    env["HOME"] = str(home_dir)
    env["USERPROFILE"] = str(home_dir)
    env["LIFE_INDEX_DATA_DIR"] = str(data_dir)
    if coverage_file is not None:
        env["COVERAGE_FILE"] = str(coverage_file)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["LIFE_INDEX_INDEX_FTS_ONLY"] = "1"
    env["PYTHONPATH"] = str(pythonpath)
    return env


def _record_counts(leg: LegResult, counts: dict[str, int] | None) -> bool:
    """A leg passes only on an unambiguous result (C4).

    At least one passed test, zero failures, zero errors; all-skipped,
    zero-collected or missing junit are all failures.
    """
    if counts is None:
        leg.detail = (leg.detail + "; " if leg.detail else "") + "no junit result was produced"
        return False
    leg.tests = counts["tests"]
    leg.passed_count = counts["passed"]
    leg.failed_count = counts["errors"] + counts["failures"]
    leg.skipped_count = counts["skipped"]
    if counts["tests"] == 0:
        leg.detail = (leg.detail + "; " if leg.detail else "") + "collected zero tests"
        return False
    if counts["passed"] < 1:
        leg.detail = (leg.detail + "; " if leg.detail else "") + "no test passed (all skipped?)"
        return False
    if counts["errors"] or counts["failures"]:
        return False
    return True


def run_native_leg(export: Path, leg_temp: Path, *, coverage: bool, log_path: Path) -> LegResult:
    """The leg that runs on the interpreter running the gate."""
    label = "windows" if os.name == "nt" else "native"
    leg = LegResult(platform=label, python_version=platform.python_version())
    watched = real_data_root()
    before = fingerprint_tree(watched)
    data_dir = leg_temp / "data"
    home_dir = leg_temp / "home"
    basetemp = leg_temp / "basetemp"
    junit = leg_temp / "junit.xml"
    for directory in (data_dir, home_dir):
        directory.mkdir(parents=True, exist_ok=True)
    leg.log_path = log_path
    env = sanitized_env(home_dir, data_dir, export, leg_temp / ".coverage" if coverage else None)
    proc = run_process(
        pytest_argv(junit, basetemp, coverage=coverage),
        cwd=export,
        env=env,
        timeout=LEG_TIMEOUT,
    )
    leg.ran = not proc.detail
    log_path.write_text(proc.stdout + "\n" + proc.stderr, encoding="utf-8", errors="replace")
    after = fingerprint_tree(watched)
    leg.tripwire = f"unchanged ({before})" if before == after else f"CHANGED ({before} -> {after})"
    if proc.detail:
        leg.detail = proc.detail
        return leg
    ok = _record_counts(leg, parse_junit(junit))
    leg.passed = proc.returncode == 0 and ok and before == after
    return leg


def linux_env_probe_script() -> str:
    return (
        "set -u\n"
        f'VENV="{WSL_VENV}"\n'
        f'HASH_FILE="{WSL_HASH_FILE}"\n'
        'if [ ! -x "$VENV/bin/python" ]; then echo MISSING-VENV; exit 0; fi\n'
        'VER="$("$VENV/bin/python" -c \'import platform; print(platform.python_version())\' '
        '2>&1)"\n'
        'case "$VER" in 3.11.*) ;; *) echo "WRONG-PYTHON $VER"; exit 0;; esac\n'
        'if [ -f "$HASH_FILE" ]; then cat "$HASH_FILE"; fi\n'
    )


def linux_leg_script(sha: str, git_source_wsl: str) -> str:
    """The bash script the Linux leg runs inside WSL.

    It clones the repository's common Git directory onto the WSL filesystem
    (tests never run through /mnt) and checks out the candidate detached.
    pytest runs from inside the clone: ``wsl.exe --exec`` starts in the
    Windows caller's directory under /mnt, so without the ``cd`` the relative
    ``tests`` argument and ``python -m``'s ``sys.path[0]`` would resolve
    against the caller's live working tree instead of the candidate.
    The test process starts from an empty environment (``env -i``) with a
    throwaway HOME and ``PYTHONPATH`` pointing at the clone: the shared
    cached environment is never mutated by a run, and nothing that runs
    candidate code inherits the caller's environment. The real home's
    default data directory is fingerprinted (stat only) before and after.
    """
    quoted_source = git_source_wsl.replace("'", "'\\''")
    return (
        "set -euo pipefail\n"
        f'VENV="{WSL_VENV}"\n'
        'REAL_HOME="$HOME"\n'
        f'TMP="$(mktemp -d {WSL_WORK_PARENT}/life-index-gate.XXXXXX)"\n'
        """trap 'rm -rf "$TMP"' EXIT\n"""
        'mkdir -p "$TMP/home" "$TMP/data" "$TMP/basetemp"\n'
        "git -c safe.directory='*' clone --quiet --shared --no-checkout "
        f"'{quoted_source}' \"$TMP/repo\"\n"
        "git -C \"$TMP/repo\" -c safe.directory='*' checkout --quiet "
        f"--detach '{sha}'\n"
        "cat > \"$TMP/leg_result.py\" <<'PY'\n"
        f"{LEG_RESULT_CODE}"
        "PY\n"
        "cat > \"$TMP/tripwire.py\" <<'PY'\n"
        f"{TRIPWIRE_CODE}"
        "PY\n"
        # Everything below runs inside the clone: the caller's working tree
        # must not be imported, collected, or left with bytecode.
        'cd "$TMP/repo"\n'
        'echo "' + PYTHON_PREFIX + '$("$VENV/bin/python" --version 2>&1)"\n'
        '"$VENV/bin/python" "$TMP/tripwire.py" '
        '"$REAL_HOME/Documents/Life-Index" > "$TMP/tripwire-before"\n'
        "set +e\n"
        'env -i PATH="$VENV/bin:/usr/bin:/bin" HOME="$TMP/home" LANG=C.UTF-8 '
        'LIFE_INDEX_DATA_DIR="$TMP/data" PYTHONUTF8=1 PYTHONIOENCODING=utf-8 '
        'LIFE_INDEX_INDEX_FTS_ONLY=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$TMP/repo" '
        f"timeout --kill-after=30 {LEG_TIMEOUT}s "
        '"$VENV/bin/python" -m pytest tests '
        f"--timeout={PER_TEST_TIMEOUT} "
        '--basetemp="$TMP/basetemp" --junitxml="$TMP/junit.xml"\n'
        "RC=$?\n"
        "set -e\n"
        '"$VENV/bin/python" "$TMP/tripwire.py" '
        '"$REAL_HOME/Documents/Life-Index" > "$TMP/tripwire-after"\n'
        'if cmp -s "$TMP/tripwire-before" "$TMP/tripwire-after"; then\n'
        '  echo "' + TRIPWIRE_PREFIX + 'unchanged ($(cat "$TMP/tripwire-before"))"\n'
        "else\n"
        '  echo "' + TRIPWIRE_PREFIX + 'CHANGED: $(cat "$TMP/tripwire-before") -> '
        '$(cat "$TMP/tripwire-after")"\n'
        "  RC=201\n"
        "fi\n"
        'if [ -s "$TMP/junit.xml" ]; then\n'
        '  "$VENV/bin/python" "$TMP/leg_result.py" "$TMP/junit.xml"\n'
        "fi\n"
        'exit "$RC"\n'
    )


def dependency_hash(pyproject: Path) -> str | None:
    """Hash the dependency sections of pyproject.toml.

    The WSL environment records this hash when --setup-linux builds it; a
    mismatch means the environment no longer matches the project.
    """
    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return None
    project = data.get("project", {})
    payload = {
        "dependencies": project.get("dependencies", []),
        "optional-dependencies": project.get("optional-dependencies", {}),
        "setup-extra-plugins": list(WSL_EXTRA_PLUGINS),
    }
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def run_linux_leg(sha: str, leg_temp: Path, expected_hash: str, log_path: Path) -> LegResult:
    """The Linux leg: Python 3.11 inside WSL, on its own clone of the SHA."""
    leg = LegResult(platform="linux")
    leg.log_path = log_path
    probe = run_wsl(["bash", "-c", linux_env_probe_script()], timeout=PROBE_TIMEOUT)
    if probe.returncode != 0:
        leg.detail = f"WSL probe failed (is WSL installed?): {probe.stderr.strip()}"
        return leg
    probe_lines = [line for line in probe.stdout.splitlines() if line.strip()]
    recorded = probe_lines[-1] if probe_lines else ""
    if probe_lines and probe_lines[0].startswith("MISSING-VENV"):
        leg.detail = (
            f"the WSL Python 3.11 gate environment is missing; create it with: {SETUP_HINT}"
        )
        return leg
    if probe_lines and probe_lines[0].startswith("WRONG-PYTHON"):
        leg.detail = (
            f"the WSL gate environment is not Python 3.11 ({probe_lines[0]}); "
            f"rebuild it with: {SETUP_HINT}"
        )
        return leg
    if recorded != expected_hash:
        leg.detail = (
            "the WSL Python 3.11 gate environment is stale (dependency hash "
            f"mismatch); refresh it with: {SETUP_HINT}"
        )
        return leg

    git_common = git_common_dir()
    if git_common is None:
        leg.detail = "cannot resolve the repository's common Git directory"
        return leg
    translated = run_wsl(["wslpath", "-a", str(git_common)], timeout=PROBE_TIMEOUT)
    if translated.returncode != 0 or not translated.stdout.strip():
        leg.detail = f"wslpath failed to translate {git_common}: {translated.stderr.strip()}"
        return leg

    script = linux_leg_script(sha, translated.stdout.strip())
    proc = run_wsl(["bash", "-c", script], timeout=LEG_TIMEOUT + 300)
    log_path.write_text(proc.stdout + "\n" + proc.stderr, encoding="utf-8", errors="replace")
    leg.ran = not proc.detail
    if proc.detail:
        leg.detail = proc.detail
        return leg

    result_json = None
    for line in proc.stdout.splitlines():
        if line.startswith(PYTHON_PREFIX):
            leg.python_version = line.removeprefix(PYTHON_PREFIX).removeprefix("Python ").strip()
        elif line.startswith(TRIPWIRE_PREFIX):
            leg.tripwire = line.removeprefix(TRIPWIRE_PREFIX).strip()
        elif line.startswith(RESULT_PREFIX):
            try:
                result_json = json.loads(line.removeprefix(RESULT_PREFIX))
            except json.JSONDecodeError:
                result_json = None
    ok = _record_counts(leg, result_json)
    tripwire_ok = leg.tripwire.startswith("unchanged")
    if proc.returncode != 0 and ok:
        leg.detail = f"pytest exited {proc.returncode}"
        ok = False
    leg.passed = proc.returncode == 0 and ok and tripwire_ok
    if not leg.tripwire:
        leg.tripwire = "unknown (no tripwire marker)"
    return leg


# ── Preflight helpers ────────────────────────────────────────────────────────


def missing_tools() -> list[str]:
    missing = []
    for name in REQUIRED_TOOLS:
        if importlib.util.find_spec(name) is None:
            missing.append(name)
    return missing


def hooks_dir() -> Path | None:
    """The Git hooks directory of this clone (overridable seam for tests)."""
    proc = git("rev-parse", "--git-path", "hooks")
    if proc.returncode != 0:
        return None
    raw = proc.stdout.strip()
    if not raw:
        return None
    path = Path(raw)
    return path if path.is_absolute() else REPO_ROOT / path


def prepush_hook_path() -> Path | None:
    hooks = hooks_dir()
    return None if hooks is None else hooks / "pre-push"


def hook_install_hint() -> str:
    return "install it with: python scripts/gate.py --install-hook"


def latest_backstop_run() -> str:
    """One line about the latest backstop run on main (advisory, never fails)."""
    if shutil.which("gh") is None:
        return "gh is not installed; the online backstop status is unknown"
    proc = run_process(
        [
            "gh",
            "run",
            "list",
            "--workflow",
            "backstop.yml",
            "--branch",
            "main",
            "--limit",
            "1",
            "--json",
            "status,conclusion,headSha,createdAt,url",
        ],
        cwd=REPO_ROOT,
        timeout=PROBE_TIMEOUT,
    )
    if proc.returncode != 0:
        return "gh could not list backstop runs; the online backstop status is unknown"
    try:
        entries = json.loads(proc.stdout)
        entry = entries[0] if entries else None
    except (json.JSONDecodeError, TypeError):
        entry = None
    if not entry:
        return "no backstop runs on main were found"
    conclusion = entry.get("conclusion")
    url = entry.get("url", "")
    if conclusion in ("failure", "startup_failure", "cancelled", "timed_out"):
        return f"WARNING: the latest backstop run on main is {conclusion!r}: {url}"
    if conclusion is None:
        return f"latest backstop run on main is in progress (status={entry.get('status')}): {url}"
    return f"latest backstop run on main: {conclusion} ({url})"


# ── Stage bookkeeping and the run itself ─────────────────────────────────────


@dataclass
class StageOutcome:
    key: str
    label: str
    status: str  # "pass" | "fail" | "skip"
    duration: float
    detail: str = ""


@dataclass
class GateOptions:
    base: str | None
    head: str
    fast: bool
    no_linux: bool
    from_hook: bool
    push_records: list[PushRecord] = field(default_factory=list)
    remote_name: str | None = None


@dataclass
class GateRun:
    options: GateOptions
    stages: list[StageOutcome] = field(default_factory=list)
    legs: list[LegResult] = field(default_factory=list)
    sha: str = ""
    outgoing: list[str] = field(default_factory=list)
    linux_leg_status: str = "run"  # run | skipped | failed | native-host
    interrupted: bool = False
    notes: list[str] = field(default_factory=list)
    run_dir: Path = REPORT_DIR
    _scratch: Path | None = None

    # -- stage helpers ------------------------------------------------------

    def _record(self, key: str, label: str, status: str, duration: float, detail: str = "") -> None:
        self.stages.append(
            StageOutcome(
                key=key, label=label, status=status, duration=round(duration, 1), detail=detail
            )
        )
        marker = {"pass": "+", "fail": "x", "skip": "-"}[status]
        print(f"  [{marker}] {key:<28} {status:<4} {duration:7.1f}s  {detail}".rstrip())

    def _failed(self) -> bool:
        return any(stage.status == "fail" for stage in self.stages)

    def scratch_dir(self) -> Path:
        if self._scratch is None:
            self._scratch = Path(tempfile.mkdtemp(prefix="life-index-gate-scratch-"))
        return self._scratch

    # -- stages -------------------------------------------------------------

    def _resolve_outgoing(self, head_sha: str) -> tuple[list[str], str]:
        """The commits this run is publishing, oldest first (C2)."""
        if self.options.from_hook:
            return push_record_outgoing(self.options.push_records, self.options.remote_name)
        if self.options.base:
            if not is_ancestor(self.options.base, head_sha):
                return [], (
                    f"--base {self.options.base} is not an ancestor of the candidate; "
                    "pass the last commit already on the remote"
                )
            commits = rev_list_outgoing(head_sha, [self.options.base])
        else:
            origin_main = resolve_full_sha("origin/main")
            if origin_main is None:
                return [], (
                    "origin/main cannot be resolved in this clone; "
                    "pass --base <sha> with the last commit already on the remote"
                )
            commits = rev_list_outgoing(head_sha, [origin_main])
        if commits is None:
            return [], (
                "git rev-list failed while resolving the outgoing commits; "
                "fetch the remote first"
            )
        return commits, ""

    def preflight(self) -> bool:
        started = time.monotonic()
        problems: list[str] = []

        head_sha = resolve_full_sha(self.options.head)
        if head_sha is None:
            problems.append(f"cannot resolve candidate ref {self.options.head!r} to a commit")
        else:
            self.sha = head_sha
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            self.run_dir = REPORT_DIR / f"{self.sha}-{stamp}-{os.getpid()}"
            commits, error = self._resolve_outgoing(head_sha)
            if error:
                problems.append(error)
            elif not commits:
                # In hook mode an empty list is legitimate for a candidate the
                # caller chose to gate anyway (F3: a main record with nothing
                # new still runs the full gate); run_from_hook skips the
                # no-op candidates before a run is created. A manual run must
                # never scan nothing and report success.
                if not self.options.from_hook:
                    problems.append(
                        "no commits are going out (the candidate adds nothing over the "
                        "base): the diff scans would inspect nothing and report "
                        "success. Pass --base <sha> with an ancestor that is already "
                        "on the remote"
                    )
            else:
                self.outgoing = commits

        missing = missing_tools()
        if missing:
            problems.append(
                "missing Python dependencies for the gate: "
                + ", ".join(missing)
                + "; install the project dev/test environment"
            )

        status = git("status", "--porcelain")
        if status.returncode == 0 and status.stdout.strip():
            self.notes.append(
                "the working tree has uncommitted changes; they are NOT part of the candidate"
            )

        hook = prepush_hook_path()
        if hook is None or not hook.is_file() or hook.read_text(encoding="utf-8") != HOOK_TEMPLATE:
            self.notes.append(
                "the gate's pre-push hook is not installed in this clone; " + hook_install_hint()
            )

        if not self.options.fast:
            self.notes.append(latest_backstop_run())

        for note in self.notes:
            print(f"  note: {note}")

        ok = not problems
        self._record(
            "preflight",
            "resolve candidate, outgoing commits, tools",
            "pass" if ok else "fail",
            time.monotonic() - started,
            "; ".join(problems),
        )
        return ok

    def export_candidate(self) -> Path | None:
        started = time.monotonic()
        workdir = Path(tempfile.mkdtemp(prefix="life-index-gate-"))
        try:
            proc = git("worktree", "add", "--detach", str(workdir), self.sha)
        except BaseException:
            shutil.rmtree(workdir, ignore_errors=True)
            raise
        if proc.returncode != 0:
            shutil.rmtree(workdir, ignore_errors=True)
            self._record(
                "export",
                "detached worktree of the candidate",
                "fail",
                time.monotonic() - started,
                (proc.stderr.strip() or proc.detail or "git worktree add failed")[:300],
            )
            return None
        self._record(
            "export",
            "detached worktree of the candidate",
            "pass",
            time.monotonic() - started,
            str(workdir),
        )
        return workdir

    def _static_env(self, export: Path) -> dict[str, str]:
        scratch = self.scratch_dir()
        home = scratch / "home"
        data = scratch / "data"
        home.mkdir(parents=True, exist_ok=True)
        data.mkdir(parents=True, exist_ok=True)
        return sanitized_env(home, data, export)

    def run_static(self, export: Path) -> bool:
        env = self._static_env(export)
        for check in static_checks(self.outgoing):
            started = time.monotonic()
            if "--per-commit" in check.argv:
                ok, detail = self._run_per_commit_scans(check, env, export)
                duration = time.monotonic() - started
                if not ok:
                    self._record(check.key, check.label, "fail", duration, detail)
                    return False  # stop at the first failing stage
                self._record(check.key, check.label, "pass", duration, detail)
                continue
            proc = run_process(check.argv, cwd=export, env=env, timeout=CHECK_TIMEOUT)
            duration = time.monotonic() - started
            if proc.detail:
                self._record(check.key, check.label, "fail", duration, proc.detail)
                return False
            if proc.returncode != 0:
                tail = _tail(proc.stdout + "\n" + proc.stderr)
                self._record(check.key, check.label, "fail", duration, tail)
                return False
            self._record(check.key, check.label, "pass", duration)
        return True

    def _run_per_commit_scans(
        self, check: Check, env: dict[str, str], export: Path
    ) -> tuple[bool, str]:
        """One public-diff scan per outgoing commit (C2).

        The scans run inside the exported candidate, so the scripts and the
        public-surface allowlist they load come from the candidate, never
        from an uncommitted working tree.
        """
        script = check.argv[-2].rsplit("/", 1)[-1]
        for commit in self.outgoing:
            parent = first_parent(commit)
            proc = run_process(
                scan_check(script, commit, parent), cwd=export, env=env, timeout=CHECK_TIMEOUT
            )
            if proc.detail:
                return False, f"{commit[:12]}: {proc.detail}"
            if proc.returncode != 0:
                tail = _tail(proc.stdout + "\n" + proc.stderr)
                return False, f"first failing commit {commit[:12]}: {tail}"
        if not self.outgoing:
            return True, "0 commits scanned (nothing new is published)"
        return True, f"{len(self.outgoing)} commits scanned"

    def run_sentinel(self, export: Path) -> bool:
        check = sentinel_check()
        started = time.monotonic()
        proc = run_process(
            check.argv, cwd=export, env=self._static_env(export), timeout=CHECK_TIMEOUT
        )
        duration = time.monotonic() - started
        if proc.returncode != 0:
            tail = _tail(proc.stdout + "\n" + proc.stderr)
            self._record(check.key, check.label, "fail", duration, tail)
            return False
        self._record(check.key, check.label, "pass", duration)
        return True

    def run_legs(self, export: Path) -> None:
        """Run the test legs; both legs always finish once started."""
        self.run_dir.mkdir(parents=True, exist_ok=True)
        leg_temps: list[Path] = []
        jobs: dict[str, Callable[[], LegResult]] = {}

        native_label = "windows" if os.name == "nt" else "native"
        native_temp = Path(tempfile.mkdtemp(prefix="life-index-gate-native-"))
        leg_temps.append(native_temp)

        def native_job() -> LegResult:
            return run_native_leg(
                export,
                native_temp,
                coverage=True,
                log_path=self.run_dir / f"{native_label}.log",
            )

        jobs[native_label] = native_job

        linux_failed_early: LegResult | None = None
        if os.name == "nt":
            if self.options.no_linux:
                self.linux_leg_status = "skipped"
                self.legs.append(LegResult(platform="linux", detail="skipped via --no-linux"))
            else:
                linux_temp = Path(tempfile.mkdtemp(prefix="life-index-gate-linux-"))
                leg_temps.append(linux_temp)
                expected = dependency_hash(export / "pyproject.toml")
                if expected is None:
                    # C4: an unhashable candidate is a failed stage, not a skip.
                    self.linux_leg_status = "failed"
                    linux_failed_early = LegResult(
                        platform="linux",
                        detail="cannot hash the candidate's pyproject.toml for the Linux leg",
                    )
                else:
                    self.linux_leg_status = "run"

                    def linux_job() -> LegResult:
                        return run_linux_leg(
                            self.sha,
                            linux_temp,
                            expected,
                            log_path=self.run_dir / "linux.log",
                        )

                    jobs["linux"] = linux_job
        else:
            self.linux_leg_status = "native-host"

        def timed(job: Callable[[], LegResult]) -> Callable[[], LegResult]:
            def run_and_time() -> LegResult:
                started = time.monotonic()
                leg = job()
                leg.duration = time.monotonic() - started
                return leg

            return run_and_time

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=len(jobs)) as pool:
                futures = {label: pool.submit(timed(fn)) for label, fn in jobs.items()}
                results = {label: future.result() for label, future in futures.items()}
        finally:
            for temp_dir in leg_temps:
                shutil.rmtree(temp_dir, ignore_errors=True)

        if linux_failed_early is not None:
            results["linux"] = linux_failed_early

        order = ["windows", "native", "linux"]
        for label in sorted(results, key=order.index):
            leg = results[label]
            self.legs.append(leg)
            self._record(
                f"tests:{leg.platform}",
                f"pytest on the {leg.platform} leg",
                "pass" if leg.passed else "fail",
                leg.duration,
                _leg_detail(leg),
            )

    # -- verdict ------------------------------------------------------------

    def complete(self) -> bool:
        """True only when every expected leg ran and passed and no stage failed."""
        if self._failed():
            return False
        if self.options.fast:
            return True
        return all(leg.passed for leg in self.legs)

    def verdict(self, exit_code: int) -> None:
        failed = [stage.key for stage in self.stages if stage.status == "fail"]
        outcome = "PASS" if exit_code == 0 else "FAIL"
        mode = "fast (static checks only)" if self.options.fast else "full"

        print()
        print("=" * 70)
        print(f"Life Index gate verdict: {outcome}  (mode: {mode})")
        if self.sha:
            print(f"Candidate: {self.sha}")
            print(
                f"Outgoing commits scanned: {len(self.outgoing)}"
                + (f" ({self.outgoing[0][:12]}..{self.outgoing[-1][:12]})" if self.outgoing else "")
            )
        if self.linux_leg_status == "skipped":
            print()
            print("!! The Linux leg was SKIPPED (--no-linux).")
            print("!! The candidate was NOT tested on Linux/Python 3.11.")
            print("!! A push to main should run the full gate without --no-linux.")
        elif self.linux_leg_status == "native-host":
            print(
                "Note: the gate runs on a non-Windows host, so there is no second "
                "leg; the single native leg ran the inventory."
            )
        for leg in self.legs:
            tripwire = f" | tripwire {leg.tripwire}" if leg.tripwire else ""
            print(
                f"  leg {leg.platform:<8} {'PASS' if leg.passed else 'FAIL'}"
                f"  {leg.duration:7.1f}s{tripwire}"
            )
        print(f"  complete: {self.complete()}")
        if failed:
            print(f"Failed stages: {', '.join(failed)}")
        for leg in self.legs:
            if leg.ran and not leg.passed and leg.log_path is not None:
                print(f"Leg log: {leg.log_path}")
        if self.sha:
            payload = json.dumps(self.as_dict(exit_code), indent=2) + "\n"
            self.run_dir.mkdir(parents=True, exist_ok=True)
            (self.run_dir / "verdict.json").write_text(payload, encoding="utf-8")
            latest = REPORT_DIR / f"{self.sha}.json"
            latest.parent.mkdir(parents=True, exist_ok=True)
            latest.write_text(payload, encoding="utf-8")
            print(f"Verdict JSON: {latest} (run evidence: {self.run_dir})")
        print("=" * 70)

    def as_dict(self, exit_code: int) -> dict[str, object]:
        return {
            "gate": "life-index-gate",
            "mode": "fast" if self.options.fast else "full",
            "outcome": "pass" if exit_code == 0 else "fail",
            "exit_code": exit_code,
            "complete": self.complete(),
            "interrupted": self.interrupted,
            "candidate_sha": self.sha,
            "outgoing_commits": self.outgoing,
            "linux_leg": self.linux_leg_status,
            "notes": self.notes,
            "stages": [stage.__dict__ for stage in self.stages],
            "legs": [
                {
                    "platform": leg.platform,
                    "python": leg.python_version,
                    "ran": leg.ran,
                    "passed": leg.passed,
                    "tests": leg.tests,
                    "passed_count": leg.passed_count,
                    "failed_count": leg.failed_count,
                    "skipped_count": leg.skipped_count,
                    "detail": leg.detail,
                    "duration": round(leg.duration, 1),
                    "tripwire": leg.tripwire,
                    "log": str(leg.log_path) if leg.log_path else None,
                }
                for leg in self.legs
            ],
        }

    # -- orchestration ------------------------------------------------------

    def run(self) -> int:
        print("Life Index gate")
        print(f"Repo: {REPO_ROOT}")
        export: Path | None = None
        exit_code = 1
        try:
            if self.preflight():
                export = self.export_candidate()
            if export is not None and not self._failed():
                if self.run_static(export):
                    if self.options.fast:
                        exit_code = 0
                    elif self.run_sentinel(export):
                        self.run_legs(export)
                        exit_code = 0 if not self._failed() else 1
        except KeyboardInterrupt:
            self.interrupted = True
            print()
            print("Interrupted (Ctrl-C).")
            exit_code = 130
        finally:
            if export is not None:
                _remove_worktree(export)
            if self._scratch is not None:
                shutil.rmtree(self._scratch, ignore_errors=True)
            self.verdict(exit_code)
        return exit_code


def _tail(text: str, lines: int = 15) -> str:
    kept = [line for line in text.splitlines() if line.strip()][-lines:]
    return " | ".join(kept)[:400]


def _leg_detail(leg: LegResult) -> str:
    if not leg.ran:
        return leg.detail or "the leg did not run"
    counts = (
        f"{leg.passed_count} passed, {leg.failed_count} failed, {leg.skipped_count} skipped"
        if leg.tests is not None
        else "no counts"
    )
    python_part = f"python {leg.python_version}" if leg.python_version else ""
    parts = [part for part in (python_part, counts, leg.detail) if part]
    return ", ".join(parts)


def _remove_worktree(path: Path) -> None:
    """Remove exactly the worktree this gate created; no repository-wide
    prune, which could delete the registration of an unrelated, temporarily
    missing worktree."""
    run_process(["git", "worktree", "remove", "--force", str(path)], cwd=REPO_ROOT, timeout=300)
    shutil.rmtree(path, ignore_errors=True)


# ── --setup-linux: the only mode that downloads ─────────────────────────────


def setup_linux() -> int:
    if os.name != "nt":
        print("--setup-linux prepares the WSL environment and only makes sense on Windows.")
        return 2
    sha = resolve_full_sha("HEAD")
    if sha is None:
        print("cannot resolve HEAD; run --setup-linux from a healthy clone")
        return 1
    expected = dependency_hash(REPO_ROOT / "pyproject.toml")
    if expected is None:
        print("cannot hash pyproject.toml")
        return 1
    git_common = git_common_dir()
    if git_common is None:
        print("cannot resolve the repository's common Git directory")
        return 1
    translated = run_wsl(["wslpath", "-a", str(git_common)], timeout=PROBE_TIMEOUT)
    if translated.returncode != 0 or not translated.stdout.strip():
        print(f"wslpath failed to translate {git_common}: {translated.stderr.strip()}")
        return 1

    quoted_source = translated.stdout.strip().replace("'", "'\\''")
    script = (
        "set -euo pipefail\n"
        f'BASE="{WSL_BASE}"\n'
        # wsl.exe --exec gives a non-login shell: a user-installed interpreter
        # under ~/.local/bin is not on PATH there.
        'PY311="$(command -v python3.11 || true)"\n'
        '[ -n "$PY311" ] || PY311="$HOME/.local/bin/python3.11"\n'
        '[ -x "$PY311" ] || { echo "python3.11 was not found in WSL"; exit 3; }\n'
        'mkdir -p "$BASE"\n'
        'rm -f "$BASE/py311-deps.sha256"\n'
        # An existing environment is refreshed in place, so a slow network
        # does not have to download everything again.
        '[ -x "$BASE/venv-py311/bin/python" ] || "$PY311" -m venv "$BASE/venv-py311"\n'
        f'SRC="$(mktemp -d {WSL_WORK_PARENT}/life-index-gate-setup.XXXXXX)"\n'
        """trap 'rm -rf "$SRC"' EXIT\n"""
        "git -c safe.directory='*' clone --quiet --shared --no-checkout "
        f"'{quoted_source}' \"$SRC/repo\"\n"
        "git -C \"$SRC/repo\" -c safe.directory='*' checkout --quiet "
        f"--detach '{sha}'\n"
        'PIP=("$BASE/venv-py311/bin/python" -m pip install --default-timeout 120 '
        "--retries 10 --disable-pip-version-check)\n"
        '"${PIP[@]}" setuptools wheel ' + " ".join(WSL_EXTRA_PLUGINS) + "\n"
        '"${PIP[@]}" -e "$SRC/repo[dev]"\n'
        # The shared environment keeps only dependencies: the project itself
        # is uninstalled, so a gate run can never test a stale shared
        # install. Runs point PYTHONPATH at the clone under test instead.
        '"$BASE/venv-py311/bin/python" -m pip uninstall --yes life-index || true\n'
        f"printf '%s\\n' '{expected}' > \"$BASE/py311-deps.sha256\"\n"
        'echo "Linux gate environment ready."\n'
    )
    print(f"Setting up the WSL Python 3.11 gate environment ({WSL_VENV})...")
    print("This installs packages (the only gate mode that downloads).")
    proc = run_wsl(["bash", "-c", script], timeout=None, capture=False)
    if proc.returncode != 0:
        print()
        print(f"Setup failed with exit code {proc.returncode}.")
        print("If python3.11 is missing in WSL, install it first, e.g.:")
        print("  sudo apt install python3.11 python3.11-venv")
        return 1
    print(f"Dependency hash recorded: {expected}")
    return 0


# ── --list ──────────────────────────────────────────────────────────────────


def print_inventory(*, fast: bool, no_linux: bool) -> int:
    checks = static_checks(())
    print("Life Index gate - inventory" + (" (fast: static checks only)" if fast else ""))
    number = 1
    print(f"  {number}. preflight           resolve candidate, outgoing commits, tools")
    number += 1
    print(f"  {number}. export              detached worktree of the candidate commit")
    for check in checks:
        number += 1
        shown = " ".join(check.argv[1:]).replace(
            " --per-commit", " --base <first parent> --head <commit>"
        )
        print(f"  {number}. {check.key:<22} {shown}")
    if not fast:
        number += 1
        check = sentinel_check()
        print(f"  {number}. {check.key:<22} {' '.join(check.argv[1:])}")
        number += 1
        native = "windows" if os.name == "nt" else "native"
        argv = pytest_argv(Path("<junit>"), Path("<basetemp>"), coverage=True)
        print(f"  {number}. tests:{native:<17} {' '.join(argv[1:])}")
        if os.name == "nt":
            number += 1
            if no_linux:
                print(f"  {number}. tests:linux           SKIPPED via --no-linux")
            else:
                print(
                    f"  {number}. tests:linux           WSL Python 3.11 ({WSL_VENV}),"
                    f" env -i: python -m pytest tests --timeout={PER_TEST_TIMEOUT}"
                )
        else:
            print("         (single-leg host: the gate runs on Linux/macOS, no WSL leg)")
    number += 1
    print(f"  {number}. verdict             summary + JSON report per run")
    return 0


# ── Hook management and hook mode (C1) ──────────────────────────────────────


def install_hook(*, force: bool) -> int:
    path = prepush_hook_path()
    if path is None:
        print("cannot resolve this clone's hooks directory")
        return 1
    if path.exists() and path.read_text(encoding="utf-8") != HOOK_TEMPLATE and not force:
        print(f"refusing to overwrite {path}: it was not written by the gate.")
        print("Re-run with --force to replace it.")
        return 2
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(HOOK_TEMPLATE, encoding="utf-8", newline="\n")
    try:
        path.chmod(0o755)
    except OSError:
        pass
    print(f"Installed the gate's pre-push hook: {path}")
    return 0


def check_hook() -> int:
    path = prepush_hook_path()
    if path is not None and path.is_file() and path.read_text(encoding="utf-8") == HOOK_TEMPLATE:
        print("pre-push hook: installed (gate-managed)")
        return 0
    print("pre-push hook: NOT installed (or not the gate's version) in this clone")
    print(hook_install_hint())
    return 1


def run_from_hook(remote_name: str | None, remote_url: str | None, *, no_linux: bool) -> int:
    """Gate every ref Git is pushing, at the strongest mode it needs."""
    del remote_url  # part of the hook's argv shape; not used by the gate
    try:
        records = parse_push_records(sys.stdin.read())
    except ValueError as error:
        print(f"pre-push: {error}")
        return 1
    records = [record for record in records if not record.is_deletion]
    if not records:
        print("pre-push: nothing to push; allowing.")
        return 0

    candidates: dict[str, list[PushRecord]] = {}
    for record in records:
        candidates.setdefault(record.local_sha, []).append(record)

    overall = 0
    for sha, recs in candidates.items():
        full = any(record.remote_ref == MAIN_BRANCH_REF for record in recs)
        refs = ", ".join(record.remote_ref for record in recs)
        outgoing, outgoing_error = push_record_outgoing(recs, remote_name)
        if outgoing_error:
            print(f"pre-push: {outgoing_error}")
            overall = 1
            continue
        if not outgoing and not full:
            # F3: a ref that publishes no new commit (a tag on an already
            # published commit, a new branch created at a published commit)
            # must not block the push; only main is gated regardless.
            print(f"refs {refs} publish no new commit; allowing without a gate run.")
            continue
        print()
        print(
            f"=== gating candidate {sha[:12]} for {refs} (mode: {'full' if full else 'fast'}) ==="
        )
        run = GateRun(
            options=GateOptions(
                base=None,
                head=sha,
                fast=not full,
                no_linux=no_linux,
                from_hook=True,
                push_records=recs,
                remote_name=remote_name,
            )
        )
        code = run.run()
        if code == 130:
            return 130
        if code != 0:
            overall = 1
    return overall


# ── entry point ─────────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--base",
        help="Base ref of the outgoing range: must be an ancestor of the candidate "
        "(default in hook mode: the push records; else origin/main)",
    )
    parser.add_argument("--head", default="HEAD", help="Candidate ref (default HEAD)")
    parser.add_argument("--fast", action="store_true", help="Static checks only, no tests")
    parser.add_argument(
        "--no-linux",
        action="store_true",
        help="Skip the WSL Linux leg (stated loudly in the verdict)",
    )
    parser.add_argument("--list", action="store_true", help="Print the inventory and exit")
    parser.add_argument(
        "--setup-linux",
        action="store_true",
        help="Create or refresh the WSL Python 3.11 environment (downloads)",
    )
    parser.add_argument(
        "--from-hook",
        action="store_true",
        help="Gate a push: read every stdin push record, never PRE_COMMIT_* or --base/--head",
    )
    parser.add_argument(
        "--install-hook",
        action="store_true",
        help="Install the gate's native pre-push hook into this clone",
    )
    parser.add_argument(
        "--check-hook",
        action="store_true",
        help="Exit non-zero when the gate's pre-push hook is not installed",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="With --install-hook: overwrite a hook the gate did not write",
    )
    parser.add_argument("remote_name", nargs="?", help=argparse.SUPPRESS)
    parser.add_argument("remote_url", nargs="?", help=argparse.SUPPRESS)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.list:
        return print_inventory(fast=args.fast, no_linux=args.no_linux)
    if args.install_hook:
        return install_hook(force=args.force)
    if args.check_hook:
        return check_hook()
    if args.setup_linux:
        return setup_linux()

    no_linux = args.no_linux
    if no_linux and os.name != "nt":
        print("--no-linux only makes sense on Windows: on this host there is no second leg.")
        return 2

    if args.from_hook:
        if args.base or args.head != "HEAD":
            print(
                "--from-hook reads its range from Git's stdin records; do not pass --base/--head."
            )
            return 2
        return run_from_hook(args.remote_name, args.remote_url, no_linux=no_linux)

    run = GateRun(
        options=GateOptions(
            base=args.base,
            head=args.head,
            fast=args.fast,
            no_linux=no_linux,
            from_hook=False,
        )
    )
    return run.run()


if __name__ == "__main__":
    raise SystemExit(main())
