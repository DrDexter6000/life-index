# CN-004: Jina v5-omni Embedding Assessment

**Status:** accepted direction
**Date:** 2026-05-14
**Scope:** Life Index embedding model direction

## Decision

Life Index keeps `BAAI/bge-m3` as the current default text embedding model.
`jina-embeddings-v5-omni` is recorded as a future multimodal-memory candidate,
not as a current replacement for the text retrieval stack.

## Rationale

The current product gap is deterministic aggregate/analyze, such as answering
"how many days in the last 60 days match this measurable predicate", with
auditable evidence. Replacing the embedding model does not solve that class of
problem.

`jina-embeddings-v5-omni` is strategically relevant for a future Life Index that
indexes images, audio, video, scans, and PDFs in one vector space. It is not a
drop-in no-reindex migration for this project because Life Index currently uses
`BAAI/bge-m3`, while Jina's compatibility claim applies to Jina v5 text indexes.

The model is also very new. Available evidence is mostly official material or
self-reported leaderboard discussion. Independent production experience is not
yet strong enough to justify making it a foundation dependency.

## Current Implications

- Do not replace `BAAI/bge-m3` in M02/M03.
- Do not start a multimodal ingestion or embedding migration project in this
  workstream.
- Continue the deterministic aggregate/analyze path first.
- If embedding work is needed, first inspect unused `bge-m3` capabilities such
  as sparse and multi-vector/ColBERT-style retrieval before adopting a new model.

## Future Trigger Conditions

Reconsider `jina-embeddings-v5-omni` or a similar multimodal model when at least
one of these conditions is true:

- Life Index starts a real media-memory module for images, audio, video, scans,
  or PDFs.
- Independent benchmarks and community evaluations mature beyond official or
  self-reported evidence.
- License and distribution constraints are acceptable for the intended release
  model.
- The codebase has explicit embedding backend metadata and index namespaces so
  model experiments cannot silently corrupt or overwrite existing indexes.

## Non-Decisions

This note does not define a multimodal roadmap, media ingestion API, commercial
licensing policy, or long-running analysis framework.
