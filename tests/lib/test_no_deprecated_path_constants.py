"""
Guard test: Verify deprecated path constants have been fully removed.

D.1 (Round 16) completed the atomic removal of deprecated path constants
from paths.py. This test ensures no one re-introduces them.

These constants were replaced by stateless getter functions:
  USER_DATA_DIR  -> get_user_data_dir()
  JOURNALS_DIR   -> get_journals_dir()
  INDEX_DIR      -> get_index_dir()
  FTS_DB_PATH    -> get_fts_db_path()
  CONFIG_DIR     -> get_config_dir()
  CONFIG_FILE    -> get_config_file()
  BY_TOPIC_DIR   -> get_by_topic_dir()
  ATTACHMENTS_DIR -> get_attachments_dir()
  CACHE_DIR      -> get_cache_dir()
  ABSTRACTS_DIR  -> (removed, never had a getter)
"""

import ast
from pathlib import Path

# Constants that should NOT exist as module-level attributes in paths.py
DEPRECATED_PATH_CONSTANTS = frozenset(
    {
        "USER_DATA_DIR",
        "JOURNALS_DIR",
        "INDEX_DIR",
        "FTS_DB_PATH",
        "CONFIG_DIR",
        "CONFIG_FILE",
        "BY_TOPIC_DIR",
        "ATTACHMENTS_DIR",
        "CACHE_DIR",
        "ABSTRACTS_DIR",
        "VEC_INDEX_PATH",
        "VEC_META_PATH",
        "METADATA_DB_PATH",
    }
)


def _get_paths_py() -> Path:
    """Resolve paths.py location."""
    return Path(__file__).parent.parent.parent / "tools" / "lib" / "paths.py"


def test_paths_module_has_no_deprecated_constants():
    """paths.py must not define deprecated module-level constants.

    D.1 atomic removal: all deprecated constants were replaced by
    stateless getter functions (get_user_data_dir(), etc.).
    """
    paths_py = _get_paths_py()
    assert paths_py.exists(), f"paths.py not found at {paths_py}"

    tree = ast.parse(paths_py.read_text(encoding="utf-8"))

    # Collect all top-level assignments and simple annotations
    defined_names = set()
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    defined_names.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            defined_names.add(node.target.id)

    offenders = defined_names & DEPRECATED_PATH_CONSTANTS
    assert offenders == set(), (
        f"paths.py still defines deprecated constants: {offenders}. "
        f"Use getter functions instead (see module docstring)."
    )


def test_no_import_of_deprecated_path_constants():
    """No file in tools/ should import deprecated path constants from paths.py.

    All consumers must use getter functions (get_user_data_dir(), etc.).
    """
    offenders = []
    tools_dir = _get_paths_py().parent.parent  # tools/

    for py_file in tools_dir.rglob("*.py"):
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            if not node.module:
                continue

            # Check imports from tools.lib.paths or .paths
            is_paths_import = (
                node.module == "tools.lib.paths"
                or (node.module == ".paths" and "tools/lib" in str(py_file))
                or node.module.endswith("lib.paths")
            )
            if not is_paths_import:
                continue

            for alias in node.names:
                if alias.name in DEPRECATED_PATH_CONSTANTS:
                    rel = py_file.relative_to(tools_dir)
                    offenders.append(f"{rel}:{node.lineno} imports deprecated {alias.name}")

    assert offenders == [], "Deprecated path constant imports found:\n" + "\n".join(offenders)


def test_paths_exposes_only_getters_and_patterns():
    """paths.py __all__ should list getters and patterns, no deprecated constants."""
    import tools.lib.paths as p

    for name in DEPRECATED_PATH_CONSTANTS:
        assert not hasattr(
            p, name
        ), f"paths.{name} is still exported. Remove it and use getter instead."

    # Verify essential getters exist
    essential_getters = [
        "get_user_data_dir",
        "get_journals_dir",
        "get_index_dir",
        "get_fts_db_path",
        "get_config_dir",
        "get_config_file",
        "get_by_topic_dir",
        "get_attachments_dir",
    ]
    for getter in essential_getters:
        assert hasattr(p, getter), f"paths.py missing essential getter: {getter}"
        assert callable(getattr(p, getter)), f"paths.{getter} should be callable"
