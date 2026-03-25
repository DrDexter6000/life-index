#!/usr/bin/env python3
"""
Life Index - Unified CLI Entry Point
统一命令行入口

Usage:
    life-index <command> [options]
    python -m tools <command> [options]

Commands:
    write     Write a journal entry
    search    Search journals
    edit      Edit a journal entry
    weather   Query weather information
    index     Build/rebuild search index
    abstract  Generate monthly/yearly summaries
    backup    Backup journal data
    health    Check installation health
"""

import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Tuple, cast

from importlib.metadata import PackageNotFoundError, version as package_version

from tools.lib.config import USER_DATA_DIR, JOURNALS_DIR, get_model_cache_dir

BOOTSTRAP_MANIFEST_PATH = Path(__file__).resolve().parent.parent / "bootstrap-manifest.json"


def read_bootstrap_manifest() -> Dict[str, Any]:
    with BOOTSTRAP_MANIFEST_PATH.open("r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError("bootstrap-manifest.json must contain a JSON object")
    return cast(Dict[str, Any], payload)


def get_package_version() -> str:
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


def _check_fastembed() -> Tuple[Dict[str, Any], str]:
    """检查 fastembed 依赖"""
    try:
        import fastembed

        fe_version = getattr(fastembed, "__version__", "unknown")
        return {
            "name": "fastembed",
            "status": "ok",
            "version": fe_version,
        }, ""
    except ImportError:
        return (
            {
                "name": "fastembed",
                "status": "warning",
                "version": None,
            },
            "fastembed is not installed. Semantic search will be disabled. "
            "To enable: pip install 'fastembed>=0.5.1'",
        )


def _check_data_dir() -> Tuple[Dict[str, Any], str]:
    """检查数据目录"""
    data_dir = USER_DATA_DIR
    journals_dir = JOURNALS_DIR
    data_exists = data_dir.exists()
    journal_count = 0
    if journals_dir.exists():
        journal_count = len(list(journals_dir.rglob("*.md")))
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
    data_dir = USER_DATA_DIR
    index_dir = data_dir / ".index"
    fts_db = index_dir / "journals_fts.db"
    vec_db = index_dir / "journals_vec.db"
    vec_pkl = index_dir / "vectors_simple.pkl"
    data_exists = USER_DATA_DIR.exists()
    check = {
        "name": "search_index",
        "status": "ok" if fts_db.exists() else "info",
        "fts_index_exists": fts_db.exists(),
        "vector_index_exists": vec_db.exists() or vec_pkl.exists(),
        "path": str(index_dir),
    }
    if not fts_db.exists() and data_exists:
        return check, "Search index not built. Run: life-index index"
    return check, ""


def _check_embedding_model() -> Dict[str, Any]:
    """检查嵌入模型缓存"""
    try:
        cache_dir = get_model_cache_dir()
        model_files = list(cache_dir.rglob("*.onnx")) if cache_dir.exists() else []
        model_downloaded = len(model_files) > 0
        cache_size_mb = 0.0
        if cache_dir.exists():
            total_bytes = sum(f.stat().st_size for f in cache_dir.rglob("*") if f.is_file())
            cache_size_mb = round(total_bytes / (1024 * 1024), 2)
        check = {
            "name": "embedding_model",
            "status": "ok" if model_downloaded else "info",
            "downloaded": model_downloaded,
            "cache_dir": str(cache_dir),
            "cache_size_mb": cache_size_mb,
        }
        if not model_downloaded:
            check["issue"] = (
                "Embedding model not downloaded yet. "
                "Run: life-index index (will download ~80MB model automatically)"
            )
        return check
    except Exception:
        return {
            "name": "embedding_model",
            "status": "warning",
            "downloaded": False,
            "error": "Could not check model cache (config import failed)",
        }


def health_check() -> None:
    """
    检查 Life Index 安装健康状态。

    检查项:
    1. Python 版本 (>=3.11)
    2. 虚拟环境状态
    3. 核心依赖 (pyyaml)
    4. 语义搜索依赖 (fastembed)
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

    # 4. Semantic search dependency: fastembed
    check, issue = _check_fastembed()
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

    # Build result
    overall = "healthy" if not has_critical else "unhealthy"
    if not has_critical and issues:
        overall = "degraded"

    result: Dict[str, Any] = {
        "success": True,
        "data": {
            "status": overall,
            "checks": checks,
            "issues": issues,
            "issue_count": len(issues),
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
        health_check()
        return

    if subcmd == "--version":
        print(json.dumps(get_version_info(), ensure_ascii=False, indent=2))
        return

    # Map subcommands to __main__ module paths
    # Each submodule has its own __main__.py with a main() function
    cmd_map = {
        "write": "tools.write_journal.__main__",
        "search": "tools.search_journals.__main__",
        "edit": "tools.edit_journal.__main__",
        "weather": "tools.query_weather.__main__",
        "index": "tools.build_index.__main__",
        "abstract": "tools.generate_abstract.__main__",
        "backup": "tools.backup.__main__",
        "serve": "web.__main__",
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
    print()
    print("Commands:")
    print("  write     Write a journal entry")
    print("  search    Search journals")
    print("  edit      Edit a journal entry")
    print("  weather   Query weather information")
    print("  index     Build/rebuild search index")
    print("  abstract  Generate monthly/yearly summaries")
    print("  backup    Backup journal data")
    print("  health    Check installation health")
    print("  version   Show package and bootstrap manifest version info")
    print()
    print("Run 'life-index <command> --help' for command-specific options.")
    print()
    print("Developer mode:")
    print("  python -m tools.write_journal --data '{...}'")
    print("  python -m tools.search_journals --query '关键词'")


if __name__ == "__main__":
    main()
