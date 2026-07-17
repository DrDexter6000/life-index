"""Stdlib-only installation truth helpers for Life Index recovery.

This module is deliberately safe to execute as a file with ``python -I``.  It
must not import ``tools`` because the problem it diagnoses can make that import
resolve to a stale physical package.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import tomllib
import zipfile
from email.parser import Parser
from importlib.metadata import Distribution
from importlib.metadata import distributions
from pathlib import Path
from typing import Any
from urllib.parse import unquote
from urllib.parse import urlparse

PROJECT_NAME = "life-index"
RECOVERY_COMMAND = "recover"
INSTALL_INTEGRITY_SCHEMA_VERSION = "m37.install_integrity.v0"
AUTHORITY_ERROR = "INSTALL_RECOVERY_AUTHORITY_INVALID"
BUILD_PREFLIGHT_ERROR = "INSTALL_RECOVERY_BUILD_PREFLIGHT_FAILED"
UNINSTALL_ERROR = "INSTALL_RECOVERY_UNINSTALL_FAILED"
UNINSTALL_STALLED_ERROR = "INSTALL_RECOVERY_UNINSTALL_STALLED"
TARGET_INSTALL_ERROR = "INSTALL_RECOVERY_TARGET_INSTALL_FAILED"
PROBE_ERROR = "INSTALL_RECOVERY_PROBE_FAILED"
ORPHAN_SHADOW_ERROR = "INSTALL_RECOVERY_ORPHAN_SHADOW"
OWNERSHIP_CONFLICT_ERROR = "INSTALL_RECOVERY_OWNERSHIP_CONFLICT"
# These values deliberately match tools.lib.workflow_signals.RecoveryStrategy.
# This isolated module must not import tools because a stale tools package is the
# condition it is responsible for diagnosing.
RECOVERY_STRATEGY_ASK_USER = "ask_user"
RECOVERY_STRATEGY_RETRY = "retry"
_SOURCE_INJECTION_ENVIRONMENT_KEYS = (
    "PYTHONHOME",
    "PYTHONPATH",
    "PYTHONSTARTUP",
    "PYTHONUSERBASE",
    "PYTHONSAFEPATH",
)


def normalize_distribution_name(name: str) -> str:
    """Return the PEP 503 comparison form without third-party packaging."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _metadata_path(distribution: Distribution) -> Path:
    raw_path = getattr(distribution, "_path", None)
    if raw_path is not None:
        return Path(raw_path)

    files = distribution.files or []
    for file in files:
        parts = Path(str(file)).parts
        for index, part in enumerate(parts):
            if part.endswith(".dist-info"):
                metadata_path = Path(str(distribution.locate_file(file)))
                for _ in parts[index + 1 :]:
                    metadata_path = metadata_path.parent
                return metadata_path
    return Path(str(distribution.locate_file("")))


def _canonical_path(path: Path) -> str:
    return os.path.normcase(str(path.resolve(strict=False)))


def _read_direct_url(distribution: Distribution) -> tuple[dict[str, Any] | None, bool]:
    raw = distribution.read_text("direct_url.json")
    if not raw:
        return None, False
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {"invalid": True}, False
    if not isinstance(payload, dict):
        return {"invalid": True}, False
    dir_info = payload.get("dir_info")
    editable = isinstance(dir_info, dict) and dir_info.get("editable") is True
    return payload, editable


def _canonical_distribution_records() -> list[dict[str, Any]]:
    """Return each current interpreter distribution once with RECORD-owned paths."""
    canonical: dict[str, dict[str, Any]] = {}
    for candidate in distributions():
        metadata_name = candidate.metadata["Name"] if "Name" in candidate.metadata else None
        metadata_path = _metadata_path(candidate)
        canonical_path = _canonical_path(metadata_path)
        if canonical_path in canonical:
            continue
        direct_url, editable = _read_direct_url(candidate)
        owned_paths: set[str] = set()
        for file in candidate.files or []:
            try:
                owned_paths.add(_canonical_path(Path(str(candidate.locate_file(file)))))
            except (OSError, TypeError, ValueError):
                continue
        canonical[canonical_path] = {
            "name": metadata_name,
            "normalized_name": (
                normalize_distribution_name(metadata_name)
                if isinstance(metadata_name, str)
                else None
            ),
            "version": candidate.version,
            "metadata_path": str(metadata_path),
            "canonical_metadata_path": canonical_path,
            "location": str(metadata_path.parent),
            "direct_url": direct_url,
            "editable": editable,
            "owned_paths": sorted(owned_paths),
        }

    return sorted(canonical.values(), key=lambda item: item["canonical_metadata_path"])


def _public_distribution_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        key: record[key]
        for key in (
            "name",
            "normalized_name",
            "version",
            "metadata_path",
            "canonical_metadata_path",
            "location",
            "direct_url",
            "editable",
        )
    }


def _life_index_inventory(records: list[dict[str, Any]]) -> dict[str, Any]:
    life_index_records = [
        _public_distribution_record(record)
        for record in records
        if record["normalized_name"] == PROJECT_NAME
    ]
    count = len(life_index_records)
    state = "absent" if count == 0 else "single" if count == 1 else "conflict"
    return {
        "project": PROJECT_NAME,
        "state": state,
        "canonical_count": count,
        "distributions": life_index_records,
    }


def _ownership_descriptor(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": record["name"],
        "version": record["version"],
        "metadata_path": record["metadata_path"],
        "canonical_metadata_path": record["canonical_metadata_path"],
    }


def _life_index_ownership_conflicts(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Find paths jointly declared by Life Index and a distinct distribution."""
    owners_by_path: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        for owned_path in record["owned_paths"]:
            owners_by_path.setdefault(owned_path, []).append(record)

    conflicts: list[dict[str, Any]] = []
    for path in sorted(owners_by_path):
        owners = owners_by_path[path]
        life_index_owners = [
            _ownership_descriptor(record)
            for record in owners
            if record["normalized_name"] == PROJECT_NAME
        ]
        unrelated_owners = [
            _ownership_descriptor(record)
            for record in owners
            if record["normalized_name"] != PROJECT_NAME
        ]
        if life_index_owners and unrelated_owners:
            conflicts.append(
                {
                    "path": path,
                    "life_index_owners": life_index_owners,
                    "unrelated_owners": unrelated_owners,
                }
            )
    return conflicts


def inventory_life_index_distributions() -> dict[str, Any]:
    """Inventory canonical Life Index distributions in the active interpreter.

    ``importlib.metadata.distributions()`` can expose the same dist-info
    directory more than once when ``sys.path`` has duplicate entries. A
    resolved, case-normalized dist-info path is the identity boundary, so that
    duplicate exposure remains one installation while distinct dist-info
    directories are a conflict.
    """
    return _life_index_inventory(_canonical_distribution_records())


def _path_from_file_url(url: str) -> Path | None:
    parsed = urlparse(url)
    if parsed.scheme != "file":
        return None
    raw_path = unquote(parsed.path)
    if os.name == "nt" and raw_path.startswith("/") and len(raw_path) > 2 and raw_path[2] == ":":
        raw_path = raw_path[1:]
    return Path(raw_path)


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(parent.resolve(strict=False))
    except ValueError:
        return False
    return True


def _clean_environment() -> dict[str, str]:
    environment = dict(os.environ)
    for key in tuple(environment):
        if key.startswith("PIP_") or key.startswith("PYTHON"):
            environment.pop(key, None)
    for key in _SOURCE_INJECTION_ENVIRONMENT_KEYS:
        environment.pop(key, None)
    environment.pop("VIRTUAL_ENV", None)
    environment["PIP_NO_INDEX"] = "1"
    environment["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    environment["PIP_NO_CACHE_DIR"] = "1"
    environment["PIP_NO_INPUT"] = "1"
    return environment


def _command_payload(
    command: list[str],
    *,
    cwd: Path,
    environment: dict[str, str],
) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            env=environment,
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "command": command,
            "returncode": None,
            "stdout": "",
            "stderr": str(exc),
        }
    return {
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def _authority_failure(reason: str, message: str) -> tuple[None, dict[str, str]]:
    return None, {"reason": reason, "message": message}


def _authority(source_root: str) -> tuple[dict[str, Any] | None, dict[str, str] | None]:
    source = Path(source_root).expanduser()
    interpreter = Path(sys.executable) if sys.executable else None
    if interpreter is None or not interpreter.is_file():
        return _authority_failure(
            "INTERPRETER_NOT_FILE",
            "The active interpreter cannot be proven as a regular file.",
        )
    if sys.prefix == sys.base_prefix:
        return _authority_failure(
            "INTERPRETER_NOT_VENV",
            "The active interpreter is not owned by a supported standard virtual environment.",
        )
    if source.is_symlink() or not source.is_dir():
        return _authority_failure(
            "SOURCE_ROOT_INVALID", "source-root must be a non-symlink directory."
        )

    source = source.resolve(strict=True)
    pyproject = source / "pyproject.toml"
    manifest = source / "bootstrap-manifest.json"
    if (
        not pyproject.is_file()
        or pyproject.is_symlink()
        or not manifest.is_file()
        or manifest.is_symlink()
    ):
        return _authority_failure(
            "SOURCE_AUTHORITY_FILES_INVALID",
            "source-root is missing non-symlink pyproject.toml or bootstrap-manifest.json.",
        )

    try:
        pyproject_payload = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError, tomllib.TOMLDecodeError) as exc:
        return _authority_failure(
            "SOURCE_AUTHORITY_FILES_UNREADABLE", f"source authority files could not be read: {exc}"
        )

    project = pyproject_payload.get("project")
    project_name = project.get("name") if isinstance(project, dict) else None
    project_version = project.get("version") if isinstance(project, dict) else None
    manifest_version = (
        manifest_payload.get("repo_version") if isinstance(manifest_payload, dict) else None
    )
    if (
        not isinstance(project_name, str)
        or normalize_distribution_name(project_name) != PROJECT_NAME
    ):
        return _authority_failure(
            "SOURCE_PROJECT_NAME_INVALID",
            "pyproject.toml does not identify the Life Index distribution.",
        )
    if not isinstance(project_version, str) or not project_version:
        return _authority_failure(
            "SOURCE_PROJECT_VERSION_INVALID",
            "pyproject.toml does not provide a project version.",
        )
    if not isinstance(manifest_version, str) or not manifest_version:
        return _authority_failure(
            "SOURCE_MANIFEST_VERSION_INVALID",
            "bootstrap-manifest.json does not provide repo_version.",
        )
    if project_version != manifest_version:
        return _authority_failure(
            "SOURCE_VERSION_MISMATCH",
            "pyproject.toml version and bootstrap-manifest.json repo_version differ.",
        )

    return {
        "source_root": str(source),
        "source_version": project_version,
        "manifest_version": manifest_version,
        "interpreter": str(interpreter.resolve(strict=False)),
    }, None


def _wheel_validation(wheel: Path, *, expected_version: str) -> tuple[dict[str, Any], str | None]:
    try:
        with zipfile.ZipFile(wheel) as archive:
            names = set(archive.namelist())
            metadata_names = sorted(name for name in names if name.endswith(".dist-info/METADATA"))
            if len(metadata_names) != 1:
                return {
                    "wheel": str(wheel),
                    "metadata_names": metadata_names,
                }, "wheel METADATA is ambiguous"
            metadata = Parser().parsestr(archive.read(metadata_names[0]).decode("utf-8"))
            bootstrap_manifest_versions: dict[str, str | None] = {}
            for manifest_name in ("bootstrap-manifest.json", "tools/bootstrap-manifest.json"):
                if manifest_name not in names:
                    bootstrap_manifest_versions[manifest_name] = None
                    continue
                manifest_payload = json.loads(archive.read(manifest_name).decode("utf-8"))
                manifest_version = (
                    manifest_payload.get("repo_version")
                    if isinstance(manifest_payload, dict)
                    else None
                )
                bootstrap_manifest_versions[manifest_name] = (
                    manifest_version if isinstance(manifest_version, str) else None
                )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, zipfile.BadZipFile) as exc:
        return {"wheel": str(wheel)}, f"wheel could not be inspected: {exc}"

    name = metadata.get("Name")
    version = metadata.get("Version")
    has_tools_package = any(
        name.startswith("tools/") and name.endswith("/__init__.py") for name in names
    )
    has_tools_entry = "tools/__main__.py" in names
    validation = {
        "wheel": str(wheel),
        "name": name,
        "version": version,
        "has_tools_package": has_tools_package,
        "has_tools_entry": has_tools_entry,
        "bootstrap_manifest_version": bootstrap_manifest_versions["tools/bootstrap-manifest.json"],
        "bootstrap_manifest_versions": bootstrap_manifest_versions,
    }
    if not isinstance(name, str) or normalize_distribution_name(name) != PROJECT_NAME:
        return validation, "wheel does not contain the Life Index distribution"
    if version != expected_version:
        return validation, "wheel version does not match source authority"
    if not has_tools_package or not has_tools_entry:
        return validation, "wheel does not contain the tools package entry surface"
    if bootstrap_manifest_versions["tools/bootstrap-manifest.json"] is None:
        return validation, "wheel does not contain the shipped tools bootstrap manifest"
    if any(
        value is not None and value != expected_version
        for value in bootstrap_manifest_versions.values()
    ):
        return validation, "wheel bootstrap manifest version does not match source authority"
    return validation, None


def _build_staged_wheel(
    authority: dict[str, Any],
    *,
    working_dir: Path,
    environment: dict[str, str],
) -> tuple[Path | None, dict[str, Any], str | None]:
    wheel_dir = working_dir / "wheelhouse"
    wheel_dir.mkdir()
    command = [
        sys.executable,
        "-m",
        "pip",
        "--isolated",
        "wheel",
        "--no-index",
        "--no-build-isolation",
        "--no-deps",
        "--wheel-dir",
        str(wheel_dir),
        str(authority["source_root"]),
    ]
    command_result = _command_payload(command, cwd=working_dir, environment=environment)
    if command_result["returncode"] != 0:
        return None, {"build": command_result}, "pip wheel preflight failed"

    wheels = sorted(wheel_dir.glob("*.whl"))
    if len(wheels) != 1:
        return (
            None,
            {"build": command_result, "wheels": [str(item) for item in wheels]},
            "wheel build was ambiguous",
        )
    validation, error = _wheel_validation(
        wheels[0], expected_version=str(authority["source_version"])
    )
    result = {"build": command_result, "wheel_validation": validation}
    if error:
        return None, result, error
    return wheels[0], result, None


_NEUTRAL_PROBE = r"""
import importlib
import importlib.machinery
import importlib.metadata as metadata
import io
import json
import os
import re
import runpy
import sys
import sysconfig
from pathlib import Path
from urllib.parse import unquote, urlparse

PROJECT = "life-index"
SOURCE = Path(sys.argv[1]).resolve(strict=False)
EXPECTED = sys.argv[2]
VERIFICATION_MODE = "isolated_no_site_explicit_target"

def normalized(name):
    return re.sub(r"[-_.]+", "-", name).lower()

def canonical(path):
    return os.path.normcase(str(path.resolve(strict=False)))

def metadata_path(dist):
    raw = getattr(dist, "_path", None)
    if raw is not None:
        return Path(raw)
    for file in dist.files or []:
        parts = Path(str(file)).parts
        for index, part in enumerate(parts):
            if part.endswith(".dist-info"):
                value = Path(dist.locate_file(file))
                for _ in parts[index + 1:]:
                    value = value.parent
                return value
    return Path(dist.locate_file(""))

def file_url(value):
    parsed = urlparse(value)
    if parsed.scheme != "file":
        return None
    path = unquote(parsed.path)
    if os.name == "nt" and path.startswith("/") and len(path) > 2 and path[2] == ":":
        path = path[1:]
    return Path(path)

def unique_paths(paths):
    result = []
    seen = set()
    for path in paths:
        value = Path(path).resolve(strict=False)
        key = canonical(value)
        if key not in seen and value.is_dir():
            seen.add(key)
            result.append(value)
    return result

def interpreter_venv_root():
    executable = Path(sys.executable).resolve(strict=False)
    candidate = executable.parent.parent
    if (candidate / "pyvenv.cfg").is_file():
        return candidate
    return Path(sys.prefix).resolve(strict=False)

def explicit_paths():
    venv_root = interpreter_venv_root()
    install_scheme = sysconfig.get_paths(
        vars={"base": str(venv_root), "platbase": str(venv_root)}
    )
    runtime_scheme = sysconfig.get_paths()
    site_paths = unique_paths(
        [install_scheme.get("purelib", ""), install_scheme.get("platlib", "")]
    )
    stdlib = Path(runtime_scheme["stdlib"])
    standard_paths = unique_paths(
        [
            stdlib,
            runtime_scheme.get("platstdlib", ""),
            stdlib / "lib-dynload",
            stdlib.parent / "DLLs",
        ]
    )
    return site_paths, standard_paths

SITE_PATHS, STANDARD_PATHS = explicit_paths()
RESOLVER_SUFFIXES = tuple(
    dict.fromkeys(
        importlib.machinery.SOURCE_SUFFIXES
        + importlib.machinery.BYTECODE_SUFFIXES
        + importlib.machinery.EXTENSION_SUFFIXES
    )
)
# These exact resolver stems can override or turn the trusted namespace package
# into a different top-level tools resolution. Do not scan unrelated site files.
PHYSICAL_TOOLS_RESOLVER_ARTIFACTS = []
for site_path in SITE_PATHS:
    for resolver_stem in ("tools", "tools/__init__", "tools/__main__"):
        for suffix in RESOLVER_SUFFIXES:
            entry = site_path / f"{resolver_stem}{suffix}"
            if entry.is_file():
                PHYSICAL_TOOLS_RESOLVER_ARTIFACTS.append(canonical(entry))
PHYSICAL_TOOLS_RESOLVER_ARTIFACTS = sorted(set(PHYSICAL_TOOLS_RESOLVER_ARTIFACTS))
PHYSICAL_TOOL_ENTRIES = []
for site_path in SITE_PATHS:
    entry = site_path / "tools" / "__main__.py"
    if entry.is_file():
        PHYSICAL_TOOL_ENTRIES.append(canonical(entry))
PHYSICAL_TOOL_ENTRIES = sorted(set(PHYSICAL_TOOL_ENTRIES))

records_by_path = {}
for dist in metadata.distributions(path=[str(path) for path in SITE_PATHS]):
    name = dist.metadata.get("Name")
    if not isinstance(name, str) or normalized(name) != PROJECT:
        continue
    path = metadata_path(dist)
    key = canonical(path)
    if key in records_by_path:
        continue
    direct_url = None
    editable = False
    raw_direct_url = dist.read_text("direct_url.json")
    if raw_direct_url:
        try:
            direct_url = json.loads(raw_direct_url)
        except json.JSONDecodeError:
            direct_url = {"invalid": True}
        editable = (
            isinstance(direct_url, dict)
            and isinstance(direct_url.get("dir_info"), dict)
            and direct_url["dir_info"].get("editable") is True
        )
    tool_entry_paths = []
    for file in dist.files or []:
        if str(file).replace("\\", "/") == "tools/__main__.py":
            tool_entry_paths.append(canonical(Path(dist.locate_file(file))))
    records_by_path[key] = {
        "name": name,
        "version": dist.version,
        "metadata_path": str(path),
        "canonical_metadata_path": key,
        "location": str(path.parent),
        "direct_url": direct_url,
        "editable": editable,
        "tool_entry_paths": sorted(set(tool_entry_paths)),
    }
records = sorted(records_by_path.values(), key=lambda item: item["canonical_metadata_path"])
record = records[0] if len(records) == 1 else None
metadata_version = record["version"] if record is not None else None

editable_target = None
editable_target_matches_source = False
owned_physical_entry = None
physical_tools_shadows = []
if record is not None:
    if record["editable"]:
        direct_url = record["direct_url"]
        editable_target = (
            file_url(str(direct_url.get("url", "")))
            if isinstance(direct_url, dict)
            else None
        )
        editable_target_matches_source = (
            editable_target is not None and canonical(editable_target) == canonical(SOURCE)
        )
        physical_tools_shadows = PHYSICAL_TOOLS_RESOLVER_ARTIFACTS
    else:
        owned = set(record["tool_entry_paths"])
        matching_entries = [path for path in PHYSICAL_TOOL_ENTRIES if path in owned]
        if len(PHYSICAL_TOOL_ENTRIES) == 1 and len(matching_entries) == 1:
            owned_physical_entry = matching_entries[0]

preloaded_tools = sorted(
    name for name in sys.modules if name == "tools" or name.startswith("tools.")
)
for name in preloaded_tools:
    sys.modules.pop(name, None)
allowed_meta_path = {
    importlib.machinery.BuiltinImporter,
    importlib.machinery.FrozenImporter,
    importlib.machinery.PathFinder,
}
sys.meta_path[:] = [finder for finder in sys.meta_path if finder in allowed_meta_path]
importlib.invalidate_caches()

expected_entry = None
if record is not None and record["editable"] and editable_target_matches_source:
    candidate = SOURCE / "tools" / "__main__.py"
    if candidate.is_file():
        expected_entry = canonical(candidate)
elif owned_physical_entry is not None:
    expected_entry = owned_physical_entry

tools_origin = None
tools_module_file = None
tools_package_paths = []
tools_error = None
bootstrap_version = None
cli_payload = None
cli_returncode = None
cli_stderr = ""
origin_matches_distribution = False
origin_matches_target = False
target_matches_authority = False
if expected_entry is not None and not physical_tools_shadows:
    strict_paths = []
    if record is not None and record["editable"]:
        strict_paths.append(SOURCE)
    strict_paths.extend(SITE_PATHS)
    strict_paths.extend(STANDARD_PATHS)
    sys.path[:] = [str(path) for path in unique_paths(strict_paths)]
    try:
        import tools
        import tools.__main__ as tools_main
        tools_module_file = getattr(tools, "__file__", None)
        tools_package_paths = [
            str(Path(item).resolve(strict=False)) for item in getattr(tools, "__path__", ())
        ]
        tools_origin = str(Path(tools_main.__file__).resolve(strict=False))
        loaded_entry = canonical(Path(tools_main.__file__))
        origin_matches_distribution = (
            loaded_entry == expected_entry
            and (
                (record is not None and record["editable"] and editable_target_matches_source)
                or (
                    record is not None
                    and not record["editable"]
                    and loaded_entry in record["tool_entry_paths"]
                )
            )
        )
        origin_matches_target = (
            record is not None
            and record["editable"]
            and loaded_entry == canonical(SOURCE / "tools" / "__main__.py")
        )
        target_matches_authority = (
            origin_matches_target
            if record is not None and record["editable"]
            else origin_matches_distribution
        )
        for candidate in (
            Path(loaded_entry).parent / "bootstrap-manifest.json",
            Path(loaded_entry).parent.parent / "bootstrap-manifest.json",
        ):
            try:
                payload = json.loads(candidate.read_text(encoding="utf-8"))
            except (OSError, ValueError, json.JSONDecodeError):
                continue
            value = payload.get("repo_version") if isinstance(payload, dict) else None
            if isinstance(value, str):
                bootstrap_version = value
                break
        original_argv = list(sys.argv)
        original_stdout = sys.stdout
        cli_stdout = io.StringIO()
        try:
            sys.argv = [str(loaded_entry), "--version"]
            sys.stdout = cli_stdout
            runner = getattr(tools_main, "main", None)
            if callable(runner):
                runner()
            else:
                runpy.run_path(str(Path(loaded_entry)), run_name="__main__")
            cli_returncode = 0
        except SystemExit as exc:
            cli_returncode = exc.code if isinstance(exc.code, int) else 1
        finally:
            sys.argv = original_argv
            sys.stdout = original_stdout
        try:
            cli_payload = json.loads(cli_stdout.getvalue())
        except json.JSONDecodeError:
            cli_stderr = "target tools.__main__ did not emit a JSON version payload"
    except Exception as exc:
        tools_error = str(exc)

cli_package_version = cli_payload.get("package_version") if isinstance(cli_payload, dict) else None
cli_manifest = cli_payload.get("bootstrap_manifest") if isinstance(cli_payload, dict) else None
cli_manifest_version = cli_manifest.get("repo_version") if isinstance(cli_manifest, dict) else None
cli_versions_equal = (
    isinstance(cli_package_version, str)
    and isinstance(cli_manifest_version, str)
    and cli_package_version == cli_manifest_version
    and cli_package_version == EXPECTED
)
orphan_shadow = bool(record is not None and record["editable"] and physical_tools_shadows)
success = bool(
    record is not None
    and metadata_version == EXPECTED
    and bootstrap_version == EXPECTED
    and cli_returncode == 0
    and cli_versions_equal
    and origin_matches_distribution
    and target_matches_authority
    and not orphan_shadow
)
print(json.dumps({
    "success": success,
    "verification_mode": VERIFICATION_MODE,
    "site_paths": [canonical(path) for path in SITE_PATHS],
    "canonical_count": len(records),
    "distributions": records,
    "metadata_version": metadata_version,
    "editable_target": str(editable_target) if editable_target is not None else None,
    "editable_target_matches_source": editable_target_matches_source,
    "owned_physical_entry": owned_physical_entry,
    "physical_tools_shadows": physical_tools_shadows,
    "preloaded_tools_removed": preloaded_tools,
    "tools_origin": tools_origin,
    "tools_module_file": tools_module_file,
    "tools_package_paths": tools_package_paths,
    "tools_error": tools_error,
    "loaded_bootstrap_version": bootstrap_version,
    "module_origin_matches_distribution": origin_matches_distribution,
    "module_origin_matches_target": origin_matches_target,
    "target_matches_authority": target_matches_authority,
    "cli_returncode": cli_returncode,
    "cli_stderr": cli_stderr,
    "cli_version_payload": cli_payload,
    "cli_versions_equal": cli_versions_equal,
    "orphan_shadow": orphan_shadow,
}))
"""


def _neutral_probe(
    authority: dict[str, Any],
    *,
    working_dir: Path,
    environment: dict[str, str],
) -> dict[str, Any]:
    command = [
        sys.executable,
        "-I",
        "-S",
        "-c",
        _NEUTRAL_PROBE,
        str(authority["source_root"]),
        str(authority["source_version"]),
    ]
    result = _command_payload(command, cwd=working_dir, environment=environment)
    if result["returncode"] != 0:
        return {
            "success": False,
            "runner": result,
            "error": "neutral probe process failed",
        }
    try:
        payload = json.loads(str(result["stdout"]))
    except json.JSONDecodeError as exc:
        return {
            "success": False,
            "runner": result,
            "error": f"neutral probe did not emit JSON: {exc}",
        }
    if not isinstance(payload, dict):
        return {"success": False, "runner": result, "error": "neutral probe JSON was not an object"}
    return payload


def _validate_wheel_rollback(
    inventory: dict[str, Any],
    probe: dict[str, Any],
    *,
    expected_version: str,
) -> dict[str, Any]:
    """Prove the fallback wheel owns one coherent, non-editable install."""
    distributions = inventory.get("distributions")
    record = (
        distributions[0] if isinstance(distributions, list) and len(distributions) == 1 else None
    )
    inventory_version = record.get("version") if isinstance(record, dict) else None
    inventory_editable = record.get("editable") if isinstance(record, dict) else None
    checks = {
        "single_canonical_distribution": (
            inventory.get("state") == "single"
            and inventory.get("canonical_count") == 1
            and isinstance(record, dict)
        ),
        "expected_metadata_version": inventory_version == expected_version,
        "non_editable_wheel": inventory_editable is False,
        "probe_metadata_version": probe.get("metadata_version") == expected_version,
        "loaded_bootstrap_version": probe.get("loaded_bootstrap_version") == expected_version,
        "cli_version_contract": probe.get("cli_returncode") == 0
        and probe.get("cli_versions_equal") is True,
        "module_origin_matches_distribution": probe.get("module_origin_matches_distribution")
        is True,
    }
    return {
        "success": all(checks.values()),
        "expected_version": expected_version,
        "inventory_version": inventory_version,
        "inventory_editable": inventory_editable,
        "checks": checks,
    }


def _result(
    *,
    success: bool,
    data: dict[str, Any],
    error_code: str | None = None,
    error_message: str | None = None,
    error_details: dict[str, Any] | None = None,
    recovery_strategy: str = RECOVERY_STRATEGY_ASK_USER,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "success": success,
        "schema_version": INSTALL_INTEGRITY_SCHEMA_VERSION,
        "command": "install-integrity",
        "mode": RECOVERY_COMMAND,
        "data": data,
    }
    if error_code and error_message:
        payload["error"] = {
            "code": error_code,
            "message": error_message,
            "details": error_details or {},
            "recovery_strategy": recovery_strategy,
        }
    return payload


def recover_install(source_root: str) -> dict[str, Any]:
    """Converge a mixed Life Index install without direct site-packages mutation."""
    authority, authority_error = _authority(source_root)
    if authority is None:
        authority_failure = authority_error or {
            "reason": "SOURCE_AUTHORITY_UNPROVEN",
            "message": "source authority could not be proven",
        }
        return _result(
            success=False,
            data={
                "source_root": source_root,
                "authority_failure": authority_failure,
                "pip_operations": [],
            },
            error_code=AUTHORITY_ERROR,
            error_message=authority_failure["message"],
            error_details={"reason": authority_failure["reason"]},
        )

    canonical_distributions = _canonical_distribution_records()
    initial_inventory = _life_index_inventory(canonical_distributions)
    data: dict[str, Any] = {
        "authority": authority,
        "initial_inventory": initial_inventory,
        "pip_operations": [],
    }
    ownership_conflicts = _life_index_ownership_conflicts(canonical_distributions)
    if ownership_conflicts:
        data["ownership_conflicts"] = ownership_conflicts
        data["terminal_inventory"] = initial_inventory
        return _result(
            success=False,
            data=data,
            error_code=OWNERSHIP_CONFLICT_ERROR,
            error_message=(
                "Life Index RECORD ownership overlaps an unrelated distribution; "
                "no package operation ran."
            ),
        )

    environment = _clean_environment()
    with tempfile.TemporaryDirectory(prefix="life-index-install-integrity-") as temporary:
        working_dir = Path(temporary)
        initial_probe = _neutral_probe(
            authority,
            working_dir=working_dir,
            environment=environment,
        )
        data["initial_neutral_probe"] = initial_probe
        if initial_inventory["state"] == "single" and initial_probe.get("success"):
            data["outcome"] = "verified_noop"
            data["terminal_inventory"] = initial_inventory
            data["neutral_probe"] = initial_probe
            return _result(success=True, data=data)
        if initial_inventory["state"] == "single" and initial_probe.get("orphan_shadow"):
            data["terminal_inventory"] = initial_inventory
            data["neutral_probe"] = initial_probe
            return _result(
                success=False,
                data=data,
                error_code=ORPHAN_SHADOW_ERROR,
                error_message=(
                    "neutral verification found an untracked tools shadow; no pip mutation " "ran."
                ),
            )

        staged_wheel, build_data, build_error = _build_staged_wheel(
            authority,
            working_dir=working_dir,
            environment=environment,
        )
        data["build_preflight"] = build_data
        build_operation = build_data.get("build")
        if isinstance(build_operation, dict):
            data["pip_operations"].append(build_operation)
        if staged_wheel is None:
            data["terminal_inventory"] = inventory_life_index_distributions()
            return _result(
                success=False,
                data=data,
                error_code=BUILD_PREFLIGHT_ERROR,
                error_message=build_error or "wheel build preflight failed",
                recovery_strategy=RECOVERY_STRATEGY_RETRY,
            )

        initial_count = int(initial_inventory["canonical_count"])
        attempts = 0
        while True:
            before = inventory_life_index_distributions()
            before_count = int(before["canonical_count"])
            if before_count == 0:
                break
            if attempts >= initial_count:
                data["terminal_inventory"] = before
                return _result(
                    success=False,
                    data=data,
                    error_code=UNINSTALL_STALLED_ERROR,
                    error_message=(
                        "pip uninstall did not converge within the initial canonical inventory "
                        "bound."
                    ),
                )
            uninstall = _command_payload(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "--isolated",
                    "uninstall",
                    "--yes",
                    PROJECT_NAME,
                ],
                cwd=working_dir,
                environment=environment,
            )
            data["pip_operations"].append(uninstall)
            attempts += 1
            if uninstall["returncode"] != 0:
                data["terminal_inventory"] = inventory_life_index_distributions()
                return _result(
                    success=False,
                    data=data,
                    error_code=UNINSTALL_ERROR,
                    error_message="pip uninstall failed before Life Index distributions converged.",
                )
            after = inventory_life_index_distributions()
            if int(after["canonical_count"]) >= before_count:
                data["terminal_inventory"] = after
                return _result(
                    success=False,
                    data=data,
                    error_code=UNINSTALL_STALLED_ERROR,
                    error_message=(
                        "pip uninstall did not strictly decrease canonical Life Index "
                        "distributions."
                    ),
                )

        install = _command_payload(
            [
                sys.executable,
                "-m",
                "pip",
                "--isolated",
                "install",
                "--no-index",
                "--no-deps",
                "--no-build-isolation",
                "-e",
                str(authority["source_root"]),
            ],
            cwd=working_dir,
            environment=environment,
        )
        data["pip_operations"].append(install)
        if install["returncode"] != 0:
            fallback = _command_payload(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "--isolated",
                    "install",
                    "--no-index",
                    "--no-deps",
                    str(staged_wheel),
                ],
                cwd=working_dir,
                environment=environment,
            )
            data["pip_operations"].append(fallback)
            data["terminal_inventory"] = inventory_life_index_distributions()
            data["neutral_probe"] = _neutral_probe(
                authority,
                working_dir=working_dir,
                environment=environment,
            )
            validation = _validate_wheel_rollback(
                data["terminal_inventory"],
                data["neutral_probe"],
                expected_version=str(authority["source_version"]),
            )
            if fallback["returncode"] != 0:
                rollback_status = "failed"
            elif validation["success"]:
                rollback_status = "validated"
            else:
                rollback_status = "invalid"
            data["rollback"] = {
                "status": rollback_status,
                "wheel": str(staged_wheel),
                "operation": fallback,
                "validation": validation,
            }
            return _result(
                success=False,
                data=data,
                error_code=TARGET_INSTALL_ERROR,
                error_message=(
                    "editable target install failed after pip-only convergence; "
                    "validated wheel rollback was attempted."
                ),
            )
        data["terminal_inventory"] = inventory_life_index_distributions()
        data["neutral_probe"] = _neutral_probe(
            authority,
            working_dir=working_dir,
            environment=environment,
        )
        if not data["neutral_probe"].get("success"):
            error_code = (
                ORPHAN_SHADOW_ERROR if data["neutral_probe"].get("orphan_shadow") else PROBE_ERROR
            )
            return _result(
                success=False,
                data=data,
                error_code=error_code,
                error_message="neutral verification did not prove the repaired target.",
            )
        return _result(success=True, data=data)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="install_integrity.py")
    parser.add_argument("command", choices=[RECOVERY_COMMAND])
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--json", action="store_true")
    arguments = parser.parse_args(sys.argv[1:] if argv is None else argv)
    payload = recover_install(arguments.source_root)
    print(json.dumps(payload, ensure_ascii=True, indent=2))
    return 0 if payload.get("success") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
