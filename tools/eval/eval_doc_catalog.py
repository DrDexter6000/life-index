#!/usr/bin/env python3
"""Doc catalog builder and DocID utility for eval (R2-B3a).

Provides:
  - DocRecord: typed representation of an indexed journal document
  - make_doc_id_from_route: validate/normalize journal_route_path as doc_id
  - collect_eval_doc_catalog: scan journals and build typed catalog
  - build_title_to_doc_ids: title -> [doc_id] lookup
  - detect_doc_id_collisions: find duplicate doc_ids

Does not touch run_eval.py, eval behavior, or baseline JSON format.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# DocID utility
# ---------------------------------------------------------------------------


def make_doc_id_from_route(journal_route_path: str) -> str:
    """Validate and normalize a journal_route_path as a doc_id.

    Normalizes backslashes to forward slashes, rejects absolute paths
    and empty strings.
    """
    if not journal_route_path or not journal_route_path.strip():
        raise ValueError("journal_route_path must not be empty")

    normalized = journal_route_path.replace("\\", "/")

    if normalized.startswith("/") or ":" in normalized.split("/")[0]:
        raise ValueError(f"Absolute path not allowed as doc_id: {journal_route_path!r}")

    return normalized


# ---------------------------------------------------------------------------
# DocRecord
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DocRecord:
    """Typed representation of an indexed journal document for eval."""

    doc_id: str
    title: str
    date: str
    journal_route_path: str
    topic: list[str] = field(default_factory=list)
    location: str | None = None
    rel_path: str | None = None
    extra: dict[str, Any] = field(default_factory=dict, repr=False)

    _KNOWN_KEYS = frozenset(
        {
            "doc_id",
            "title",
            "date",
            "journal_route_path",
            "topic",
            "location",
            "rel_path",
        }
    )

    def __post_init__(self) -> None:
        normalized_route = make_doc_id_from_route(self.journal_route_path)
        object.__setattr__(self, "journal_route_path", normalized_route)
        normalized_id = make_doc_id_from_route(self.doc_id)
        object.__setattr__(self, "doc_id", normalized_id)
        if self.doc_id != self.journal_route_path:
            raise ValueError(
                f"doc_id must equal normalized journal_route_path: "
                f"{self.doc_id!r} != {self.journal_route_path!r}"
            )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DocRecord:
        raw_route = str(data.get("journal_route_path", ""))
        journal_route_path = make_doc_id_from_route(raw_route)
        if "doc_id" in data:
            provided_id = make_doc_id_from_route(data["doc_id"])
            if provided_id != journal_route_path:
                raise ValueError(
                    f"doc_id must equal normalized journal_route_path: "
                    f"{provided_id!r} != {journal_route_path!r}"
                )
        return cls(
            doc_id=journal_route_path,
            title=str(data.get("title", "")),
            date=str(data.get("date", "")),
            journal_route_path=journal_route_path,
            topic=list(data.get("topic", [])),
            location=data.get("location"),
            rel_path=data.get("rel_path"),
            extra={k: v for k, v in data.items() if k not in cls._KNOWN_KEYS},
        )

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "doc_id": self.doc_id,
            "title": self.title,
            "date": self.date,
            "journal_route_path": self.journal_route_path,
        }
        if self.topic:
            d["topic"] = self.topic
        if self.location is not None:
            d["location"] = self.location
        if self.rel_path is not None:
            d["rel_path"] = self.rel_path
        d.update(self.extra)
        return d


# ---------------------------------------------------------------------------
# Catalog builder
# ---------------------------------------------------------------------------


def collect_eval_doc_catalog(
    data_dir: Path | None = None,
) -> list[DocRecord]:
    """Scan journals directory and build a typed doc catalog.

    Uses frontmatter scanning (same pattern as run_eval's
    _collect_all_indexed_docs). Returns DocRecords with stable
    doc_id = journal_route_path.
    """
    from tools.lib.frontmatter import parse_journal_file
    from tools.lib.path_contract import build_journal_path_fields
    from tools.lib.paths import get_user_data_dir

    user_data_dir = data_dir or get_user_data_dir()
    journals_dir = user_data_dir / "Journals"

    if not journals_dir.exists():
        return []

    records: list[DocRecord] = []
    for file_path in sorted(journals_dir.glob("**/life-index_*.md")):
        if ".revisions" in file_path.parts:
            continue

        try:
            metadata = parse_journal_file(file_path)
        except Exception:
            continue

        path_fields = build_journal_path_fields(
            file_path, journals_dir=journals_dir, user_data_dir=user_data_dir
        )
        journal_route_path = path_fields["journal_route_path"]

        records.append(
            DocRecord(
                doc_id=make_doc_id_from_route(journal_route_path),
                title=str(metadata.get("title") or metadata.get("_title") or ""),
                date=str(metadata.get("date", "")),
                journal_route_path=journal_route_path,
                topic=list(
                    metadata.get("topic", [])
                    if isinstance(metadata.get("topic"), list)
                    else [metadata.get("topic", "")] if metadata.get("topic") else []
                ),
                location=metadata.get("location"),
                rel_path=path_fields.get("rel_path"),
            )
        )

    return records


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------


def build_title_to_doc_ids(
    catalog: list[DocRecord],
) -> dict[str, list[str]]:
    """Build title -> [doc_id] lookup. Multiple docs may share a title."""
    mapping: dict[str, list[str]] = {}
    for rec in catalog:
        mapping.setdefault(rec.title, []).append(rec.doc_id)
    return mapping


def detect_doc_id_collisions(
    catalog: list[DocRecord],
) -> dict[str, list[DocRecord]]:
    """Find doc_ids that appear more than once. Returns {doc_id: [records]}."""
    seen: dict[str, list[DocRecord]] = {}
    for rec in catalog:
        seen.setdefault(rec.doc_id, []).append(rec)
    return {did: recs for did, recs in seen.items() if len(recs) > 1}
