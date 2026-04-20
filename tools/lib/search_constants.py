"""
Life Index - Search Constants Module
====================================
Centralized constants for search pipelines with ADR rationale.

This module is the SSOT for all search-related magic numbers.
Any change to these values must be documented with the rationale.

ADR-001: RRF k=60
-----------------
The Reciprocal Rank Fusion smoothing constant k=60 is a well-established
default from Cormack et al. (SIGIR 2009). It balances rank position influence
vs. score distribution across heterogeneous retrieval pipelines.

Lower values (k=20-40) give more weight to top-ranked items.
Higher values (k=80-100) flatten the score distribution.
k=60 is the industry standard that works well for most hybrid search scenarios.

ADR-002 / ADR-006: Semantic threshold floor + adaptive baseline
---------------------------------------------------------------
Semantic search now uses an absolute floor of 0.40 plus an adaptive layer:
`max(0.40, semantic_baseline_p25 + 0.02)`.

ADR-006 records the rationale: the old 0.15 floor was too permissive and let
semantic noise leak into results. Rebuild-time corpus calibration persists the
baseline P25 into `index_meta`, allowing future corpus growth to auto-adjust.

ADR-003: FTS min_relevance=25
----------------------------
BM25 relevance threshold (0-100 scale) for keyword results. Below 25, matches
are typically fragment hits or stop-word contamination.

This value ensures only meaningful keyword matches appear in results.

ADR-004: RRF min_score=0.008
----------------------------
Minimum RRF score for hybrid results. Below this threshold, documents have
very weak evidence from BOTH pipelines and should be excluded.

Calculated from typical RRF score distribution:
- Strong matches: 0.02-0.05
- Moderate matches: 0.01-0.02
- Weak matches: 0.005-0.01
- Noise: < 0.005

ADR-005: Semantic top_k=30
--------------------------
Maximum semantic candidates to retrieve. Higher values increase recall but
may dilute precision and slow down the pipeline.

30 is a good balance: captures most relevant semantic matches while keeping
the ranking phase efficient.

ADR-006: Max results=20
-----------------------
Maximum results returned to user. Beyond 20, cognitive load increases while
marginal value decreases sharply.

Users can paginate or refine queries if they need more.

ADR-007: FTS fallback threshold=5
---------------------------------
When FTS returns fewer than 5 results, we supplement with full-corpus scan.
This catches body-only keyword matches that might be missed by stale index.

5 is low enough to avoid unnecessary scans, but high enough to catch
legitimate low-recall scenarios.

ADR-008: Score weights
----------------------
- L1 base score: 10 (presence indicator)
- L2 base score: 30 (metadata match, must exceed FTS_MIN_RELEVANCE=25)
- L3 base score: BM25 relevance (content match, highest)
- Title match bonus: 10 (strong signal)
- Abstract match bonus: 4 (moderate signal)
- Tags match bonus: 1 (weak auxiliary signal)

These ensure proper ordering: L3 > L2 > L1 for same-query scenarios.
L2 base must exceed FTS_MIN_RELEVANCE so that L2-only results survive the
non-hybrid merge_and_rank_results threshold (which uses FTS_MIN_RELEVANCE as floor).

ADR-009: BM25 relevance formula
-------------------------------
BM25 scores are negative for highly relevant documents (standard BM25 behavior).
We convert to 0-100 relevance using: relevance = max(0, min(100, 70 - bm25_score * 5))

- BM25 <= -5: relevance 95-100% (highly relevant)
- BM25 = 0: relevance 70% (moderately relevant)
- BM25 >= 5: relevance 30% (weakly relevant)

ADR-010: Snippet length=32 tokens
---------------------------------
FTS snippet uses 32 tokens context around match. This provides enough
context to understand the match without overwhelming the UI.

ADR-011: Tokenizer version for index freshness detection
---------------------------------------------------------
A TOKENIZER_VERSION integer is stored alongside the FTS index. When the
Chinese tokenizer (jieba) configuration changes, bumping this version
triggers an automatic full rebuild so that index tokens stay consistent
with query-time segmentation.

ADR-012: Entity hint ranking bonus=6
------------------------------------
When a query resolves to entity hints, results whose metadata people/tags fields
contain one of the entity expansion terms receive a modest bonus.

This bonus should break ties among weak L2/L1 matches without overtaking strong
L3 lexical evidence.

ADR-013: High-frequency term min_relevance=50
---------------------------------------------
Queries dominated by ubiquitous project terms like "Life Index" and "OpenClaw"
produce many weak matches. For these terms, we apply a stricter default FTS
relevance threshold while still allowing explicit `min_relevance` overrides.

ADR-014: Score dimension normalization in hybrid ranking
--------------------------------------------------------
Within each priority bucket, scores from different sources have different scales:
- RRF scores: ~0.01-0.05 (rank-based, dimensionless)
- L2 absolute scores: ~30-40 (metadata match bonuses)

Without normalization, a single L2-only result with score 30+ would dominate
all RRF results (max ~0.05) within the same priority bucket. Solution: normalize
fts_score and semantic_score to [0, 1] per bucket, then combine with RRF
contribution. Non-RRF items get their absolute score normalized to [0, 1] range
as well, ensuring fair comparison.

ADR-015: Tukey IQR fence for dynamic thresholds
------------------------------------------------
Dynamic thresholds use Tukey's IQR fence method instead of mean-1.5σ.
IQR is more robust to outliers and small sample sizes than mean/stddev.
The minimum sample size remains 8 — below this, the base threshold is used unchanged.
"""

# =============================================================================
# RRF (Reciprocal Rank Fusion) Constants
# =============================================================================

# ADR-001: Industry standard RRF smoothing constant
RRF_K: int = 60

# ADR-004: Minimum RRF score for hybrid results (Round 10 Phase 2 T2.0 A/B experiment)
# Selected via A/B experiment on {0.005, 0.008, 0.012}:
#   - 0.005: P@5=0.3158 (too permissive, 10.2 avg results)
#   - 0.008: P@5=0.7342 (+132% precision, 3.0 avg results) [SELECTED]
#   - 0.012: identical to 0.008 (no marginal benefit)
# See docs/adr/ADR-004-rrf-min-score.md for full experiment data.
RRF_MIN_SCORE: float = 0.008


# =============================================================================
# Semantic Pipeline Constants
# =============================================================================

# ADR-002 / ADR-006: Minimum cosine similarity floor for semantic results
SEMANTIC_MIN_SIMILARITY: float = 0.40

# ADR-006: Adaptive baseline threshold tuning
SEMANTIC_BASELINE_OFFSET: float = 0.02
SEMANTIC_ABSOLUTE_FLOOR: float = 0.40

# ADR-005: Maximum semantic candidates to retrieve
SEMANTIC_TOP_K_DEFAULT: int = 30

# ADR-010: Semantic weight in hybrid RRF ranking (Round 10 Phase 4 T4.1)
# Raised from 0.4 to 0.6 to reduce FTS weak-hit dominance over semantic strong-hits.
# R4 root cause: FTS weight 1.0 vs semantic 0.4 caused semantically relevant results
# (e.g. "想起女儿" → "想念小英雄") to be outranked by FTS noise.
# Rollback window: before Phase 5 completion.
# See docs/adr/ADR-010-rrf-weight-tuning.md for rationale.
SEMANTIC_WEIGHT_DEFAULT: float = 0.6


# =============================================================================
# FTS (Full-Text Search) Constants
# =============================================================================

# ADR-003: Minimum BM25 relevance (0-100) for FTS results
FTS_MIN_RELEVANCE: int = 25

# FTS weight in hybrid ranking (vs semantic)
FTS_WEIGHT_DEFAULT: float = 1.0

# Maximum FTS results to retrieve
FTS_LIMIT: int = 100

# ADR-007: FTS fallback threshold (supplement with full scan if below)
FTS_FALLBACK_THRESHOLD: int = 5

# ADR-010: Snippet token count for FTS highlights
FTS_SNIPPET_TOKENS: int = 32

# ADR-013: stricter defaults for noisy project terms
HIGH_FREQUENCY_TERMS: frozenset[str] = frozenset({"life index", "openclaw"})
HIGH_FREQUENCY_MIN_RELEVANCE: int = 50


# =============================================================================
# Ranking Score Constants
# =============================================================================

# ADR-008: Base scores for each layer
SCORE_L1_BASE: int = 10  # Index presence
# Metadata match (must exceed FTS_MIN_RELEVANCE=25 to survive non-hybrid merge threshold)
SCORE_L2_BASE: int = 30
# L3 uses BM25 relevance directly

# ADR-008: Match bonuses
SCORE_TITLE_MATCH_BONUS: int = 10
SCORE_TITLE_MATCH_BONUS_L2: int = 8  # Slightly lower for L2
SCORE_ABSTRACT_MATCH_BONUS: int = 4
SCORE_TAGS_MATCH_BONUS: int = 1
SCORE_ENTITY_BONUS: int = 6

# ADR-016: Topic hint ranking boost (Phase 4 T4.2)
# Conservative 1.1x multiplier applied to results whose topic matches search_plan.topic_hints.
# Must not override large FTS/RRF score gaps — only breaks close ties.
TOPIC_HINT_BOOST: float = 1.1

# Minimum score for non-RRF results (pure keyword/semantic)
NON_RRF_MIN_SCORE: int = 10


# =============================================================================
# Result Limits
# =============================================================================

# ADR-006: Maximum results returned to user
MAX_RESULTS_DEFAULT: int = 20


# =============================================================================
# BM25 Relevance Conversion Constants
# =============================================================================

# ADR-009: BM25 to relevance conversion
# relevance = max(0, min(100, int(BM25_RELEVANCE_BASE - bm25_score * BM25_RELEVANCE_MULTIPLIER)))
BM25_RELEVANCE_BASE: int = 70
BM25_RELEVANCE_MULTIPLIER: int = 5


# =============================================================================
# Performance Thresholds
# =============================================================================

# Snippet length for semantic results (characters)
SEMANTIC_SNIPPET_LENGTH: int = 200


# =============================================================================
# Tokenizer Version (Round 8 Phase 1)
# =============================================================================

# ADR-011: Tokenizer version for index freshness detection
# v1 = no segmentation (pre-jieba), v2 = jieba Chinese segmentation
# When this value changes, index must be rebuilt automatically.
TOKENIZER_VERSION: int = 2


# =============================================================================
# Export all constants
# =============================================================================

__all__ = [
    # RRF
    "RRF_K",
    "RRF_MIN_SCORE",
    # Semantic
    "SEMANTIC_MIN_SIMILARITY",
    "SEMANTIC_BASELINE_OFFSET",
    "SEMANTIC_ABSOLUTE_FLOOR",
    "SEMANTIC_TOP_K_DEFAULT",
    "SEMANTIC_WEIGHT_DEFAULT",
    # FTS
    "FTS_MIN_RELEVANCE",
    "FTS_WEIGHT_DEFAULT",
    "FTS_LIMIT",
    "FTS_FALLBACK_THRESHOLD",
    "FTS_SNIPPET_TOKENS",
    "HIGH_FREQUENCY_TERMS",
    "HIGH_FREQUENCY_MIN_RELEVANCE",
    # Scoring
    "SCORE_L1_BASE",
    "SCORE_L2_BASE",
    "SCORE_TITLE_MATCH_BONUS",
    "SCORE_TITLE_MATCH_BONUS_L2",
    "SCORE_ABSTRACT_MATCH_BONUS",
    "SCORE_TAGS_MATCH_BONUS",
    "SCORE_ENTITY_BONUS",
    "TOPIC_HINT_BOOST",
    "NON_RRF_MIN_SCORE",
    # Limits
    "MAX_RESULTS_DEFAULT",
    # BM25
    "BM25_RELEVANCE_BASE",
    "BM25_RELEVANCE_MULTIPLIER",
    # Performance
    "SEMANTIC_SNIPPET_LENGTH",
    # Tokenizer
    "TOKENIZER_VERSION",
]
