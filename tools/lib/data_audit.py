"""Data directory cleanliness audit — detect anomalies without fixing anything.

Round 12 Phase 0 Task 0.3: read-only audit that checks for revision files
left in Journals/, non-standard naming, and distribution anomalies.
"""

import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List


@dataclass
class Anomaly:
    """A single detected anomaly in the data directory."""

    type: str  # e.g. "revision_file", "naming", "distribution"
    severity: str  # "warning" or "info"
    description: str
    path: str


@dataclass
class DataAuditReport:
    """Structured result of a data directory audit."""

    file_count: int = 0
    anomalies: List[Anomaly] = field(default_factory=list)
    distribution: Dict[str, int] = field(default_factory=dict)


# Standard file name prefixes that are allowed in Journals/
_ALLOWED_PREFIXES = ("life-index_", "index_", "monthly_report_")

# Pattern to detect revision file names like: life-index_2026-03-01_001_20260418_120000_000000.md
_REVISION_PATTERN = re.compile(r"_\d{8}_\d{6}_\d{6}\.md$")

# Pattern to extract YYYY-MM from a path for distribution counting
_MONTH_PATTERN = re.compile(r"(\d{4})[\\/](\d{2})[\\/]")


def audit_data_directory(data_dir: Path) -> DataAuditReport:
    """Audit data directory for anomalies.

    This is a read-only operation — it never modifies any file.

    Checks:
    1. Revision files loose in Journals/ (not inside .revisions/)
    2. Non-standard file naming
    3. Monthly distribution anomalies (> 3x average)
    """
    journals_dir = data_dir / "Journals"
    report = DataAuditReport()

    if not journals_dir.exists():
        return report

    # Collect all .md files in Journals/
    all_md_files: list[Path] = list(journals_dir.rglob("*.md"))
    journal_files: list[Path] = []

    for md_file in all_md_files:
        # Skip files inside .revisions/ directories
        if ".revisions" in md_file.parts:
            continue

        rel_path = md_file.relative_to(journals_dir).as_posix()
        basename = md_file.name

        # Check for revision files loose in Journals/ (not inside .revisions/)
        if _REVISION_PATTERN.search(basename):
            report.anomalies.append(
                Anomaly(
                    type="revision_file",
                    severity="warning",
                    description=f"Revision file found outside .revisions/: {basename}",
                    path=rel_path,
                )
            )
            continue  # Don't count as a journal

        # Check for non-standard naming
        if not basename.startswith(_ALLOWED_PREFIXES):
            report.anomalies.append(
                Anomaly(
                    type="naming",
                    severity="info",
                    description=f"Non-standard file name: {basename}",
                    path=rel_path,
                )
            )
            continue  # Don't count as a journal

        # Only count actual journal files (life-index_*)
        if basename.startswith("life-index_"):
            journal_files.append(md_file)

    report.file_count = len(journal_files)

    # Compute monthly distribution
    month_counts: Dict[str, int] = defaultdict(int)
    for jf in journal_files:
        match = _MONTH_PATTERN.search(jf.as_posix())
        if match:
            month_key = f"{match.group(1)}-{match.group(2)}"
            month_counts[month_key] += 1
    report.distribution = dict(month_counts)

    # Check for distribution anomalies
    _check_distribution_anomaly(report, month_counts)

    return report


def _check_distribution_anomaly(report: DataAuditReport, month_counts: Dict[str, int]) -> None:
    """Flag months with journal count > 3x the monthly average."""
    if len(month_counts) < 2:
        return  # Need at least 2 months to compare

    avg = sum(month_counts.values()) / len(month_counts)
    threshold = avg * 3

    for month, count in month_counts.items():
        if count > threshold and count > 5:  # Minimum 5 to avoid noise
            report.anomalies.append(
                Anomaly(
                    type="distribution",
                    severity="info",
                    description=(
                        f"Month {month} has {count} journals "
                        f"(avg={avg:.1f}, threshold={threshold:.1f})"
                    ),
                    path=f"Journals/{month.replace('-', '/')}",
                )
            )
