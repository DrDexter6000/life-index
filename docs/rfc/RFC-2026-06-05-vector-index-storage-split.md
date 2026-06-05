# RFC: Vector Index Storage Split (metadata pickle + matrix file)

Status: Proposed (Foundation Freeze — schema/format decision, gated for M16–M24)
Created: 2026-06-05
Classification: index storage-format change; back-compat migration; no user-data
(Markdown) change; no search-ranking change. Implementation deferred to acceptance.
Related: `tools/lib/vector_index_simple.py`, `tools/lib/semantic_baseline.py`,
`tools/build_index/__init__.py`, `tests/contract/test_r12_crash_recovery.py`,
`tests/unit/test_vector_atomic_write.py`, `CHARTER.md` (rebuildable-index principle),
[[project_vector_index_scale]]

## 1. Decision

Split the `SimpleVectorIndex` on-disk representation into:

- a **metadata pickle** (`vectors_simple.pkl`) holding only `{path: {date, hash,
  added_at}}` — no embeddings; and
- an **embedding matrix file** (`vectors_simple_emb.npz`) holding a single
  normalized `float32 (N, dim)` array plus a parallel `paths` array.

In memory, embeddings leave `self.vectors` (which becomes metadata-only) and live
solely in the cached matrix. Loads mmap the matrix instead of unpickling N Python
lists. Old single-file pickles (embeddings inline) are auto-migrated to the split
format on first load.

This RFC authorizes TDD implementation **after acceptance**. It does not itself
change CLI behavior, JSON output, search ranking, or user data.

This RFC is the deferred follow-up to the already-shipped vectorized `search()`
fix (single matmul, cached matrix), which removed the per-query O(N) cliff but
left the cold-load cost untouched.

## 2. Problem And Evidence

A 2026-06-05 scale-decay benchmark (`tools/dev/scale_benchmark.py`, dim=1024
bge-m3, 500 ms p95 SLO) established:

- Query-time semantic search runs **only** through `SimpleVectorIndex.search()`
  (`tools/search_journals/semantic.py`); the sqlite-vec `journal_vectors` table is
  built but never queried for similarity. So the simple index is the real path.
- The pre-vectorization per-doc loop crossed the SLO at **~12.5k docs** — below a
  lifetime of daily journaling (~18k). The vectorized fix made per-query latency
  flat (~17 ms p95 @ 50k).
- The remaining bottleneck is **cold load**, measured at 50k:

  | step | time | size |
  |---|---|---|
  | pickle load (dict-of-lists, current) | **2397 ms** | 463 MB |
  | metadata-only pickle load | 30 ms | 2 MB |
  | matrix `.npz` load (full read) | 234 ms | 209 MB |
  | matrix `.npz` mmap | **0.9 ms** | — |

A one-shot CLI search pays the full load each invocation. At 50k the current
format is ~2.6 s — ~5× over SLO. The split format yields ~30 ms (meta) + ~1 ms
(mmap) + ~4 ms (matmul) ≈ **35 ms**, ~14× under SLO; ~70 ms projected at 100k.

Realistic lifetime scale is tens of thousands (daily 50 yr ≈ 18k; 5/day ≈ 91k),
not millions. The split comfortably covers that range without an external vector
DB, preserving the no-heavy-dependency / 50-year-survival posture.

## 3. Design

In-memory model:

- `self.vectors: Dict[str, Dict]` — metadata only (`date`, `hash`, `added_at`).
- `self._matrix: np.ndarray | None` — normalized `float32 (N, dim)`; the embedding
  source of truth in memory.
- `self._matrix_paths`, `self._row_of` — row ↔ path mapping; `self._matrix_dates`
  — `<U32` array for date filtering.
- `self._pending_emb: Dict[str, list]` — embeddings staged by `add()` this session,
  not yet materialized into the matrix.

Method changes:

- `add(path, emb, date, hash)`: store metadata in `self.vectors`; stage `emb` in
  `_pending_emb`; invalidate matrix.
- `remove` / `clear`: drop metadata + pending; invalidate.
- `_build_matrix()`: assemble rows for `list(self.vectors)` taking each embedding
  from `_pending_emb` if present, else the prior matrix row via `_row_of`
  (preserves unchanged rows on incremental update); clear pending.
- `get(path)` → metadata; new `get_embedding(path)` / `get_matrix()` for the few
  embedding consumers.
- `search()`: unchanged from the vectorized version (operates on `self._matrix`).
- `_save()`: write matrix `.npz` (atomic temp+rename) **first**, then metadata
  pickle (atomic temp+rename), then meta json.
- `_load()`: load metadata pickle; if entries contain `embedding` → migrate; else
  mmap the matrix and verify `set(paths) == set(self.vectors)`.

## 4. Back-Compat And Migration

On `_load()`, if the pickle is old-format (entries contain `embedding`):

1. extract each embedding, normalizing any entry lacking `normalized: True`
   (mirrors the legacy per-doc normalization);
2. stage them, rebuild the matrix, strip `embedding`/`normalized` from metadata;
3. write the split format (metadata pickle + matrix `.npz`).

The Markdown journals are untouched; the index remains fully rebuildable from
source, so migration is best-effort and self-healing (a failed/partial migration
falls back to a full rebuild on the next `index` run).

## 5. Atomicity And Crash Recovery (r12)

Moving from one file to two introduces a consistency window. Invariants to keep:

- **Graceful degradation** (`test_r12_crash_recovery.py`): a missing/inconsistent
  vector index ⇒ semantic returns empty and keyword search still works — never a
  crash. Load must treat *either* file missing, or a `paths`-set mismatch, as
  "no semantic index" (degraded), not an error.
- **Write order**: matrix first, pickle last. If the pickle (metadata-only) is
  present it implies the matrix was written; the only crash residue is a stale
  matrix with an old/inline pickle, which the migration path rebuilds.
- **`vector_checksum` freshness**: keep the existing index-meta checksum coherent
  with the new files so `test_r12_index_reliability.py` freshness checks hold.
- `get_vec_index_path().exists()` (used by `get_semantic_runtime_status`) stays a
  valid "index built" signal because the metadata pickle keeps that name.

## 6. Blast Radius

| File | Change |
|---|---|
| `tools/lib/vector_index_simple.py` | storage model + save/load + migration |
| `tools/lib/semantic_baseline.py` | add `compute_semantic_baseline_from_matrix()` |
| `tools/build_index/__init__.py` | baseline call site uses the matrix |
| `tests/unit/test_vector_atomic_write.py` | assert new two-file atomic write |
| `tests/unit/test_vector_search_semantics.py` | set up via `add()` (model-agnostic) |
| `tests/unit/test_vector_split_format.py` (new) | round-trip, migration, incremental |

## 7. Test Plan (TDD, on acceptance)

1. Round-trip: `add` → `commit` → fresh instance `load` → identical ranked results.
2. Format: post-commit pickle has no `embedding`; matrix `.npz` exists with matching `paths`.
3. Migration: old inline pickle (incl. a legacy un-normalized vector) → migrates →
   correct normalized search → split format on disk.
4. Incremental: build {a,b}, commit; add c incrementally, commit; reload → a,b,c
   all present with correct vectors (unchanged rows preserved).
5. Degradation: matrix missing / pickle missing / `paths` mismatch → search returns
   `[]`, no crash (re-assert r12 contract).
6. Baseline: `compute_semantic_baseline_from_matrix` matches the previous
   dict-based result within tolerance.
7. Full suite: unit layer + `test_r12_*` + `test_build_index` + `test_search_semantic`.

## 8. Alternatives Considered

- **`.npz` sidecar cache, pickle unchanged** — rejected: removes only the matrix
  *build*, not the 2.4 s pickle *load*; does not meet the SLO goal.
- **Wire up the existing sqlite-vec `journal_vectors` KNN** — scales further but
  depends on `vec0.dll`, the Windows fragility that drove the pure-Python path;
  conflicts with the no-native-dependency posture. Tracked separately as the
  "vec0 built-but-never-queried" cleanup decision.
- **External vector DB (milvus/qdrant/weaviate)** — rejected: heavyweight service
  dependency, contrary to data-sovereignty / 50-year-survival.

## 9. Non-Goals

- No change to journal Markdown, search ranking, JSON envelopes, or CLI surface.
- No model retraining/fine-tuning.
- No resolution of the sqlite-vec build-vs-query question (separate decision).

## 10. Rollout

Implement behind the existing rebuildable-index guarantee; first `index` run after
upgrade migrates in place. No version bump until the owning milestone's release
gate. Benchmark (`tools/dev/scale_benchmark.py`) re-run as the acceptance evidence.
