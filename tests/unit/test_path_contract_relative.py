"""D7: the ``safe_relative_path`` fast path must match ``Path.relative_to``.

The old string-prefix fast path normalized separators but not other lexical
noise, so un-normalized string input (doubled separators, for example) returned
a different relative string than the previous implementation.
"""

from pathlib import Path

import pytest

from tools.lib.path_contract import safe_relative_path


def _reference(path: Path | str, base: Path | str) -> str:
    """The implementation before the fast path was introduced."""
    path_obj = Path(path)
    base_obj = Path(base)
    try:
        return str(path_obj.relative_to(base_obj)).replace("\\", "/")
    except ValueError:
        return str(path_obj).replace("\\", "/")


CASES = [
    ("Journals/2026/03/a.md", "Journals"),
    ("Journals/2026/03/a.md", "Journals/2026/03"),
    ("Journals\\2026\\03\\a.md", "Journals"),
    ("Journals//2026/03/a.md", "Journals"),
    ("Journals/2026//03///a.md", "Journals/2026"),
    ("Journals/2026/03/../03/a.md", "Journals"),
    ("Journals/./2026/03/a.md", "Journals"),
    ("Journals/2026/03/", "Journals/2026"),
    ("Journals/2026/03/a.md", "Journals/2026/03/"),
    ("Journals/2026/03/a.md", "Journals/2026/03"),
    ("journals/2026/03/a.md", "Journals"),
    ("Journals2/03/a.md", "Journals"),
    ("Journals/2026/03/a.md", "Journals/2026/03/a.md"),
    ("Journals", "Journals"),
    ("/tmp/life-index/Journals/2026/03/a.md", "/tmp/life-index"),
    ("/tmp/life-index/Journals/2026/03/a.md", "/tmp/life-index/Journals/"),
]


@pytest.mark.parametrize(("path", "base"), CASES)
def test_string_input_matches_previous_implementation(path: str, base: str) -> None:
    assert safe_relative_path(path, base) == _reference(path, base)


@pytest.mark.parametrize(("path", "base"), CASES)
def test_path_input_matches_previous_implementation(path: str, base: str) -> None:
    assert safe_relative_path(Path(path), Path(base)) == _reference(Path(path), Path(base))
