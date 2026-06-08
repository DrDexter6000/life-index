#!/usr/bin/env python3
"""
Life Index - Unified CLI Entry Point
统一命令行入口

Usage:
    life-index <command> [options]
    python -m tools <command> [options]

Commands:
    write     Write a journal entry
    confirm   Apply write confirmation updates
    search    Search journals (pure dual-pipeline)
    smart-search  Smart search with LLM orchestration
    edit      Edit a journal entry
    journal   Read journals through stable get/list contracts
    attachment  Read/export archived attachments
    entity    Manage entity graph
    weather   Query weather information
    index     Build/rebuild search index
    generate-index  Generate index tree (monthly/yearly/root)
    abstract  (alias for generate-index)
    backup    Backup journal data
    verify    Verify data integrity
    timeline  Output chronological summary stream
    on-this-day  Find prior-year entries on same month/day
    recall    Recall search with mode selection (default/recall/deep)
    trajectory  Typed observations (weight/sleep/mood/location/project)
    migrate   Schema migration tool
    eval      Run search evaluation gate
    entity-graph-eval  Run graph ablation evaluation (gbrain #1)
    aggregate Deterministic aggregate/trend computation
    analyze   Alias for aggregate
    maintenance  Run maintenance cycle (dry-run health checks)
    bootstrap    Detect install/data state and route onboarding (read-only)
    health    Check installation health
              --data-audit  Audit data directory for anomalies
              --cache-audit  Read-only cache version audit (JSON)
    import    Import provider (plan, run, status, rollback)
    index-tree  Read-only Index Tree Evidence Navigation
    version   Show package and bootstrap manifest version info
"""

import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Tuple

from importlib.metadata import PackageNotFoundError, version as package_version

from tools.lib.journal_files import count_journal_files
from tools.lib.config import get_model_cache_dir  # noqa: F401 — used via monkeypatch in tests
from tools.lib.paths import get_user_data_dir, get_journals_dir
from tools.lib.bootstrap_manifest import read_bootstrap_manifest as _read_bootstrap_manifest

HEALTH_SCHEMA_VERSION = "m16.health.v0"

BOOTSTRAP_MANIFEST_PATH = Path(__file__).resolve().parent.parent / "bootstrap-manifest.json"


def read_bootstrap_manifest() -> Dict[str, Any]:
    return _read_bootstrap_manifest(BOOTSTRAP_MANIFEST_PATH)


def get_package_version() -> str:
    try:
        manifest_version = read_bootstrap_manifest().get("repo_version")
        if isinstance(manifest_version, str) and manifest_version:
            return manifest_version
    except (OSError, ValueError, json.JSONDecodeError):
        pass

    try:
        return package_version("life-index")
    except PackageNotFoundError:
        return "dev"


def get_version_info() -> Dict[str, Any]:
    return {
        "package_version": get_package_version(),
        "bootstrap_manifest": read_bootstrap_manifest(),
    }


def _check_python_version() -> Tuple[Dict[str, Any], str, bool]:
    """检查 Python 版本"""
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    py_ok = sys.version_info >= (3, 11)
    check = {
        "name": "python_version",
        "status": "ok" if py_ok else "error",
        "value": py_version,
        "required": ">=3.11",
    }
    issue = f"Python {py_version} is too old. Requires >=3.11." if not py_ok else ""
    return check, issue, not py_ok


def _check_venv() -> Tuple[Dict[str, Any], str]:
    """检查虚拟环境"""
    in_venv = sys.prefix != sys.base_prefix
    venv_path = sys.prefix if in_venv else None
    check = {
        "name": "virtual_env",
        "status": "ok" if in_venv else "warning",
        "active": in_venv,
        "path": venv_path,
    }
    if not in_venv:
        issue = (
            "Not running inside a virtual environment. "
            "Recommended: create venv with 'python -m venv .venv' in skill directory."
        )
    else:
        issue = ""
    return check, issue


def _check_pyyaml() -> Tuple[Dict[str, Any], str, bool]:
    """检查 pyyaml 依赖"""
    try:
        import yaml

        yaml_version = getattr(yaml, "__version__", "unknown")
        return (
            {
                "name": "pyyaml",
                "status": "ok",
                "version": yaml_version,
            },
            "",
            False,
        )
    except ImportError:
        return (
            {
                "name": "pyyaml",
                "status": "error",
                "version": None,
            },
            "pyyaml is not installed. Run: pip install pyyaml",
            True,
        )


def _check_sentence_transformers() -> Tuple[Dict[str, Any], str]:
    """检查 sentence-transformers 依赖"""
    try:
        import sentence_transformers

        st_version = getattr(sentence_transformers, "__version__", "unknown")
        return {
            "name": "sentence_transformers",
            "status": "ok",
            "version": st_version,
        }, ""
    except ImportError:
        return (
            {
                "name": "sentence_transformers",
                "status": "warning",
                "version": None,
            },
            "sentence-transformers is not installed. Semantic search will be disabled. "
            "To enable: pip install 'life-index[semantic]'",
        )


def _check_data_dir() -> Tuple[Dict[str, Any], str]:
    """检查数据目录"""
    data_dir = get_user_data_dir()
    journals_dir = get_journals_dir()
    data_exists = data_dir.exists()
    journal_count = count_journal_files(journals_dir)
    check = {
        "name": "data_directory",
        "status": "ok" if data_exists else "info",
        "path": str(data_dir),
        "exists": data_exists,
        "journal_count": journal_count,
    }
    if not data_exists:
        issue = (
            f"Data directory not found: {data_dir}. "
            "It will be created automatically on first journal write."
        )
    else:
        issue = ""
    return check, issue


def _check_index() -> Tuple[Dict[str, Any], str]:
    """检查索引状态"""
    data_dir = get_user_data_dir()
    index_dir = data_dir / ".index"
    fts_db = index_dir / "journals_fts.db"
    vec_db = index_dir / "journals_vec.db"
    vec_pkl = index_dir / "vectors_simple.pkl"
    data_exists = get_user_data_dir().exists()
    from tools.lib.semantic_status import get_semantic_index_status

    semantic = get_semantic_index_status(index_dir)
    semantic_status = str(semantic.get("status", "disabled"))
    check = {
        "name": "search_index",
        "status": "ok" if fts_db.exists() else "info",
        "fts_index_exists": fts_db.exists(),
        "vector_index_exists": vec_db.exists() or vec_pkl.exists(),
        "semantic_status": semantic_status,
        "semantic": semantic,
        "path": str(index_dir),
    }
    if semantic_status == "failed":
        return check, f"Semantic index failed: {semantic.get('error', 'unknown error')}"
    if not fts_db.exists() and data_exists:
        return check, "Search index not built. Run: life-index index"
    return check, ""


def _check_embedding_model() -> Dict[str, Any]:
    try:
        from tools.lib.paths import get_user_data_dir

        model_dir = get_user_data_dir() / ".index" / "models"
        check: Dict[str, Any] = {
            "name": "embedding_model",
            "status": "ok",
            "downloaded": False,
        }

        if model_dir.exists() and any(model_dir.iterdir()):
            check["downloaded"] = True
        else:
            # Check HuggingFace cache as fallback
            hf_cache = Path.home() / ".cache" / "huggingface"
            if hf_cache.exists():
                check["downloaded"] = True
            else:
                check["status"] = "warning"
                check["issue"] = (
                    "Embedding model not cached — first semantic search will download (~2GB)"
                )
        return check
    except Exception:
        return {
            "name": "embedding_model",
            "status": "warning",
            "downloaded": False,
            "error": "Could not check model cache (config import failed)",
        }


def _check_entity_graph(graph_path: Path) -> Dict[str, Any]:
    """Check if entity graph exists and is populated (Round 10, T1.3)."""
    check: Dict[str, Any] = {
        "name": "entity_graph",
        "status": "ok",
        "entity_count": 0,
        "suggested_command": None,
    }

    if not graph_path.exists():
        check["status"] = "warning"
        check["issue"] = "Entity graph not found — search may miss alias-based expansion"
        check["suggested_command"] = "life-index entity --seed"
        return check

    try:
        from tools.lib.entity_graph import load_entity_graph

        entities = load_entity_graph(graph_path)
        check["entity_count"] = len(entities)

        if len(entities) == 0:
            check["status"] = "warning"
            check["issue"] = "Entity graph is empty — run seed to create initial graph"
            check["suggested_command"] = "life-index entity --seed"
    except Exception as e:
        check["status"] = "warning"
        check["issue"] = f"Entity graph error: {e}"

    return check


def _check_index_tree() -> Dict[str, Any]:
    """Check Index Tree freshness using existing check_index_tree_freshness()."""
    check: Dict[str, Any] = {
        "name": "index_tree",
        "status": "ok",
        "freshness_status": None,
        "total_nodes": 0,
        "issues": [],
    }

    try:
        from tools.generate_index.navigation import check_index_tree_freshness

        result = check_index_tree_freshness(level="month")
        check["freshness_status"] = result.get("status")
        check["total_nodes"] = result.get("total_nodes", 0)
        issues = result.get("issues", [])

        if result.get("status") == "empty_tree":
            check["status"] = "info"
            check["issue"] = "Index Tree is empty — run 'life-index generate-index' to build"
        elif issues:
            check["status"] = "warning"
            check["issues"] = issues
            stale_count = sum(1 for i in issues if i.get("freshness") == "stale")
            missing_count = sum(1 for i in issues if i.get("freshness") == "missing_index")
            parts = []
            if stale_count:
                parts.append(f"{stale_count} stale")
            if missing_count:
                parts.append(f"{missing_count} missing")
            check["issue"] = (
                f"Index Tree has {' and '.join(parts)} nodes — run 'life-index generate-index'"
            )
        else:
            check["status"] = "ok"
    except Exception as e:
        check["status"] = "info"
        check["issue"] = f"Could not check Index Tree: {e}"

    return check


def health_check() -> None:
    """
    检查 Life Index 安装健康状态。

    检查项:
    1. Python 版本 (>=3.11)
    2. 虚拟环境状态
    3. 核心依赖 (pyyaml)
    4. 语义搜索依赖 (sentence-transformers)
    5. 数据目录
    6. 索引状态
    7. 嵌入模型缓存
    """
    checks: List[Dict[str, Any]] = []
    issues: List[str] = []
    has_critical = False

    # 1. Python version
    check, issue, critical = _check_python_version()
    checks.append(check)
    if issue:
        issues.append(issue)
    has_critical = has_critical or critical

    # 2. Virtual environment
    check, issue = _check_venv()
    checks.append(check)
    if issue:
        issues.append(issue)

    # 3. Core dependency: pyyaml
    check, issue, critical = _check_pyyaml()
    checks.append(check)
    if issue:
        issues.append(issue)
    has_critical = has_critical or critical

    # 4. Semantic search dependency: sentence-transformers
    check, issue = _check_sentence_transformers()
    checks.append(check)
    if issue:
        issues.append(issue)

    # 5. Data directory
    check, issue = _check_data_dir()
    checks.append(check)
    if issue:
        issues.append(issue)

    # 6. Index status
    check, issue = _check_index()
    checks.append(check)
    if issue:
        issues.append(issue)

    # 7. Embedding model cache
    check = _check_embedding_model()
    checks.append(check)
    if check.get("issue"):
        issues.append(check["issue"])

    # 8. Entity graph (Round 10, T1.3)
    from tools.lib.paths import resolve_user_data_dir

    graph_path = resolve_user_data_dir() / "entity_graph.yaml"
    check = _check_entity_graph(graph_path)
    checks.append(check)
    if check.get("issue"):
        issues.append(check["issue"])

    # 9. Index Tree freshness
    check = _check_index_tree()
    checks.append(check)
    if check.get("issue"):
        issues.append(check["issue"])

    # Build result
    overall = "healthy" if not has_critical else "unhealthy"
    if not has_critical and issues:
        overall = "degraded"

    result: Dict[str, Any] = {
        "success": True,
        "schema_version": HEALTH_SCHEMA_VERSION,
        "data": {
            "status": overall,
            "checks": checks,
            "issues": issues,
            "issue_count": len(issues),
        },
    }

    # Attach piggyback events
    from tools.lib.events import detect_events
    from tools.lib.event_detectors import register_all_detectors

    register_all_detectors()
    context = {"journals_dir": get_journals_dir(), "data_dir": get_user_data_dir()}
    events = detect_events(context=context)
    result["events"] = [e.to_dict() for e in events]

    print(json.dumps(result, ensure_ascii=False, indent=2))


def _run_data_audit() -> None:
    """Run data directory audit and print JSON result."""
    from tools.lib.data_audit import audit_data_directory

    report = audit_data_directory(get_user_data_dir())
    result = {
        "success": True,
        "schema_version": HEALTH_SCHEMA_VERSION,
        "data": {
            "file_count": report.file_count,
            "anomalies": [
                {
                    "type": a.type,
                    "severity": a.severity,
                    "description": a.description,
                    "path": a.path,
                }
                for a in report.anomalies
            ],
            "distribution": report.distribution,
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main() -> None:
    """Unified CLI entry point"""
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)

    subcmd = sys.argv[1]

    # Handle health check directly (no submodule import needed)
    if subcmd == "health":
        if "--cache-audit" in sys.argv[2:]:
            from tools.lib.metadata_cache import run_cache_audit

            report = run_cache_audit()
            print(json.dumps(report, ensure_ascii=False, indent=2))
        elif "--data-audit" in sys.argv[2:]:
            _run_data_audit()
        else:
            health_check()
        return

    if subcmd == "--version":
        print(json.dumps(get_version_info(), ensure_ascii=False, indent=2))
        return

    # Map subcommands to __main__ module paths
    # Each submodule has its own __main__.py with a main() function
    cmd_map = {
        "write": "tools.write_journal.__main__",
        "confirm": "tools.write_journal.__main__",
        "search": "tools.search_journals.__main__",
        "edit": "tools.edit_journal.__main__",
        "journal": "tools.journal.__main__",
        "attachment": "tools.attachment.__main__",
        "entity": "tools.entity.__main__",
        "weather": "tools.query_weather.__main__",
        "index": "tools.build_index.__main__",
        "generate-index": "tools.generate_index.__main__",
        "abstract": "tools.generate_index.__main__",
        "backup": "tools.backup.__main__",
        "verify": "tools.verify.__main__",  # Task 1.3.2
        "timeline": "tools.timeline.__main__",  # Task 3.2
        "migrate": "tools.migrate.__main__",  # Round 6 Phase 1
        "eval": "tools.eval.__main__",
        "entity-graph-eval": "tools.eval.ablation.__main__",
        "smart-search": "tools.smart_search.__main__",
        "agent-bridge": "tools.agent_bridge.__main__",
        "aggregate": "tools.aggregate.__main__",
        "analyze": "tools.aggregate.__main__",
        "on-this-day": "tools.on_this_day.__main__",
        "recall": "tools.recall.__main__",
        "maintenance": "tools.maintenance.__main__",
        "bootstrap": "tools.bootstrap.__main__",
        "trajectory": "tools.trajectory.__main__",
        "import": "tools.ingest.__main__",
        "index-tree": "tools.index_tree.__main__",
    }

    if subcmd in cmd_map:
        # Rewrite argv so the submodule's argparse works correctly
        # Keep the original argv[0] for proper error messages
        sys.argv = [f"life-index {subcmd}"] + sys.argv[2:]

        # Import and run the submodule's main()
        module = __import__(cmd_map[subcmd], fromlist=["main"])
        module.main()
    elif subcmd in ("-V", "version"):
        print(json.dumps(get_version_info(), ensure_ascii=False, indent=2))
    elif subcmd in ("--help", "-h", "help"):
        print_usage()
    else:
        print(f"Unknown command: {subcmd}")
        print_usage()
        sys.exit(1)


def print_usage() -> None:
    """Print usage information"""
    print("Usage: life-index <command> [options]")
    print("       python -m tools <command> [options]")
    print()
    print("Commands:")
    print("  write     Write a journal entry")
    print("  confirm   Apply write confirmation updates")
    print("  search    Search journals")
    print("  edit      Edit a journal entry")
    print("  journal   Read journals through stable get/list contracts")
    print("  attachment  Read/export archived attachments")
    print("  entity    Manage entity graph")
    print("  weather   Query weather information")
    print("  index     Build/rebuild search index")
    print("  generate-index  Generate index tree (monthly/yearly/root)")
    print("  abstract        (alias for generate-index)")
    print("  backup    Backup journal data")
    print("  verify    Verify data integrity")
    print("  timeline  Output chronological summary stream")
    print("  on-this-day  Find prior-year entries on same month/day")
    print("  recall    Recall search with mode selection (default/recall/deep)")
    print("  trajectory  Typed observations (weight/sleep/mood/location/project)")
    print("  migrate   Schema migration tool")
    print("  eval      Run search evaluation gate")
    print("  entity-graph-eval  Run graph ablation evaluation")
    print("  maintenance  Run maintenance cycle (dry-run health checks)")
    print("  bootstrap  Detect install/data state and route onboarding (read-only)")
    print("  smart-search  Smart search with LLM orchestration")
    print("  agent-bridge  L3 host-agent bridge probe/handoff")
    print("  aggregate  Deterministic aggregate/trend computation")
    print("  analyze   Alias for deterministic aggregate/trend computation")
    print("  health    Check installation health")
    print("            --data-audit  Audit data directory for anomalies")
    print("            --cache-audit  Read-only cache version audit (JSON)")
    print("  import    Import provider (plan, run, status, rollback)")
    print("  index-tree  Read-only Index Tree Evidence Navigation")
    print("  version   Show package and bootstrap manifest version info")
    print()
    print("Run 'life-index <command> --help' for command-specific options.")
    print()
    print("Developer mode:")
    print("  python -m tools.write_journal --data '{...}'")
    print("  python -m tools.search_journals --query '关键词'")


if __name__ == "__main__":
    main()
