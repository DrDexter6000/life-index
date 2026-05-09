"""Evidence Pack: typed search result container (R2-C MVP)."""

from tools.evidence.adapter import (
    extract_evidence_from_orchestrator,
    extract_evidence_from_search_result,
)
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
    "extract_evidence_from_orchestrator",
    "extract_evidence_from_search_result",
]
