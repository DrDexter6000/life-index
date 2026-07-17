"""Hermetic regression coverage for Life Index mixed-install recovery."""

from __future__ import annotations

import importlib.machinery
import json
import os
import py_compile
import subprocess
import sys
import tomllib
import zipfile
from importlib.metadata import distribution as metadata_distribution
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALL_INTEGRITY_PATH = REPO_ROOT / "tools" / "upgrade" / "install_integrity.py"


def _venv_python(venv: Path) -> Path:
    if os.name == "nt":
        return venv / "Scripts" / "python.exe"
    return venv / "bin" / "python"


def _clean_pip_env() -> dict[str, str]:
    env = dict(os.environ)
    env["PIP_NO_INDEX"] = "1"
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    return env


def _run(
    command: list[str],
    *,
    cwd: Path | None = None,
    environment_updates: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    environment = _clean_pip_env()
    if environment_updates:
        environment.update(environment_updates)
    result = subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        capture_output=True,
        text=True,
        errors="replace",
        timeout=120,
        check=False,
    )
    assert (
        result.returncode == 0
    ), f"command failed: {command!r}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    return result


def _repo_version() -> str:
    payload = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return str(payload["project"]["version"])


def _write_synthetic_wheel(
    wheel: Path,
    *,
    version: str,
    manifest_version: str | None = None,
) -> None:
    """Write a deterministic, locally installable stale Life Index wheel."""
    manifest_version = manifest_version or version
    dist_info = f"life_index-{version}.dist-info"
    members = {
        "tools/__init__.py": f"__version__ = {version!r}\n",
        "tools/__main__.py": (
            "import json\n"
            "import sys\n"
            "if '--version' in sys.argv or 'version' in sys.argv:\n"
            f"    print(json.dumps({{'package_version': {version!r}, "
            f"'bootstrap_manifest': {{'repo_version': {version!r}}}}}))\n"
        ),
        "bootstrap-manifest.json": json.dumps({"repo_version": manifest_version}),
        "tools/bootstrap-manifest.json": json.dumps({"repo_version": manifest_version}),
        f"{dist_info}/METADATA": (
            "Metadata-Version: 2.1\n" "Name: life-index\n" f"Version: {version}\n"
        ),
        f"{dist_info}/WHEEL": (
            "Wheel-Version: 1.0\n"
            "Generator: life-index-test\n"
            "Root-Is-Purelib: true\n"
            "Tag: py3-none-any\n"
        ),
    }
    members[f"{dist_info}/RECORD"] = "".join(f"{name},,\n" for name in sorted(members))

    with zipfile.ZipFile(wheel, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(members):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.external_attr = 0o100644 << 16
            archive.writestr(info, members[name])


def _write_unrelated_wheel(wheel: Path) -> None:
    dist_info = "unrelated_package-1.0.0.dist-info"
    members = {
        "unrelated_package/__init__.py": "SENTINEL = 'unrelated package remains'\n",
        f"{dist_info}/METADATA": (
            "Metadata-Version: 2.1\nName: unrelated-package\nVersion: 1.0.0\n"
        ),
        f"{dist_info}/WHEEL": (
            "Wheel-Version: 1.0\nGenerator: life-index-test\n"
            "Root-Is-Purelib: true\nTag: py3-none-any\n"
        ),
    }
    members[f"{dist_info}/RECORD"] = "".join(f"{name},,\n" for name in sorted(members))
    with zipfile.ZipFile(wheel, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(members):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.external_attr = 0o100644 << 16
            archive.writestr(info, members[name])


def _write_overlapping_unrelated_wheel(wheel: Path) -> None:
    """Create an unrelated wheel whose RECORD owns Life Index's tools init path."""
    dist_info = "unrelated_overlap-1.0.0.dist-info"
    members = {
        "tools/__init__.py": "UNRELATED_OWNER_SENTINEL = True\n",
        f"{dist_info}/METADATA": (
            "Metadata-Version: 2.1\nName: unrelated-overlap\nVersion: 1.0.0\n"
        ),
        f"{dist_info}/WHEEL": (
            "Wheel-Version: 1.0\nGenerator: life-index-test\n"
            "Root-Is-Purelib: true\nTag: py3-none-any\n"
        ),
    }
    members[f"{dist_info}/RECORD"] = "".join(f"{name},,\n" for name in sorted(members))
    with zipfile.ZipFile(wheel, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(members):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.external_attr = 0o100644 << 16
            archive.writestr(info, members[name])


def _write_backend_support_wheel(wheel: Path, *, distribution_name: str) -> None:
    """Package an already installed build backend into a local deterministic wheel."""
    installed = metadata_distribution(distribution_name)
    metadata_path = Path(getattr(installed, "_path"))
    members: dict[str, bytes] = {}
    for file in installed.files or []:
        relative = Path(str(file))
        if relative.name == "RECORD" or ".." in relative.parts:
            continue
        source = Path(installed.locate_file(file))
        if source.is_file():
            members[relative.as_posix()] = source.read_bytes()

    record_name = f"{metadata_path.name}/RECORD"
    members[record_name] = "".join(f"{name},,\n" for name in sorted(members)).encode("utf-8")
    with zipfile.ZipFile(wheel, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(members):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.external_attr = 0o100644 << 16
            archive.writestr(info, members[name])


def _install_local_build_backend(python: Path, tmp_path: Path) -> None:
    for distribution_name in ("setuptools", "wheel", "PyYAML"):
        installed = metadata_distribution(distribution_name)
        filename_name = distribution_name.lower().replace("-", "_")
        wheel = tmp_path / f"{filename_name}-{installed.version}-py3-none-any.whl"
        _write_backend_support_wheel(wheel, distribution_name=distribution_name)
        _run(
            [
                str(python),
                "-m",
                "pip",
                "install",
                "--no-index",
                "--no-deps",
                str(wheel),
            ]
        )


def _mixed_install_fixture(tmp_path: Path) -> tuple[Path, Path]:
    venv = tmp_path / "mixed install venv"
    _run([sys.executable, "-m", "venv", str(venv)])
    python = _venv_python(venv)
    _install_local_build_backend(python, tmp_path)
    wheel = tmp_path / "life_index-0.0.1-py3-none-any.whl"
    _write_synthetic_wheel(wheel, version="0.0.1")
    _run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--no-index",
            "--no-deps",
            str(wheel),
        ]
    )
    _run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--no-index",
            "--no-build-isolation",
            "--no-deps",
            "--ignore-installed",
            "-e",
            str(REPO_ROOT),
        ]
    )
    return python, wheel


def _single_editable_fixture(tmp_path: Path) -> Path:
    """Install one authoritative editable target for physical-shadow regression tests."""
    venv = tmp_path / "single editable venv"
    _run([sys.executable, "-m", "venv", str(venv)])
    python = _venv_python(venv)
    _install_local_build_backend(python, tmp_path)
    _run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--no-index",
            "--no-build-isolation",
            "--no-deps",
            "-e",
            str(REPO_ROOT),
        ]
    )
    return python


def _clean_wheel_fixture(tmp_path: Path) -> tuple[Path, Path]:
    """Build and install one real wheel without leaking outer site-packages."""
    venv = tmp_path / "clean wheel venv"
    _run([sys.executable, "-m", "venv", str(venv)])
    python = _venv_python(venv)
    _install_local_build_backend(python, tmp_path)
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    _run(
        [
            str(python),
            "-m",
            "pip",
            "wheel",
            "--no-index",
            "--no-build-isolation",
            "--no-deps",
            "--wheel-dir",
            str(wheelhouse),
            str(REPO_ROOT),
        ],
        cwd=tmp_path,
    )
    wheels = sorted(wheelhouse.glob("life_index-*.whl"))
    assert len(wheels) == 1
    wheel = wheels[0]
    _run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--no-index",
            "--no-deps",
            str(wheel),
        ]
    )
    return python, wheel


def _stale_wheel_fixture(tmp_path: Path) -> tuple[Path, Path]:
    """Install one old wheel so recovery must prove it is not a no-op."""
    venv = tmp_path / "stale wheel venv"
    _run([sys.executable, "-m", "venv", str(venv)])
    python = _venv_python(venv)
    _install_local_build_backend(python, tmp_path)
    wheel = tmp_path / "life_index-0.0.1-py3-none-any.whl"
    _write_synthetic_wheel(wheel, version="0.0.1")
    _run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--no-index",
            "--no-deps",
            str(wheel),
        ]
    )
    return python, wheel


def _run_inventory(python: Path) -> dict[str, Any]:
    code = (
        "import json, runpy, sys; "
        "module = runpy.run_path(sys.argv[1]); "
        "print(json.dumps(module['inventory_life_index_distributions']()))"
    )
    result = _run([str(python), "-I", "-c", code, str(INSTALL_INTEGRITY_PATH)])
    return json.loads(result.stdout)


def _neutral_import_probe(python: Path, cwd: Path) -> dict[str, Any]:
    code = (
        "import json, pathlib, tools; "
        "print(json.dumps({'tools_origin': str(pathlib.Path(tools.__file__).resolve())}))"
    )
    result = _run([str(python), "-I", "-c", code], cwd=cwd)
    return json.loads(result.stdout)


def _run_recovery(
    python: Path,
    *,
    data_dir: Path,
    source_root: Path = REPO_ROOT,
    environment_updates: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = _clean_pip_env()
    env["LIFE_INDEX_DATA_DIR"] = str(data_dir)
    if environment_updates:
        env.update(environment_updates)
    return subprocess.run(
        [
            str(python),
            "-I",
            str(INSTALL_INTEGRITY_PATH),
            "recover",
            "--source-root",
            str(source_root),
            "--json",
        ],
        cwd=data_dir.parent,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )


def _venv_site_packages(python: Path) -> Path:
    result = _run(
        [
            str(python),
            "-I",
            "-c",
            "import json, sysconfig; print(json.dumps(sysconfig.get_paths()))",
        ]
    )
    paths = json.loads(result.stdout)
    purelib = Path(paths["purelib"])
    assert purelib.is_dir()
    return purelib


def _write_malicious_editable_finder_setup(
    site_packages: Path, *, source_root: Path, sentinel: Path
) -> Path:
    """Install metadata whose .pth finder spoofs the trusted tools entry path."""
    version = _repo_version()
    dist_info = site_packages / f"life_index-{version}.dist-info"
    dist_info.mkdir()
    attacker = site_packages / "attacker_editable_finder.py"
    finder_source = f"""
import importlib.abc
import importlib.util
import json
import sys
from pathlib import Path

Path({str(sentinel)!r}).write_text("finder executed\\n", encoding="utf-8")
TRUSTED_ENTRY = {str(source_root / "tools" / "__main__.py")!r}
VERSION = {version!r}

class Loader(importlib.abc.InspectLoader):
    def __init__(self, fullname):
        self.fullname = fullname

    def is_package(self, fullname):
        return fullname == "tools"

    def get_source(self, fullname):
        if fullname == "tools":
            return "__file__ = " + repr(TRUSTED_ENTRY) + "\\n__path__ = []\\n"
        return (
            "__file__ = " + repr(TRUSTED_ENTRY) + "\\n"
            "import json, sys\\n"
            "if __name__ == '__main__' and '--version' in sys.argv:\\n"
            "    print(json.dumps({{'package_version': " + repr(VERSION) + ", "
            "'bootstrap_manifest': {{'repo_version': " + repr(VERSION) + "}}}}))\\n"
        )

    def get_code(self, fullname):
        return compile(self.get_source(fullname), TRUSTED_ENTRY, "exec")

class Finder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname in {{"tools", "tools.__main__"}}:
            return importlib.util.spec_from_loader(
                fullname, Loader(fullname), is_package=(fullname == "tools")
            )
        return None

sys.meta_path.insert(0, Finder())
"""
    attacker.write_text(finder_source.lstrip(), encoding="utf-8")
    pth_name = "__editable__.life_index_malicious.pth"
    (site_packages / pth_name).write_text("import attacker_editable_finder\n", encoding="utf-8")
    (dist_info / "METADATA").write_text(
        f"Metadata-Version: 2.1\nName: life-index\nVersion: {version}\n", encoding="utf-8"
    )
    (dist_info / "direct_url.json").write_text(
        json.dumps({"url": source_root.as_uri(), "dir_info": {"editable": True}}),
        encoding="utf-8",
    )
    record_members = [
        pth_name,
        attacker.name,
        f"{dist_info.name}/METADATA",
        f"{dist_info.name}/direct_url.json",
    ]
    (dist_info / "RECORD").write_text(
        "".join(f"{member},,\n" for member in sorted(record_members)), encoding="utf-8"
    )
    shadow = site_packages / "tools" / "__main__.py"
    shadow.parent.mkdir()
    shadow.parent.joinpath("__init__.py").write_text("SHADOW = True\n", encoding="utf-8")
    shadow.write_text("raise RuntimeError('physical shadow must not execute')\n", encoding="utf-8")
    return shadow


def _run_no_site_neutral_probe(python: Path, *, source_root: Path) -> dict[str, Any]:
    authority = {
        "source_root": str(source_root),
        "source_version": _repo_version(),
        "manifest_version": _repo_version(),
        "interpreter": str(python),
    }
    code = """
import json
import os
import runpy
import sys
import tempfile
from pathlib import Path

module = runpy.run_path(sys.argv[1])
authority = json.loads(sys.argv[2])
with tempfile.TemporaryDirectory() as temporary:
    payload = module["_neutral_probe"](
        authority,
        working_dir=Path(temporary),
        environment=dict(os.environ),
    )
print(json.dumps(payload))
"""
    result = _run(
        [
            str(python),
            "-I",
            "-S",
            "-c",
            code,
            str(INSTALL_INTEGRITY_PATH),
            json.dumps(authority),
        ]
    )
    return json.loads(result.stdout)


def _write_editable_failure_source(source_root: Path) -> None:
    source_root.mkdir()
    version = _repo_version()
    (source_root / "pyproject.toml").write_text(
        "\n".join(
            [
                "[build-system]",
                "requires = []",
                'build-backend = "backend"',
                'backend-path = ["."]',
                "",
                "[project]",
                'name = "life-index"',
                f'version = "{version}"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    (source_root / "bootstrap-manifest.json").write_text(
        json.dumps({"repo_version": version}), encoding="utf-8"
    )
    backend = """
from pathlib import Path
import json
import zipfile

VERSION = __VERSION__

def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    filename = f"life_index-{VERSION}-py3-none-any.whl"
    destination = Path(wheel_directory) / filename
    dist_info = f"life_index-{VERSION}.dist-info"
    members = {
        "tools/__init__.py": "",
        "tools/__main__.py": (
            "import json\\n"
            "import sys\\n"
            "if '--version' in sys.argv:\\n"
            "    print(json.dumps({'package_version': %r, "
            "'bootstrap_manifest': {'repo_version': %r}}))\\n" % (VERSION, VERSION)
        ),
        "bootstrap-manifest.json": json.dumps({"repo_version": VERSION}),
        "tools/bootstrap-manifest.json": json.dumps({"repo_version": VERSION}),
        f"{dist_info}/METADATA": (
            f"Metadata-Version: 2.1\\nName: life-index\\nVersion: {VERSION}\\n"
        ),
        f"{dist_info}/WHEEL": "Wheel-Version: 1.0\\nRoot-Is-Purelib: true\\nTag: py3-none-any\\n",
    }
    members[f"{dist_info}/RECORD"] = "".join(f"{name},,\\n" for name in sorted(members))
    with zipfile.ZipFile(destination, "w") as archive:
        for name, content in sorted(members.items()):
            archive.writestr(name, content)
    return filename

def build_editable(wheel_directory, config_settings=None, metadata_directory=None):
    raise RuntimeError("editable installation intentionally fails")
"""
    (source_root / "backend.py").write_text(
        backend.replace("__VERSION__", repr(version)).lstrip(), encoding="utf-8"
    )


def _write_build_preflight_failure_source(source_root: Path) -> None:
    """Write authority-valid source whose build backend cannot be imported."""
    source_root.mkdir()
    version = _repo_version()
    (source_root / "pyproject.toml").write_text(
        "\n".join(
            [
                "[build-system]",
                "requires = []",
                'build-backend = "missing_backend"',
                "",
                "[project]",
                'name = "life-index"',
                f'version = "{version}"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    (source_root / "bootstrap-manifest.json").write_text(
        json.dumps({"repo_version": version}), encoding="utf-8"
    )


def _write_injected_tools(root: Path, *, version: str) -> None:
    tools = root / "tools"
    tools.mkdir(parents=True)
    (tools / "__init__.py").write_text("INJECTED = True\n", encoding="utf-8")
    (tools / "__main__.py").write_text(
        "import json\n"
        "if __name__ == '__main__':\n"
        f"    print(json.dumps({{'package_version': {version!r}, "
        f"'bootstrap_manifest': {{'repo_version': {version!r}}}}}))\n",
        encoding="utf-8",
    )
    (tools / "bootstrap-manifest.json").write_text(
        json.dumps({"repo_version": version}), encoding="utf-8"
    )


def _fault_inventory(site_packages: Path, *, state: str) -> dict[str, Any]:
    """Return one deterministic install inventory for fail-closed branch tests."""
    counts = {"absent": 0, "single": 1, "conflict": 2}
    count = counts[state]
    distributions = [
        {
            "name": "life-index",
            "normalized_name": "life-index",
            "version": _repo_version(),
            "metadata_path": str(site_packages / f"life_index-{index}.dist-info"),
            "canonical_metadata_path": str(
                (site_packages / f"life_index-{index}.dist-info").resolve(strict=False)
            ),
            "location": str(site_packages),
            "direct_url": None,
            "editable": False,
        }
        for index in range(count)
    ]
    return {
        "project": "life-index",
        "state": state,
        "canonical_count": count,
        "distributions": distributions,
    }


def _prepare_fault_injected_recovery(
    monkeypatch: Any,
    tmp_path: Path,
    *,
    inventory_sequence: list[dict[str, Any]],
    command_returncodes: list[int],
) -> tuple[Any, list[list[str]]]:
    """Inject deterministic pip/inventory outcomes without touching site-packages."""
    from tools.upgrade import install_integrity

    authority = {
        "source_root": str(REPO_ROOT),
        "source_version": _repo_version(),
        "manifest_version": _repo_version(),
        "interpreter": str(sys.executable),
    }
    commands: list[list[str]] = []
    staged_wheel = tmp_path / "life_index-staged.whl"
    build_operation = {
        "command": [str(sys.executable), "-m", "pip", "--isolated", "wheel"],
        "returncode": 0,
        "stdout": "",
        "stderr": "",
    }

    def fake_inventory() -> dict[str, Any]:
        if not inventory_sequence:
            raise AssertionError("recovery requested more inventories than this branch permits")
        return inventory_sequence.pop(0)

    if not inventory_sequence:
        raise AssertionError("fault-injected recovery requires an initial inventory")
    initial_inventory = inventory_sequence.pop(0)
    initial_records = [
        {**record, "owned_paths": []} for record in initial_inventory["distributions"]
    ]

    def fake_command(
        command: list[str],
        *,
        cwd: Path,
        environment: dict[str, str],
    ) -> dict[str, Any]:
        del cwd, environment
        if not command_returncodes:
            raise AssertionError("recovery issued more pip commands than this branch permits")
        commands.append(command)
        return {
            "command": command,
            "returncode": command_returncodes.pop(0),
            "stdout": "",
            "stderr": "simulated pip result",
        }

    monkeypatch.setattr(install_integrity, "_authority", lambda _source_root: (authority, None))
    monkeypatch.setattr(
        install_integrity, "_canonical_distribution_records", lambda: initial_records
    )
    monkeypatch.setattr(install_integrity, "inventory_life_index_distributions", fake_inventory)
    monkeypatch.setattr(
        install_integrity,
        "_build_staged_wheel",
        lambda *_args, **_kwargs: (staged_wheel, {"build": build_operation}, None),
    )
    monkeypatch.setattr(install_integrity, "_command_payload", fake_command)
    monkeypatch.setattr(
        install_integrity,
        "_neutral_probe",
        lambda *_args, **_kwargs: {"success": False, "orphan_shadow": False},
    )
    return install_integrity, commands


def test_clean_wheel_has_one_truthful_distribution_and_core_read_only_cli_surface(
    tmp_path: Path,
) -> None:
    """A clean wheel must retain version, health, and sync-skill read-only behavior."""
    python, _wheel = _clean_wheel_fixture(tmp_path)
    data_dir = tmp_path / "isolated data"
    data_dir.mkdir()
    host_home = tmp_path / "empty host home"
    host_home.mkdir()
    environment = {"LIFE_INDEX_DATA_DIR": str(data_dir)}

    inventory = _run_inventory(python)
    version = _run(
        [str(python), "-I", "-m", "tools", "--version"],
        cwd=tmp_path,
        environment_updates=environment,
    )
    health = _run(
        [str(python), "-I", "-m", "tools", "health", "--json"],
        cwd=tmp_path,
        environment_updates=environment,
    )
    sync_skill = _run(
        [
            str(python),
            "-I",
            "-m",
            "tools",
            "sync-skill",
            "--list",
            "--host-home",
            str(host_home),
            "--json",
        ],
        cwd=tmp_path,
        environment_updates=environment,
    )

    assert inventory["state"] == "single"
    assert inventory["canonical_count"] == 1
    assert inventory["distributions"][0]["version"] == _repo_version()
    assert json.loads(version.stdout)["package_version"] == _repo_version()
    assert json.loads(health.stdout)["schema_version"] == "m16.health.v0"
    assert json.loads(sync_skill.stdout)["command"] == "sync-skill"


def test_matching_clean_wheel_recovery_is_a_verified_noop(tmp_path: Path) -> None:
    """One truthful packaged wheel is already the target and must not churn pip."""
    python, _wheel = _clean_wheel_fixture(tmp_path)
    data_dir = tmp_path / "synthetic data"
    data_dir.mkdir()

    result = _run_recovery(python, data_dir=data_dir)

    assert result.returncode == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "m37.install_integrity.v0"
    assert payload["success"] is True
    assert payload["data"]["outcome"] == "verified_noop"
    assert payload["data"]["initial_inventory"]["state"] == "single"
    assert payload["data"]["terminal_inventory"]["state"] == "single"
    assert payload["data"]["pip_operations"] == []
    assert payload["data"]["neutral_probe"]["success"] is True


def test_old_version_single_wheel_still_requires_recovery(tmp_path: Path) -> None:
    """One canonical distribution is insufficient when it does not match authority."""
    python, _wheel = _stale_wheel_fixture(tmp_path)
    data_dir = tmp_path / "synthetic data"
    data_dir.mkdir()

    result = _run_recovery(python, data_dir=data_dir)

    assert result.returncode == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["success"] is True
    assert payload["data"]["initial_inventory"]["state"] == "single"
    assert payload["data"]["initial_inventory"]["distributions"][0]["version"] == "0.0.1"
    assert payload["data"].get("outcome") != "verified_noop"
    assert any(
        "uninstall" in operation["command"] for operation in payload["data"]["pip_operations"]
    )
    assert payload["data"]["terminal_inventory"]["distributions"][0]["version"] == _repo_version()


def test_recovery_refuses_cross_distribution_file_ownership_before_pip(tmp_path: Path) -> None:
    """A shared RECORD path is evidence, not permission to uninstall either owner."""
    python, _wheel = _stale_wheel_fixture(tmp_path)
    overlap_wheel = tmp_path / "unrelated_overlap-1.0.0-py3-none-any.whl"
    _write_overlapping_unrelated_wheel(overlap_wheel)
    _run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--no-index",
            "--no-deps",
            str(overlap_wheel),
        ]
    )
    inventory = _run_inventory(python)
    owned_path = Path(inventory["distributions"][0]["location"]) / "tools" / "__init__.py"
    before_bytes = owned_path.read_bytes()
    data_dir = tmp_path / "synthetic data"
    data_dir.mkdir()

    result = _run_recovery(python, data_dir=data_dir)

    assert result.returncode == 1, result.stdout
    payload = json.loads(result.stdout)
    assert payload["success"] is False
    assert payload["error"]["code"] == "INSTALL_RECOVERY_OWNERSHIP_CONFLICT"
    assert payload["error"]["recovery_strategy"] == "ask_user"
    assert payload["data"]["pip_operations"] == []
    assert payload["data"]["terminal_inventory"] == inventory
    overlaps = payload["data"]["ownership_conflicts"]
    overlap = next(
        item
        for item in overlaps
        if item["path"] == os.path.normcase(str(owned_path.resolve(strict=False)))
    )
    assert [owner["name"] for owner in overlap["life_index_owners"]] == ["life-index"]
    assert [owner["name"] for owner in overlap["unrelated_owners"]] == ["unrelated-overlap"]
    assert owned_path.read_bytes() == before_bytes


def test_neutral_probe_ignores_malicious_editable_pth_finder_and_reports_shadow(
    tmp_path: Path,
) -> None:
    """The no-site probe must not let a .pth finder hide a physical tools shadow."""
    venv = tmp_path / "malicious finder venv"
    _run([sys.executable, "-m", "venv", str(venv)])
    python = _venv_python(venv)
    _install_local_build_backend(python, tmp_path)
    sentinel = tmp_path / "finder-executed.txt"
    shadow = _write_malicious_editable_finder_setup(
        _venv_site_packages(python), source_root=REPO_ROOT, sentinel=sentinel
    )

    payload = _run_no_site_neutral_probe(python, source_root=REPO_ROOT)

    assert not sentinel.exists(), "-I -S probe must not process the malicious .pth finder"
    assert payload["verification_mode"] == "isolated_no_site_explicit_target"
    assert payload["success"] is False
    assert payload["orphan_shadow"] is True
    assert os.path.normcase(str(shadow.resolve(strict=False))) in payload["physical_tools_shadows"]

    _run([str(python), "-I", "-c", "print('normal site startup')"])
    assert sentinel.read_text(encoding="utf-8") == "finder executed\n"


def test_mixed_install_inventory_detects_conflict_and_neutral_import_is_stale(
    tmp_path: Path,
) -> None:
    """A stale wheel must not hide behind an editable distribution's metadata."""
    assert INSTALL_INTEGRITY_PATH.is_file()
    python, _wheel = _mixed_install_fixture(tmp_path)

    inventory = _run_inventory(python)
    assert inventory["state"] == "conflict"
    assert inventory["canonical_count"] == 2
    assert {item["version"] for item in inventory["distributions"]} == {"0.0.1", _repo_version()}
    assert {item["editable"] for item in inventory["distributions"]} == {False, True}
    assert all(item["direct_url"] is not None for item in inventory["distributions"])

    probe = _neutral_import_probe(python, tmp_path)
    assert "site-packages" in probe["tools_origin"].replace("\\", "/").lower()


def test_inventory_ignores_unrelated_and_dedupes_the_same_dist_info(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """Duplicate ``sys.path`` exposure is one install, unlike a true conflict."""
    from tools.upgrade import install_integrity

    class FakeDistribution:
        def __init__(self, name: str, version: str, root: Path, dist_info: str) -> None:
            self.metadata = {"Name": name}
            self.version = version
            self.files = [Path(dist_info) / "METADATA"]
            self._root = root

        def locate_file(self, file: Any) -> Path:
            return self._root / Path(str(file))

        def read_text(self, filename: str) -> str | None:
            return None

    site_packages = tmp_path / "site-packages"
    life_info = "life_index-1.5.1.dist-info"
    life = FakeDistribution("Life.Index", "1.5.1", site_packages, life_info)
    duplicate_exposure = FakeDistribution("life-index", "1.5.1", site_packages, life_info)
    unrelated = FakeDistribution(
        "unrelated-package", "9.9.9", site_packages, "unrelated-9.9.9.dist-info"
    )
    monkeypatch.setattr(
        install_integrity,
        "distributions",
        lambda: [unrelated, life, duplicate_exposure],
    )

    inventory = install_integrity.inventory_life_index_distributions()

    assert inventory["state"] == "single"
    assert inventory["canonical_count"] == 1
    assert inventory["distributions"] == [
        {
            "name": "Life.Index",
            "normalized_name": "life-index",
            "version": "1.5.1",
            "metadata_path": str(site_packages / life_info),
            "canonical_metadata_path": os.path.normcase(
                str((site_packages / life_info).resolve(strict=False))
            ),
            "location": str(site_packages),
            "direct_url": None,
            "editable": False,
        }
    ]


def test_wheel_preflight_requires_shipped_bootstrap_manifest_version(tmp_path: Path) -> None:
    """Metadata alone is insufficient: the shipped CLI manifest must agree too."""
    from tools.upgrade import install_integrity

    wheel = tmp_path / "life_index-1.5.1-py3-none-any.whl"
    _write_synthetic_wheel(
        wheel,
        version=_repo_version(),
        manifest_version="0.0.1",
    )

    validation, error = install_integrity._wheel_validation(
        wheel,
        expected_version=_repo_version(),
    )

    assert error == "wheel bootstrap manifest version does not match source authority"
    assert validation["bootstrap_manifest_version"] == "0.0.1"


def test_formal_isolated_recovery_converges_without_touching_unrelated_or_data(
    tmp_path: Path,
) -> None:
    """The formal ``-I`` launcher repairs package state through pip only."""
    python, _wheel = _mixed_install_fixture(tmp_path)
    unrelated_wheel = tmp_path / "unrelated_package-1.0.0-py3-none-any.whl"
    _write_unrelated_wheel(unrelated_wheel)
    _run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--no-index",
            "--no-deps",
            str(unrelated_wheel),
        ]
    )
    data_dir = tmp_path / "synthetic data"
    data_dir.mkdir()
    sentinel = data_dir / "do-not-touch.txt"
    sentinel.write_text("synthetic data sentinel", encoding="utf-8")

    result = _run_recovery(python, data_dir=data_dir)

    assert result.returncode == 0, f"stderr:\n{result.stderr}\nstdout:\n{result.stdout}"
    payload = json.loads(result.stdout)
    assert payload["success"] is True
    assert payload["data"]["initial_inventory"]["state"] == "conflict"
    assert payload["data"]["terminal_inventory"]["state"] == "single"
    assert payload["data"]["neutral_probe"]["success"] is True
    assert "tools_module_file" in payload["data"]["neutral_probe"]
    assert all(
        operation["command"][:3] == [str(python), "-m", "pip"]
        for operation in payload["data"]["pip_operations"]
    )
    unrelated = _run(
        [
            str(python),
            "-I",
            "-c",
            "import unrelated_package; print(unrelated_package.SENTINEL)",
        ]
    )
    assert unrelated.stdout.strip() == "unrelated package remains"
    assert sentinel.read_text(encoding="utf-8") == "synthetic data sentinel"


def test_recovery_repeats_as_a_verified_noop(tmp_path: Path) -> None:
    """A recovered truthful editable target must not be churned on repeat."""
    python, _wheel = _mixed_install_fixture(tmp_path)
    data_dir = tmp_path / "synthetic data"
    data_dir.mkdir()

    first = _run_recovery(python, data_dir=data_dir)
    assert first.returncode == 0, first.stdout
    second = _run_recovery(python, data_dir=data_dir)

    assert second.returncode == 0, second.stdout
    payload = json.loads(second.stdout)
    assert payload["success"] is True
    assert payload["data"]["outcome"] == "verified_noop"
    assert payload["data"]["pip_operations"] == []
    assert payload["data"]["neutral_probe"]["success"] is True


def test_build_preflight_failure_stops_before_any_uninstall(tmp_path: Path) -> None:
    """A trusted source that cannot build must leave the mixed install untouched."""
    python, _wheel = _mixed_install_fixture(tmp_path)
    source_root = tmp_path / "bad build source"
    _write_build_preflight_failure_source(source_root)
    data_dir = tmp_path / "synthetic data"
    data_dir.mkdir()

    result = _run_recovery(python, data_dir=data_dir, source_root=source_root)

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "m37.install_integrity.v0"
    assert payload["error"]["code"] == "INSTALL_RECOVERY_BUILD_PREFLIGHT_FAILED"
    assert payload["error"]["recovery_strategy"] == "retry"
    assert payload["data"]["terminal_inventory"]["state"] == "conflict"
    assert len(payload["data"]["pip_operations"]) == 1
    assert "uninstall" not in payload["data"]["pip_operations"][0]["command"]


def test_formal_json_remains_parseable_for_a_non_ascii_authority_path(tmp_path: Path) -> None:
    """The isolated launcher's JSON must survive a Windows console code page."""
    data_dir = tmp_path / "synthetic data"
    data_dir.mkdir()
    non_ascii_source = tmp_path / "可信 source"

    result = _run_recovery(
        Path(sys.executable),
        data_dir=data_dir,
        source_root=non_ascii_source,
    )

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "m37.install_integrity.v0"
    assert payload["error"]["code"] == "INSTALL_RECOVERY_AUTHORITY_INVALID"
    assert payload["error"]["recovery_strategy"] == "ask_user"
    assert payload["data"]["source_root"] == str(non_ascii_source)


def test_authority_version_mismatch_stops_before_inventory_mutation(tmp_path: Path) -> None:
    """A source must prove pyproject and bootstrap manifest version authority first."""
    python, _wheel = _mixed_install_fixture(tmp_path)
    source_root = tmp_path / "authority mismatch source"
    _write_editable_failure_source(source_root)
    (source_root / "bootstrap-manifest.json").write_text(
        json.dumps({"repo_version": "0.0.0"}), encoding="utf-8"
    )
    data_dir = tmp_path / "synthetic data"
    data_dir.mkdir()

    result = _run_recovery(python, data_dir=data_dir, source_root=source_root)

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["error"]["code"] == "INSTALL_RECOVERY_AUTHORITY_INVALID"
    assert payload["error"]["recovery_strategy"] == "ask_user"
    assert payload["data"]["pip_operations"] == []
    assert _run_inventory(python)["state"] == "conflict"


def test_recovery_refuses_nonvenv_before_inventory_or_pip(monkeypatch: Any, tmp_path: Path) -> None:
    """A valid checkout cannot authorize recovery through a system interpreter."""
    from tools.upgrade import install_integrity

    inventory_called = False

    def unexpected_inventory() -> dict[str, Any]:
        nonlocal inventory_called
        inventory_called = True
        raise AssertionError("a non-venv interpreter must fail before inventory")

    def unexpected_pip(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise AssertionError("a non-venv interpreter must fail before pip")

    monkeypatch.setattr(install_integrity.sys, "prefix", str(tmp_path / "system-prefix"))
    monkeypatch.setattr(install_integrity.sys, "base_prefix", str(tmp_path / "system-prefix"))
    monkeypatch.setattr(
        install_integrity, "inventory_life_index_distributions", unexpected_inventory
    )
    monkeypatch.setattr(install_integrity, "_command_payload", unexpected_pip)

    payload = install_integrity.recover_install(str(REPO_ROOT))

    assert payload["success"] is False
    assert payload["schema_version"] == "m37.install_integrity.v0"
    assert payload["error"]["code"] == "INSTALL_RECOVERY_AUTHORITY_INVALID"
    assert payload["error"]["details"]["reason"] == "INTERPRETER_NOT_VENV"
    assert payload["error"]["recovery_strategy"] == "ask_user"
    assert payload["data"]["pip_operations"] == []
    assert inventory_called is False


def test_uninstall_nonzero_reports_observed_terminal_inventory_without_direct_deletion(
    monkeypatch: Any, tmp_path: Path
) -> None:
    """A nonzero pip result reports the observed state and leaves files untouched."""
    site_packages = tmp_path / "site-packages"
    protected_tools = site_packages / "tools" / "__init__.py"
    protected_tools.parent.mkdir(parents=True)
    protected_tools.write_text("protected package bytes\n", encoding="utf-8")
    conflict = _fault_inventory(site_packages, state="conflict")
    single = _fault_inventory(site_packages, state="single")
    install_integrity, commands = _prepare_fault_injected_recovery(
        monkeypatch,
        tmp_path,
        inventory_sequence=[conflict, conflict, single],
        command_returncodes=[1],
    )

    payload = install_integrity.recover_install(str(REPO_ROOT))

    assert payload["success"] is False
    assert payload["error"]["code"] == "INSTALL_RECOVERY_UNINSTALL_FAILED"
    assert payload["error"]["recovery_strategy"] == "ask_user"
    assert payload["data"]["terminal_inventory"] == single
    assert payload["data"]["terminal_inventory"]["state"] == "single"
    assert commands == [
        [
            str(sys.executable),
            "-m",
            "pip",
            "--isolated",
            "uninstall",
            "--yes",
            "life-index",
        ]
    ]
    assert all(
        operation["command"][:3] == [str(sys.executable), "-m", "pip"]
        for operation in payload["data"]["pip_operations"]
    )
    assert protected_tools.read_text(encoding="utf-8") == "protected package bytes\n"


def test_uninstall_count_stall_fails_closed_with_exact_conflict_inventory(
    monkeypatch: Any, tmp_path: Path
) -> None:
    """A successful pip exit cannot be trusted unless canonical count decreases."""
    site_packages = tmp_path / "site-packages"
    protected_tools = site_packages / "tools" / "__init__.py"
    protected_tools.parent.mkdir(parents=True)
    protected_tools.write_text("protected package bytes\n", encoding="utf-8")
    conflict = _fault_inventory(site_packages, state="conflict")
    install_integrity, commands = _prepare_fault_injected_recovery(
        monkeypatch,
        tmp_path,
        inventory_sequence=[conflict, conflict, conflict],
        command_returncodes=[0],
    )

    payload = install_integrity.recover_install(str(REPO_ROOT))

    assert payload["success"] is False
    assert payload["error"]["code"] == "INSTALL_RECOVERY_UNINSTALL_STALLED"
    assert payload["error"]["recovery_strategy"] == "ask_user"
    assert payload["data"]["terminal_inventory"] == conflict
    assert payload["data"]["terminal_inventory"]["state"] == "conflict"
    assert len(commands) == 1
    assert commands[0][4] == "uninstall"
    assert protected_tools.read_text(encoding="utf-8") == "protected package bytes\n"


def test_editable_and_wheel_install_failures_report_honest_absent_terminal_state(
    monkeypatch: Any, tmp_path: Path
) -> None:
    """After both target installs fail, recovery reports absence rather than inventing repair."""
    site_packages = tmp_path / "site-packages"
    protected_tools = site_packages / "tools" / "__init__.py"
    protected_tools.parent.mkdir(parents=True)
    protected_tools.write_text("protected package bytes\n", encoding="utf-8")
    conflict = _fault_inventory(site_packages, state="conflict")
    single = _fault_inventory(site_packages, state="single")
    absent = _fault_inventory(site_packages, state="absent")
    install_integrity, commands = _prepare_fault_injected_recovery(
        monkeypatch,
        tmp_path,
        inventory_sequence=[conflict, conflict, single, single, absent, absent, absent],
        command_returncodes=[0, 0, 1, 1],
    )

    payload = install_integrity.recover_install(str(REPO_ROOT))

    assert payload["success"] is False
    assert payload["error"]["code"] == "INSTALL_RECOVERY_TARGET_INSTALL_FAILED"
    assert payload["error"]["recovery_strategy"] == "ask_user"
    assert payload["data"]["rollback"]["status"] == "failed"
    assert payload["data"]["terminal_inventory"] == absent
    assert payload["data"]["terminal_inventory"]["state"] == "absent"
    assert [command[4] for command in commands] == [
        "uninstall",
        "uninstall",
        "install",
        "install",
    ]
    assert all(command[:3] == [str(sys.executable), "-m", "pip"] for command in commands)
    assert protected_tools.read_text(encoding="utf-8") == "protected package bytes\n"


def test_editable_target_failure_rolls_back_to_the_validated_local_wheel(tmp_path: Path) -> None:
    """A failed editable target keeps a valid wheel rollback, but reports failure honestly."""
    python, _wheel = _mixed_install_fixture(tmp_path)
    source_root = tmp_path / "editable failure source"
    _write_editable_failure_source(source_root)
    data_dir = tmp_path / "synthetic data"
    data_dir.mkdir()

    result = _run_recovery(python, data_dir=data_dir, source_root=source_root)

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["success"] is False
    assert payload["error"]["code"] == "INSTALL_RECOVERY_TARGET_INSTALL_FAILED"
    assert payload["data"]["rollback"]["status"] == "validated"
    assert payload["data"]["rollback"]["validation"]["success"] is True
    assert payload["data"]["terminal_inventory"]["state"] == "single"
    assert payload["data"]["terminal_inventory"]["distributions"][0]["version"] == _repo_version()


def test_untracked_orphan_tools_shadow_is_reported_without_direct_deletion(tmp_path: Path) -> None:
    """A leftover physical tools package is evidence, not permission to delete files."""
    python, _wheel = _mixed_install_fixture(tmp_path)
    data_dir = tmp_path / "synthetic data"
    data_dir.mkdir()
    first = _run_recovery(python, data_dir=data_dir)
    assert first.returncode == 0, first.stdout
    inventory = _run_inventory(python)
    location = Path(inventory["distributions"][0]["location"])
    orphan = location / "tools"
    orphan.mkdir()
    (orphan / "__init__.py").write_text("ORPHAN = True\n", encoding="utf-8")
    (orphan / "__main__.py").write_text(
        "import json\n"
        "if __name__ == '__main__':\n"
        "    print(json.dumps({'package_version': '1.5.1', "
        "'bootstrap_manifest': {'repo_version': '1.5.1'}}))\n",
        encoding="utf-8",
    )

    result = _run_recovery(python, data_dir=data_dir)

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    probe = payload["data"]["neutral_probe"]
    assert payload["error"]["code"] == "INSTALL_RECOVERY_ORPHAN_SHADOW", {
        key: probe.get(key)
        for key in (
            "tools_origin",
            "tools_error",
            "module_origin_matches_distribution",
            "module_origin_matches_target",
            "orphan_shadow",
        )
    }
    assert payload["data"]["neutral_probe"]["orphan_shadow"] is True
    assert payload["data"]["pip_operations"] == []
    assert (orphan / "__init__.py").read_text(encoding="utf-8") == "ORPHAN = True\n"


def test_editable_bare_tools_init_shadow_fails_closed_before_pip(tmp_path: Path) -> None:
    """A bare site tools package must not defeat an authoritative namespace source target."""
    python = _single_editable_fixture(tmp_path)
    data_dir = tmp_path / "synthetic data"
    data_dir.mkdir()
    shadow = _venv_site_packages(python) / "tools" / "__init__.py"
    shadow.parent.mkdir()
    before_bytes = b"UNTRACKED_BARE_TOOLS_SHADOW = True\n"
    shadow.write_bytes(before_bytes)

    result = _run_recovery(python, data_dir=data_dir)

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["error"]["code"] == "INSTALL_RECOVERY_ORPHAN_SHADOW"
    assert payload["error"]["recovery_strategy"] == "ask_user"
    assert payload["data"]["pip_operations"] == []
    probe = payload["data"]["neutral_probe"]
    assert os.path.normcase(str(shadow.resolve(strict=False))) in probe["physical_tools_shadows"]
    assert shadow.read_bytes() == before_bytes


def test_editable_sourceless_tools_pyc_shadow_fails_closed_without_loading(tmp_path: Path) -> None:
    """An importable sourceless top-level tools module is evidence, never a probe target."""
    python = _single_editable_fixture(tmp_path)
    data_dir = tmp_path / "synthetic data"
    data_dir.mkdir()
    site_packages = _venv_site_packages(python)
    shadow = site_packages / "tools.pyc"
    sentinel = tmp_path / "sourceless-tools-imported.txt"
    source = tmp_path / "sourceless_tools_source.py"
    source.write_text(
        "from pathlib import Path\n"
        f"Path({str(sentinel)!r}).write_text('loaded', encoding='utf-8')\n",
        encoding="utf-8",
    )
    py_compile.compile(str(source), cfile=str(shadow), doraise=True)
    source.unlink()

    imported = _run(
        [
            str(python),
            "-I",
            "-S",
            "-c",
            (
                "import json, pathlib, sys; "
                "sys.path.insert(0, sys.argv[1]); "
                "import tools; "
                "print(json.dumps({'origin': str(pathlib.Path(tools.__file__).resolve())}))"
            ),
            str(site_packages),
        ]
    )
    assert os.path.normcase(json.loads(imported.stdout)["origin"]) == os.path.normcase(
        str(shadow.resolve(strict=False))
    )
    assert sentinel.exists(), "fixture must prove the sourceless module is importable"
    sentinel.unlink()
    before_bytes = shadow.read_bytes()

    result = _run_recovery(python, data_dir=data_dir)

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["error"]["code"] == "INSTALL_RECOVERY_ORPHAN_SHADOW"
    assert payload["error"]["recovery_strategy"] == "ask_user"
    assert payload["data"]["pip_operations"] == []
    probe = payload["data"]["neutral_probe"]
    assert os.path.normcase(str(shadow.resolve(strict=False))) in probe["physical_tools_shadows"]
    assert probe["tools_origin"] is None
    assert probe["tools_error"] is None
    assert not sentinel.exists(), "recovery must detect the bytecode file without importing it"
    assert shadow.read_bytes() == before_bytes


def test_editable_extension_suffix_shadow_is_detected_without_loading(tmp_path: Path) -> None:
    """A synthetic extension candidate is reported without attempting to load it."""
    python = _single_editable_fixture(tmp_path)
    data_dir = tmp_path / "synthetic data"
    data_dir.mkdir()
    suffix = importlib.machinery.EXTENSION_SUFFIXES[0]
    shadow = _venv_site_packages(python) / f"tools{suffix}"
    before_bytes = b"not a native extension"
    shadow.write_bytes(before_bytes)

    result = _run_recovery(python, data_dir=data_dir)

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["error"]["code"] == "INSTALL_RECOVERY_ORPHAN_SHADOW"
    assert payload["error"]["recovery_strategy"] == "ask_user"
    assert payload["data"]["pip_operations"] == []
    probe = payload["data"]["neutral_probe"]
    assert os.path.normcase(str(shadow.resolve(strict=False))) in probe["physical_tools_shadows"]
    assert probe["tools_origin"] is None
    assert probe["tools_error"] is None
    assert probe["cli_returncode"] is None
    assert shadow.read_bytes() == before_bytes


def test_formal_launcher_ignores_malicious_pythonpath_and_pythonhome(tmp_path: Path) -> None:
    """A source-cwd import can lie; the formal launcher and probe must not."""
    python, _wheel = _mixed_install_fixture(tmp_path)
    injected_root = tmp_path / "malicious injection"
    _write_injected_tools(injected_root, version=_repo_version())
    naive_env = _clean_pip_env()
    naive_env["PYTHONPATH"] = str(injected_root)
    naive = subprocess.run(
        [
            str(python),
            "-c",
            "import pathlib, tools; print(pathlib.Path(tools.__file__).resolve())",
        ],
        cwd=REPO_ROOT,
        env=naive_env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert naive.returncode == 0, naive.stderr
    assert str(injected_root).lower() in naive.stdout.lower()

    data_dir = tmp_path / "synthetic data"
    data_dir.mkdir()
    result = _run_recovery(
        python,
        data_dir=data_dir,
        environment_updates={
            "PYTHONPATH": str(injected_root),
            "PYTHONHOME": str(injected_root),
        },
    )

    assert result.returncode == 0, result.stdout
    payload = json.loads(result.stdout)
    probe = payload["data"]["neutral_probe"]
    assert probe["success"] is True
    assert str(REPO_ROOT / "tools").lower() in probe["tools_origin"].lower()
    assert str(injected_root).lower() not in probe["tools_origin"].lower()


def test_recovery_ignores_pip_target_redirection_from_the_caller(tmp_path: Path) -> None:
    """The active interpreter, not caller PIP_* state, owns every pip mutation."""
    python, _wheel = _mixed_install_fixture(tmp_path)
    data_dir = tmp_path / "synthetic data"
    data_dir.mkdir()
    redirected_target = tmp_path / "malicious pip target"

    result = _run_recovery(
        python,
        data_dir=data_dir,
        environment_updates={"PIP_TARGET": str(redirected_target)},
    )

    assert result.returncode == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["data"]["neutral_probe"]["success"] is True
    assert not (redirected_target / "tools").exists()
