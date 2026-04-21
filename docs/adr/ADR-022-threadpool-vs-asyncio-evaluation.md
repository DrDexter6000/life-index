# ADR-022: ThreadPoolExecutor Reuse vs asyncio Migration Evaluation

**Status**: Proposed
**Date**: 2026-04-21
**Round/Phase**: Round 16 Package D

## Context

In `tools/search_journals/core.py` at line 732, the dual-pipeline search creates a new `ThreadPoolExecutor(max_workers=2)` on every call:

```python
with ThreadPoolExecutor(max_workers=2) as executor:
    future_keyword = executor.submit(run_keyword_pipeline, ...)
    future_semantic = executor.submit(run_semantic_pipeline, ...)
    # ...
```

This happens on every search invocation. Two refactoring paths exist:

- **Path A**: Global singleton `ThreadPoolExecutor(max_workers=2)` — reuse a persistent pool across calls
- **Path B**: `asyncio.gather()` + `run_in_executor()` — migrate to native async/await

## Decision

### Path A: Global Singleton ThreadPoolExecutor

```python
# module-level singleton
_search_executor: ThreadPoolExecutor | None = None

def _get_search_executor() -> ThreadPoolExecutor:
    global _search_executor
    if _search_executor is None:
        _search_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="search")
    return _search_executor
```

**Pros:**
- Minimal code change; structural refactor only
- Thread pool is reused across calls, eliminating thread creation overhead
- Existing `concurrent.futures` code stays as-is; no asyncio migration needed
- `shutdown()` on process exit via `atexit` handler is straightforward

**Cons:**
- `ThreadPoolExecutor` is process-local; still subject to Python GIL for CPU-bound work (though the search pipelines are mostly I/O-bound)
- Singleton lifetime management is manual; need `atexit` cleanup
- Does not address the fundamental blocking nature of `executor.submit()` in an async context (if the project ever adds async callers)

### Path B: asyncio.gather + run_in_executor

```python
async def search_journals_async(...):
    loop = asyncio.get_running_loop()
    keyword_future = loop.run_in_executor(None, run_keyword_pipeline, ...)
    semantic_future = loop.run_in_executor(None, run_semantic_pipeline, ...)
    keyword_result, semantic_result = await asyncio.gather(keyword_future, semantic_future)
    # ...
```

**Pros:**
- Native async/await — no thread context switching overhead
- If the project ever adds FastAPI/Starlette web endpoints, this path integrates naturally
- Better cancellation semantics via `asyncio.Future`
- `gather()` handles exceptions cleanly with `return_exceptions=True`

**Cons:**
- Requires converting the entire call chain to `async` — `search_journals` CLI entry point is synchronous; the change ripples upward to the tool's `__main__.py`
- `asyncio` event loop management on Windows has edge cases (though not blocking for this tool)
- Higher implementation complexity: need to handle loop setup, executor shutdown, and potential nested loop scenarios
- The current synchronous code is readable and correct; the benefit is not obvious for a CLI tool that is not I/O-bound on the Python side

### Order-of-Magnitude Overhead Estimate

**ThreadPoolExecutor creation cost per call:**

Based on typical Python benchmarks, creating a `ThreadPoolExecutor` with 2 workers involves:
- Allocating thread stack space (~$8KB per thread minimum, OS-dependent)
- Starting 2 native threads (~$1-5ms on typical hardware)
- Creating the executor's internal work queue and state

Rough estimate: **1-5ms overhead per search call** just for pool creation, on top of the actual search time (typically 50-500ms for a search with I/O).

For a CLI tool invoked a few times per day by a human user, this overhead is negligible (~0.1% of total search time).

For a high-frequency automated scenario (e.g., an Agent looping over 100 searches), the cumulative overhead could reach **100-500ms** — still small relative to the I/O-bound search time.

### Recommendation

**Defer both paths. No implementation in Round 16.**

Performance changes are explicitly **out of scope for Round 16 freeze period**. Round 16 is a hardening and baseline freeze; no performance refactors should land during the freeze.

**Trigger conditions for Path A (global singleton) in Round 17:**

1. A performance baseline measurement shows ThreadPool creation is ≥5% of total search time (measured via `timing_ms` in search results)
2. Round 16 pytest suite passes with no changes needed
3. `file_lock.py` is confirmed to be the sole serialization mechanism (not ThreadPool-based) — already true, but should be verified

**Trigger conditions for Path B (asyncio migration) in Round 18+:**

1. The project adopts an async web layer (FastAPI/Starlette) that requires non-blocking I/O
2. Path A has been live for ≥1 round with no issues
3. Performance profiling shows asyncio `gather()` + `run_in_executor()` provides measurable benefit over Path A

**Path A is preferred over Path B for the Round 17 implementation** because:
- Simpler change surface (no async/await ripple through call chain)
- Sufficient performance gain (eliminates pool creation overhead)
- Thread pool reuse is a well-understood pattern with clear lifetime management

### Prerequisites Before Implementation

1. **Performance baseline** — Run `search_journals` 20 times with representative queries, record `timing_ms` in each result. Establish mean and p95 before any change.
2. **file_lock verification** — Confirm `file_lock.py` is the only cross-process serialization mechanism; ThreadPool is not used for any locking. Verified already (see `core.py` imports), but should be logged as a TODO comment at implementation time.
3. **Test coverage** — Ensure `tests/unit/tools/search_journals/` covers the dual-pipeline path; if not, add tests before refactoring.
4. **Windows compatibility check** — `ThreadPoolExecutor` with `thread_name_prefix` works on Windows but verify no OS-specific edge cases in the project CI.

### Explicit Scope Exclusion

> **Performance changes are out of scope for Round 16 freeze period.**

This ADR is an evaluation and decision record. Implementation of either path is deferred to Round 17 or later, after the Round 16 freeze lifts.

## Consequences

### Positive

- No change to existing behavior during Round 16 freeze
- Decision is made now so Round 17 implementors have a clear direction and trigger conditions
- Path A requires only a structural change; no algorithmic changes to search pipelines

### Negative

- Thread pool creation overhead remains on every search call through Round 16
- The overhead is measurable but small; no user-visible degradation

### Risk

- If Path A is implemented and `atexit` handler is forgotten, the singleton executor's threads may not be cleaned up on process exit — minor resource leak, not a correctness issue
- Path B, if chosen later, will be more disruptive the longer it is deferred; but there is no current driver for Path B (no async web layer)
