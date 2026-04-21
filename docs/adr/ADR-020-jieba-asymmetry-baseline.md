# ADR-020: Jieba Dual-Mode Tokenization Asymmetry Baseline

**Status**: Accepted
**Date**: 2026-04-21
**Round/Phase**: Round 16 Phase 0 (Baselines)

## Context

Round 13 introduced jieba-based Chinese tokenization with a dual-mode design (chinese_tokenizer.py):
- **Index mode**: `jieba.cut()` — precise segmentation, used at FTS index build time
- **Query mode**: `jieba.cut_for_search()` — finer granularity, used at search query time

This asymmetry is intentional (MD1 in chinese_tokenizer.py): precise tokens for indexing, expanded tokens for searching. However, if jieba's internal implementation changes between versions (dictionary updates, HMM model adjustments), the output spaces of these two modes may drift relative to each other, silently reducing recall (index tokens and query tokens overlap less).

Round 16 Audit Synthesis §10.2 (R1) identified that the original "60% intersection" threshold was a made-up number that would self-trigger on any jieba upgrade. This ADR replaces it with a measured baseline approach.

## Baseline Measurement

**Measured on**: 2026-04-21
**Jieba version**: `0.42.1` (exact-pinned in `pyproject.toml`)
**Corpus**: `tests/golden/jieba_asymmetry_corpus.json` — 20 fixed entries, 5 categories (family/work/health/emotion/location × 4 each)

### Results

| Metric | Value |
|--------|-------|
| **r₀ (mean intersection ratio)** | **0.9008** |
| r₀ std | 0.0948 |
| r₀ min | 0.7059 |
| r₀ max | 1.0000 |

**Intersection ratio per entry**: Jaccard similarity between `set(jieba.cut(text))` and `set(jieba.cut_for_search(text))`.

### Threshold Formula

```
golden_threshold = max(0.5, r₀ - 0.05) = max(0.5, 0.9008 - 0.05) = 0.8508
```

- **Threshold = 0.8508**: Any jieba version upgrade must maintain intersection ratio ≥ 0.8508 across all 20 corpus entries (mean)
- **Alert threshold = r₀ - 0.10 = 0.8008**: Ratio dropping below this triggers a hard alert — real drift detected
- **Note threshold = r₀ - 0.05 = 0.8508**: Ratio dropping below this but above 0.8008 is a "needs attention" signal, not a block

## Decision

1. Pin jieba to exact version `0.42.1` in `pyproject.toml` (not `>=0.42.1`)
2. Fix corpus at `tests/golden/jieba_asymmetry_corpus.json` (20 entries, immutable)
3. Golden test uses measured threshold `0.8508`, not a hardcoded percentage
4. On jieba upgrade: re-run `scripts/measure_jieba_baseline.py`, update this ADR with new r₀, update test code comments
5. Test code must include comment: `# baseline measured on jieba 0.42.1: r₀ = 0.9008, threshold = 0.8508`

### HMM Model Inclusion Decision

**Decision**: HMM model state is NOT included in the version fingerprint for tokenizer freshness detection.

**Reason**: jieba does not expose a stable API for querying HMM model state. The dictionary hash + jieba version string already provide sufficient change detection for the tokenization output space. If jieba internally changes HMM behavior without a version bump, the golden test will catch it via the intersection ratio threshold.

## Consequences

### Positive
- Jieba upgrades are safe: threshold is empirically grounded, not arbitrary
- Silent recall degradation becomes detectable and measurable
- Corpus is fixed and reproducible across machines

### Negative
- Jieba version upgrades require manual baseline re-measurement
- Threshold may need adjustment if corpus is changed (but corpus should be immutable)

### Risk
- If r₀ is very high (0.90), even small jieba changes may trigger "note" alerts — this is acceptable and by design (better over-sensitive than under-sensitive)

## Files

- Baseline data: `tests/golden/jieba_baseline.json`
- Corpus: `tests/golden/jieba_asymmetry_corpus.json`
- Measurement script: `scripts/measure_jieba_baseline.py`
- Ranking baseline: `tests/golden/ranking_eval_baseline.json`
