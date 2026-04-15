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

ADR-002: Semantic min_similarity=0.15
--------------------------------------
Vector similarity threshold for semantic results. Values below 0.15 are
typically low-quality matches that introduce noise without adding signal.

empirical observation: with MiniLM-L12-v2, similarities < 0.15 are often
topic-drifted or tangentially related. This threshold balances recall vs precision.

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
"""

# =============================================================================
# RRF (Reciprocal Rank Fusion) Constants
# =============================================================================

# ADR-001: Industry standard RRF smoothing constant
RRF_K: int = 60

# ADR-004: Minimum RRF score for hybrid results
RRF_MIN_SCORE: float = 0.008


# =============================================================================
# Semantic Pipeline Constants
# =============================================================================

# ADR-002: Minimum cosine similarity for semantic results
SEMANTIC_MIN_SIMILARITY: float = 0.15

# ADR-005: Maximum semantic candidates to retrieve
SEMANTIC_TOP_K_DEFAULT: int = 30

# Semantic weight in hybrid ranking (vs FTS)
SEMANTIC_WEIGHT_DEFAULT: float = 0.4


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


# =============================================================================
# Ranking Score Constants
# =============================================================================

# ADR-008: Base scores for each layer
SCORE_L1_BASE: int = 10  # Index presence
SCORE_L2_BASE: int = 30  # Metadata match (must exceed FTS_MIN_RELEVANCE=25 to survive non-hybrid merge threshold)
# L3 uses BM25 relevance directly

# ADR-008: Match bonuses
SCORE_TITLE_MATCH_BONUS: int = 10
SCORE_TITLE_MATCH_BONUS_L2: int = 8  # Slightly lower for L2
SCORE_ABSTRACT_MATCH_BONUS: int = 4
SCORE_TAGS_MATCH_BONUS: int = 1

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
# Export all constants
# =============================================================================

__all__ = [
    # RRF
    "RRF_K",
    "RRF_MIN_SCORE",
    # Semantic
    "SEMANTIC_MIN_SIMILARITY",
    "SEMANTIC_TOP_K_DEFAULT",
    "SEMANTIC_WEIGHT_DEFAULT",
    # FTS
    "FTS_MIN_RELEVANCE",
    "FTS_WEIGHT_DEFAULT",
    "FTS_LIMIT",
    "FTS_FALLBACK_THRESHOLD",
    "FTS_SNIPPET_TOKENS",
    # Scoring
    "SCORE_L1_BASE",
    "SCORE_L2_BASE",
    "SCORE_TITLE_MATCH_BONUS",
    "SCORE_TITLE_MATCH_BONUS_L2",
    "SCORE_ABSTRACT_MATCH_BONUS",
    "SCORE_TAGS_MATCH_BONUS",
    "NON_RRF_MIN_SCORE",
    # Limits
    "MAX_RESULTS_DEFAULT",
    # BM25
    "BM25_RELEVANCE_BASE",
    "BM25_RELEVANCE_MULTIPLIER",
    # Performance
    "SEMANTIC_SNIPPET_LENGTH",
]
