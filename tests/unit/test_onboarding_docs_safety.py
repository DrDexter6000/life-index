"""Safety checks for agent-facing onboarding instructions."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def test_onboarding_is_bootstrap_driven_one_page() -> None:
    onboarding = _read("AGENT_ONBOARDING.md")

    assert len(onboarding.splitlines()) <= 140
    assert "life-index bootstrap --json" in onboarding
    assert "safe_next_steps" in onboarding
    assert "needs_human" in onboarding
    assert "Step 4.1" not in onboarding
    assert "Step 5.3" not in onboarding
    assert "CLI Quick Reference" not in onboarding


def test_onboarding_forbids_waiting_for_semantic_ready() -> None:
    # whitespace-normalized so assertions survive doc line-wrapping
    onboarding = " ".join(_read("AGENT_ONBOARDING.md").split())

    assert "no semantic/vector indexing to wait for" in onboarding
    assert "keyword readiness is all onboarding needs" in onboarding


def test_onboarding_data_safety_rule_stays_visible() -> None:
    onboarding = _read("AGENT_ONBOARDING.md")

    assert "Never delete" in onboarding
    assert "~/Documents/Life-Index" in onboarding
    assert "fresh install" in onboarding


def test_onboarding_documents_reversible_skill_install_safety() -> None:
    onboarding = _read("AGENT_ONBOARDING.md")

    assert "life-index sync-skill --list --json" in onboarding
    assert "life-index sync-skill --uninstall --host-home <host-home> --json" in onboarding
    assert "only removes agent skill artifacts" in onboarding
    assert "never deletes journals" in onboarding


def test_onboarding_explains_cli_gui_host_agent_relationship() -> None:
    onboarding = _read("AGENT_ONBOARDING.md")

    assert "System Overview" in onboarding
    assert (
        "Life Index is a deterministic toolset for a host agent, not a standalone "
        "human-facing intelligent app."
    ) in onboarding
    assert "CLI (life-index) is the deterministic tool layer" in onboarding
    assert "Host agent (for example, Hermes) is the intelligence layer." in onboarding
    assert "GUI is the optional UX layer over the same CLI-backed capabilities." in onboarding
    assert "Data stays separate from program code." in onboarding


def test_readme_does_not_reference_real_first_entry_smoke_file() -> None:
    readme = _read("README.md")
    readme_en = _read("README.en.md")
    skill = _read("SKILL.md")
    onboarding = _read("AGENT_ONBOARDING.md")

    assert "first-entry.json" not in readme
    assert "first-entry.json" not in readme_en
    assert "first-entry.json" not in skill
    assert "sandbox" in onboarding.lower()
    assert "LIFE_INDEX_DATA_DIR" in onboarding


def test_readme_metrics_use_current_108_query_baseline() -> None:
    readme = _read("README.md")
    readme_en = _read("README.en.md")

    for text in (readme, readme_en):
        assert "2,400+ unit tests" not in text
        assert "keyword-only Recall@5 = **0.7857**" not in text
        assert "4,200+ pytest-collected tests" in text
        assert "108-query" in text
        assert "Recall@5 = **0.9231**" in text


def test_readme_current_version_points_to_release_ssot() -> None:
    readme = _read("README.md")
    readme_en = _read("README.en.md")

    assert "当前稳定线（" not in readme
    assert "current stable line (" not in readme_en
    assert "life-index --version" in readme
    assert "life-index --version" in readme_en
    assert "CHANGELOG.md" in readme
    assert "CHANGELOG.md" in readme_en


def test_skill_uses_progressive_disclosure_for_grounded_query_playbook() -> None:
    skill = _read("SKILL.md")
    playbook = _read("references/GROUNDED_QUERY_PLAYBOOK.md")

    assert len(skill.splitlines()) <= 590
    assert "references/GROUNDED_QUERY_PLAYBOOK.md" in skill
    assert "Full grounded query playbook" in skill
    assert "life-index journal batch-get" in playbook
    assert "answer.insights[]" in playbook
    assert "ensure` -> `discover` -> `navigate" in playbook
