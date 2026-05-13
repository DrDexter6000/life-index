# M02 Evidence-Based Aggregate & Analysis Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add additive `claim_envelope` and aggregate `evidence_pack` objects to deterministic aggregate/analyze results.

**Architecture:** Keep `tools.aggregate.core.run_aggregate()` as the deterministic calculator. Add a pure helper module that builds claim/evidence objects from aggregate result metadata and scanned journal entries. Smart-search receives the new objects automatically through the existing `aggregate_result` path.

**Tech Stack:** Python stdlib, pytest, existing `tools.aggregate`, `tools.search_journals`, and docs/API markdown.

---

## Files

- Create: `tools/aggregate/claim_envelope.py`
- Modify: `tools/aggregate/core.py`
- Modify: `tests/unit/test_aggregate.py`
- Modify: `tests/unit/test_orchestrator.py`
- Modify: `tests/contract/test_aggregate_cli_contract.py`
- Modify: `docs/API.md`

Do not modify `CHARTER.md`, `.strategy/**`, real user data, dependency files, or unrelated modules.

---

### Task 1: Add Red Tests For Aggregate Claim/Evidence Objects

**Files:**
- Modify: `tests/unit/test_aggregate.py`
- Modify: `tests/unit/test_orchestrator.py`
- Modify: `tests/contract/test_aggregate_cli_contract.py`

- [ ] Add a unit test asserting `journal_count` returns `claim_envelope.schema_version == "m02a.claim_envelope.v0"`, `claim_type == "measurable_exact"`, `value == result.count`, and `evidence_pack.items` contains matched relative paths.

- [ ] Add a unit test asserting `term_presence=晚睡` returns `claim_type == "measurable_approximate"` and an evidence pack with `role == "matched"` for matched entries.

- [ ] Add a unit test asserting date-only `entry_time_after=22:00` returns `claim_type == "not_measurable"`, `value == 0`, and unknown evidence items with `reason == "no_time_field_available"`.

- [ ] Add a smart-search unit test asserting aggregate-routed queries include `aggregate_result.claim_envelope` and `aggregate_result.evidence_pack` while preserving no-LLM routing behavior.

- [ ] Add a contract test asserting CLI JSON output includes `claim_envelope` and `evidence_pack`, and evidence item paths are relative with forward slashes.

- [ ] Run:

```powershell
pytest tests/unit/test_aggregate.py tests/unit/test_orchestrator.py tests/contract/test_aggregate_cli_contract.py -q
```

Expected: new tests fail because implementation is not present yet.

---

### Task 2: Implement Pure Aggregate Claim/Evidence Builder

**Files:**
- Create: `tools/aggregate/claim_envelope.py`

- [ ] Implement constants:

```python
CLAIM_SCHEMA_VERSION = "m02a.claim_envelope.v0"
EVIDENCE_SCHEMA_VERSION = "m02a.aggregate_evidence_pack.v0"
```

- [ ] Implement exactness mapping:

```python
def claim_type_from_exactness(exactness: str) -> str:
    if exactness == "exact":
        return "measurable_exact"
    if exactness == "approximate":
        return "measurable_approximate"
    return "not_measurable"
```

- [ ] Implement a helper that returns month-level `index_node_ref` from an entry date:

```python
def index_node_ref_for_date(date_str: str) -> dict[str, str] | None:
    # "2026-03-14" -> Journals/2026/03/index_2026-03.md
```

- [ ] Implement:

```python
def build_claim_envelope(aggregate_result: dict[str, Any]) -> dict[str, Any]:
    ...
```

It must copy query, metric, unit, range, predicate, value, denominator, exactness, confidence, limitations, and source command from the aggregate result.

- [ ] Implement:

```python
def build_evidence_pack(
    *,
    aggregate_result: dict[str, Any],
    entry_dates: dict[str, str],
    bucket_by_path: dict[str, str],
) -> dict[str, Any]:
    ...
```

It must include matched/excluded/unknown items, `page_info`, and optional `index_node_ref`.

---

### Task 3: Integrate Builder Into `run_aggregate`

**Files:**
- Modify: `tools/aggregate/core.py`

- [ ] Preserve the existing aggregate output fields exactly.

- [ ] While computing buckets, build:

```python
entry_dates = {entry["path"]: entry["date"].isoformat() for entry in entries}
bucket_by_path = {entry["path"]: _bucket_key(entry["date"], unit) for entry in entries}
```

- [ ] After the existing `result` dict is assembled, add:

```python
from tools.aggregate.claim_envelope import build_claim_envelope, build_evidence_pack

result["claim_envelope"] = build_claim_envelope(result)
result["evidence_pack"] = build_evidence_pack(
    aggregate_result=result,
    entry_dates=entry_dates,
    bucket_by_path=bucket_by_path,
)
```

- [ ] Do not add these objects to error results in v0.

- [ ] Run:

```powershell
pytest tests/unit/test_aggregate.py -q
```

Expected: aggregate unit tests pass.

---

### Task 4: Verify Smart-Search Delegation And CLI Contract

**Files:**
- Modify only if needed: `tools/search_journals/orchestrator.py`
- Modify only if needed: `tools/aggregate/__main__.py`

- [ ] Confirm no orchestrator changes are needed if `aggregate_result` already carries the new objects.

- [ ] Run:

```powershell
pytest tests/unit/test_orchestrator.py tests/contract/test_aggregate_cli_contract.py -q
```

Expected: tests pass.

---

### Task 5: Update API Documentation

**Files:**
- Modify: `docs/API.md`

- [ ] In the aggregate section, document additive `claim_envelope` and `evidence_pack`.

- [ ] In the smart-search aggregate delegation section, clarify the new objects live inside `aggregate_result`.

- [ ] State that `index_node_ref` and `page_info` are future-compatibility hooks, not full Index Tree API or batch/cursor commitments.

---

### Task 6: Final Verification

- [ ] Run focused tests:

```powershell
pytest tests/unit/test_aggregate.py tests/unit/test_orchestrator.py tests/contract/test_aggregate_cli_contract.py -q
```

- [ ] Run aggregate eval if quick:

```powershell
python -m tools eval --quick
```

If this command is unavailable or too broad, report the exact failure and run the focused tests instead.

- [ ] Run:

```powershell
git diff --check
git status --short --branch
```

- [ ] Report changed files, tests run, and any residual risks.
