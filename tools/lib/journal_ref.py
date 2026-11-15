"""The one journal-reference predicate shared by the whole read contract.

``get --path`` serves exactly one shape of file: a selector whose parts,
relative to the data directory, are ``Journals/<dir>/<dir>/life-index_<date>_
<seq>.md`` **and** whose resolved path stays inside the data directory. The
id lookup (:mod:`tools.lib.entry_id_lookup`) admits exactly the same files,
so the two rules live here once and both callers use them — the lookup never
returns an entry the path selector would refuse (a nested entry, or a
canonical-looking symlink that resolves outside the data directory).
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path

# The canonical entry filename (and its sequence group, used for ordering).
JOURNAL_NAME_RE = re.compile(r"^life-index_(\d{4}-\d{2}-\d{2})_(\d+)\.md$")


def canonical_journal_parts(parts: Sequence[str]) -> bool:
    """Whether *parts* (relative to the data directory) match the served shape.

    Exactly four parts — ``Journals`` plus two directory names plus a canonical
    entry filename. Anything deeper (``Journals/2026/05/nested/…``), shallower,
    or otherwise shaped is not servable by ``--path`` and is not a lookup
    candidate.
    """
    return (
        len(parts) == 4 and parts[0] == "Journals" and JOURNAL_NAME_RE.match(parts[-1]) is not None
    )


def resolves_within_data_dir(path: Path, data_root: Path) -> bool:
    """Whether *path*, resolved, stays inside *data_root* (resolved).

    The check ``_resolve_journal_ref`` applies before serving a selector: a
    canonical-looking symlink whose target lies outside the data directory
    fails it, and so does any path that cannot be resolved.
    """
    try:
        path.resolve().relative_to(data_root.resolve())
    except (OSError, ValueError):
        return False
    return True
