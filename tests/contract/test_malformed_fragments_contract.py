#!/usr/bin/env python3
"""Contract: one malformed fragment never breaks a search, index, health or verify.

Every shape in :data:`SHAPES` is written next to a second, valid fragment and
then driven through every operation a user or agent can reach: a full rebuild, an
incremental rebuild after the file changed, a level-3 token search (twice) and
the same search through the CLI, ``index --check``, ``health``, ``verify``, the
event detectors, ``timeline``, ``on-this-day``, ``edit`` and ``index --rebuild``.

For every cell the requirement is the same:

* no exception escapes and no error envelope is caused by the malformed file;
* the token search returns the malformed fragment with its path (from its FTS
  row), and the valid fragment is unaffected.

``edit`` on a file whose bytes are not UTF-8 is the one documented refusal: the
bytes cannot be rewritten without corrupting them, so edit returns its standard
error envelope (E0200) instead of raising. Whether edit should refuse such files
is decided by a separate package.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]

TOKEN = "malformedfragmenttoken"
VALID_TOKEN = "validfragmenttoken"
DATE = "2026-03-04"
VALID_DATE = "2026-03-05"

VALID_FRAGMENT = (
    '---\ntitle: "Valid fragment"\ndate: "2026-03-05"\ntopic: [life]\n'
    "tags: [validtag]\n---\n\n" + VALID_TOKEN + " valid body\n"
)


def _body(token: str = TOKEN) -> str:
    return f"{token} malformed body\n"


# shape name -> exact file bytes
SHAPES: dict[str, bytes] = {
    "no_frontmatter": _body().encode(),
    "empty_frontmatter": b"---\n---\n\n" + _body().encode(),
    "invalid_yaml": ("---\ntitle: [unterminated\ndate: 2026-03-04\n---\n\n" + _body()).encode(),
    "list_root": ("---\n- a\n- b\n---\n\n" + _body()).encode(),
    "scalar_root": ("---\njust a scalar\n---\n\n" + _body()).encode(),
    "title_mapping": ("---\ntitle:\n  nested: value\ndate: 2026-03-04\n---\n\n" + _body()).encode(),
    "title_list": ("---\ntitle: [a, b]\ndate: 2026-03-04\n---\n\n" + _body()).encode(),
    "title_number": ("---\ntitle: 2024\ndate: 2026-03-04\n---\n\n" + _body()).encode(),
    "title_boolean": ("---\ntitle: true\ndate: 2026-03-04\n---\n\n" + _body()).encode(),
    "title_null": ("---\ntitle:\ndate: 2026-03-04\n---\n\n" + _body()).encode(),
    "date_number": ("---\ntitle: T\ndate: 20260304\n---\n\n" + _body()).encode(),
    "date_list": ("---\ntitle: T\ndate: [2026]\n---\n\n" + _body()).encode(),
    "date_impossible": ("---\ntitle: T\ndate: 2026-99-99\n---\n\n" + _body()).encode(),
    "date_missing": ("---\ntitle: T\n---\n\n" + _body()).encode(),
    "topic_scalar": ("---\ntitle: T\ndate: 2026-03-04\ntopic: life\n---\n\n" + _body()).encode(),
    "topic_mapping": (
        "---\ntitle: T\ndate: 2026-03-04\ntopic:\n  a: b\n---\n\n" + _body()
    ).encode(),
    "topic_list_mapping": (
        "---\ntitle: T\ndate: 2026-03-04\ntopic:\n  - a\n  - b: c\n---\n\n" + _body()
    ).encode(),
    "topic_null": ("---\ntitle: T\ndate: 2026-03-04\ntopic:\n---\n\n" + _body()).encode(),
    "tags_scalar": (
        "---\ntitle: T\ndate: 2026-03-04\ntags: alpha, beta\n---\n\n" + _body()
    ).encode(),
    "tags_mapping": ("---\ntitle: T\ndate: 2026-03-04\ntags: {a: b}\n---\n\n" + _body()).encode(),
    "tags_list_mapping": (
        "---\ntitle: T\ndate: 2026-03-04\ntags:\n  - a\n  - k: v\n---\n\n" + _body()
    ).encode(),
    "tags_null": ("---\ntitle: T\ndate: 2026-03-04\ntags:\n---\n\n" + _body()).encode(),
    "people_scalar": ("---\ntitle: T\ndate: 2026-03-04\npeople: Alice\n---\n\n" + _body()).encode(),
    "people_mapping": (
        "---\ntitle: T\ndate: 2026-03-04\npeople: {a: b}\n---\n\n" + _body()
    ).encode(),
    "people_list_mapping": (
        "---\ntitle: T\ndate: 2026-03-04\npeople:\n  - a\n  - k: v\n---\n\n" + _body()
    ).encode(),
    "people_null": ("---\ntitle: T\ndate: 2026-03-04\npeople:\n---\n\n" + _body()).encode(),
    "mood_scalar": ("---\ntitle: T\ndate: 2026-03-04\nmood: calm\n---\n\n" + _body()).encode(),
    "mood_mapping": ("---\ntitle: T\ndate: 2026-03-04\nmood: {a: b}\n---\n\n" + _body()).encode(),
    "mood_list_mapping": (
        "---\ntitle: T\ndate: 2026-03-04\nmood:\n  - a\n  - k: v\n---\n\n" + _body()
    ).encode(),
    "mood_null": ("---\ntitle: T\ndate: 2026-03-04\nmood:\n---\n\n" + _body()).encode(),
    "not_utf8": b"---\ntitle: T\ndate: 2026-03-04\n---\n\nmalformedfragmenttoken \xff\xfe bytes\n",
    "utf8_bom": b"\xef\xbb\xbf---\ntitle: T\ndate: 2026-03-04\n---\n\n" + _body().encode(),
    "crlf": ("---\r\ntitle: T\r\ndate: 2026-03-04\r\n---\r\n\r\n" + _body())
    .replace("\n", "\r\n")
    .encode(),
    "unclosed_frontmatter": ("---\ntitle: T\ndate: 2026-03-04\n\n" + _body()).encode(),
}


def _paths() -> tuple[Path, Path]:
    journals = Path(os.environ["LIFE_INDEX_DATA_DIR"]) / "Journals" / "2026" / "03"
    return journals / f"life-index_{DATE}_001.md", journals / f"life-index_{VALID_DATE}_001.md"


def _write_fragments(payload: bytes) -> None:
    malformed, valid = _paths()
    malformed.parent.mkdir(parents=True, exist_ok=True)
    valid.write_text(VALID_FRAGMENT, encoding="utf-8")
    malformed.write_bytes(payload)


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    return subprocess.run(
        [sys.executable, "-m", "tools", *args],
        cwd=str(PROJECT_ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )


def _cli_json(result: subprocess.CompletedProcess, step: str, failures: list[str]):
    if "Traceback" in (result.stderr or ""):
        failures.append(f"{step}: traceback in stderr:\n{result.stderr[-1500:]}")
        return None
    try:
        return json.loads(result.stdout)
    except (ValueError, TypeError):
        failures.append(f"{step}: stdout is not JSON: {result.stdout[:300]!r}")
        return None


def _step(failures: list[str], name: str, func):
    try:
        return func()
    except Exception as exc:  # noqa: BLE001 - reported as a cell failure
        failures.append(f"{name}: {type(exc).__name__}: {exc}")
        return None


def _check_fts_row(data_dir: Path, malformed_path: Path, failures: list[str]) -> None:
    """The malformed fragment must have its own FTS row carrying the token."""
    import sqlite3

    from tools.lib.path_contract import build_journal_path_fields

    rel_path = build_journal_path_fields(
        malformed_path, journals_dir=data_dir / "Journals", user_data_dir=data_dir
    )["rel_path"]
    db_path = data_dir / ".index" / "journals_fts.db"
    if not db_path.exists():
        failures.append("fts row: no FTS database")
        return
    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute("SELECT content FROM journals WHERE path = ?", (rel_path,)).fetchone()
    finally:
        conn.close()
    if row is None:
        failures.append(f"fts row: no row for {rel_path}")
    elif TOKEN not in row[0]:
        failures.append(f"fts row: token missing from the row content of {rel_path}")


@pytest.mark.parametrize("shape", sorted(SHAPES))
def test_malformed_fragment_survives_every_operation(isolated_data_dir, shape):
    from tools.build_index import build_all
    from tools.edit_journal import edit_journal
    from tools.search_journals.core import hierarchical_search
    from tools.search_journals.l3_content import search_l3_content

    _write_fragments(SHAPES[shape])
    malformed_path, valid_path = _paths()
    failures: list[str] = []

    def check_success(name: str, result) -> None:
        if not isinstance(result, dict):
            failures.append(f"{name}: no result object")
            return
        if result.get("success") is not True:
            failures.append(f"{name}: error envelope {result.get('error')!r}")

    # 1. Cold full rebuild (the index does not exist yet).
    rebuild = _step(failures, "build_all(incremental=False)", lambda: build_all(incremental=False))
    check_success("build_all(incremental=False)", rebuild)
    if isinstance(rebuild, dict) and isinstance(rebuild.get("fts"), dict):
        if rebuild["fts"].get("unreadable_paths"):
            failures.append(f"build_all(incremental=False): unreadable {rebuild['fts']}")
        if rebuild["fts"].get("total") != 2:
            failures.append(f"build_all(incremental=False): total {rebuild['fts'].get('total')}")

    # 2. Incremental rebuild after the file changed.
    malformed_path.write_bytes(malformed_path.read_bytes() + b"\nappended line\n")

    def incremental():
        return build_all(incremental=True)

    result = _step(failures, "build_all(incremental=True)", incremental)
    check_success("build_all(incremental=True)", result)

    # 3. Level-3 token search, twice, from the malformed file's own token.
    for attempt in (1, 2):
        response = _step(
            failures,
            f"hierarchical_search#{attempt}",
            lambda: hierarchical_search(query=TOKEN, level=3),
        )
        if not isinstance(response, dict):
            continue
        check_success(f"hierarchical_search#{attempt}", response)
        paths = {
            str(item.get("path") or item.get("journal_route_path") or "").replace("\\", "/")
            for item in (response.get("merged_results") or [])
        }
        if str(malformed_path).replace("\\", "/") not in paths:
            failures.append(
                f"hierarchical_search#{attempt}: malformed fragment missing, hits={sorted(paths)}"
            )

    valid_response = _step(
        failures, "hierarchical_search(valid)", lambda: hierarchical_search(query=VALID_TOKEN)
    )
    if isinstance(valid_response, dict):
        valid_paths = {
            str(item.get("path") or item.get("journal_route_path") or "").replace("\\", "/")
            for item in (valid_response.get("merged_results") or [])
        }
        if str(valid_path).replace("\\", "/") not in valid_paths:
            failures.append(
                f"hierarchical_search(valid): valid fragment missing {sorted(valid_paths)}"
            )

    # 4. The same search through the CLI.
    cli_search = _step(
        failures,
        "cli search",
        lambda: _run_cli("search", "--query", TOKEN, "--level", "3"),
    )
    if cli_search is not None:
        payload = _cli_json(cli_search, "cli search", failures)
        if payload is not None:
            if payload.get("success") is not True:
                failures.append(f"cli search: error envelope {payload.get('error')!r}")
            dumped = json.dumps(payload.get("merged_results") or [], ensure_ascii=False)
            if DATE not in dumped:
                failures.append("cli search: malformed fragment missing from the response")

    # The hit comes from the fragment's own FTS row (not from the fallback scan).
    _check_fts_row(isolated_data_dir, malformed_path, failures)

    # 5. Read-only checks on a current index.
    _step(failures, "settle", lambda: build_all(incremental=True))

    index_check = _step(failures, "index --check", lambda: _run_cli("index", "--check"))
    if index_check is not None:
        payload = _cli_json(index_check, "index --check", failures)
        if payload is not None and payload.get("healthy") is not True:
            failures.append(f"index --check: unhealthy {payload.get('issues')}")

    health = _step(failures, "health", lambda: _run_cli("health"))
    if health is not None:
        payload = _cli_json(health, "health", failures)
        if payload is not None and payload.get("success") is not True:
            failures.append(f"health: error envelope {payload.get('error')!r}")

    verify = _step(failures, "verify --json", lambda: _run_cli("verify", "--json"))
    if verify is not None:
        # verify reports missing required fields as warnings and exits 1 by
        # design; only a crash or a non-JSON result is a defect here.
        payload = _cli_json(verify, "verify --json", failures)
        if payload is not None and not isinstance(payload.get("checks"), list):
            failures.append(f"verify: unexpected envelope {sorted(payload)}")

    # 6. Event detectors.
    def events():
        from tools.lib.event_detectors import register_all_detectors
        from tools.lib.events import detect_events
        from tools.lib.paths import get_journals_dir, get_user_data_dir

        register_all_detectors()
        return detect_events(
            context={"journals_dir": get_journals_dir(), "data_dir": get_user_data_dir()}
        )

    _step(failures, "event detectors", events)

    # 7. timeline / on-this-day for that date.
    timeline = _step(
        failures, "timeline", lambda: _run_cli("timeline", "--range", "2026-03", "2026-03")
    )
    if timeline is not None:
        payload = _cli_json(timeline, "timeline", failures)
        if payload is not None and payload.get("success") is not True:
            failures.append(f"timeline: error envelope {payload.get('error')!r}")

    on_this_day = _step(
        failures,
        "on-this-day",
        lambda: _run_cli("on-this-day", "--date", DATE, "--years-back", "3", "--json"),
    )
    if on_this_day is not None:
        payload = _cli_json(on_this_day, "on-this-day", failures)
        if payload is not None and payload.get("success") is not True:
            failures.append(f"on-this-day: error envelope {payload.get('error')!r}")

    # 8. The fallback content scan must not raise on any shape.
    _step(failures, "l3_content fallback scan", lambda: search_l3_content(TOKEN))

    # 9. Edit one field.
    edit_result = _step(
        failures,
        "edit",
        lambda: edit_journal(journal_path=malformed_path, frontmatter_updates={"weather": "sunny"}),
    )
    if isinstance(edit_result, dict):
        refused = edit_result.get("success") is False
        if refused and shape != "not_utf8":
            failures.append(f"edit: error envelope {edit_result.get('error')!r}")
        if refused and shape == "not_utf8":
            error = edit_result.get("error") or {}
            if error.get("code") != "E0200":
                failures.append(f"edit: unexpected refusal {error!r}")

    # 10. Full rebuild through the CLI.
    cli_rebuild = _step(
        failures, "index --rebuild", lambda: _run_cli("index", "--rebuild", "--json")
    )
    if cli_rebuild is not None:
        payload = _cli_json(cli_rebuild, "index --rebuild", failures)
        if payload is not None:
            fts = payload.get("fts") or {}
            if payload.get("success") is not True or fts.get("success") is not True:
                failures.append(f"index --rebuild: unsuccessful {payload.get('error')!r}")
            if cli_rebuild.returncode != 0:
                failures.append(f"index --rebuild: exit {cli_rebuild.returncode}")

    assert not failures, f"shape {shape!r} broke an operation:\n" + "\n".join(failures)


def _hit_paths(response, key: str = "merged_results") -> set[str]:
    return {
        str(item.get("path") or "").replace("\\", "/") for item in ((response or {}).get(key) or [])
    }


# YAML keys need not be strings: ``2024: x`` is an int key, and YAML 1.1 reads a
# bare ``yes``/``on``/``true`` key as a boolean.
NON_STRING_KEYS = {
    "key_number": "2024: x",
    "key_float": "1.5: x",
    "key_boolean": "true: x",
    "key_null": "null: x",
}


@pytest.mark.parametrize("shape", sorted(NON_STRING_KEYS))
def test_non_string_frontmatter_key_does_not_break_index_or_search(isolated_data_dir, shape):
    """A frontmatter key that is not a string is ignored, not fatal."""
    from tools.build_index import build_all
    from tools.search_journals.core import hierarchical_search

    payload = f"---\ntitle: Keyed\ndate: {DATE}\n{NON_STRING_KEYS[shape]}\n---\n\n" + _body()
    _write_fragments(payload.encode())
    malformed_path, valid_path = _paths()

    rebuild = build_all(incremental=False)
    assert rebuild["success"] is True
    assert rebuild["fts"]["unparsable_paths"] == []

    response = hierarchical_search(query=TOKEN, level=3)
    assert response["success"] is True
    hits = {
        str(item.get("path") or "").replace("\\", "/"): item for item in response["merged_results"]
    }
    hit = hits[str(malformed_path).replace("\\", "/")]
    assert hit["title"] == "Keyed"

    by_date = hierarchical_search(date_from=DATE, date_to=DATE, level=2)
    assert by_date["success"] is True
    assert str(malformed_path).replace("\\", "/") in _hit_paths(by_date, "l2_results")


UNPARSABLE = (
    "no_frontmatter",
    "empty_frontmatter",
    "invalid_yaml",
    "list_root",
    "scalar_root",
    "title_mapping",
    "date_impossible",
    "tags_list_mapping",
    "not_utf8",
    "unclosed_frontmatter",
)


@pytest.mark.parametrize("shape", UNPARSABLE)
def test_unparsable_fragment_is_found_by_its_filename_date(isolated_data_dir, shape):
    """Both derived stores date an unparsable fragment from its filename.

    A date-range query without a token is answered from the metadata cache; the
    fragment must not vanish from "what did I write that day" because its
    frontmatter is broken.
    """
    from tools.build_index import build_all
    from tools.search_journals.core import hierarchical_search

    _write_fragments(SHAPES[shape])
    malformed_path, _valid_path = _paths()
    assert build_all(incremental=False)["success"] is True

    response = hierarchical_search(date_from=DATE, date_to=DATE, level=2)

    assert response["success"] is True
    assert str(malformed_path).replace("\\", "/") in _hit_paths(response, "l2_results")


@pytest.mark.parametrize("shape", sorted(SHAPES))
def test_fallback_scan_returns_the_malformed_fragment(isolated_data_dir, shape):
    """The fallback content scan searches a malformed fragment; it never skips it.

    The scan runs exactly when the index cannot be trusted, so the fragment's
    FTS row is no substitute. Two body hits clear the scan's relevance cut-off.
    """
    from tools.search_journals.l3_content import search_l3_content

    _write_fragments(SHAPES[shape] + b"\n" + TOKEN.encode() + b" second hit\n")
    malformed_path, _valid_path = _paths()

    results = search_l3_content(TOKEN)

    found = {str(item["path"]).replace("\\", "/"): item for item in results}
    hit = found[str(malformed_path).replace("\\", "/")]
    assert isinstance(hit["title"], str)
    assert isinstance(hit["date"], str)
    for field in ("topic", "tags", "mood", "people"):
        assert all(isinstance(value, str) for value in hit[field]), field
