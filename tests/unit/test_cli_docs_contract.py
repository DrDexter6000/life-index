from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _contract_files() -> tuple[str, Path, Path, str]:
    api = (REPO_ROOT / "docs" / "API.md").read_text(encoding="utf-8")
    skill_path = REPO_ROOT / "SKILL.md"
    packaged_skill_path = REPO_ROOT / "tools" / "_skill_artifacts" / "SKILL.md"
    skill = skill_path.read_text(encoding="utf-8")
    return api, skill_path, packaged_skill_path, skill


def test_cli_and_skill_use_official_confirm_command() -> None:
    api, _skill_path, _packaged_skill_path, skill = _contract_files()

    assert "life-index confirm --journal" in api
    assert "life-index confirm --journal" in skill
    assert "write_journal confirm" not in skill


def test_cli_and_skill_document_literal_append_content() -> None:
    api, _skill_path, _packaged_skill_path, skill = _contract_files()
    literal_append_contract = (
        "`life-index edit --append-content` receives a literal string and does not "
        "expand `@file` arguments."
    )
    assert literal_append_contract in api
    assert literal_append_contract in skill


def test_installed_skill_requires_exact_help_instead_of_guessed_options() -> None:
    _api, _skill_path, _packaged_skill_path, skill = _contract_files()
    installed_help_contract = (
        "If an installed Skill cannot access repository docs, run the exact "
        "`life-index <command> --help` for that installed command and do not guess options."
    )
    assert installed_help_contract in skill


def test_canonical_and_packaged_skill_are_byte_identical() -> None:
    _api, skill_path, packaged_skill_path, _skill = _contract_files()
    assert skill_path.read_bytes() == packaged_skill_path.read_bytes()
