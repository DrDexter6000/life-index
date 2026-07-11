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
    "版本": "v1.11.0",
    "批准日期": "2026-07-11",
    "修订次数": "11",
}
INTELLIGENCE_OWNER_RULE = (
    "Host Agent + Skill own provider selection and all planning, multi-hop reasoning, "
    "orchestration, interpretation, and synthesis."
)
CURRENT_SYNTHESIZE_TRUTH = (
    "The accepted `--synthesize` flag is retained for at least two major versions. "
    "It has no provider/client/LLM injection path, emits no `answer`, and preserves "
    "the ordinary deterministic domain output."
)
SYNTHESIZE_FOLLOW_ON_TRUTH = (
    "#163 remains open for eval/A5 removal and the remaining D1-A work. This "
    "implemented A3/A4 truth does not claim A5, #163, or the D1 phase complete."
)
STABLE_DISTRIBUTION_HOST_OPERATIONS_RULE = "\n".join(
    (
        "- `Distribution/Host Operations` is the sole bounded non-Core category. It is",
        "  limited to install, version, and host-playbook lifecycle operations.",
        "  Co-packaging or shared command dispatch grants no Core authority. It cannot",
        "  own canonical journal, frontmatter, entity, or search semantics; be a Core",
        "  correctness dependency; or create Core-admission precedent.",
    )
)
STABLE_WEATHER_EXCEPTION_RULE = "\n".join(
    (
        "- `weather` is the sole named `Legacy External Adapter` compatibility exception.",
        "  It is optional and must not decide or block canonical journal-write success.",
        "  Outbound weather requests may send only the minimum location and date context",
        "  required for the lookup.",
        "  #166 tracks current runtime behavior and disposition; D0 does not claim",
        "  current runtime compliance. It creates no Core-admission precedent.",
    )
)
STABLE_OWNER_GATE_RULE = "\n".join(
    (
        "- Any new Core domain, non-Core category, or compatibility exception requires",
        "  new Human Owner substantive approval.",
    )
)
CLASSIFICATION_OWNERSHIP_NOT_CERTIFICATION_RULE = "\n".join(
    (
        "**Classification assigns ownership, not certification**:",
        "",
        "- A classification assigns constitutional ownership/admission; it does not",
        "  certify that every current route or option complies with this Charter.",
        "- A shipped or reachable route or option that violates this Charter remains",
        "  an implementation defect. Reachability grants no approval, sanction,",
        "  grandfathering, Non-Core status, compatibility exception, or Core-admission",
        "  precedent.",
    )
)
CHARTER_ARCHITECTURE_AUTHORITY_SPLIT = "\n".join(
    (
        "`CHARTER.md §1.10` is the sole authority for the stable C1–C7 and non-Core",
        "classification rules and the sole named compatibility exception.",
        "`docs/ARCHITECTURE.md` owns only the exhaustive current 31-route mapping under",
        "those rules; it does not own or duplicate them.",
    )
)
EXPECTED_STABLE_NON_CORE_CLASSIFICATION_RULES = "\n".join(
    (
        "**Stable non-Core classification rules**:",
        "",
        STABLE_DISTRIBUTION_HOST_OPERATIONS_RULE,
        STABLE_WEATHER_EXCEPTION_RULE,
        STABLE_OWNER_GATE_RULE,
        "",
        CLASSIFICATION_OWNERSHIP_NOT_CERTIFICATION_RULE,
        "",
        CHARTER_ARCHITECTURE_AUTHORITY_SPLIT,
    )
)
ARCHITECTURE_CLASSIFICATION_POINTER = "\n".join(
    (
        "This table is the exhaustive current 31-route mapping under the Charter-owned",
        "C1–C7 and stable non-Core classification rules in `CHARTER.md §1.10`.",
        "It maps current routes only; it does not own or duplicate those stable rules.",
    )
)
EXPECTED_ARCHITECTURE_EVAL_LLM_DEVIATION = "\n".join(
    (
        "### Eval language-judge compatibility boundary",
        "",
        "`eval` remains Core under C7. The public command classification is a",
        "constitutional ownership/admission map, not a certification that every current",
        "route or option complies.",
        "",
        "Current runtime: the product CLI recognizes `life-index eval --judge llm` but",
        "returns a stable non-success result before evaluation, configuration reading,",
        "or provider-module import. It does not silently fall back to keyword and does",
        "not claim a language-assisted evaluation ran.",
        "",
        "Production `tools/eval` contains only deterministic C7 measurement and",
        "serialization behavior; language-assisted evaluation belongs to Host Agent +",
        "Life Index Skill. The A5 candidate does not close #163 or complete D1-A before",
        "review and adjudication.",
    )
)
EXPECTED_API_EVAL_LLM_TRANSITION = "\n".join(
    (
        "### `eval --judge llm` compatibility boundary",
        "",
        "`life-index eval --judge llm` remains recognizable for compatibility, but it",
        "fails before evaluation or any provider/configuration import. The stable",
        "non-success payload is:",
        "",
        "```json",
        "{",
        '  "success": false,',
        '  "error": {',
        '    "code": "EVAL_LLM_JUDGE_HOST_AGENT_REQUIRED",',
        '    "message": "Language-assisted evaluation belongs to the Host Agent + '
        'Life Index Skill."',
        "  }",
        "}",
        "```",
        "",
        "There is no fallback to keyword and no provider/model recommendation. The A5",
        "candidate removes product eval provider selection, prompts, clients, and calls",
        "while preserving deterministic C7 metrics. #163 remains open pending review;",
        "this runtime fact does not close the Issue or complete D1-A.",
    )
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

The following program work remains incomplete; D0 ratification did not itself
implement it:

"""
    "- #163 — smart-search A3/A4 is implemented, and the A5 candidate makes eval "
    "deterministic-only: `--judge llm` fails before provider/configuration import, "
    "production eval provider/prompt/client ownership is removed, and the public hard "
    "check scans search, smart-search, and eval roots. #163 remains open pending review, "
    "so D1-A is not complete.\n"
    """- #162 — transactional write, side-effect, and freshness repair: unimplemented.
- #165 — backup, restore, and recovery proof: unimplemented.
- #164 — optional Core Capability Gateway typed 1:1 projection: unimplemented.
"""
)

EXPECTED_SMART_SEARCH_CURRENT_CONTRACT = "\n".join(
    (
        "### Smart-search current contract",
        "",
        "- Default/no-flag `life-index smart-search` returns a deterministic scaffold.",
        "- Current explicit `--synthesize` is accepted for at least two major versions. The product CLI constructs `SmartSearchOrchestrator()` with no injection surface, emits no `answer`, and preserves the ordinary deterministic domain payload.",  # noqa: E501
        "- The CLI emits exactly one stderr warning: `DEPRECATED: --synthesize is a compatibility no-op; synthesis belongs to the Host Agent + Life Index Skill.`",  # noqa: E501
        "- Search/smart-search production packages contain no dormant/injectable LLM rewrite, filter, provider, prompt, trust-gate, or synthesis implementation; the Tier 1 no-LLM hard check enforces the documented static structural policy over these production roots.",  # noqa: E501
        "- A5 extends the deterministic-only boundary and structural scan to product eval; #163 remains open pending review, so D1-A is not complete.",  # noqa: E501
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
        "Core Capability Gateway cannot own intelligence or semantics. The accepted `--synthesize`",
        "flag is retained for at least two major versions, has no provider/client/LLM",
        "injection path, emits no `answer`, preserves ordinary deterministic domain output,",
        "and emits exactly one stderr warning: `DEPRECATED: --synthesize is a compatibility",
        "no-op; synthesis belongs to the Host Agent + Life Index Skill.` Eval/A5 and the",
        "remaining #163 work are pending; A3/A4 does not claim A5, #163, or D1 complete.",
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
        EXPECTED_STABLE_NON_CORE_CLASSIFICATION_RULES,
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
        "| Core Capability Gateway | Optional future typed 1:1 projection under #164; unimplemented; not a second semantic API; no intelligence. |",  # noqa: E501
        "",
        "The table above is the sole normative role-assignment surface in this block.",
        "The future Core Capability Gateway, if implemented, is only a contract-equivalent transport of",  # noqa: E501
        "Core operations. It cannot create a parallel semantic contract, and direct Core",
        "use does not depend on it. The active closed admission-domain catalog belongs",
        "only to `CHARTER.md §1.10`; this document references C1–C7 without duplicating",
        "their domain descriptions.",
    )
)

EXPECTED_ADVANCED_ADDON_CHARTER_INVARIANT = (
    "Future advanced Addons are dual-channel consumers: deterministic data, view, and "
    "atomic operations use the canonical Core Capability Contract, while semantic "
    "understanding, multi-step retrieval or orchestration, interpretation, and synthesis "
    "use the shared Host Agent Handoff and Host Agent + Life Index Skill/Domain Skill. "
    "An Addon is presentation + Domain Skill + an optional deterministic helper; it "
    "cannot own an LLM/provider/runtime or bypass Core to read or write L1. An optional "
    "deterministic helper enters Core only under the already-ratified closed C1-C7 "
    "admission model or new Human Owner substantive approval; otherwise it remains "
    "Addon-local."
)

EXPECTED_ADVANCED_ADDON_DUAL_CHANNEL = "\n".join(
    (
        "### Future advanced Addon dual-channel boundary",
        "",
        "This is normative guidance for future advanced Addons, not an implemented Addon",
        "contract, SDK, runtime, schema, or UI. An advanced Addon is composed of a",
        "presentation layer, a Domain Skill, and, only when needed, an optional",
        "deterministic helper.",
        "",
        "```text",
        "User <-> Addon presentation",
        "           |-- deterministic data/view/atomic operation",
        "           |     -> Core Capability Contract",
        "           |        -> direct local CLI or optional Core Capability Gateway projection",
        "           |           -> Core -> L1",
        "           |-- semantic understanding/multi-step retrieval/orchestration/interpretation/synthesis",  # noqa: E501
        "                 -> shared Host Agent Handoff",
        "                    -> Host Agent + Life Index Skill + Domain Skill",
        "                       -> Core Capability Contract for deterministic evidence/operations",
        "```",
        "",
        "#### Access paths",
        "",
        "| Need | Required path | Boundary |",
        "|---|---|---|",
        "| Deterministic data, view, or atomic operation | Addon presentation/helper -> Core Capability Contract | May call the local CLI directly or use a contract-equivalent Core Capability Gateway projection; no Host Agent round trip is required. |",  # noqa: E501
        "| Semantic understanding, multi-step retrieval or orchestration, interpretation, or synthesis | Addon presentation -> shared Host Agent Handoff -> Host Agent + Life Index Skill/Domain Skill | The Host Agent owns intelligence and uses the Core Capability Contract for deterministic evidence and operations. |",  # noqa: E501
        "",
        "#### State ownership",
        "",
        "| State | Owner | Rule |",
        "|---|---|---|",
        "| Canonical durable journal, frontmatter, entity, index, and metric state | L1/L2 through Core | Addons and Host Agents never create a second truth source or bypass Core. |",  # noqa: E501
        "| Reasoning, orchestration, and agent-session state | Host Agent/runtime | It remains outside Core and is not owned by the Addon presentation or helper. |",  # noqa: E501
        "| Presentation and user-visible draft state | Addon | It is non-canonical, replaceable, and cannot become a Core correctness dependency. |",  # noqa: E501
        "| Optional deterministic-helper state | Addon unless admitted to Core | It remains local, non-canonical, clearable, and cannot read or write L1 directly. |",  # noqa: E501
        "",
        "#### Optional deterministic-helper admission",
        "",
        "| Candidate | Decision |",
        "|---|---|",
        "| Already covered by the closed C1-C7 Core authority | Consume the canonical Core capability; do not duplicate it in the Addon. |",  # noqa: E501
        "| Satisfies every already-ratified admission constraint and belongs within C1-C7, or receives new Human Owner substantive approval for the required authority expansion | Propose Core admission through the existing RFC/substantive-gate process; determinism and all non-waivable constraints still apply. |",  # noqa: E501
        "| Does not satisfy those conditions | Keep it Addon-local and non-canonical. |",
        "| Performs semantic understanding, orchestration, interpretation, or synthesis | It is not a deterministic helper; route it through the shared Host Agent Handoff and Host Agent + Skills. |",  # noqa: E501
        "",
        "#### Prohibitions and gateway distinction",
        "",
        "- An Addon must not own an LLM, provider selection, API-key handling, or an agent runtime.",  # noqa: E501
        "- An Addon and its helper must not bypass Core to read or write L1, duplicate a canonical Core capability, or duplicate runtime adapters.",  # noqa: E501
        "- A Core Capability Gateway, if implemented, is only a typed transport projection of the canonical Core Capability Contract. It is not an Agent Runtime Gateway, Host Agent, Life Index brain, reasoning or session owner, or provider boundary.",  # noqa: E501
        "- The local CLI remains a canonical direct Core consumer surface. A Core Capability Gateway is optional and cannot become mandatory for direct Core use or replace the CLI.",  # noqa: E501
        "",
        "Advanced Addon implementation, its SDK and schemas, placeholder UI, and later",
        "program phases remain deferred. This boundary does not claim that any such runtime",
        "surface exists.",
    )
)

SYNTHESIZE_TRANSITION_SEMANTICS = "\n".join(
    (
        "Current runtime: the product CLI accepts `--synthesize` for at least two major versions and constructs `SmartSearchOrchestrator()` with no injection surface. It emits no `answer` and preserves the ordinary deterministic domain payload.",  # noqa: E501
        "",
        "Current warning: exactly one stderr line is emitted: `DEPRECATED: --synthesize is a compatibility no-op; synthesis belongs to the Host Agent + Life Index Skill.`",  # noqa: E501
        "",
        "A3/A4 implementation: search/smart-search production packages contain no dormant/injectable LLM rewrite, filter, provider, prompt, trust-gate, or synthesis implementation. The Tier 1 no-LLM hard check enforces the documented static structural policy over these production roots. A5 extends the deterministic-only boundary and structural scan to product eval; #163 remains open pending review, so D1-A is not complete.",  # noqa: E501
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

The public #163 ownership invariant is implemented: the Tier 1 no-LLM check
scans every Python AST in search/smart-search/eval for known provider imports
and aliases, normalized LLM/provider/model-client declarations and storage,
simple provider bindings, provider-specific SDK call suffixes regardless of
owner name, and generic provider verbs only with structural provider provenance.
It also rejects legacy prompt/trust/synthesis ownership and constant-string
dynamic imports supplied as the first positional argument or `name=` keyword.
Syntax/parse failure is non-green. This is a
static structural boundary, not a universal proof against computed strings or
arbitrary runtime metaprogramming.

The blocker job first runs `.github/scripts/run_public_core_assertions.py`. Its
JSON sentinel is the assertion-count authority: green requires at least one
executed public synthetic token-match assertion. Zero collected, missing,
deselected, all-skipped, or setup-skipped assertions are non-green. Private
eval and broad/noise/quality metrics remain advisory and cannot satisfy this
count or defend result deletion.
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
        "当前产品 CLI 不输出；`--synthesize` 不注入 LLM、不添加 `answer`，并保持普通 "
        "deterministic domain payload；see the named `--synthesize` transition authority block",
        "当前无此字段；语言合成由 Host Agent + Skill 完成",
        "**stable**",
    ),
    "`--synthesize`": (
        "`--synthesize`",
        "当前接受至少两个主版本；stderr 发出一次稳定弃用警告；不注入 LLM、不添加 `answer`，"
        "domain payload 与普通调用等价",
    ),
    "`--include-evidence --synthesize`": (
        "`--include-evidence --synthesize`",
        "添加 evidence_pack；stderr 发出一次稳定弃用警告；`--synthesize` 不改变 JSON/domain 输出",
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
    return str(matches[0]).strip()


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
    assert latest_revision.startswith("2026-07-11")
    assert "Addon dual-channel boundary" in latest_revision
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
    assert "SmartSearchOrchestrator()" in smart_search_cli

    smart_search_end = "<!-- PLATFORM-SSOT:SMART-SEARCH-CURRENT-CONTRACT:END -->"
    provider_backed_drift = architecture.replace(
        smart_search_end,
        "- Current `--synthesize` also requests provider-backed LLM synthesis.\n"
        + smart_search_end,
        1,
    )
    assert (
        "constructs `SmartSearchOrchestrator()` with no injection surface" in provider_backed_drift
    )
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


def test_charter_owns_stable_non_core_rules_and_architecture_only_maps_routes() -> None:
    charter = AUTHORITY_PATHS["charter"].read_text(encoding="utf-8")
    architecture = AUTHORITY_PATHS["architecture"].read_text(encoding="utf-8")

    charter_start = "<!-- PLATFORM-SSOT:CORE-ADMISSION-DOMAINS:START -->"
    charter_end = "<!-- PLATFORM-SSOT:CORE-ADMISSION-DOMAINS:END -->"
    assert charter.count(charter_start) == charter.count(charter_end) == 1
    charter_block = charter[
        charter.index(charter_start) + len(charter_start) : charter.index(charter_end)
    ]

    for stable_rule in (
        STABLE_DISTRIBUTION_HOST_OPERATIONS_RULE,
        STABLE_WEATHER_EXCEPTION_RULE,
        STABLE_OWNER_GATE_RULE,
    ):
        assert stable_rule in charter_block
    assert EXPECTED_STABLE_NON_CORE_CLASSIFICATION_RULES in charter_block
    assert charter_block.count("`Distribution/Host Operations`") == 1
    assert charter_block.count("`Legacy External Adapter`") == 1
    assert "| Command | Classification | Authority refs |" not in charter_block

    architecture_start = "<!-- PLATFORM-SSOT:PUBLIC-COMMAND-CLASSIFICATION:START -->"
    architecture_end = "<!-- PLATFORM-SSOT:PUBLIC-COMMAND-CLASSIFICATION:END -->"
    assert architecture.count(architecture_start) == architecture.count(architecture_end) == 1
    architecture_block = architecture[
        architecture.index(architecture_start)
        + len(architecture_start) : architecture.index(architecture_end)
    ]

    assert ARCHITECTURE_CLASSIFICATION_POINTER in architecture_block
    for stable_rule in (
        STABLE_DISTRIBUTION_HOST_OPERATIONS_RULE,
        STABLE_WEATHER_EXCEPTION_RULE,
        STABLE_OWNER_GATE_RULE,
    ):
        assert stable_rule not in architecture_block
    assert (
        "Distribution/Host Operations are non-Core even when co-packaged" not in architecture_block
    )
    assert (
        "Any new Core domain, non-Core category, or compatibility exception"
        not in architecture_block
    )

    minimum_weather_context = "\n".join(
        (
            "Outbound weather requests may send only the minimum location and date context",
            "  required for the lookup.",
        )
    )
    overbroad_weather_contexts = (
        "Outbound weather requests may send journal content and frontmatter when useful.",
        "Outbound weather requests may send necessary context for the lookup.",
    )
    for overbroad_context in overbroad_weather_contexts:
        drifted = charter.replace(minimum_weather_context, overbroad_context, 1)
        assert drifted != charter
        with pytest.raises(AssertionError):
            _assert_named_block_snapshot(
                drifted,
                "CORE-ADMISSION-DOMAINS",
                EXPECTED_CORE_ADMISSION_DOMAINS,
                "CHARTER.md §1.10",
            )


def test_classification_assigns_ownership_without_certifying_runtime_compliance() -> None:
    charter = AUTHORITY_PATHS["charter"].read_text(encoding="utf-8")
    architecture = AUTHORITY_PATHS["architecture"].read_text(encoding="utf-8")

    charter_start = "<!-- PLATFORM-SSOT:CORE-ADMISSION-DOMAINS:START -->"
    charter_end = "<!-- PLATFORM-SSOT:CORE-ADMISSION-DOMAINS:END -->"
    charter_block = charter[
        charter.index(charter_start) + len(charter_start) : charter.index(charter_end)
    ]
    assert CLASSIFICATION_OWNERSHIP_NOT_CERTIFICATION_RULE in charter_block
    assert "| Command | Classification | Authority refs |" not in charter_block

    classification_start = "<!-- PLATFORM-SSOT:PUBLIC-COMMAND-CLASSIFICATION:START -->"
    classification_end = "<!-- PLATFORM-SSOT:PUBLIC-COMMAND-CLASSIFICATION:END -->"
    classification_block = architecture[
        architecture.index(classification_start)
        + len(classification_start) : architecture.index(classification_end)
    ]
    assert "### Public command constitutional ownership/admission mapping" in classification_block
    assert classification_block.count("| eval | Core | C7 |") == 1

    drifted = charter.replace(
        "Reachability grants no approval, sanction,\n"
        "  grandfathering, Non-Core status, compatibility exception, or Core-admission\n"
        "  precedent.",
        "Reachability makes violating options grandfathered and approved.",
        1,
    )
    with pytest.raises(AssertionError):
        _assert_named_block_snapshot(
            drifted,
            "CORE-ADMISSION-DOMAINS",
            EXPECTED_CORE_ADMISSION_DOMAINS,
            "CHARTER.md §1.10",
        )


def test_eval_language_judge_fails_before_provider_ownership() -> None:
    architecture = AUTHORITY_PATHS["architecture"].read_text(encoding="utf-8")
    api = AUTHORITY_PATHS["api"].read_text(encoding="utf-8")

    _assert_named_block_snapshot(
        architecture,
        "EVAL-LLM-DEVIATION",
        EXPECTED_ARCHITECTURE_EVAL_LLM_DEVIATION,
        "docs/ARCHITECTURE.md",
    )
    _assert_named_block_snapshot(
        api,
        "EVAL-LLM-TRANSITION",
        EXPECTED_API_EVAL_LLM_TRANSITION,
        "docs/API.md",
    )
    assert architecture.count("| eval | Core | C7 |") == 1

    forbidden_drifts = (
        (
            "returns a stable non-success result before evaluation, configuration reading,",
            "loads provider configuration before returning a non-success result,",
        ),
        (
            "language-assisted evaluation belongs to Host Agent +",
            "language-assisted evaluation belongs to Core +",
        ),
    )
    for current, forbidden in forbidden_drifts:
        drifted = architecture.replace(current, forbidden, 1)
        assert drifted != architecture
        with pytest.raises(AssertionError):
            _assert_named_block_snapshot(
                drifted,
                "EVAL-LLM-DEVIATION",
                EXPECTED_ARCHITECTURE_EVAL_LLM_DEVIATION,
                "docs/ARCHITECTURE.md",
            )


@pytest.mark.parametrize(
    "path",
    (
        REPO_ROOT / "CHARTER.md",
        REPO_ROOT / "docs" / "API.md",
        REPO_ROOT / "docs" / "ARCHITECTURE.md",
        REPO_ROOT / "docs" / "CI_HARD_CHECKS.md",
        REPO_ROOT / "SKILL.md",
        REPO_ROOT / "tools" / "_skill_artifacts" / "SKILL.md",
    ),
)
def test_public_eval_authorities_do_not_publish_private_corpus_fingerprints(
    path: Path,
) -> None:
    text = path.read_text(encoding="utf-8")
    private_fingerprints = (
        "Round 17 冻结基线",
        "实测基线（Round 17",
        "85 queries",
        "0.3836",
        "0.3565",
        "0.2716",
        "golden_queries.yaml",
        "golden_rejection_queries.yaml",
        "15 个 broad recall",
        "precision < 0.8",
        "68 篇日志",
        "108-query",
        "tests/eval/baselines/",
        "65 篇日志",
        "晴岚",
        "王某某",
        "wife-001",
        "C:/Users/example/Documents/Life-Index",
    )

    matches = [item for item in private_fingerprints if item in text]
    matches.extend(re.findall(r"\b(?:GQ|AGQ|SAGQ)\d+\b", text))
    assert matches == []


def test_public_aggregate_eval_contract_has_no_private_case_values() -> None:
    api = AUTHORITY_PATHS["api"].read_text(encoding="utf-8")
    aggregate_eval_section = api.split(
        "### Aggregate Evaluation Coverage (Internal Developer Tooling)", 1
    )[1].split("#### Diagnostic-Only Mode", 1)[0]

    concrete_measurements = re.findall(
        r'"(?:total_queries|passed_queries|failed_queries|query_count|count|pass_rate)"'
        r"\s*:\s*-?\d+(?:\.\d+)?",
        aggregate_eval_section,
    )
    private_case_ids = re.findall(
        r"\b(?:GQ|AGQ|SAGQ)\d+\b",
        aggregate_eval_section,
    )

    assert concrete_measurements == []
    assert private_case_ids == []
    assert '"late sleep"' not in aggregate_eval_section
    assert "entry_time_after=22:00" not in aggregate_eval_section


def test_architecture_describes_broad_private_eval_as_advisory_only() -> None:
    architecture = AUTHORITY_PATHS["architecture"].read_text(encoding="utf-8")
    assert (
        "Broad/private quality metrics remain observable and advisory; weak or errored "
        "broad metrics do not enter blocking failures or override exact Core results."
        in architecture
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


def test_advanced_addon_dual_channel_boundary_has_one_constitutional_owner() -> None:
    charter = AUTHORITY_PATHS["charter"].read_text(encoding="utf-8")
    architecture = AUTHORITY_PATHS["architecture"].read_text(encoding="utf-8")

    assert charter.count(EXPECTED_ADVANCED_ADDON_CHARTER_INVARIANT) == 1
    block = _assert_named_block_snapshot(
        architecture,
        "ADVANCED-ADDON-DUAL-CHANNEL",
        EXPECTED_ADVANCED_ADDON_DUAL_CHANNEL,
        "docs/ARCHITECTURE.md",
    )

    assert "closed C1-C7 Core authority" in block
    assert "| C1 |" not in block
    for _, domain_name in RATIFIED_CORE_DOMAINS:
        assert domain_name not in block


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
