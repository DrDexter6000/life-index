#!/usr/bin/env python3
"""Scale-decay benchmark for the SimpleVectorIndex search path (no LLM needed).

Why no LLM / no embedding model:
  Vector-scan latency, memory, and footprint depend only on (N, dim) -- not on
  text semantics. A cosine over N x 1024 floats costs the same for any content.
  So we synthesise N random *unit* vectors directly. dim=1024 is faithful to the
  real embedding model (BAAI/bge-m3).

What it measures, per corpus size N:
  baseline_p95 : a verbatim copy of the PRE-vectorization per-doc Python loop
                 (kept here only to document why the fix matters / regression).
  current_p95  : the real SimpleVectorIndex.search() (vectorized matmul).
  build_ms     : one-time cost to build the cached matrix on the first search
                 of a process (the list-pickle -> ndarray conversion). Amortized
                 across queries in a long-running process; paid per invocation
                 by a one-shot CLI.
  dict_mb/mat_mb : Python-heap footprint of the list storage vs the float32 matrix.

This never touches real user data: it points the index at an empty temp dir.

Usage:
  python -m tools.dev.scale_benchmark            # default grid up to 50k
  python -m tools.dev.scale_benchmark --max 100000
"""

import argparse
import gc
import os
import sys
import tempfile
import time
import tracemalloc
from typing import Any, Dict, List, Tuple

import numpy as np

DIM = 1024
TOP_K = 20
N_QUERIES = 25
SLO_MS = 500.0
DEFAULT_GRID = [1_000, 5_000, 10_000, 25_000, 50_000]


def _unit_matrix(n: int) -> np.ndarray:
    m = np.random.default_rng(42).standard_normal((n, DIM)).astype(np.float32)
    m /= np.linalg.norm(m, axis=1, keepdims=True) + 1e-8
    return m


def _baseline_loop(
    vectors: Dict[str, Dict[str, Any]], query: List[float], top_k: int = TOP_K
) -> List[Tuple[str, float]]:
    """Verbatim pre-fix search(): per-doc np.array() conversion + np.dot."""
    q = np.array(query, dtype=np.float32)
    results = []
    for path, data in vectors.items():
        dv = np.array(data["embedding"], dtype=np.float32)
        if not data.get("normalized", False):
            dv = dv / (np.linalg.norm(dv) + 1e-8)
        results.append((path, float(np.dot(q, dv))))
    results.sort(key=lambda x: x[1], reverse=True)
    return results[:top_k]


def _pct(xs: List[float], p: float) -> float:
    return float(np.percentile(xs, p))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--max", type=int, default=50_000, help="largest corpus size to measure (default 50000)"
    )
    args = ap.parse_args()
    grid = [n for n in DEFAULT_GRID if n <= args.max]
    if args.max not in grid:
        grid.append(args.max)

    # Isolate before importing path-aware modules; never touch real data.
    os.environ["LIFE_INDEX_DATA_DIR"] = tempfile.mkdtemp()
    from tools.lib.vector_index_simple import SimpleVectorIndex

    queries = [
        np.random.default_rng(i).standard_normal(DIM).astype(np.float32).tolist()
        for i in range(N_QUERIES)
    ]
    rows = []

    for n in grid:
        print(f"[N={n:,}] building ...", file=sys.stderr, flush=True)
        M = _unit_matrix(n)
        mat_mb = M.nbytes / (1024 * 1024)

        gc.collect()
        tracemalloc.start()
        vectors = {
            f"Journals/2026/p{i}.md": {
                "embedding": M[i].tolist(),
                "date": "2026-01-01",
                "normalized": True,
            }
            for i in range(n)
        }
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        dict_mb = peak / (1024 * 1024)

        # Pre-fix baseline (per-doc loop).
        _baseline_loop(vectors, queries[0])  # warm
        base = []
        for q in queries:
            t = time.perf_counter()
            _baseline_loop(vectors, q)
            base.append((time.perf_counter() - t) * 1000)

        # Current real search() (vectorized). First call builds the matrix.
        idx = SimpleVectorIndex()
        idx.vectors = vectors
        idx._invalidate_matrix()
        t0 = time.perf_counter()
        idx.search(queries[0], top_k=TOP_K)
        build_ms = (time.perf_counter() - t0) * 1000
        cur = []
        for q in queries:
            t = time.perf_counter()
            idx.search(q, top_k=TOP_K)
            cur.append((time.perf_counter() - t) * 1000)

        rows.append((n, _pct(base, 95), _pct(cur, 95), build_ms, dict_mb, mat_mb))
        del vectors, idx, M
        gc.collect()

    print()
    print(
        f"SimpleVectorIndex scale-decay  (dim={DIM}, top_k={TOP_K}, "
        f"{N_QUERIES} queries, SLO p95<{SLO_MS:.0f}ms)"
    )
    print("=" * 84)
    print(
        f"{'N':>8} | {'baseline p95':>13} | {'current p95':>12} | "
        f"{'build ms':>9} | {'dict MB':>8} | {'mat MB':>7}"
    )
    print("-" * 84)
    for n, bp95, cp95, bms, dmb, mmb in rows:
        print(
            f"{n:>8,} | {bp95:11.1f}   | {cp95:10.2f}   | {bms:8.1f}  | "
            f"{dmb:7.1f}  | {mmb:6.1f} "
        )
    print("-" * 84)
    print("baseline = pre-fix per-doc Python loop; current = vectorized matmul.")
    print(
        "Per-query scan is now flat; one-time build_ms is the list-pickle -> "
        "ndarray cost\n(amortized in a long-running process; paid per one-shot "
        "CLI invocation)."
    )


if __name__ == "__main__":
    main()
