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
    onboarding = _read("AGENT_ONBOARDING.md")

    assert "Do not wait for semantic indexing" in onboarding
    assert "Keyword readiness is enough for onboarding" in onboarding


def test_onboarding_data_safety_rule_stays_visible() -> None:
    onboarding = _read("AGENT_ONBOARDING.md")

    assert "Never delete" in onboarding
    assert "~/Documents/Life-Index" in onboarding
    assert "fresh install" in onboarding


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
