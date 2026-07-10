"""D0 contracts for the named platform authority snapshots."""

from __future__ import annotations

import difflib
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
    "shipped_skill": REPO_ROOT / "tools" / "_skill_artifacts" / "SKILL.md",
}

PROPOSED_CORE_DOMAINS = (
    "Canonical journal and attachment mutation",
    "Schema, validation, migration, transaction, locking, and audit",
    "Deterministic indexing, retrieval, freshness, and evidence navigation",
    "Deterministic aggregation and analysis",
    "Entity graph",
    "Integrity, health, backup, restore, and recovery",
    "Deterministic contract and eval verification",
)
PENDING_OWNER_STATUS = "proposed / pending Human Owner substantive approval"

EXPECTED_CURRENT_TARGET_STATUS = """
### Platform program: current runtime vs ratified target

Current runtime: direct CLI/Core contracts are the implemented public route;
`--synthesize` still has provider-backed LLM synthesis and trust-gate behavior,
the current bridge is non-Core and GUI-owned, and the later P0/P1/P2 work below
has not been implemented. The design memo is not an authority or SSOT; it is
Owner-ratified decision background being absorbed into the existing authority
chain. The exact closed §1.10 admission-domain candidate remains pending Human
Owner substantive approval.

Ratified target phase sequence: P0 truth/safety repair -> GUI activation and
strict-adapter proof -> P1 -> read-only P2 Gateway. These target decisions do
not describe current runtime completion:

- #163 — recall/eval correction and provider-backed synthesis retirement: unimplemented.
- #162 — transactional write, side-effect, and freshness repair: unimplemented.
- #165 — backup, restore, and recovery proof: unimplemented.
- #164 — optional Gateway typed 1:1 projection: unimplemented.
"""

EXPECTED_SMART_SEARCH_CURRENT_CONTRACT = "\n".join(
    (
        "### Smart-search current contract",
        "",
        "- Default/no-flag `life-index smart-search` returns a deterministic scaffold.",
        "- Current explicit `--synthesize` still requests provider-backed LLM synthesis and applies the trust gate when its runtime prerequisites are available.",  # noqa: E501
        "- Target under #163: `--synthesize` becomes a deprecated no-op; this is not yet implemented.",  # noqa: E501
        "- Host Agent + Skill remain the target intelligence owner.",
    )
)

EXPECTED_CORE_ADMISSION_DOMAINS = "\n".join(
    (
        "#### Pending §1.9 / §1.10 amendment candidate — not active Charter authority",
        "",
        "This candidate resolves the APEX conflict only if it later passes §5.2. On",
        "approval, the stale §1.9 P0→P1→P2→deterministic-only provider-fallback",
        "direction is superseded: the Host Agent + Skill own planning, multi-hop",
        "reasoning, orchestration, interpretation, and synthesis; Core remains",
        "deterministic; GUI remains presentation-only; and an optional Gateway cannot",
        "own intelligence or semantics. The current provider-backed `--synthesize`",
        "runtime remains a compatibility fact until #163 implements its separately",
        "approved deprecated-no-op target.",
        "",
        "| Candidate closed admission domain | Status |",
        "|---|---|",
        "| Canonical journal and attachment mutation | proposed / pending Human Owner substantive approval |",  # noqa: E501
        "| Schema, validation, migration, transaction, locking, and audit | proposed / pending Human Owner substantive approval |",  # noqa: E501
        "| Deterministic indexing, retrieval, freshness, and evidence navigation | proposed / pending Human Owner substantive approval |",  # noqa: E501
        "| Deterministic aggregation and analysis | proposed / pending Human Owner substantive approval |",  # noqa: E501
        "| Entity graph | proposed / pending Human Owner substantive approval |",
        "| Integrity, health, backup, restore, and recovery | proposed / pending Human Owner substantive approval |",  # noqa: E501
        "| Deterministic contract and eval verification | proposed / pending Human Owner substantive approval |",  # noqa: E501
        "",
        "These domains are proposed only: they are not active, approved, or ratified",
        "Charter authority. If approved, CHARTER.md §1.10 becomes the sole list authority;",
        "lower-level documents must point here and must not duplicate the catalog. The",
        "enumeration is closed. Every added domain requires new Human Owner substantive",
        "approval.",
        "",
        "Human Owner approval may replace only second-production-consumer evidence. It",
        "cannot waive determinism, low/zero LLM content, cross-time semantic stability,",
        "RFC/substantive-gate evidence, or any other current Charter admission constraint.",
        "",
        "**Substantive-gate candidate record**:",
        "",
        "- **Rationale**: align stale §1.9 fallback language with APEX and make Core",
        "  admission reviewable against one closed, long-lived set of domains.",
        "- **Opposition addressed**: (1) removing a standalone provider fallback may",
        "  inconvenience direct CLI users, so #163 retains `--synthesize` as a deprecated",
        "  no-op for at least two major versions after the target is implemented; (2) a",
        "  closed list may delay a valuable primitive, so each addition remains possible",
        "  through new Human Owner substantive approval without weakening the other",
        "  admission criteria.",
        "- **Impact**: this candidate affects §1.9 / §1.10 interpretation and the public",
        "  architecture, API, CI, and Skill pointers only. It does not implement #163,",
        "  #162, #165, or #164 and does not change runtime or data contracts.",
        "- **Rollback**: before approval, withdraw or revise this candidate as one unit;",
        "  the currently ratified Charter text remains in force.",
        "- **Gold Set regression**: pending before land; no result is claimed by this",
        "  docs-only candidate.",
        "- **Human Owner ack**: PENDING — the exact seven-domain list has not received",
        "  Human Owner substantive approval.",
        "",
        "Accordingly this candidate is not land-ready, does not increment the Charter",
        "version / revision / approval date, and cannot authorize D0 GO or integration.",
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
        "use does not depend on it. The eventual closed admission-domain catalog belongs",
        "only to `CHARTER.md §1.10` after Human Owner substantive approval.",
    )
)

SYNTHESIZE_TRANSITION_SEMANTICS = "\n".join(
    (
        "Current runtime: `--synthesize` requests provider-backed LLM synthesis and applies the trust gate when its runtime prerequisites are available.",  # noqa: E501
        "",
        "Target under #163: `--synthesize` becomes a deprecated no-op; this is not yet implemented.",  # noqa: E501
        "",
        "Compatibility: retain the accepted flag for at least two major versions after the #163 transition is implemented.",  # noqa: E501
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
        "当前 `--synthesize` 的 provider-backed LLM synthesis + trust gate 输出；"
        "see the named `--synthesize` transition authority block",
        "优先展示当前 answer output",
        "**stable**",
    ),
    "`--synthesize`": (
        "`--synthesize`",
        "内部构建 evidence；当前添加 provider-backed LLM synthesis + trust gate answer；"
        "see the named `--synthesize` transition authority block",
    ),
    "`--include-evidence --synthesize`": (
        "`--include-evidence --synthesize`",
        "添加 evidence_pack + 当前 provider-backed LLM synthesis + trust gate answer；"
        "see the named `--synthesize` transition authority block",
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


def test_authority_surfaces_distinguish_current_behavior_from_ratified_target() -> None:
    charter = AUTHORITY_PATHS["charter"].read_text(encoding="utf-8")
    agents = AUTHORITY_PATHS["agents"].read_text(encoding="utf-8")
    architecture = AUTHORITY_PATHS["architecture"].read_text(encoding="utf-8")

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

    smart_search_end = "<!-- PLATFORM-SSOT:SMART-SEARCH-CURRENT-CONTRACT:END -->"
    absolute_claim = architecture.replace(
        smart_search_end,
        "- `smart-search` only emits deterministic output.\n" + smart_search_end,
        1,
    )
    with pytest.raises(AssertionError):
        _assert_named_block_snapshot(
            absolute_claim,
            "SMART-SEARCH-CURRENT-CONTRACT",
            EXPECTED_SMART_SEARCH_CURRENT_CONTRACT,
            "docs/ARCHITECTURE.md",
        )

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


def test_closed_core_admission_domains_are_exact_owner_gated_and_preserve_other_criteria() -> None:
    charter = AUTHORITY_PATHS["charter"].read_text(encoding="utf-8")
    block = _assert_named_block_snapshot(
        charter,
        "CORE-ADMISSION-DOMAINS",
        EXPECTED_CORE_ADMISSION_DOMAINS,
        "CHARTER.md §1.10",
    )
    expected_rows = [
        ("Candidate closed admission domain", "Status"),
        *((domain, PENDING_OWNER_STATUS) for domain in PROPOSED_CORE_DOMAINS),
    ]
    assert _markdown_rows(block) == expected_rows

    first_row = f"| {PROPOSED_CORE_DOMAINS[0]} | {PENDING_OWNER_STATUS} |"
    last_row = f"| {PROPOSED_CORE_DOMAINS[-1]} | {PENDING_OWNER_STATUS} |"
    end_marker = "<!-- PLATFORM-SSOT:CORE-ADMISSION-DOMAINS:END -->"
    drifted_documents = (
        charter.replace(first_row + "\n", "", 1),
        charter.replace(
            last_row,
            last_row + f"\n| Workflow orchestration | {PENDING_OWNER_STATUS} |",
            1,
        ),
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
    skill_bytes = AUTHORITY_PATHS["skill"].read_bytes()
    shipped_bytes = AUTHORITY_PATHS["shipped_skill"].read_bytes()
    assert skill_bytes == shipped_bytes, "packaged Skill artifact drifted from canonical SKILL.md"
    skill = skill_bytes.decode("utf-8")
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
