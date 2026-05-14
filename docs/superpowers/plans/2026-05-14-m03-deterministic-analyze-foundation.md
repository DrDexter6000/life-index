# M03 Deterministic Analyze Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a minimal `analyze` CLI alias for deterministic aggregate output and document the contract boundary.

**Architecture:** Route `analyze` through the existing aggregate CLI module. Preserve `run_aggregate()` as the only calculator and keep JSON output compatible with `aggregate`.

**Tech Stack:** Python stdlib, pytest, existing `tools.__main__`, `tools.aggregate`, and `docs/API.md`.

---

## Files

- Modify: `tools/__main__.py`
- Modify: `tests/contract/test_aggregate_cli_contract.py`
- Modify: `docs/API.md`

Do not modify `CHARTER.md`, `AGENTS.md`, `.strategy/**`, real user data,
dependency files, or unrelated modules.

---

### Task 1: RED - Add Analyze Alias Contract Test

- [ ] Add a contract test to `tests/contract/test_aggregate_cli_contract.py`
  that runs:

```powershell
python -m tools analyze --range 2026-03-14..2026-03-16 --unit day --predicate journal_count --json
```

- [ ] Assert:
  - return code is `0`
  - stdout is valid JSON
  - `payload["success"] is True`
  - `payload["command"] == "aggregate"`
  - `payload["result"]["count"] == 3`
  - `claim_envelope` and `evidence_pack` are present

- [ ] Run:

```powershell
pytest tests/contract/test_aggregate_cli_contract.py::TestAggregateCliContract::test_analyze_alias_matches_aggregate_contract -q
```

Expected: fail because `analyze` is not yet registered in `tools.__main__`.

---

### Task 2: GREEN - Register Analyze Alias

- [ ] In `tools/__main__.py`, add `analyze` to `cmd_map` with the same target
  as `aggregate`:

```python
"analyze": "tools.aggregate.__main__",
```

- [ ] Add a usage line:

```python
print("  analyze   Alias for deterministic aggregate/trend computation")
```

- [ ] Run the new contract test again.

Expected: pass.

---

### Task 3: Document Alias Boundary

- [ ] In `docs/API.md`, update the aggregate endpoint block to include:

```bash
life-index analyze --range <since>..<until> --unit <unit> --predicate <predicate> [--query "..."] [--explain] [--json]
python -m tools analyze --range <since>..<until> --unit <unit> --predicate <predicate> [--query "..."] [--explain] [--json]
```

- [ ] Replace the limitation saying `analyze` is unimplemented with:

```markdown
- `analyze` is an alias for `aggregate`; JSON output still uses `"command": "aggregate"`.
```

---

### Task 4: Verification and Post-Commit CI Polling

- [ ] Run:

```powershell
pytest tests/contract/test_aggregate_cli_contract.py tests/unit/test_aggregate.py -q
```

- [ ] Run:

```powershell
git diff --check
git status --short --branch
```

- [ ] If changes are committed and pushed, run a 3-minute GitHub Actions polling window per `.agent-governance/maestro/MAESTRO-ORCHESTRATION-SOP.md` §Post-Commit Gate Ownership Rule. Report started workflows, early failures, and any workflows still running after the window.

- [ ] Report changed files, verification commands, and residual risks.
