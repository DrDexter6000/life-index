# RFC-2026-06-05: sqlite-vec Query Path Decision Note

**Status**: Decision note; owner decision pending
**Scope**: Evidence and recommendation only; no sqlite-vec code changes
**Related**: RFC-2026-06-05 Vector Index Storage Split

## Finding

`journal_vectors` is built and maintained, but query-time semantic retrieval does
not use it for similarity search. Semantic retrieval enters through
`tools/search_journals/semantic.py`, which calls `SimpleVectorIndex.search()`.

Grep evidence from `tools/`:

- `rg "journal_vectors" tools -n` finds build/maintenance/verify references:
  - `tools/lib/semantic_search.py` creates, deletes, inserts, counts, and reads
    path/hash rows for `journal_vectors`.
  - `tools/verify/core.py` checks paths from `journal_vectors`.
- `rg "vec_distance|MATCH\\s+|knn|kNN|ORDER BY .*distance|distance\\(" tools -n`
  finds FTS `MATCH` usage only; no sqlite-vec KNN or `vec_distance` query against
  `journal_vectors`.
- `rg "SimpleVectorIndex|vector_index_simple|get_index\\(\\)|semantic_search" tools/search_journals tools/lib -n`
  shows `tools/search_journals/semantic.py` importing `get_model` and `get_index`
  from `tools/lib/vector_index_simple.py` and calling the simple vector index at
  query time.

## Options

### A) Wire sqlite-vec KNN at query time

This would use the already-built `journal_vectors` vec0 table and could scale
beyond brute-force matrix search.

Trade-offs:

- Pros: reuses an existing built index; gives an ANN-style path if future corpus
  size exceeds the matrix SLO.
- Cons: depends on sqlite-vec / `vec0.dll`, reintroducing the Windows native
  dependency fragility that the pure-Python path avoids.
- Cons: conflicts with the no-native-dependency and long-horizon portability
  posture unless sqlite-vec becomes an explicit optional backend.

### B) Drop the unused sqlite-vec build

This removes the dead ANN build path and keeps query-time semantic retrieval on
the split `SimpleVectorIndex` matrix format.

Trade-offs:

- Pros: removes dead code, dual-path build complexity, native dependency
  fragility, and unnecessary index work.
- Pros: the split matrix format already satisfies the lifetime-scale one-shot
  CLI SLO measured by the vector storage split benchmark.
- Cons: gives up the prebuilt ANN fallback unless a future RFC reintroduces it
  as an explicit optional backend.

## Recommendation

Recommend option B: drop the unused sqlite-vec build in a future owner-approved
cleanup RFC/PR. The split `SimpleVectorIndex` format meets the current
lifetime-scale SLO without the native sqlite-vec dependency, and retaining an
unqueried ANN table adds build cost and operational ambiguity without user-facing
benefit.

Do not change sqlite-vec code as part of the vector storage split PR.
