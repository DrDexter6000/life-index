#!/usr/bin/env python3
"""Deterministic materialized Index B navigation documents."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from tools.generate_index.builder import safe_relative_path
from tools.lib.frontmatter import parse_frontmatter
from tools.lib.paths import get_journals_dir, get_user_data_dir

INDEX_B_SCHEMA_VERSION = "m31.index_tree.index_b.v0"
INDEX_B_DIR = ".life-index/index-b"
_MONTH_RE = re.compile(r"^\d{4}-\d{2}$")
_JOURNAL_DATE_RE = re.compile(r"life-index_(\d{4}-\d{2}-\d{2})_\d{3}\.md$")


@dataclass(frozen=True)
class FacetSpec:
    name: str
    fields: tuple[str, ...]


@dataclass(frozen=True)
class IndexBEntry:
    rel_path: str
    year: str
    month: str
    date: str
    title: str
    metadata: dict[str, Any]


FACETS: tuple[FacetSpec, ...] = (
    FacetSpec("weather", ("weather",)),
    FacetSpec("location", ("location",)),
    FacetSpec("task", ("task", "tasks")),
    FacetSpec("project", ("project", "projects")),
    FacetSpec("tag", ("tags", "tag")),
    FacetSpec("people", ("people",)),
)


def _generated_at() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_month(value: str | None, *, fallback: str | None = None) -> str | None:
    if value is None or not value.strip():
        return fallback
    text = value.strip()
    if not _MONTH_RE.match(text):
        raise ValueError(f"month must use YYYY-MM format, got: {value!r}")
    return text


def _entry_in_range(entry: IndexBEntry, date_from: str | None, date_to: str | None) -> bool:
    entry_month = f"{entry.year}-{entry.month}"
    if date_from is not None and entry_month < date_from:
        return False
    if date_to is not None and entry_month > date_to:
        return False
    return True


def _parse_frontmatter(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {}
    if not text.startswith("---\n"):
        return {}
    try:
        metadata, _body = parse_frontmatter(text)
    except (TypeError, ValueError):
        return {}
    return metadata if isinstance(metadata, dict) else {}


def _date_from_filename(path: Path) -> str:
    match = _JOURNAL_DATE_RE.match(path.name)
    return match.group(1) if match else ""


def _iter_values(value: Any) -> Iterable[str]:
    if isinstance(value, list):
        for item in value:
            text = str(item).strip()
            if text:
                yield text
        return
    text = str(value or "").strip()
    if text:
        yield text


def _facet_values(entry: IndexBEntry, spec: FacetSpec) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for field in spec.fields:
        for value in _iter_values(entry.metadata.get(field)):
            if value not in seen:
                seen.add(value)
                values.append(value)
    return values


def _collect_entries(date_from: str | None, date_to: str | None) -> list[IndexBEntry]:
    data_dir = get_user_data_dir()
    journals_dir = get_journals_dir()
    entries: list[IndexBEntry] = []
    for path in sorted(journals_dir.glob("*/*/life-index_*.md")):
        if not path.is_file():
            continue
        rel = safe_relative_path(path, data_dir)
        if not rel:
            continue
        parts = path.relative_to(journals_dir).parts
        if len(parts) < 3:
            continue
        year, month = parts[0], parts[1]
        metadata = _parse_frontmatter(path)
        date_value = str(metadata.get("date") or _date_from_filename(path))
        entry = IndexBEntry(
            rel_path=rel,
            year=year,
            month=month,
            date=date_value,
            title=str(metadata.get("title") or path.stem),
            metadata=metadata,
        )
        if _entry_in_range(entry, date_from, date_to):
            entries.append(entry)
    return entries


def _escape_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip()


def _doc_rel(*parts: str) -> str:
    return "/".join((INDEX_B_DIR, *parts))


def _frontmatter(scope: str, date_from: str | None, date_to: str | None, count: int) -> str:
    lines = [
        "---",
        f"schema_version: {INDEX_B_SCHEMA_VERSION}",
        "generator: life-index index-tree materialize",
        f"scope: {scope}",
        f"entry_count: {count}",
    ]
    if date_from:
        lines.append(f"date_from: {date_from}")
    if date_to:
        lines.append(f"date_to: {date_to}")
    lines.extend(["---", ""])
    return "\n".join(lines)


def _facet_markdown(entries: list[IndexBEntry]) -> str:
    lines = ["## Facets", ""]
    for spec in FACETS:
        buckets: dict[str, list[str]] = defaultdict(list)
        for entry in entries:
            for value in _facet_values(entry, spec):
                buckets[value].append(entry.rel_path)
        lines.extend([f"### {spec.name}", "", "| value | count | pointers |", "|---|---:|---|"])
        if not buckets:
            lines.append("| (none) | 0 | |")
        else:
            counts = Counter({value: len(paths) for value, paths in buckets.items()})
            for value, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
                pointers = ", ".join(sorted(buckets[value]))
                lines.append(f"| {_escape_cell(value)} | {count} | {_escape_cell(pointers)} |")
        lines.append("")
    return "\n".join(lines)


def _entry_pointer_markdown(entries: list[IndexBEntry]) -> str:
    lines = ["## Entry Pointers", "", "| date | title | path |", "|---|---|---|"]
    if not entries:
        lines.append("| (none) | | |")
    for entry in entries:
        lines.append(
            f"| {_escape_cell(entry.date)} | {_escape_cell(entry.title)} | "
            f"{_escape_cell(entry.rel_path)} |"
        )
    lines.append("")
    return "\n".join(lines)


def _root_doc(
    entries: list[IndexBEntry],
    years: dict[str, list[IndexBEntry]],
    date_from: str | None,
    date_to: str | None,
) -> str:
    lines = [
        _frontmatter("root", date_from, date_to, len(entries)),
        "# Index B Root Navigation",
        "",
        "Deterministic, rebuildable facet navigation. It is not a summary and does not "
        "replace journal evidence.",
        "",
        "## Child Nodes",
        "",
        "| year | count | doc |",
        "|---|---:|---|",
    ]
    for year, year_entries in sorted(years.items()):
        lines.append(f"| {year} | {len(year_entries)} | {_doc_rel('Journals', year, 'index.md')} |")
    if not years:
        lines.append("| (none) | 0 | |")
    lines.extend(["", _facet_markdown(entries)])
    return "\n".join(lines).rstrip() + "\n"


def _year_doc(
    year: str,
    entries: list[IndexBEntry],
    months: dict[str, list[IndexBEntry]],
    date_from: str | None,
    date_to: str | None,
) -> str:
    lines = [
        _frontmatter(f"year:{year}", date_from, date_to, len(entries)),
        f"# Index B Year {year}",
        "",
        "## Child Nodes",
        "",
        "| month | count | doc |",
        "|---|---:|---|",
    ]
    for month, month_entries in sorted(months.items()):
        lines.append(
            f"| {year}-{month} | {len(month_entries)} | "
            f"{_doc_rel('Journals', year, month, 'index.md')} |"
        )
    lines.extend(["", _facet_markdown(entries)])
    return "\n".join(lines).rstrip() + "\n"


def _month_doc(
    year: str,
    month: str,
    entries: list[IndexBEntry],
    date_from: str | None,
    date_to: str | None,
) -> str:
    lines = [
        _frontmatter(f"month:{year}-{month}", date_from, date_to, len(entries)),
        f"# Index B Month {year}-{month}",
        "",
        _entry_pointer_markdown(entries),
        _facet_markdown(entries),
    ]
    return "\n".join(lines).rstrip() + "\n"


def _write_text(path: Path, text: str, *, dry_run: bool) -> None:
    if dry_run:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(path.name + ".tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(path)


def build_materialize_payload(
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Build and optionally write deterministic Index B navigation docs."""
    start = _parse_month(date_from)
    end = _parse_month(date_to, fallback=start)
    if start is not None and end is not None and end < start:
        raise ValueError("--to must be greater than or equal to --from")

    data_dir = get_user_data_dir()
    output_dir = data_dir / INDEX_B_DIR
    entries = _collect_entries(start, end)
    years: dict[str, list[IndexBEntry]] = defaultdict(list)
    months_by_year: dict[str, dict[str, list[IndexBEntry]]] = defaultdict(lambda: defaultdict(list))
    for entry in entries:
        years[entry.year].append(entry)
        months_by_year[entry.year][entry.month].append(entry)

    written_docs: list[str] = []

    root_path = output_dir / "INDEX.md"
    _write_text(root_path, _root_doc(entries, years, start, end), dry_run=dry_run)
    written_docs.append(safe_relative_path(root_path, data_dir))

    for year, year_entries in sorted(years.items()):
        year_path = output_dir / "Journals" / year / "index.md"
        _write_text(
            year_path,
            _year_doc(year, year_entries, months_by_year[year], start, end),
            dry_run=dry_run,
        )
        written_docs.append(safe_relative_path(year_path, data_dir))
        for month, month_entries in sorted(months_by_year[year].items()):
            month_path = output_dir / "Journals" / year / month / "index.md"
            _write_text(
                month_path,
                _month_doc(year, month, month_entries, start, end),
                dry_run=dry_run,
            )
            written_docs.append(safe_relative_path(month_path, data_dir))

    return {
        "truth_source": "journals",
        "artifact": "index-b",
        "schema_version": INDEX_B_SCHEMA_VERSION,
        "generated_at": _generated_at(),
        "output_dir": INDEX_B_DIR,
        "date_from": start,
        "date_to": end,
        "entry_count": len(entries),
        "year_count": len(years),
        "month_count": sum(len(months) for months in months_by_year.values()),
        "facets": [spec.name for spec in FACETS],
        "written_docs": written_docs,
        "dry_run": dry_run,
    }
