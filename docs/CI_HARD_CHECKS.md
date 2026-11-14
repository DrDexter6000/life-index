# CI Hard Checks - SSOT

Status: local gate and online backstop
Scope: Life Index CLI repository

This file describes the two mechanisms that guard a push: the local gate
(the authority for pushing to `main`) and the online backstop (advisory,
never blocking). It deliberately does not list the individual checks —
`python scripts/gate.py --list` owns and prints the inventory.

## The local gate

The gate is one command with one verdict, installed as a native Git
pre-push hook:

```bash
python scripts/gate.py          # full gate on HEAD
python scripts/gate.py --fast   # static checks only, for quick feedback
```

What it is for: proving that the *committed* candidate — never the working
tree — passes every check before it is pushed to `main`. The gate exports
the candidate commit into a detached temporary worktree, so uncommitted or
untracked files can never make a push pass.

The hook reads **every** record Git sends on stdin (`<local ref> <local
sha> <remote ref> <remote sha>`): pre-commit's pre-push support collapses a
multi-ref push to its first record, so the gate ships as a native hook
instead. Deletions are ignored; every remaining candidate is gated once, at
the strongest mode any of its records needs — a record whose remote ref is
`refs/heads/main` means the full gate, anything else the fast gate. The
push is allowed only when all candidates pass. Install it (once per clone):

```bash
python scripts/gate.py --install-hook
```

`--install-hook` refuses to overwrite a hook it did not write (use
`--force` to replace one). `--check-hook` exits non-zero unless the
installed hook is exactly the one `--install-hook` writes.

The scans cover **every outgoing commit**, not the tip's cumulative diff:
for each push record the gate lists the commits the push would add
(`git rev-list <local> --not <remote sha>`, or `--not --remotes=<remote>`
for a new remote ref; a manual run uses `origin/main` unless `--base` is
given), then runs both public-diff scans once per commit with `--base` set
to that commit's first parent (a root commit is scanned against the empty
tree). A file added in one outgoing commit and deleted in a later one is
still scanned. An empty outgoing list must never silently pass: a manual
run fails with instructions to pass `--base`; in a push, a candidate whose
records publish no new commit and none of which targets `refs/heads/main`
is allowed with a one-line notice and no gate run (a tag on an already
published commit, a new branch created at a published commit), while a
`main` record always runs the full gate with the scans reporting
"0 commits scanned (nothing new is published)". A `rev-list` failure
stays a failure and asks to fetch the remote first. `--base` must be an
ancestor of the candidate.

What it runs: static checks (format, lint, types, security scan, doc
sync, no-LLM scan, the two per-commit public diff scans, the
packaged-skill mirror check), the public Core assertion sentinel, and the
full test suite on the local interpreter — with coverage collected in the
same run, the threshold staying owned by `pyproject.toml` — plus, on
Windows, the same test suite on Python 3.11 inside WSL on its own clone,
running pytest from inside that clone on the WSL filesystem (never against
the caller's working tree through /mnt) and writing no bytecode outside
its own temporary directory.

Every process that runs candidate code — static checks, sentinel and test
legs alike — gets one sanitized environment: nothing inherited that starts
with `LIFE_INDEX_`, `PYTHON`, `PYTEST_`, `COVERAGE_`, `COV_CORE_`, `PIP_`,
`PRE_COMMIT_` or `GIT_` (and no `VIRTUAL_ENV`) — Git exports `GIT_DIR` and
friends to the pre-push hook, and a test that runs git in a temporary
directory must act on its own directory, not on the pushing worktree's
repository; a forced synthetic
`LIFE_INDEX_DATA_DIR`, UTF-8, a throwaway `HOME`, and the exported
candidate on `PYTHONPATH`. The Linux leg's pytest runs inside `env -i`.
Each test leg fingerprints the real home's default data directory
(`Documents/Life-Index`; file count and a hash of size+mtime — stat only,
no file is ever opened, no name printed) before and after the run, and
fails if it changed. A leg passes only on an unambiguous result: exit 0,
at least one passed test, zero failures, zero errors.

The verdict prints per-stage results and durations, per-leg interpreter
versions, counts read from junit XML and tripwire results, and is written
as JSON per run (one evidence directory per run) with the latest verdict
for a SHA kept at the git-ignored gate report path. A run is
`"complete": true` only when every expected leg ran and passed.

The Linux leg needs a one-time WSL environment (Python 3.11 under
`~/.cache/life-index-gate/venv-py311`, dependencies only — the project
itself stays uninstalled and each run puts the clone under test on
`PYTHONPATH`). Create or refresh it with:

```bash
python scripts/gate.py --setup-linux
```

This is the only gate mode that downloads anything. The environment
records a hash of the dependency sections of `pyproject.toml`; when the
hash differs, the full gate fails and names this exact command. On a
Linux or macOS host there is no second leg: the gate runs the one native
leg and says so. `--no-linux` skips the WSL leg, the verdict says so
loudly, and the run is never `"complete"`.

## The online backstop

`.github/workflows/backstop.yml` is a single `ubuntu-latest` / Python 3.11
job, triggered on push to `main`, on pull requests to `main` (outside
contributors; nothing is a required check), and manually. It is advisory:
it never blocks a push, and its failures must be triaged.

What it covers that a local run cannot: a clean hosted Linux machine, a
clean install of the project, and a clean wheel — it builds the package,
installs it into a fresh virtual environment, and runs the
`version` / `bootstrap` / `health` smoke. It runs the gate's own static
inventory (`python scripts/gate.py --fast` with the push's outgoing range;
with no usable base — first push or manual dispatch — the head commit
against its first parent, and the log says so), then the sentinel, the
full suite and the package smoke, each even when an earlier step failed
(`if: !cancelled()`), so a red fast pass cannot hide the rest.

How a red backstop gets seen: the gate's preflight prints the conclusion
of the latest backstop run on `main` whenever the `gh` command is
available, with a loud warning on a failure — so the next push surfaces
it.

When the backstop is red: find the failing step in the run's log, fix the
cause, and push the fix through the full gate. A red backstop must not be
left red; it means something a local machine did not reproduce (clean
environment, clean install, or Linux-specific).

## What the gate does not cover

Said plainly, so nobody mistakes the gate for more than it is:

- A push made with `--no-verify` skips the hook entirely; only the
  backstop sees such a push, and only afterwards.
- The Windows leg runs on whatever interpreter runs the gate; Windows
  with Python 3.11 specifically is not covered locally (the Linux leg is
  the 3.11 check).
- The Linux leg is pinned to Python 3.11; Linux with Python 3.12 is not
  covered locally (the backstop's Ubuntu runner covers 3.11 only too).

## Maintenance protocol

The gate owns the inventory. Adding, removing, or rescoping a check means
changing `scripts/gate.py` (and, when CI must mirror it,
`.github/workflows/backstop.yml`) plus tests that pin the new shape, in
the same commit. The commit message should include
`ci-hard-check inventory updated`.

<!-- PLATFORM-SSOT:PUBLIC-BLOCKER-EXECUTION:START -->
## Public blocker execution contract

A public hard blocker is green only when at least one core assertion executed.
All-skipped assertion sets are not green. Private-only assertions are advisory
and cannot be the sole evidence for a Tier 1 public blocker.

The public #163 ownership invariant is implemented: the Tier 1 no-LLM check
scans every Python AST in search/smart-search/eval for known provider imports
and aliases, normalized LLM/provider/model-client declarations and storage,
simple provider bindings, provider-specific SDK call suffixes regardless of
owner name, and generic provider verbs only with structural provider provenance.
It also rejects legacy prompt/trust/synthesis ownership and constant-string
dynamic imports supplied as the first positional argument or `name=` keyword.
Syntax/parse failure is non-green. This is a
static structural boundary, not a universal proof against computed strings or
arbitrary runtime metaprogramming.

The blocker job first runs `.github/scripts/run_public_core_assertions.py`. Its
JSON sentinel is the assertion-count authority: green requires at least one
executed public synthetic token-match assertion. Zero collected, missing,
deselected, all-skipped, or setup-skipped assertions are non-green. Private
eval and broad/noise/quality metrics remain advisory and cannot satisfy this
count or defend result deletion.
<!-- PLATFORM-SSOT:PUBLIC-BLOCKER-EXECUTION:END -->

Platform-boundary checks follow the Charter's closed Core admission domains in
`CHARTER.md §1.10` and the exact route mapping in the
`PLATFORM-SSOT:PUBLIC-COMMAND-CLASSIFICATION` block of
`docs/ARCHITECTURE.md`; this file does not duplicate either SSOT.
Distribution/Host Operations remain non-Core when co-packaged, and `weather`
remains the #166 Legacy External Adapter exception.

## Deterministic eval contracts (maintenance tools)

`scripts/run_eval_gate.sh` still owns the deterministic eval-contract
inventory and its public Core sentinel call; its `--snapshot=PHASE` mode is
a maintenance tool. `scripts/run_eval_advisory.sh` remains advisory-only.
The gate does not call either script: their test targets are part of
`pytest tests`.

## Version History

- v2.1.1-public (2026-11-14): the WSL leg runs pytest from inside the clone
  it creates (`cd` after the checkout) and disables bytecode writing, so the
  leg tests the candidate commit on the WSL filesystem instead of silently
  collecting the caller's working tree through /mnt.
- v2.1-public (2026-11-13): the push gate is a native pre-push hook
  (`--install-hook`) that gates every pushed ref; the public-diff scans
  cover every outgoing commit; one sanitized environment (throwaway HOME,
  candidate on PYTHONPATH) for every process running candidate code, with
  a real-data tripwire; the backstop runs the gate's `--fast` inventory.
- v2.0-public (2026-11-13): one local gate (`scripts/gate.py`, run by the
  pre-push hook) and one non-blocking online backstop replace tests.yml,
  quality.yml, nightly.yml and the three local gate scripts; the gate owns
  the check inventory and `--list` prints it.
- v1.3-public (2026-11-13): the integration, end-to-end and sanity suites moved
  from quarantine to the blocker gate. They had been green for months and ran
  only after the merge, so a change could land with tests it had made stale.
- v1.2.1-public (2026-07-02): Clarified Tier 2 benchmark thresholds as
  shared-runner fail-safes, not precise local performance gates.
- v1.2-public (2026-06-20): added public-surface-allowlist as a Tier 1 hard check.
- v1.1-public (2026-06-19): added L2 no-LLM scan as a Tier 1 hard check.
- v1.0-public (2026-06-18): curated the CI inventory for public visibility.
- v0.4 (2026-06-17): added public-diff-names as a Tier 1 hard check.
