"""Evidence Pack: typed search result container (R2-C MVP)."""

from tools.evidence.builder import build_evidence_pack
from tools.evidence.types import (
    DocumentRef,
    EvidenceItem,
    EvidencePack,
    QueryContext,
    ScoreBreakdown,
    SemanticCandidate,
)

__all__ = [
    "DocumentRef",
    "EvidenceItem",
    "EvidencePack",
    "QueryContext",
    "ScoreBreakdown",
    "SemanticCandidate",
    "build_evidence_pack",
]
