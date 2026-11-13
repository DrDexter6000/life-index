"""Unit tests for the local gate (scripts/gate.py).

Subprocess execution is replaced by a recorder: every external command the
gate spawns (git, the static checks, pytest, wsl.exe, gh) goes through the
``run_process`` seam, which these tests swap for a scripted recorder. No
real subprocess, no real data directory, no real WSL is touched. The tests
are platform-independent (C6): native-leg assertions work on Windows and
Linux, Windows-only cases are explicitly marked, and one test pins that
``--no-linux`` is refused elsewhere.
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
GATE_PATH = REPO_ROOT / "scripts" / "gate.py"

HEAD_SHA = "a" * 40
MAIN_SHA = "b" * 40
C_OLD = "1" * 40  # the older of the two outgoing commits
FEATURE_SHA = "d" * 40
TAG_SHA = "e" * 40
REMOTE_SHA = "f" * 40
ZERO_SHA = "0" * 40

EXPORT_PYPROJECT = (
    "[project]\n"
    'name = "life-index"\n'
    'version = "9.9.9"\n'
    'dependencies = ["pyyaml>=6.0"]\n'
    "\n"
    "[project.optional-dependencies]\n"
    'dev = ["pytest>=7.4.0"]\n'
)

STATIC_KEYS = [
    "static:black",
    "static:flake8",
    "static:mypy",
    "static:bandit",
    "static:doc-sync",
    "static:l2-no-llm",
    "static:public-diff-names",
    "static:public-surface-allowlist",
    "static:skill-mirror",
]

# The pinned argv of every non-scan static check: what would be executed,
# not the label it runs under.
PINNED_STATIC_ARGV = {
    "static:black": ("-m", "black", "--check", "--diff", "tools/"),
    "static:flake8": (
        "-m",
        "flake8",
        "tools/",
        "--count",
        "--max-complexity=40",
        "--max-line-length=100",
        "--show-source",
        "--statistics",
    ),
    "static:mypy": ("-m", "mypy", "tools/", "--ignore-missing-imports"),
    "static:bandit": ("-m", "bandit", "-r", "tools/", "-ll", "-c", "pyproject.toml"),
    "static:doc-sync": (".github/scripts/check_doc_sync.py",),
    "static:l2-no-llm": (".github/scripts/check_l2_no_llm.py",),
    "static:skill-mirror": ("scripts/sync_skill_artifacts.py", "--check"),
}

HOOK_STDIN_MAIN = f"refs/heads/main {HEAD_SHA} refs/heads/main {REMOTE_SHA}\n"


def native_platform() -> str:
    return "windows" if os.name == "nt" else "native"


def _full_native_run(gate):
    """A full run whose only test leg is the native one (platform-independent)."""
    if os.name == "nt":
        return run_gate(gate, "--no-linux")
    return gate.module.main(["--head", "HEAD"])


# ── The recorder: subprocess execution replaced ─────────────────────────────


@dataclass
class RecordedCall:
    argv: tuple[str, ...]
    cwd: str | None
    env: dict[str, str] | None


@dataclass
class GateRecorder:
    gate: object
    calls: list[RecordedCall] = field(default_factory=list)
    shas: dict[str, str] = field(
        default_factory=lambda: {"HEAD": HEAD_SHA, "origin/main": MAIN_SHA}
    )
    rev_lists: dict[str, list[str]] = field(default_factory=lambda: {None: [C_OLD, HEAD_SHA]})
    parents: dict[str, str] = field(default_factory=lambda: {C_OLD: MAIN_SHA, HEAD_SHA: C_OLD})
    ancestor_ok: bool = True
    rev_list_error: bool = False
    status_output: str = ""
    fail_black: bool = False
    interrupt_on_black: bool = False
    pytest_rc: int = 0
    junit: dict[str, int] = field(
        default_factory=lambda: {"tests": 3, "errors": 0, "failures": 0, "skipped": 0}
    )
    wsl_missing_venv: bool = False
    wsl_wrong_python: str | None = None
    wsl_recorded_hash: str | None = None  # None: answer with the hash the gate expects
    wsl_probe_rc: int = 0
    wsl_probe_stderr: str = ""
    linux_rc: int = 0
    linux_tripwire: str = "unchanged (files=7:abc123)"
    linux_result: dict[str, int] | None = None
    gh_output: str = ""
    gh_rc: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _export_dir: Path | None = None

    # -- recording ---------------------------------------------------------

    def __call__(self, argv, *, cwd=None, env=None, timeout=None, capture=True):  # noqa: ARG002
        argv = tuple(str(part) for part in argv)
        with self._lock:
            self.calls.append(RecordedCall(argv, None if cwd is None else str(cwd), env))
        return self._dispatch(argv)

    def with_argv(self, *fragments: str) -> list[RecordedCall]:
        wanted = [tuple(fragment.split()) for fragment in fragments]
        return [
            call
            for call in self.calls
            if any(all(part in call.argv for part in frag) for frag in wanted)
        ]

    # -- scripted answers ----------------------------------------------------

    def _dispatch(self, argv):
        gate = self.gate
        if argv[0] == "git":
            return self._git(argv)
        if argv[0] == "gh":
            return gate.ProcResult(self.gh_rc, self.gh_output)
        if argv[0] == "wsl.exe":
            return self._wsl(argv[2:])
        if self.interrupt_on_black and "-m" in argv and "black" in argv:
            raise KeyboardInterrupt
        if self.fail_black and "-m" in argv and "black" in argv:
            return gate.ProcResult(1, "", "would reformat tools/example.py")
        if "-m" in argv and "pytest" in argv:
            return self._pytest(argv)
        return gate.ProcResult(0)

    def _git(self, argv):
        gate = self.gate
        if argv[1] == "rev-parse":
            if "--verify" in argv:
                ref = argv[-1].removesuffix("^{commit}")
                if ref.endswith("^"):
                    parent = self.parents.get(ref[:-1])
                    if parent is None:
                        return gate.ProcResult(1)  # root commit: no first parent
                    return gate.ProcResult(0, parent + "\n")
                sha = self._resolve_ref(ref)
                if sha is None:
                    return gate.ProcResult(1)
                return gate.ProcResult(0, sha + "\n")
            if "--git-path" in argv:
                return gate.ProcResult(0, ".git/hooks\n")
            if "--git-common-dir" in argv:
                return gate.ProcResult(0, "D:/fake/repo/.git\n")
            return gate.ProcResult(0)
        if argv[1] == "rev-list":
            if self.rev_list_error:
                return gate.ProcResult(1, "", "fatal: bad revision")
            head = argv[3]  # after "rev-list --reverse"
            commits = self.rev_lists.get(head, self.rev_lists.get(None, []))
            return gate.ProcResult(0, "".join(commit + "\n" for commit in commits))
        if argv[1] == "merge-base" and "--is-ancestor" in argv:
            return gate.ProcResult(0 if self.ancestor_ok else 1)
        if argv[1] == "status":
            return gate.ProcResult(0, self.status_output)
        if argv[1] == "worktree" and argv[2] == "add":
            export = Path(argv[4])
            export.mkdir(parents=True, exist_ok=True)
            (export / "pyproject.toml").write_text(EXPORT_PYPROJECT, encoding="utf-8")
            self._export_dir = export
            return gate.ProcResult(0)
        return gate.ProcResult(0)

    def _resolve_ref(self, ref):
        if ref in self.shas:
            return self.shas[ref]
        if re.fullmatch(r"[0-9a-f]{40}", ref):
            return ref
        return None

    def _pytest(self, argv):
        gate = self.gate
        junit_path = next(
            part.removeprefix("--junitxml=") for part in argv if part.startswith("--junitxml=")
        )
        counts = self.junit
        body = (
            '<?xml version="1.0" encoding="utf-8"?>'
            "<testsuites>"
            f'<testsuite name="tests" tests="{counts["tests"]}" '
            f'errors="{counts["errors"]}" failures="{counts["failures"]}" '
            f'skipped="{counts["skipped"]}" time="1">'
            "</testsuite></testsuites>"
        )
        Path(junit_path).write_text(body, encoding="utf-8")
        return gate.ProcResult(self.pytest_rc, "3 passed in 0.1s\n")

    def _wsl(self, args):
        gate = self.gate
        if args[0] == "wslpath":
            return gate.ProcResult(0, "/mnt/c/fake/repo/.git\n")
        script = args[2]
        if "mktemp" in script:  # the Linux leg run script
            counts = self.linux_result or {
                "tests": 5,
                "errors": 0,
                "failures": 0,
                "skipped": 0,
                "passed": 5,
            }
            payload = dict(counts)
            payload.setdefault("passed", payload["tests"])
            stdout = (
                "GATE-LEG-PYTHON Python 3.11.9\n"
                + gate.TRIPWIRE_PREFIX
                + self.linux_tripwire
                + "\n"
                + gate.RESULT_PREFIX
                + json.dumps(payload)
                + "\n"
            )
            return gate.ProcResult(self.linux_rc, stdout)
        # the environment probe
        if self.wsl_probe_rc != 0:
            return gate.ProcResult(self.wsl_probe_rc, "", self.wsl_probe_stderr)
        if self.wsl_missing_venv:
            return gate.ProcResult(0, "MISSING-VENV\n")
        if self.wsl_wrong_python:
            return gate.ProcResult(0, f"WRONG-PYTHON {self.wsl_wrong_python}\n")
        recorded = self.wsl_recorded_hash
        if recorded is None and self._export_dir is not None:
            recorded = self.gate.dependency_hash(self._export_dir / "pyproject.toml")
        return gate.ProcResult(0, (recorded or "") + "\n")


@pytest.fixture
def gate(tmp_path, monkeypatch):
    """The gate module with subprocess execution replaced by the recorder."""
    spec = importlib.util.spec_from_file_location("life_index_gate_under_test", GATE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses resolve annotations via sys.modules
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "REPORT_DIR", tmp_path / "reports")
    recorder = GateRecorder(gate=module)
    real_run_process = module.run_process
    monkeypatch.setattr(module, "run_process", recorder)
    return SimpleNamespace(module=module, rec=recorder, tmp=tmp_path, real_run=real_run_process)


def run_gate(gate, *extra):
    return gate.module.main(["--base", MAIN_SHA, "--head", HEAD_SHA, *extra])


def latest_report(gate):
    reports = sorted((gate.tmp / "reports").glob("*.json"))
    assert reports, "no verdict JSON was written"
    return json.loads(reports[-1].read_text(encoding="utf-8"))


def run_stage(gate, key, report=None):
    report = report or latest_report(gate)
    stages = {stage["key"]: stage for stage in report["stages"]}
    return stages[key]


def feed_stdin(monkeypatch, text):
    monkeypatch.setattr(sys, "stdin", io.StringIO(text))


def _expected_hash(gate):
    export = gate.tmp / "export"
    export.mkdir()
    (export / "pyproject.toml").write_text(EXPORT_PYPROJECT, encoding="utf-8")
    gate.rec._export_dir = export
    expected = gate.module.dependency_hash(export / "pyproject.toml")
    assert expected is not None
    return expected


# ── The inventory: pinned on what would be executed ─────────────────────────


def test_static_inventory_argv_is_pinned(gate):
    checks = gate.module.static_checks(())
    assert [check.key for check in checks] == STATIC_KEYS
    by_key = {check.key: check.argv for check in checks}
    for key, pinned in PINNED_STATIC_ARGV.items():
        assert by_key[key][0] == sys.executable, key
        assert by_key[key][1:] == pinned, key
    # The scans are per-commit markers; their real argv is pinned below.
    assert by_key["static:public-diff-names"][1] == ".github/scripts/check_public_diff_names.py"
    assert by_key["static:public-surface-allowlist"][1] == (
        ".github/scripts/check_public_surface_allowlist.py"
    )
    sentinel = gate.module.sentinel_check()
    assert sentinel.argv == (sys.executable, ".github/scripts/run_public_core_assertions.py")


def test_scan_argv_pins_first_parent_and_commit(gate):
    argv = gate.module.scan_check("check_public_diff_names.py", HEAD_SHA, C_OLD)
    assert argv == [
        sys.executable,
        ".github/scripts/check_public_diff_names.py",
        "--base",
        C_OLD,
        "--head",
        HEAD_SHA,
    ]


def test_list_prints_the_full_inventory_in_order(gate, capsys):
    assert gate.module.main(["--list"]) == 0
    out = capsys.readouterr().out
    keys = ["preflight", "export", *STATIC_KEYS, "sentinel", f"tests:{native_platform()}"]
    if os.name == "nt":
        keys += ["tests:linux"]
    keys += ["verdict"]
    positions = [out.find(key) for key in keys]
    assert all(position != -1 for position in positions), out
    assert positions == sorted(positions), out


def test_fast_list_omits_the_test_legs(gate, capsys):
    gate.module.main(["--fast", "--list"])
    out = capsys.readouterr().out
    assert "static:black" in out
    assert "sentinel" not in out
    assert "tests:" not in out


# ── The checks run on the committed candidate, with per-commit scans (C2) ───


def test_checks_run_in_the_exported_worktree(gate):
    assert run_gate(gate, "--fast") == 0
    add_calls = gate.rec.with_argv("worktree add --detach")
    assert len(add_calls) == 1
    export_dir = Path(add_calls[0].argv[4])
    assert add_calls[0].argv[5] == HEAD_SHA
    assert export_dir != gate.module.REPO_ROOT
    static_calls = gate.rec.with_argv("black --check", "flake8", "mypy", "bandit")
    assert static_calls
    assert all(Path(call.cwd) == export_dir for call in static_calls)


def test_scans_run_once_per_outgoing_commit_with_first_parent_bases(gate):
    assert run_gate(gate, "--fast") == 0
    for script in (
        ".github/scripts/check_public_diff_names.py",
        ".github/scripts/check_public_surface_allowlist.py",
    ):
        calls = gate.rec.with_argv(script)
        assert len(calls) == 2, script  # one per outgoing commit
        bases = [call.argv[call.argv.index("--base") + 1] for call in calls]
        heads = [call.argv[call.argv.index("--head") + 1] for call in calls]
        assert heads == [C_OLD, HEAD_SHA]  # oldest first
        assert bases == [MAIN_SHA, C_OLD]  # each commit's first parent
    assert "2 commits scanned" in run_stage(gate, "static:public-diff-names")["detail"]


def test_root_commit_is_scanned_against_the_empty_tree(gate):
    gate.rec.rev_lists[None] = [HEAD_SHA]
    gate.rec.parents.pop(HEAD_SHA)  # HEAD_SHA is now a root commit
    assert run_gate(gate, "--fast") == 0
    call = gate.rec.with_argv(".github/scripts/check_public_diff_names.py")[0]
    assert call.argv[call.argv.index("--base") + 1] == gate.module.EMPTY_TREE_SHA


def test_hook_records_scan_the_commits_the_push_adds(gate, monkeypatch):
    feed_stdin(monkeypatch, HOOK_STDIN_MAIN)
    assert gate.module.main(["--from-hook", "origin", "https://example/repo.git"]) == 0
    rev_list = gate.rec.with_argv("rev-list --reverse")[0]
    assert rev_list.argv[3] == HEAD_SHA
    assert rev_list.argv[-1] == REMOTE_SHA  # --not <remote sha>


def test_new_remote_ref_scans_against_the_remote_tracking_refs(gate, monkeypatch):
    feed_stdin(
        monkeypatch,
        f"refs/heads/feature {FEATURE_SHA} refs/heads/feature {ZERO_SHA}\n",
    )
    assert gate.module.main(["--from-hook", "upstream"]) == 0
    rev_list = gate.rec.with_argv("rev-list --reverse")[0]
    assert rev_list.argv[-1] == "--remotes=upstream"


def test_manual_run_scans_against_origin_main(gate):
    assert gate.module.main(["--fast", "--head", "HEAD"]) == 0
    rev_list = gate.rec.with_argv("rev-list --reverse")[0]
    assert rev_list.argv[-1] == MAIN_SHA


def test_empty_outgoing_list_is_a_failure(gate, capsys):
    gate.rec.rev_lists[None] = []
    assert run_gate(gate, "--fast") == 1
    assert "--base" in capsys.readouterr().out
    assert run_stage(gate, "preflight")["status"] == "fail"


def test_base_must_be_an_ancestor(gate, capsys):
    gate.rec.ancestor_ok = False
    assert run_gate(gate, "--fast") == 1
    assert "not an ancestor" in capsys.readouterr().out


def test_static_stage_stops_at_the_first_failure(gate):
    gate.rec.fail_black = True
    assert run_gate(gate, "--fast") == 1
    assert gate.rec.with_argv("black --check")
    assert not gate.rec.with_argv("flake8")  # never reached
    assert not gate.rec.with_argv("pytest")


# ── F1: Git's own environment never reaches candidate code ──────────────────


def test_gates_own_git_calls_keep_the_callers_environment(gate, monkeypatch):
    """The git() seam addresses the pushing repository on purpose: its calls
    run without a stripped environment, while candidate code gets the
    sanitized one."""
    for name, value in HOSTILE_VARS.items():
        monkeypatch.setenv(name, value)
    assert run_gate(gate, "--fast") == 0
    for fragment in ("rev-list --reverse", "worktree add --detach", "worktree remove"):
        calls = gate.rec.with_argv(fragment)
        assert calls, fragment
        assert all(call.env is None for call in calls), fragment


# ── F2: the per-commit scans run the candidate's scripts and allowlist ──────


def test_scans_run_inside_the_exported_candidate(gate):
    """cwd must be the export, so the scripts and the public-surface
    allowlist they load come from the candidate, not the working tree."""
    assert run_gate(gate, "--fast") == 0
    export_dir = Path(gate.rec.with_argv("worktree add --detach")[0].argv[4])
    scans = gate.rec.with_argv(
        ".github/scripts/check_public_diff_names.py",
        ".github/scripts/check_public_surface_allowlist.py",
    )
    assert len(scans) == 4  # two scripts x two outgoing commits
    assert all(Path(call.cwd) == export_dir for call in scans)
    assert all(Path(call.cwd) != gate.module.REPO_ROOT for call in scans)


# ── F3: a ref that publishes no new commit must not block the push ──────────


def test_hook_tag_on_a_published_commit_is_allowed_without_a_gate_run(gate, monkeypatch, capsys):
    gate.rec.rev_lists[TAG_SHA] = []  # the tag points at an already-published commit
    feed_stdin(monkeypatch, f"refs/tags/v1 {TAG_SHA} refs/tags/v1 {ZERO_SHA}\n")
    assert gate.module.main(["--from-hook", "origin"]) == 0
    out = capsys.readouterr().out
    assert "publish no new commit; allowing without a gate run" in out
    assert not gate.rec.with_argv("worktree add --detach")


def test_hook_new_branch_at_a_published_commit_is_allowed_without_a_gate_run(
    gate, monkeypatch, capsys
):
    gate.rec.rev_lists[FEATURE_SHA] = []
    feed_stdin(monkeypatch, f"refs/heads/release {FEATURE_SHA} refs/heads/release {ZERO_SHA}\n")
    assert gate.module.main(["--from-hook", "origin"]) == 0
    out = capsys.readouterr().out
    assert "publish no new commit; allowing without a gate run" in out
    assert not gate.rec.with_argv("worktree add --detach")


def test_hook_tag_with_a_new_commit_still_gets_the_fast_gate(gate, monkeypatch):
    gate.rec.rev_lists[TAG_SHA] = [TAG_SHA]
    feed_stdin(monkeypatch, f"refs/tags/v2 {TAG_SHA} refs/tags/v2 {ZERO_SHA}\n")
    assert gate.module.main(["--from-hook", "origin"]) == 0
    assert gate.rec.with_argv("worktree add --detach")  # the gate really ran
    assert latest_report(gate)["mode"] == "fast"


def test_hook_main_with_no_new_commits_runs_the_full_gate(gate, monkeypatch, capsys):
    gate.rec.rev_lists[HEAD_SHA] = []  # main publishes nothing new
    feed_stdin(monkeypatch, HOOK_STDIN_MAIN)
    assert gate.module.main(["--from-hook", "origin"]) == 0
    assert gate.rec.with_argv("worktree add --detach")
    report = latest_report(gate)
    assert report["mode"] == "full"
    assert report["outgoing_commits"] == []
    assert report["complete"] is True
    assert "0 commits scanned (nothing new is published)" in capsys.readouterr().out


def test_rev_list_failure_is_an_error_that_names_the_fix(gate, monkeypatch, capsys):
    gate.rec.rev_list_error = True
    feed_stdin(monkeypatch, HOOK_STDIN_MAIN)
    assert gate.module.main(["--from-hook", "origin"]) == 1
    assert "fetch the remote first" in capsys.readouterr().out

    gate.rec.calls.clear()
    assert run_gate(gate, "--fast") == 1  # a manual run fails the same way
    assert "fetch the remote first" in capsys.readouterr().out


# ── Push records and hook mode (C1) ─────────────────────────────────────────


def test_parse_push_records_from_real_stdin_text(gate):
    text = (
        f"refs/heads/feature {FEATURE_SHA} refs/heads/feature {REMOTE_SHA}\n"
        f"refs/heads/main {HEAD_SHA} refs/heads/main {REMOTE_SHA}\n"
        f"refs/tags/v1 {TAG_SHA} refs/tags/v1 {ZERO_SHA}\n"
        f"refs/heads/gone {ZERO_SHA} refs/heads/gone {REMOTE_SHA}\n"
        "\n"
    )
    records = gate.module.parse_push_records(text)
    assert len(records) == 4
    assert records[0].local_sha == FEATURE_SHA
    assert records[3].is_deletion is True
    assert records[2].is_new_remote_ref is True
    with pytest.raises(ValueError):
        gate.module.parse_push_records("this is not a record\n")


def test_hook_with_one_main_record_runs_the_full_gate(gate, monkeypatch):
    feed_stdin(monkeypatch, HOOK_STDIN_MAIN)
    assert gate.module.main(["--from-hook", "origin", "https://example/repo.git"]) == 0
    assert gate.rec.with_argv("pytest")
    assert gate.rec.with_argv(".github/scripts/run_public_core_assertions.py")
    assert latest_report(gate)["mode"] == "full"


def test_hook_feature_then_main_gates_each_candidate_at_its_mode(gate, monkeypatch):
    gate.rec.rev_lists[FEATURE_SHA] = [FEATURE_SHA]
    feed_stdin(
        monkeypatch,
        f"refs/heads/feature {FEATURE_SHA} refs/heads/feature {REMOTE_SHA}\n"
        f"refs/heads/main {HEAD_SHA} refs/heads/main {REMOTE_SHA}\n",
    )
    assert gate.module.main(["--from-hook", "origin"]) == 0
    adds = gate.rec.with_argv("worktree add --detach")
    assert sorted(call.argv[5] for call in adds) == sorted([FEATURE_SHA, HEAD_SHA])
    # The feature candidate ran fast (no tests); the main candidate ran full.
    pytest_calls = gate.rec.with_argv("pytest")
    assert len(pytest_calls) == 1
    reports = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((gate.tmp / "reports").glob("*.json"))
    ]
    modes = {report["candidate_sha"]: report["mode"] for report in reports}
    assert modes == {FEATURE_SHA: "fast", HEAD_SHA: "full"}


def test_hook_tag_then_main_gates_main_in_full_mode(gate, monkeypatch):
    gate.rec.rev_lists[TAG_SHA] = [TAG_SHA]
    feed_stdin(
        monkeypatch,
        f"refs/tags/v1 {TAG_SHA} refs/tags/v1 {ZERO_SHA}\n"
        f"refs/heads/main {HEAD_SHA} refs/heads/main {REMOTE_SHA}\n",
    )
    assert gate.module.main(["--from-hook", "origin"]) == 0
    reports = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((gate.tmp / "reports").glob("*.json"))
    ]
    modes = {report["candidate_sha"]: report["mode"] for report in reports}
    assert modes == {TAG_SHA: "fast", HEAD_SHA: "full"}


def test_hook_blocks_the_push_when_any_candidate_fails(gate, monkeypatch):
    gate.rec.fail_black = True
    feed_stdin(monkeypatch, HOOK_STDIN_MAIN)
    assert gate.module.main(["--from-hook", "origin"]) == 1


def test_hook_deletion_records_are_ignored(gate, monkeypatch, capsys):
    feed_stdin(monkeypatch, f"refs/heads/gone {ZERO_SHA} refs/heads/gone {REMOTE_SHA}\n")
    assert gate.module.main(["--from-hook", "origin"]) == 0
    assert "nothing to push" in capsys.readouterr().out
    assert not gate.rec.with_argv("worktree add --detach")


def test_hook_with_no_records_allows_the_push(gate, monkeypatch, capsys):
    feed_stdin(monkeypatch, "")
    assert gate.module.main(["--from-hook", "origin"]) == 0
    assert "nothing to push" in capsys.readouterr().out


def test_hook_mode_ignores_pre_commit_variables_and_range_args(gate, monkeypatch, capsys):
    monkeypatch.setenv("PRE_COMMIT_FROM_REF", "f" * 41)  # garbage on purpose
    monkeypatch.setenv("PRE_COMMIT_TO_REF", "e" * 41)
    feed_stdin(monkeypatch, HOOK_STDIN_MAIN)
    assert gate.module.main(["--from-hook", "origin"]) == 0
    rev_list = gate.rec.with_argv("rev-list --reverse")[0]
    assert rev_list.argv[-1] == REMOTE_SHA  # the record's remote sha, not the env

    feed_stdin(monkeypatch, HOOK_STDIN_MAIN)
    assert gate.module.main(["--from-hook", "origin", "--base", MAIN_SHA]) == 2
    assert "do not pass --base" in capsys.readouterr().out


# ── The hook file itself (C1) ───────────────────────────────────────────────


def test_hook_template_delegates_stdin_to_the_gate(gate):
    template = gate.module.HOOK_TEMPLATE
    assert template.startswith("#!/bin/sh\n")
    assert "git rev-parse --show-toplevel" in template
    assert 'exec python "$toplevel/scripts/gate.py" --from-hook "$@"' in template


def test_install_hook_writes_the_template_and_check_hook_compares_content(
    gate, tmp_path, monkeypatch
):
    hooks = tmp_path / "hooks"
    hooks.mkdir()
    monkeypatch.setattr(gate.module, "hooks_dir", lambda: hooks)
    hook = hooks / "pre-push"

    assert gate.module.main(["--install-hook"]) == 0
    assert hook.read_text(encoding="utf-8") == gate.module.HOOK_TEMPLATE
    assert gate.module.main(["--check-hook"]) == 0

    hook.write_text("#!/bin/sh\nsome other hook\n", encoding="utf-8")
    assert gate.module.main(["--check-hook"]) == 1  # content must match exactly
    assert gate.module.main(["--install-hook"]) == 2  # refuses a foreign hook
    assert gate.module.main(["--install-hook", "--force"]) == 0
    assert gate.module.main(["--check-hook"]) == 0


def test_preflight_warns_when_the_gate_hook_is_not_installed(gate, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(gate.module, "hooks_dir", lambda: tmp_path / "absent")
    assert run_gate(gate, "--fast") == 0  # a warning, never a failure
    assert "pre-push hook is not installed" in capsys.readouterr().out


def test_pre_commit_config_owns_no_push_gate():
    """pre-commit must not run the push gate: it collapses a multi-ref push."""
    import yaml

    config_text = (REPO_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    config = yaml.safe_load(config_text)
    assert "default_install_hook_types" not in config
    entries = [
        str(hook.get("entry", "")) for repo in config["repos"] for hook in repo.get("hooks", [])
    ]
    assert not any("gate.py" in entry for entry in entries)
    assert "scripts/gate.py --install-hook" in config_text  # points at the native hook


# ── One sanitized environment for everything that runs code (C3) ────────────


HOSTILE_VARS = {
    "LIFE_INDEX_EVAL_DATA_DIR": "C:/somewhere/else",
    "PYTHONPATH": "C:/uncommitted/package",
    "PYTHONHOME": "C:/wrong/home",
    "PYTEST_ADDOPTS": "-p no:cacheprovider --basetemp=C:/hostile",
    "COVERAGE_RCFILE": "C:/no-threshold.ini",
    "COV_CORE_CONFIG": "x",
    "PIP_INDEX_URL": "http://hostile/simple",
    "PRE_COMMIT_FROM_REF": "f" * 40,
    "VIRTUAL_ENV": "C:/hostile/venv",
    # Git exports these to the pre-push hook (F1); candidate code must
    # never inherit them, or a test's `git init` acts on the wrong repo.
    "GIT_DIR": "C:/real/repo/.git/worktrees/pushing",
    "GIT_WORK_TREE": "C:/real/repo",
    "GIT_INDEX_FILE": "C:/real/repo/.git/index",
    "GIT_PREFIX": "sub/dir/",
}


def _hostile_environment(monkeypatch):
    for name, value in HOSTILE_VARS.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("APPDATA", "C:/keep/appdata")


def test_sanitized_env_drops_every_dangerous_variable(gate, monkeypatch):
    _hostile_environment(monkeypatch)
    env = gate.module.sanitized_env(
        gate.tmp / "home", gate.tmp / "data", Path("C:/export/candidate")
    )
    for name in HOSTILE_VARS:
        if name == "PYTHONPATH":
            continue  # re-forced to the candidate below, not dropped
        assert name not in env, name
    assert env["APPDATA"] == "C:/keep/appdata"  # untouched, per contract


def test_sanitized_env_forces_home_data_and_candidate(gate, monkeypatch):
    _hostile_environment(monkeypatch)
    env = gate.module.sanitized_env(
        gate.tmp / "home",
        gate.tmp / "data",
        Path("C:/export/candidate"),
        coverage_file=Path("C:/run/.coverage"),
    )
    assert env["HOME"] == str(gate.tmp / "home")
    assert env["USERPROFILE"] == str(gate.tmp / "home")
    assert env["LIFE_INDEX_DATA_DIR"] == str(gate.tmp / "data")
    assert Path(env["PYTHONPATH"]) == Path("C:/export/candidate")
    assert env["PYTHONUTF8"] == "1"
    assert env["PYTHONIOENCODING"] == "utf-8"
    assert env["LIFE_INDEX_INDEX_FTS_ONLY"] == "1"
    assert Path(env["COVERAGE_FILE"]) == Path("C:/run/.coverage")  # set where relevant


def test_static_checks_and_sentinel_run_in_the_sanitized_environment(gate, monkeypatch):
    _hostile_environment(monkeypatch)
    assert _full_native_run(gate) == 0
    for fragment in ("black --check", ".github/scripts/run_public_core_assertions.py"):
        call = gate.rec.with_argv(fragment)[0]
        assert call.env is not None, fragment
        for name in HOSTILE_VARS:
            if name == "PYTHONPATH":
                continue  # forced to the exported candidate, not dropped
            assert name not in call.env, (fragment, name)


def test_native_leg_runs_in_the_sanitized_environment(gate, monkeypatch):
    _hostile_environment(monkeypatch)
    hostile_data = str(gate.tmp / "hostile-real-data")
    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", hostile_data)  # re-forced, not kept
    assert _full_native_run(gate) == 0
    pytest_call = gate.rec.with_argv("pytest")[0]
    env = pytest_call.env
    for name in HOSTILE_VARS:
        if name == "PYTHONPATH":
            continue  # re-forced to the exported candidate below
        assert name not in env, name
    add_call = gate.rec.with_argv("worktree add --detach")[0]
    assert env["PYTHONPATH"] == add_call.argv[4]  # the exported candidate
    assert env["LIFE_INDEX_DATA_DIR"] != hostile_data
    assert Path(env["LIFE_INDEX_DATA_DIR"]).name == "data"
    assert env["COVERAGE_FILE"].endswith(".coverage")


def test_native_leg_isolates_a_throwaway_home(gate, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(gate.tmp / "real-home"))
    monkeypatch.setenv("HOME", str(gate.tmp / "real-home"))
    assert _full_native_run(gate) == 0
    env = gate.rec.with_argv("pytest")[0].env
    assert env["HOME"] != str(gate.tmp / "real-home")
    assert env["USERPROFILE"] != str(gate.tmp / "real-home")


def test_linux_leg_test_process_cannot_reach_the_real_home(gate):
    script = gate.module.linux_leg_script(HEAD_SHA, "/mnt/c/some repo/.git")
    pytest_line = next(line for line in script.splitlines() if " -m pytest tests " in line)

    assert pytest_line.startswith("env -i ")  # nothing inherited from the caller
    assert 'HOME="$TMP/home"' in pytest_line
    assert 'LIFE_INDEX_DATA_DIR="$TMP/data"' in pytest_line
    assert "PYTHONUTF8=1" in pytest_line
    assert "LIFE_INDEX_INDEX_FTS_ONLY=1" in pytest_line
    assert 'PYTHONPATH="$TMP/repo"' in pytest_line  # the clone, not a shared install
    assert "timeout --kill-after=30 " in pytest_line
    assert 'mkdir -p "$TMP/home" "$TMP/data" "$TMP/basetemp"' in script


def test_linux_leg_never_mutates_the_shared_environment(gate):
    script = gate.module.linux_leg_script(HEAD_SHA, "/mnt/c/some repo/.git")
    assert "pip install" not in script  # no per-run install into the cached venv
    assert "pip uninstall" not in script


def test_setup_linux_installs_dependencies_and_leaves_the_project_uninstalled(gate):
    source = GATE_PATH.read_text(encoding="utf-8")
    assert '"${PIP[@]}" -e "$SRC/repo[dev]"' in source  # dependencies via the project
    assert "pip uninstall --yes life-index" in source  # the project itself removed
    assert "bandit" in source  # the gate's own required tool is installed


def test_linux_leg_paths_expand_and_stay_out_of_dot_directories(gate):
    script = gate.module.linux_leg_script(HEAD_SHA, "/mnt/c/some repo/.git")
    # A tilde inside double quotes does not expand in bash.
    assert "~" not in script
    assert 'VENV="$HOME/.cache/life-index-gate/venv-py311"' in script
    assert 'TMP="$(mktemp -d /var/tmp/life-index-gate.XXXXXX)"' in script
    assert "~" not in gate.module.linux_env_probe_script()


def test_probe_script_checks_for_python_3_11(gate):
    script = gate.module.linux_env_probe_script()
    assert "platform.python_version()" in script
    assert "WRONG-PYTHON" in script
    assert "3.11.*" in script


def test_probe_rejects_a_wrong_python(gate):
    gate.rec.wsl_wrong_python = "3.12.4"
    leg = gate.module.run_linux_leg(HEAD_SHA, gate.tmp / "linux", "0" * 64, gate.tmp / "l.log")
    assert not leg.ran and not leg.passed
    assert "not Python 3.11" in leg.detail
    assert "python scripts/gate.py --setup-linux" in leg.detail


# ── The real-data tripwire (C3) ─────────────────────────────────────────────


def run_embedded_tripwire(gate, root: Path) -> str:
    proc = subprocess.run(
        [sys.executable, "-c", gate.module.TRIPWIRE_CODE, str(root)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


def test_fingerprint_tree_matches_the_embedded_twin(gate, tmp_path):
    tree = tmp_path / "Life-Index"
    (tree / "Journals" / "2026").mkdir(parents=True)
    (tree / "Journals" / "2026" / "a.md").write_bytes(b"entry")
    (tree / "index.db").write_bytes(b"cache")
    native = gate.module.fingerprint_tree(tree)
    assert native == run_embedded_tripwire(gate, tree)
    assert native.startswith("files=2:")
    assert gate.module.fingerprint_tree(tmp_path / "absent") == "absent"


def test_fingerprint_changes_when_a_file_appears_or_mtime_moves(gate, tmp_path):
    tree = tmp_path / "Life-Index"
    tree.mkdir()
    first = gate.module.fingerprint_tree(tree)
    (tree / "journal.md").write_bytes(b"entry")
    second = gate.module.fingerprint_tree(tree)
    assert first != second
    os.utime(tree / "journal.md", (1, 1))
    assert gate.module.fingerprint_tree(tree) != second


def test_native_leg_fails_when_the_tripwire_fires(gate, tmp_path, monkeypatch):
    watched = tmp_path / "watched"
    watched.mkdir()
    monkeypatch.setattr(gate.module, "real_data_root", lambda: watched)
    real_fingerprint = gate.module.fingerprint_tree
    state = {"calls": 0}

    def changing_fingerprint(path):
        state["calls"] += 1
        if state["calls"] == 1:
            return "files=1:before"
        return real_fingerprint(path)

    monkeypatch.setattr(gate.module, "fingerprint_tree", changing_fingerprint)
    (watched / "touched.txt").write_text("simulated real-data touch", encoding="utf-8")

    assert _full_native_run(gate) == 1
    report = latest_report(gate)
    leg = next(leg for leg in report["legs"] if leg["platform"] == native_platform())
    assert leg["passed"] is False
    assert leg["tripwire"].startswith("CHANGED")


def test_native_leg_reports_an_unchanged_tripwire(gate, tmp_path, monkeypatch):
    watched = tmp_path / "watched"
    watched.mkdir()
    monkeypatch.setattr(gate.module, "real_data_root", lambda: watched)
    assert _full_native_run(gate) == 0
    report = latest_report(gate)
    leg = next(leg for leg in report["legs"] if leg["platform"] == native_platform())
    assert leg["passed"] is True
    assert leg["tripwire"].startswith("unchanged")


def test_linux_leg_fails_when_the_tripwire_fires(gate):
    gate.rec.linux_tripwire = "CHANGED: files=1:x -> files=2:y"
    gate.rec.linux_rc = 201
    leg = gate.module.run_linux_leg(
        HEAD_SHA, gate.tmp / "linux", _expected_hash(gate), gate.tmp / "l.log"
    )
    assert not leg.passed
    assert leg.tripwire.startswith("CHANGED")


# ── Test legs ────────────────────────────────────────────────────────────────


def test_one_pytest_invocation_per_leg_coverage_only_on_the_native_leg(gate):
    assert run_gate(gate) == 0  # full run
    pytest_calls = [call for call in gate.rec.calls if "-m" in call.argv and "pytest" in call.argv]
    assert len(pytest_calls) == 1  # the native leg runs pytest exactly once
    native = pytest_calls[0]
    assert "--cov=tools" in native.argv
    assert "--timeout=600" in native.argv
    assert "tests" in native.argv

    if os.name == "nt":
        leg_scripts = [
            call
            for call in gate.rec.calls
            if call.argv[:1] == ("wsl.exe",) and "mktemp" in call.argv[-1]
        ]
        assert len(leg_scripts) == 1
        script = leg_scripts[0].argv[-1]
        assert script.count("-m pytest tests") == 1  # one invocation in the Linux leg
        assert "--cov" not in script  # and it collects no coverage


def test_leg_with_zero_collected_tests_is_a_failure(gate):
    gate.rec.junit = {"tests": 0, "errors": 0, "failures": 0, "skipped": 0}
    assert _full_native_run(gate) == 1
    stage = run_stage(gate, f"tests:{native_platform()}")
    assert stage["status"] == "fail"
    assert "collected zero tests" in stage["detail"]


def test_all_skipped_leg_is_a_failure(gate):
    gate.rec.junit = {"tests": 4, "errors": 0, "failures": 0, "skipped": 4}
    gate.rec.pytest_rc = 0
    assert _full_native_run(gate) == 1
    stage = run_stage(gate, f"tests:{native_platform()}")
    assert stage["status"] == "fail"
    assert "no test passed" in stage["detail"]


def test_failing_tests_fail_the_leg_and_the_gate(gate):
    gate.rec.junit = {"tests": 4, "errors": 0, "failures": 1, "skipped": 0}
    gate.rec.pytest_rc = 1
    assert _full_native_run(gate) == 1
    stage = run_stage(gate, f"tests:{native_platform()}")
    assert stage["status"] == "fail"
    assert "3 passed, 1 failed, 0 skipped" in stage["detail"]


def test_leg_without_junit_is_a_failure(gate, monkeypatch):
    monkeypatch.setattr(
        gate.rec, "_pytest", lambda argv: gate.module.ProcResult(0, "ok"), raising=False
    )
    assert _full_native_run(gate) == 1
    assert "no junit result was produced" in run_stage(gate, f"tests:{native_platform()}")["detail"]


@pytest.mark.skipif(os.name != "nt", reason="--no-linux only exists on Windows")
def test_no_linux_is_loud_and_never_complete(gate, capsys):
    assert run_gate(gate, "--no-linux") == 0
    out = capsys.readouterr().out
    assert "SKIPPED (--no-linux)" in out
    assert "NOT tested on Linux" in out
    report = latest_report(gate)
    assert report["complete"] is False  # a skipped leg is never complete
    assert report["linux_leg"] == "skipped"


@pytest.mark.skipif(os.name == "nt", reason="on Windows --no-linux is legal")
def test_no_linux_is_refused_on_non_windows_hosts(gate, capsys):
    assert gate.module.main(["--no-linux"]) == 2
    assert "no second leg" in capsys.readouterr().out


@pytest.mark.skipif(os.name != "nt", reason="the WSL leg only exists on Windows")
def test_unhashable_pyproject_fails_the_linux_leg_stage(gate, monkeypatch):
    monkeypatch.setattr(gate.module, "dependency_hash", lambda pyproject: None)
    assert run_gate(gate) == 1
    stage = run_stage(gate, "tests:linux")
    assert stage["status"] == "fail"  # a failed stage, never a silent skip
    assert "cannot hash" in stage["detail"]
    report = latest_report(gate)
    assert report["linux_leg"] == "failed"
    assert report["complete"] is False


def test_full_pass_reports_complete(gate):
    if os.name == "nt":
        assert run_gate(gate) == 0  # both legs, recorder-scripted
        legs = {leg["platform"]: leg for leg in latest_report(gate)["legs"]}
        assert set(legs) == {"windows", "linux"}
    else:
        assert gate.module.main(["--head", "HEAD"]) == 0
        legs = {leg["platform"]: leg for leg in latest_report(gate)["legs"]}
        assert set(legs) == {"native"}
    assert latest_report(gate)["complete"] is True


# ── The Linux environment hash check ─────────────────────────────────────────


def test_linux_leg_fails_with_the_setup_command_when_the_venv_is_missing(gate):
    gate.rec.wsl_missing_venv = True
    leg = gate.module.run_linux_leg(HEAD_SHA, gate.tmp / "linux", "0" * 64, gate.tmp / "l.log")
    assert not leg.ran and not leg.passed
    assert "python scripts/gate.py --setup-linux" in leg.detail


def test_linux_leg_fails_with_the_setup_command_when_the_hash_is_stale(gate):
    gate.rec.wsl_recorded_hash = "e" * 64
    leg = gate.module.run_linux_leg(HEAD_SHA, gate.tmp / "linux", "0" * 64, gate.tmp / "l.log")
    assert not leg.ran and not leg.passed
    assert "stale (dependency hash mismatch)" in leg.detail


def test_linux_leg_runs_when_the_hash_matches(gate):
    expected = _expected_hash(gate)
    leg = gate.module.run_linux_leg(HEAD_SHA, gate.tmp / "linux", expected, gate.tmp / "l.log")
    assert leg.ran and leg.passed, leg.detail
    assert leg.python_version == "3.11.9"
    assert leg.tests == 5
    assert leg.tripwire.startswith("unchanged")


def test_dependency_hash_tracks_the_dependency_sections(gate, tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(EXPORT_PYPROJECT, encoding="utf-8")
    first = gate.module.dependency_hash(pyproject)
    assert first is not None and re.fullmatch(r"[0-9a-f]{64}", first)

    pyproject.write_text(
        EXPORT_PYPROJECT.replace('dev = ["pytest>=7.4.0"]', 'dev = ["pytest>=8.0.0"]'),
        encoding="utf-8",
    )
    assert gate.module.dependency_hash(pyproject) != first

    pyproject.write_text(
        EXPORT_PYPROJECT.replace('version = "9.9.9"', 'version = "8.8.8"'), encoding="utf-8"
    )
    assert gate.module.dependency_hash(pyproject) == first  # non-dependency edits ignored


# ── The Linux result parser runs under a real bash (C5) ─────────────────────


def _real_bash() -> str | None:
    """A real bash, avoiding Windows System32\\bash.exe (the WSL launcher,
    which re-quotes argv and mangles the script text)."""
    candidates: list[str] = []
    git = shutil.which("git")
    if git:
        for parent in Path(git).resolve().parents:
            candidate = parent / "bin" / "bash.exe"
            if candidate.is_file():
                candidates.append(str(candidate))
    bash = shutil.which("bash")
    if bash and Path(bash).resolve().parent.name.lower() != "system32":
        candidates.append(bash)
    if os.name != "nt" and bash:
        candidates.append(bash)
    return candidates[0] if candidates else None


def test_linux_result_fragment_runs_under_real_bash(gate, tmp_path):
    bash = _real_bash()
    if bash is None:
        pytest.skip("no real bash on PATH")
    script = gate.module.linux_leg_script(HEAD_SHA, "/mnt/c/repo/.git")
    start = script.index('cat > "$TMP/leg_result.py"')
    end = script.index("\nPY\n", start) + len("\nPY\n")
    junit = tmp_path / "junit.xml"
    junit.write_text(
        '<?xml version="1.0"?><testsuites><testsuite name="t" tests="4" errors="0" '
        'failures="1" skipped="1"></testsuite></testsuites>',
        encoding="utf-8",
    )
    # Run the generated fragment as-is: its own TMP dir, and the interpreter
    # and junit path spelled with forward slashes so bash never mangles them.
    interpreter = sys.executable.replace("\\", "/")
    fragment = (
        'TMP="$(mktemp -d)"\n'
        + script[start:end]
        + f'\n"{interpreter}" "$TMP/leg_result.py" "{junit.as_posix()}"\n'
    )
    proc = subprocess.run(
        [bash, "-c", fragment],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    marker = next(line for line in proc.stdout.splitlines() if line.startswith("GATE-LEG-RESULT "))
    payload = json.loads(marker.removeprefix("GATE-LEG-RESULT "))
    assert payload == {"tests": 4, "errors": 0, "failures": 1, "skipped": 1, "passed": 2}


# ── Exported worktree lifecycle and evidence (C7) ───────────────────────────


def assert_worktree_cleaned_up(gate):
    add = gate.rec.with_argv("worktree add --detach")[0]
    export_dir = add.argv[4]
    removed = gate.rec.with_argv("worktree remove --force")
    assert any(call.argv[-1] == export_dir for call in removed)
    assert not gate.rec.with_argv("worktree prune")  # never a repository-wide prune


def test_worktree_is_removed_after_a_successful_run(gate):
    assert run_gate(gate, "--fast") == 0
    assert_worktree_cleaned_up(gate)


def test_worktree_is_removed_after_a_failing_run(gate):
    gate.rec.fail_black = True
    assert run_gate(gate, "--fast") == 1
    assert_worktree_cleaned_up(gate)


def test_worktree_is_removed_after_an_interruption(gate):
    gate.rec.interrupt_on_black = True
    assert run_gate(gate, "--fast") == 130
    assert_worktree_cleaned_up(gate)


def test_each_run_gets_its_own_evidence_directory(gate):
    assert run_gate(gate, "--fast") == 0
    assert run_gate(gate, "--fast") == 0
    runs = sorted(p.name for p in (gate.tmp / "reports").iterdir() if p.is_dir())
    assert len(runs) == 2
    assert all(re.fullmatch(rf"{HEAD_SHA}-\d{{8}}T\d{{6}}\d*Z-\d+", name) for name in runs), runs
    for run in runs:
        assert ((gate.tmp / "reports") / run / "verdict.json").is_file()
    assert latest_report(gate)["candidate_sha"] == HEAD_SHA  # <sha>.json latest copy


# ── Verdict JSON and reporting ───────────────────────────────────────────────


def test_verdict_json_records_stages_legs_and_outgoing_commits(gate):
    assert _full_native_run(gate) == 0
    report = latest_report(gate)
    assert report["outcome"] == "pass"
    assert report["candidate_sha"] == HEAD_SHA
    assert report["outgoing_commits"] == [C_OLD, HEAD_SHA]
    keys = [stage["key"] for stage in report["stages"]]
    assert keys[:2] == ["preflight", "export"]
    assert keys[2:11] == STATIC_KEYS
    assert keys[11] == "sentinel"
    assert keys[12] == f"tests:{native_platform()}"
    legs = {leg["platform"]: leg for leg in report["legs"]}
    assert legs[native_platform()]["ran"] is True
    assert legs[native_platform()]["passed_count"] == 3
    assert legs[native_platform()]["tripwire"].startswith("unchanged")
    if os.name == "nt":
        assert legs["linux"]["ran"] is False  # never reported as passed
        assert legs["linux"]["passed"] is False


def test_uncommitted_changes_are_noted_but_not_fatal(gate, capsys):
    gate.rec.status_output = " M scripts/gate.py\n"
    assert run_gate(gate, "--fast") == 0
    assert "uncommitted changes" in capsys.readouterr().out


def test_red_backstop_is_reported_loudly_but_never_fails_the_gate(gate, monkeypatch, capsys):
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/gh" if name == "gh" else None)
    gate.rec.gh_rc = 0
    gate.rec.gh_output = json.dumps(
        [{"status": "completed", "conclusion": "failure", "url": "https://example/run/1"}]
    )
    assert _full_native_run(gate) == 0
    assert "WARNING: the latest backstop run" in capsys.readouterr().out


def test_backstop_conclusion_is_read_from_json_not_the_table(gate, monkeypatch, capsys):
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/gh" if name == "gh" else None)
    gate.rec.gh_rc = 0
    # The old text form started with "completed"; the gate must not call that
    # a success. With --json this input is unusable, never a false all-clear.
    gate.rec.gh_output = "completed  Backstop  main  push  1  2h ago"
    assert _full_native_run(gate) == 0
    out = capsys.readouterr().out
    assert "WARNING" not in out
    assert "unknown" in out or "no backstop runs" in out


def test_in_progress_backstop_is_reported_as_such(gate, monkeypatch, capsys):
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/gh" if name == "gh" else None)
    gate.rec.gh_output = json.dumps(
        [{"status": "in_progress", "conclusion": None, "url": "https://example/run/2"}]
    )
    assert _full_native_run(gate) == 0
    assert "in progress" in capsys.readouterr().out


def test_missing_gh_is_not_an_error(gate, monkeypatch, capsys):
    monkeypatch.setattr("shutil.which", lambda name: None)
    assert _full_native_run(gate) == 0
    assert "backstop status is unknown" in capsys.readouterr().out


def test_missing_gate_dependencies_fail_preflight(gate, monkeypatch, capsys):
    real_spec = importlib.util.find_spec

    def fake_find_spec(name, *args, **kwargs):
        if name == "bandit":
            return None
        return real_spec(name, *args, **kwargs)

    monkeypatch.setattr("importlib.util.find_spec", fake_find_spec)
    assert run_gate(gate, "--fast") == 1
    assert "bandit" in capsys.readouterr().out


# ── Timeouts kill the process tree (C7) ─────────────────────────────────────


def test_timeout_kills_the_child_and_reports_it(gate):
    started = time.monotonic()
    result = gate.real_run([sys.executable, "-c", "import time; time.sleep(60)"], timeout=2)
    elapsed = time.monotonic() - started
    assert result.returncode == 124
    assert result.detail.startswith("timed out after")
    assert elapsed < 30  # the tree was killed, not waited out


def test_taskkill_is_used_on_windows_timeouts(gate, monkeypatch):
    if os.name != "nt":
        pytest.skip("taskkill is the Windows timeout path")
    seen = []

    def fake_taskkill(argv, **kwargs):
        seen.append(tuple(argv))
        return None

    monkeypatch.setattr(subprocess, "run", fake_taskkill, raising=False)
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        gate.module._kill_tree(proc)
    finally:
        proc.kill()
        proc.communicate(timeout=30)
    assert seen and "/PID" in seen[0] and "/T" in seen[0] and "/F" in seen[0]
