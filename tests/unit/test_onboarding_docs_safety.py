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


def test_skill_session_surface_mentions_upgrade_freshness_signal() -> None:
    skill = _read("SKILL.md")

    assert "life-index health --json" in skill
    assert "upgrade_freshness" in skill
    assert "git_freshness" in skill


def test_skill_teaches_host_agent_ops_discipline() -> None:
    skill = _read("SKILL.md")
    playbook = _read("references/ENTITY_MAINTENANCE_PLAYBOOK.md")

    assert "运维纪律" in skill
    assert "不是开发者" in skill
    assert "不要向产品仓库克隆 commit/push" in skill
    assert "git status --porcelain" in skill
    assert "git checkout -- ." in skill
    assert "<data>/frictions/" in skill
    assert "运维纪律" in playbook


def test_skill_entity_interview_teaches_agent_recommend_user_confirm_write() -> None:
    skill = _read("SKILL.md")

    assert "筛 → 荐 → 问 → 写" in skill
    assert "按 `evidence` 指针读原文" in skill
    assert "带理由建议" in skill
    assert "批量授权" in skill
    assert "队列外" in skill
    assert "写入必须有人判" in skill
    assert "life-index entity --review --action add_relationship" in skill
    assert "life-index entity --unmerge" in skill


def test_skill_entity_reference_teaches_workflow_facades_not_update_shortcut() -> None:
    skill = _read("SKILL.md")

    assert "life-index entity build --from-journals --preview --json" in skill
    assert "life-index entity profile --id ENTITY_ID --json" in skill
    assert "life-index abstract --entities --json" in skill
    assert "life-index abstract --entities --id ENTITY_ID --json" in skill
    assert "life-index entity audit --json" in skill
    assert "life-index entity maintain --normalize --preview --json" in skill
    assert "life-index entity maintain --delete --id ENTITY_ID --preview --json" in skill
    assert "life-index entity --list|--add|--resolve|--update" not in skill
    for retired in (
        "life-index entity --seed",
        "life-index entity --merge",
        "life-index entity --delete",
        "life-index entity --update",
    ):
        assert retired not in skill


def test_api_marks_retired_entity_primitives_as_removed_with_replacements() -> None:
    api = _read("docs/API.md")

    assert "Retired top-level primitives" in api
    assert "profile --id ENTITY_ID --json" in api
    assert "life-index abstract --entities --json" in api
    assert "`Entities/<entity_id>.md`" in api
    assert "candidate entities fail closed" in api.lower()
    assert "`--seed`" in api
    assert "`entity build --from-journals --preview --json`" in api
    assert "`--update`" in api
    assert "`entity --add-alias ALIAS --id ENTITY_ID`" in api
    assert "`--merge`" in api
    assert "`entity --review --action preview`" in api
    assert "`--delete`" in api
    assert "`entity maintain --delete --id ENTITY_ID --preview --json`" in api
