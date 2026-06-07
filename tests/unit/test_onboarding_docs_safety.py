"""Safety checks for agent-facing onboarding instructions."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def test_onboarding_smoke_test_does_not_call_write_in_default_data_dir() -> None:
    onboarding = _read("AGENT_ONBOARDING.md")
    smoke_section = onboarding.split("### Step 5.3:", maxsplit=1)[1].split(
        "### Step 5.4:", maxsplit=1
    )[0]

    assert "life-index write" not in smoke_section
    assert "LIFE_INDEX_DATA_DIR" in smoke_section
    assert "temporary sandbox" in smoke_section.lower()


def test_onboarding_forbids_waiting_for_semantic_ready() -> None:
    onboarding = _read("AGENT_ONBOARDING.md")

    assert "Do not wait for `semantic_status: ready`" in onboarding
    assert "Installation succeeds when keyword search is ready" in onboarding


def test_readme_does_not_reference_real_first_entry_smoke_file() -> None:
    readme = _read("README.md")
    readme_en = _read("README.en.md")
    skill = _read("SKILL.md")

    assert "first-entry.json" not in readme
    assert "first-entry.json" not in readme_en
    assert "first-entry.json" not in skill
    assert "sandbox" in readme.lower()
    assert "sandbox" in readme_en.lower()
