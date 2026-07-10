"""D0 contracts for the named platform authority snapshots."""

from __future__ import annotations

import difflib
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
AUTHORITY_PATHS = {
    "charter": REPO_ROOT / "CHARTER.md",
    "agents": REPO_ROOT / "AGENTS.md",
    "architecture": REPO_ROOT / "docs" / "ARCHITECTURE.md",
    "api": REPO_ROOT / "docs" / "API.md",
    "ci": REPO_ROOT / "docs" / "CI_HARD_CHECKS.md",
    "skill": REPO_ROOT / "SKILL.md",
    "smart_search_cli": REPO_ROOT / "tools" / "smart_search" / "__main__.py",
}

RATIFIED_CORE_DOMAINS = (
    ("C1", "Canonical journal and attachment mutation"),
    ("C2", "Schema, validation, migration, transaction, locking, and audit"),
    ("C3", "Deterministic indexing, retrieval, freshness, and evidence navigation"),
    ("C4", "Deterministic aggregation and analysis"),
    ("C5", "Entity graph"),
    ("C6", "Integrity, health, backup, restore, and recovery"),
    ("C7", "Deterministic contract and eval verification"),
)
EXPECTED_CHARTER_METADATA = {
    "版本": "v1.10.0",
    "批准日期": "2026-07-10",
    "修订次数": "10",
}
INTELLIGENCE_OWNER_RULE = (
    "Host Agent + Skill own provider selection and all planning, multi-hop reasoning, "
    "orchestration, interpretation, and synthesis."
)
CURRENT_SYNTHESIZE_TRUTH = (
    "The accepted `--synthesize` flag currently runs with no LLM injection and emits "
    "no `answer`."
)
SYNTHESIZE_FOLLOW_ON_TRUTH = (
    "#163 owns the future deprecation warning, deterministic equivalence proof, and "
    "unreachable LLM-path cleanup."
)

EXPECTED_CURRENT_TARGET_STATUS = (
    """
### Platform program: current runtime vs ratified target

Current runtime: direct CLI/Core contracts are the implemented public route;
the accepted `--synthesize` flag follows the deterministic no-LLM/no-answer
contract named below, and the current bridge is non-Core and GUI-owned. The
design memo is not an authority or SSOT. The exact closed C1–C7 domains are now
active Charter authority, and the former §1.9 direct provider-fallback direction
is superseded: Host Agent + Skill own provider selection and intelligence.

The following implementation work remains future work; D0 ratification does
not describe any of it as complete:

"""
    "- #163 — recall/eval correction, explicit deprecation warning, ordinary "
    "deterministic smart-search equivalence proof, and unreachable LLM-path deletion: "
    "unimplemented.\n"
    """- #162 — transactional write, side-effect, and freshness repair: unimplemented.
- #165 — backup, restore, and recovery proof: unimplemented.
- #164 — optional Gateway typed 1:1 projection: unimplemented.
"""
)

EXPECTED_SMART_SEARCH_CURRENT_CONTRACT = "\n".join(
    (
        "### Smart-search current contract",
        "",
        "- Default/no-flag `life-index smart-search` returns a deterministic scaffold.",
        "- Current explicit `--synthesize` is accepted, but the product CLI always constructs `SmartSearchOrchestrator(llm_client=None)`: it never instantiates or injects an LLM and emits no `answer`; the flag is behaviorally a deterministic no-op/no-answer path.",  # noqa: E501
        "- Current runtime does not yet emit the approved explicit deprecation warning.",
        "- Target under #163: retain the accepted flag for at least two major versions, document and emit the deprecation warning, prove equivalence to ordinary deterministic smart-search, and delete dormant/injectable LLM rewrite, filter, provider, prompt, trust-gate, and synthesis code unreachable from the product CLI.",  # noqa: E501
        "- Host Agent + Skill remain the intelligence owner; #163 does not change that role boundary.",  # noqa: E501
    )
)

EXPECTED_CORE_ADMISSION_DOMAINS = "\n".join(
    (
        "#### Active §1.10 closed Core admission domains",
        "",
        "The former §1.9 P0→P1→P2→deterministic-only direct provider-fallback",
        "direction is superseded. Host Agent + Skill own provider selection and all",
        "planning, multi-hop reasoning, orchestration, interpretation, and synthesis;",
        "Core remains deterministic; GUI remains presentation-only; and an optional",
        "Gateway cannot own intelligence or semantics. The accepted `--synthesize`",
        "flag currently runs through the product CLI with no LLM injection and no",
        "`answer`; #163 owns the future deprecation warning, deterministic equivalence",
        "proof, and unreachable LLM-path cleanup.",
        "",
        "| ID | Active closed Core admission domain |",
        "|---|---|",
        "| C1 | Canonical journal and attachment mutation |",
        "| C2 | Schema, validation, migration, transaction, locking, and audit |",
        "| C3 | Deterministic indexing, retrieval, freshness, and evidence navigation |",
        "| C4 | Deterministic aggregation and analysis |",
        "| C5 | Entity graph |",
        "| C6 | Integrity, health, backup, restore, and recovery |",
        "| C7 | Deterministic contract and eval verification |",
        "",
        "The C1–C7 identifiers are additive labels; they do not rename or weaken the",
        "exact approved domain names. These seven domains are active Charter authority.",
        "CHARTER.md §1.10 is the sole list authority; lower-level documents must reference",
        "C1–C7 and must not duplicate domain descriptions. The enumeration is closed.",
        "Every added Core domain requires new Human Owner substantive approval.",
        "",
        "Human Owner approval may replace only second-production-consumer evidence. It",
        "cannot waive determinism, low/zero LLM content, cross-time semantic stability,",
        "RFC/substantive-gate evidence, or any other current Charter admission constraint.",
        "",
        "**Substantive-gate ratification record**:",
        "",
        "- **Rationale**: align stale §1.9 fallback language with APEX and make Core",
        "  admission reviewable against one closed, long-lived set of domains.",
        "- **Opposition addressed**: (1) removing a standalone provider fallback may",
        "  inconvenience direct CLI users, so #163 retains the already accepted",
        "  no-op/no-answer `--synthesize` flag for at least two major versions and adds",
        "  an explicit deprecation warning; (2) a",
        "  closed list may delay a valuable primitive, so each addition remains possible",
        "  through new Human Owner substantive approval without weakening the other",
        "  admission criteria.",
        "- **Impact**: this ratification affects §1.9 / §1.10 interpretation and the public",
        "  architecture, API, CI, and Skill pointers only. It does not implement #163,",
        "  #162, #165, or #164 and does not change runtime or data contracts.",
        "- **Rollback**: any reversal or weakening requires a new §5.2 substantive",
        "  amendment; no lower-level document can waive this ratification.",
        "- **Gold Set regression**: PASS — observational evidence against the 2026-05-04",
        "  baseline; D0 is docs-only and did not cause the result.",
        "- **Human Owner ack**: COMPLETE — on 2026-07-10 the Human Owner substantively",
        "  approved exactly C1–C7 and no additional domain.",
        "",
        "This ratification lands D0 Charter authority only. It does not implement #163,",
        "#162, #165, or #164 and does not change current runtime or data contracts.",
    )
)

EXPECTED_PLATFORM_ROLE_BOUNDARY = "\n".join(
    (
        "### Platform role boundary",
        "",
        "| Role | Authority boundary |",
        "|---|---|",
        "| Core | Deterministic tools; no planning, reasoning, orchestration, interpretation, or synthesis. |",  # noqa: E501
        "| Host Agent + Skill | Owns planning, multi-hop reasoning, orchestration, interpretation, and synthesis. |",  # noqa: E501
        "| GUI | Presentation only; no intelligence; strict adapter stays GUI-owned. |",
        "| Current bridge | Non-Core and GUI-owned. |",
        "| Gateway | Optional future typed 1:1 projection under #164; unimplemented; not a second semantic API; no intelligence. |",  # noqa: E501
        "",
        "The table above is the sole normative role-assignment surface in this block.",
        "The future Gateway, if implemented, is only a contract-equivalent transport of",
        "Core operations. It cannot create a parallel semantic contract, and direct Core",
        "use does not depend on it. The active closed admission-domain catalog belongs",
        "only to `CHARTER.md §1.10`; this document references C1–C7 without duplicating",
        "their domain descriptions.",
    )
)

SYNTHESIZE_TRANSITION_SEMANTICS = "\n".join(
    (
        "Current runtime: the product CLI accepts `--synthesize` but always constructs `SmartSearchOrchestrator(llm_client=None)`; it never instantiates or injects an LLM, emits no `answer`, and is behaviorally a deterministic no-op/no-answer path.",  # noqa: E501
        "",
        "Current warning status: the approved explicit deprecation warning is not yet emitted.",  # noqa: E501
        "",
        "Target under #163: retain the accepted flag for at least two major versions, document and emit the deprecation warning, prove equivalence to ordinary deterministic smart-search, and delete dormant/injectable LLM rewrite, filter, provider, prompt, trust-gate, and synthesis code unreachable from the product CLI.",  # noqa: E501
        "",
        "Intelligence owner: Host Agent + Skill remain responsible for planning, multi-hop reasoning, orchestration, interpretation, and synthesis.",  # noqa: E501
    )
)
EXPECTED_API_SYNTHESIZE_TRANSITION = "\n".join(
    ("### `--synthesize` transition authority", "", SYNTHESIZE_TRANSITION_SEMANTICS)
)
EXPECTED_SKILL_SYNTHESIZE_TRANSITION = "\n".join(
    ("**`--synthesize` transition**", "", SYNTHESIZE_TRANSITION_SEMANTICS)
)

EXPECTED_PUBLIC_BLOCKER_EXECUTION = """
## Public blocker execution contract

A public hard blocker is green only when at least one core assertion executed.
All-skipped assertion sets are not green. Private-only assertions are advisory
and cannot be the sole evidence for a Tier 1 public blocker.

The public synthetic invariant work tracked by #163 is pending implementation;
this inventory rule does not claim that future assertion or its CI result
already exists.
"""

EXPECTED_HOST_AGENT_ROUTING = "\n".join(
    (
        "## Host Agent / Core / Gateway routing boundary",
        "",
        "- Host Agent + Skill own planning, multi-hop reasoning, interpretation, and synthesis. They also own orchestration.",  # noqa: E501
        "- Core calls remain deterministic; Core does not plan, reason, orchestrate, interpret, or synthesize.",  # noqa: E501
        "- Gateway is an optional future typed 1:1 projection under #164; it is not yet implemented, is not a second semantic API, and owns no intelligence. If introduced, it is only a contract-equivalent transport. Gateway is never required for the core route.",  # noqa: E501
    )
)

EXPECTED_API_CURRENT_ROWS = {
    "`answer` / `answer.*`": (
        "`answer` / `answer.*`",
        "当前产品 CLI 不输出；`--synthesize` 不注入 LLM 且不添加 `answer`；"
        "see the named `--synthesize` transition authority block；#163 将删除不可达实现",
        "当前无此字段；如未来由新契约引入，再按该契约消费",
        "**stable**",
    ),
    "`--synthesize`": (
        "`--synthesize`",
        "当前接受但不注入 LLM、不添加 `answer`，行为上是 deterministic no-op/no-answer；"
        "see the named `--synthesize` transition authority block",
    ),
    "`--include-evidence --synthesize`": (
        "`--include-evidence --synthesize`",
        "添加 evidence_pack；`--synthesize` 当前不注入 LLM、不添加 `answer`；"
        "see the named `--synthesize` transition authority block",
    ),
}

EXPECTED_API_PERFORMANCE_ROWS = {
    "`rewrite_time_ms`": (
        "`rewrite_time_ms`",
        "float",
        "始终",
        "当前确定性产品 CLI 路径固定为 `0`",
    ),
    "`filter_time_ms`": (
        "`filter_time_ms`",
        "float",
        "始终",
        "当前确定性产品 CLI 路径固定为 `0`",
    ),
    "`evidence_build_ms`": (
        "`evidence_build_ms`",
        "float",
        "仅传递 `--include-evidence` 时",
        "Evidence pack 构建耗时；`--synthesize` 单独使用不触发构建",
    ),
    "`synthesis_ms`": (
        "`synthesis_ms`",
        "float",
        "当前产品 CLI 不出现",
        "不可达旧实现的非稳定字段；#163 清理",
    ),
}


def _assert_named_block_snapshot(
    text: str,
    marker: str,
    expected: str,
    source: str,
) -> str:
    start_marker = f"<!-- PLATFORM-SSOT:{marker}:START -->"
    end_marker = f"<!-- PLATFORM-SSOT:{marker}:END -->"
    assert text.count(start_marker) == text.count(end_marker) == 1
    start = text.index(start_marker) + len(start_marker)
    end = text.index(end_marker, start)
    block = text[start:end]
    actual_normalized = (
        block.replace("\r\n", "\n").replace("\r", "\n").removeprefix("\n").removesuffix("\n")
    )  # noqa: E501
    expected_normalized = (
        expected.replace("\r\n", "\n").replace("\r", "\n").removeprefix("\n").removesuffix("\n")
    )  # noqa: E501
    if actual_normalized != expected_normalized:
        diff = "\n".join(
            difflib.unified_diff(
                expected_normalized.splitlines(),
                actual_normalized.splitlines(),
                fromfile=f"{source}:{marker}:expected",
                tofile=f"{source}:{marker}:actual",
                lineterm="",
            )
        )
        raise AssertionError(f"{source} {marker} snapshot drift:\n{diff}")
    return block


def _markdown_rows(text: str) -> list[tuple[str, ...]]:
    rows: list[tuple[str, ...]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not (stripped.startswith("|") and stripped.endswith("|")):
            continue
        cells = tuple(cell.strip() for cell in stripped[1:-1].split("|"))
        if not (cells and all(cell and set(cell) <= {"-", ":"} for cell in cells)):
            rows.append(cells)
    return rows


def _charter_metadata_value(charter: str, label: str) -> str:
    matches = re.findall(rf"^> \*\*{re.escape(label)}\*\*：(.+)$", charter, re.MULTILINE)
    assert len(matches) == 1, f"CHARTER metadata field {label!r} must occur exactly once"
    return matches[0].strip()


def _charter_section(charter: str, start_heading: str, end_heading: str) -> str:
    assert charter.count(start_heading) == charter.count(end_heading) == 1
    start = charter.index(start_heading) + len(start_heading)
    end = charter.index(end_heading, start)
    return charter[start:end]


def test_charter_header_records_completed_d0_owner_ratification() -> None:
    charter = AUTHORITY_PATHS["charter"].read_text(encoding="utf-8")
    for label, expected in EXPECTED_CHARTER_METADATA.items():
        actual = _charter_metadata_value(charter, label)
        if label == "批准日期":
            actual = actual.split("（", 1)[0].strip()
        assert actual == expected

    latest_revision = _charter_metadata_value(charter, "最近修订")
    assert latest_revision.startswith("2026-07-10")
    assert "C1–C7" in latest_revision
    assert "owner" in latest_revision.casefold()


def test_section_1_9_supersedes_direct_provider_fallback_without_overclaiming_runtime() -> None:
    charter = AUTHORITY_PATHS["charter"].read_text(encoding="utf-8")
    section = _charter_section(
        charter,
        "### §1.9 Agent-Native 模块原则（Agent-Native Module Principle）",
        "### §1.10 模块-基础层契约边界（Module-Foundation Contract Boundary）",
    )

    assert "P0→P1→P2→deterministic-only" not in section
    assert "provider opt-in fallback" not in section
    assert INTELLIGENCE_OWNER_RULE in section
    assert CURRENT_SYNTHESIZE_TRUTH in section
    assert SYNTHESIZE_FOLLOW_ON_TRUTH in section


def test_authority_surfaces_distinguish_current_behavior_from_ratified_target() -> None:
    charter = AUTHORITY_PATHS["charter"].read_text(encoding="utf-8")
    agents = AUTHORITY_PATHS["agents"].read_text(encoding="utf-8")
    architecture = AUTHORITY_PATHS["architecture"].read_text(encoding="utf-8")
    smart_search_cli = AUTHORITY_PATHS["smart_search_cli"].read_text(encoding="utf-8")

    assert "CHARTER.md（本文件，最高权威）" in charter
    assert "1. `CHARTER.md` owns constitutional invariants." in agents
    _assert_named_block_snapshot(
        architecture,
        "CURRENT-TARGET-STATUS",
        EXPECTED_CURRENT_TARGET_STATUS,
        "docs/ARCHITECTURE.md",
    )
    _assert_named_block_snapshot(
        architecture,
        "SMART-SEARCH-CURRENT-CONTRACT",
        EXPECTED_SMART_SEARCH_CURRENT_CONTRACT,
        "docs/ARCHITECTURE.md",
    )
    assert "SmartSearchOrchestrator(llm_client=None)" in smart_search_cli

    smart_search_end = "<!-- PLATFORM-SSOT:SMART-SEARCH-CURRENT-CONTRACT:END -->"
    provider_backed_drift = architecture.replace(
        smart_search_end,
        "- Current `--synthesize` also requests provider-backed LLM synthesis.\n"
        + smart_search_end,
        1,
    )
    assert "always constructs `SmartSearchOrchestrator(llm_client=None)`" in provider_backed_drift
    with pytest.raises(AssertionError) as exc_info:
        _assert_named_block_snapshot(
            provider_backed_drift,
            "SMART-SEARCH-CURRENT-CONTRACT",
            EXPECTED_SMART_SEARCH_CURRENT_CONTRACT,
            "docs/ARCHITECTURE.md",
        )
    assert "provider-backed LLM synthesis" in str(exc_info.value)

    end_marker = "<!-- PLATFORM-SSOT:CURRENT-TARGET-STATUS:END -->"
    drifted = architecture.replace(
        end_marker,
        "The #163 target is already implemented.\n" + end_marker,
        1,
    )
    with pytest.raises(AssertionError) as exc_info:
        _assert_named_block_snapshot(
            drifted,
            "CURRENT-TARGET-STATUS",
            EXPECTED_CURRENT_TARGET_STATUS,
            "docs/ARCHITECTURE.md",
        )
    assert "snapshot drift" in str(exc_info.value)
    assert "already implemented" in str(exc_info.value)


def test_ratified_core_admission_domains_are_exact_active_and_owner_gated() -> None:
    charter = AUTHORITY_PATHS["charter"].read_text(encoding="utf-8")
    block = _assert_named_block_snapshot(
        charter,
        "CORE-ADMISSION-DOMAINS",
        EXPECTED_CORE_ADMISSION_DOMAINS,
        "CHARTER.md §1.10",
    )
    expected_rows = [
        ("ID", "Active closed Core admission domain"),
        *RATIFIED_CORE_DOMAINS,
    ]
    assert _markdown_rows(block) == expected_rows
    assert "PENDING" not in block
    assert "not active" not in block
    assert "not land-ready" not in block
    assert "GO-AFTER-DECISION" not in block

    first_id, first_domain = RATIFIED_CORE_DOMAINS[0]
    last_id, last_domain = RATIFIED_CORE_DOMAINS[-1]
    first_row = f"| {first_id} | {first_domain} |"
    last_row = f"| {last_id} | {last_domain} |"
    end_marker = "<!-- PLATFORM-SSOT:CORE-ADMISSION-DOMAINS:END -->"
    drifted_documents = (
        charter.replace(first_row + "\n", "", 1),
        charter.replace(
            last_row,
            last_row + "\n| C8 | Workflow orchestration |",
            1,
        ),
        charter.replace(first_row, f"| {first_id} | Journal mutation |", 1),
        charter.replace(first_row, f"| C8 | {first_domain} |", 1),
        charter.replace(
            end_marker,
            "Human Owner approval is authorized to waive determinism.\n" + end_marker,
            1,
        ),
    )
    for drifted in drifted_documents:
        with pytest.raises(AssertionError):
            _assert_named_block_snapshot(
                drifted,
                "CORE-ADMISSION-DOMAINS",
                EXPECTED_CORE_ADMISSION_DOMAINS,
                "CHARTER.md §1.10",
            )


def test_no_authority_surface_assigns_intelligence_to_core_gui_or_gateway() -> None:
    architecture = AUTHORITY_PATHS["architecture"].read_text(encoding="utf-8")
    _assert_named_block_snapshot(
        architecture,
        "PLATFORM-ROLE-BOUNDARY",
        EXPECTED_PLATFORM_ROLE_BOUNDARY,
        "docs/ARCHITECTURE.md",
    )
    collapsed_boundary = architecture.replace(
        "### Platform role boundary\n\n| Role | Authority boundary |",
        "### Platform role boundary | Role | Authority boundary |",
        1,
    )
    with pytest.raises(AssertionError):
        _assert_named_block_snapshot(
            collapsed_boundary,
            "PLATFORM-ROLE-BOUNDARY",
            EXPECTED_PLATFORM_ROLE_BOUNDARY,
            "docs/ARCHITECTURE.md",
        )
    drifted = architecture.replace(
        "Deterministic tools; no planning, reasoning, orchestration, interpretation, or synthesis.",
        "Deterministic tools; no planning, reasoning, orchestration, interpretation, "
        "or synthesis. Also owns synthesis.",
        1,
    )
    with pytest.raises(AssertionError):
        _assert_named_block_snapshot(
            drifted,
            "PLATFORM-ROLE-BOUNDARY",
            EXPECTED_PLATFORM_ROLE_BOUNDARY,
            "docs/ARCHITECTURE.md",
        )

    charter = AUTHORITY_PATHS["charter"].read_text(encoding="utf-8")
    assert "编排 / 多跳 / 推理 / 叙述合成由**宿主 agent**完成" in charter
    assert "GUI 的价值在终端做不到的**呈现与交互**，零智能、零编排" in charter


def test_role_contract_rejects_appended_contradictions_and_external_duty_verbs() -> None:
    skill = AUTHORITY_PATHS["skill"].read_text(encoding="utf-8")
    _assert_named_block_snapshot(
        skill,
        "HOST-AGENT-ROUTING",
        EXPECTED_HOST_AGENT_ROUTING,
        "SKILL.md",
    )

    merged_bullets = skill.replace(
        "They also own orchestration.\n- Core calls remain deterministic",
        "They also own orchestration. - Core calls remain deterministic",
        1,
    )
    with pytest.raises(AssertionError):
        _assert_named_block_snapshot(
            merged_bullets,
            "HOST-AGENT-ROUTING",
            EXPECTED_HOST_AGENT_ROUTING,
            "SKILL.md",
        )

    architecture = AUTHORITY_PATHS["architecture"].read_text(encoding="utf-8")
    end_marker = "<!-- PLATFORM-SSOT:PLATFORM-ROLE-BOUNDARY:END -->"
    plural_drift = architecture.replace(
        end_marker,
        "Core and GUI are the planners and orchestrators.\n" + end_marker,
        1,
    )
    with pytest.raises(AssertionError):
        _assert_named_block_snapshot(
            plural_drift,
            "PLATFORM-ROLE-BOUNDARY",
            EXPECTED_PLATFORM_ROLE_BOUNDARY,
            "docs/ARCHITECTURE.md",
        )


def test_deprecation_text_names_owner_issue_and_runtime_state() -> None:
    api = AUTHORITY_PATHS["api"].read_text(encoding="utf-8")
    skill = AUTHORITY_PATHS["skill"].read_text(encoding="utf-8")
    _assert_named_block_snapshot(
        api,
        "SYNTHESIZE-TRANSITION",
        EXPECTED_API_SYNTHESIZE_TRANSITION,
        "docs/API.md",
    )
    _assert_named_block_snapshot(
        skill,
        "SYNTHESIZE-TRANSITION",
        EXPECTED_SKILL_SYNTHESIZE_TRANSITION,
        "SKILL.md",
    )

    api_rows = _markdown_rows(api)
    for key, expected_row in EXPECTED_API_CURRENT_ROWS.items():
        matches = [row for row in api_rows if row and row[0] == key]
        assert matches == [expected_row], f"docs/API.md current contract row drift for {key}"

    end_marker = "<!-- PLATFORM-SSOT:SYNTHESIZE-TRANSITION:END -->"
    drifted = api.replace(
        end_marker,
        "The #163 target is already implemented.\n" + end_marker,
        1,
    )
    with pytest.raises(AssertionError):
        _assert_named_block_snapshot(
            drifted,
            "SYNTHESIZE-TRANSITION",
            EXPECTED_API_SYNTHESIZE_TRANSITION,
            "docs/API.md",
        )


def test_api_performance_rows_match_current_deterministic_cli_truth() -> None:
    api = AUTHORITY_PATHS["api"].read_text(encoding="utf-8")
    api_rows = _markdown_rows(api)
    for key, expected_row in EXPECTED_API_PERFORMANCE_ROWS.items():
        matches = [row for row in api_rows if row and row[0] == key]
        assert matches == [expected_row], f"docs/API.md performance row drift for {key}"


def test_ci_hard_check_inventory_cannot_call_all_skipped_private_assertions_green() -> None:
    ci = AUTHORITY_PATHS["ci"].read_text(encoding="utf-8")
    _assert_named_block_snapshot(
        ci,
        "PUBLIC-BLOCKER-EXECUTION",
        EXPECTED_PUBLIC_BLOCKER_EXECUTION,
        "docs/CI_HARD_CHECKS.md",
    )
    drifted = ci.replace(
        "All-skipped assertion sets are not green", "All-skipped sets are green", 1
    )
    with pytest.raises(AssertionError):
        _assert_named_block_snapshot(
            drifted,
            "PUBLIC-BLOCKER-EXECUTION",
            EXPECTED_PUBLIC_BLOCKER_EXECUTION,
            "docs/CI_HARD_CHECKS.md",
        )
