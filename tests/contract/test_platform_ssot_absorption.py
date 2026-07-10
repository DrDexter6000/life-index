"""RED contracts for the D0 platform authority absorption.

These tests read repository-controlled public authority surfaces only.  Named
markers keep the checks away from historical notes and examples that may quote
superseded behavior.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AUTHORITY_PATHS = {
    "charter": REPO_ROOT / "CHARTER.md",
    "agents": REPO_ROOT / "AGENTS.md",
    "architecture": REPO_ROOT / "docs" / "ARCHITECTURE.md",
    "api": REPO_ROOT / "docs" / "API.md",
    "ci": REPO_ROOT / "docs" / "CI_HARD_CHECKS.md",
    "skill": REPO_ROOT / "SKILL.md",
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
API_SYNTHESIZE_CURRENT_FRAGMENTS = ("provider-backed", "llm synthesis", "trust gate")
CURRENT_SYNTHESIZE_RUNTIME_FRAGMENTS = (
    "--synthesize",
    *API_SYNTHESIZE_CURRENT_FRAGMENTS,
)
API_SYNTHESIZE_TRANSITION_POINTER = "see the named `--synthesize` transition authority block"
API_SYNTHESIZE_STALE_FRAGMENTS = (
    "deterministic scaffold",
    "deterministic answer scaffold",
)
HOST_AGENT_INTELLIGENCE_DUTIES = (
    "planning",
    "reasoning",
    "orchestration",
    "interpretation",
    "synthesis",
)


def _read_authority(name: str) -> str:
    return AUTHORITY_PATHS[name].read_text(encoding="utf-8")


def _marked_block(text: str, marker: str, source: str) -> str:
    start_marker = f"<!-- PLATFORM-SSOT:{marker}:START -->"
    end_marker = f"<!-- PLATFORM-SSOT:{marker}:END -->"
    assert text.count(start_marker) == 1 and text.count(end_marker) == 1, (
        f"{source} must contain exactly one {marker} authority block delimited by "
        f"{start_marker!r} and {end_marker!r}"
    )
    start = text.index(start_marker) + len(start_marker)
    end = text.index(end_marker, start)
    return text[start:end]


def _heading_section(text: str, heading: str) -> str:
    start = text.index(heading)
    heading_level = heading.split(maxsplit=1)[0]
    match = re.search(
        rf"^{re.escape(heading_level)}\s+",
        text[start + len(heading) :],
        flags=re.MULTILINE,
    )
    if match is None:
        return text[start:]
    return text[start : start + len(heading) + match.start()]


def _markdown_rows(block: str) -> list[tuple[str, ...]]:
    rows: list[tuple[str, ...]] = []
    for line in block.splitlines():
        stripped = line.strip()
        if not (stripped.startswith("|") and stripped.endswith("|")):
            continue
        cells = tuple(cell.strip() for cell in stripped[1:-1].split("|"))
        if cells and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
            continue
        rows.append(cells)
    return rows


def _named_markdown_table_rows(
    block: str,
    header: tuple[str, ...],
) -> list[tuple[str, ...]] | None:
    lines = block.splitlines()
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not (stripped.startswith("|") and stripped.endswith("|")):
            continue
        cells = tuple(cell.strip() for cell in stripped[1:-1].split("|"))
        if cells != header:
            continue

        data_rows: list[tuple[str, ...]] = []
        for row_line in lines[index + 1 :]:
            row_text = row_line.strip()
            if not (row_text.startswith("|") and row_text.endswith("|")):
                break
            row = tuple(cell.strip() for cell in row_text[1:-1].split("|"))
            if row and all(re.fullmatch(r":?-{3,}:?", cell) for cell in row):
                continue
            data_rows.append(row)
        return data_rows
    return None


def _current_runtime_statement(block: str) -> str | None:
    match = re.search(
        r"^Current runtime:\s*.*?(?=\n\s*\n|\Z)",
        block,
        flags=re.IGNORECASE | re.MULTILINE | re.DOTALL,
    )
    return match.group(0).strip() if match is not None else None


def _current_synthesize_runtime_errors(statement: str) -> list[str]:
    normalized = statement.lower().replace("trust-gate", "trust gate")
    errors = [
        f"Current runtime is missing {fragment!r}"
        for fragment in CURRENT_SYNTHESIZE_RUNTIME_FRAGMENTS
        if fragment not in normalized
    ]
    deprecated_current = re.search(
        r"--synthesize.{0,80}\b(?:is|acts as|behaves as)\s+"
        r"(?:already\s+)?(?:a\s+)?(?:deprecated(?:\s+no-op)?|no-op)\b",
        normalized,
        flags=re.IGNORECASE,
    )
    if deprecated_current is not None:
        errors.append("Current runtime must not claim --synthesize is already deprecated/no-op")
    return errors


def _current_target_errors(block: str) -> list[str]:
    errors: list[str] = []
    lowered = block.lower()
    current_statement = _current_runtime_statement(block)
    if current_statement is None:
        errors.append("missing an explicit Current runtime label")
    else:
        errors.extend(_current_synthesize_runtime_errors(current_statement))
    if "ratified target" not in lowered:
        errors.append("missing an explicit Ratified target label")
    if not re.search(
        r"design memo.{0,100}(?:is not|not a).{0,40}(?:ssot|authority)", block, re.I | re.S
    ):
        errors.append("must say the design memo is not an authority/SSOT")
    if not re.search(
        r"P0.{0,80}truth/safety.{0,120}GUI.{0,80}P1.{0,80}P2.{0,80}Gateway",
        block,
        re.IGNORECASE | re.DOTALL,
    ):
        errors.append("missing the ratified P0 -> GUI -> P1 -> read-only P2 Gateway sequence")
    issue_fragments = {
        "#163": ("recall", "provider", "synthesis"),
        "#162": ("transactional", "side-effect", "freshness"),
        "#165": ("backup", "restore", "recovery"),
        "#164": ("gateway", "typed", "projection"),
    }
    for issue, fragments in issue_fragments.items():
        issue_match = re.search(rf"{re.escape(issue)}[^\n]*", block, flags=re.IGNORECASE)
        if issue_match is None:
            errors.append(f"missing implementation status for {issue}")
            continue
        issue_line = issue_match.group(0)
        if not re.search(
            r"unimplemented|not yet implemented|pending implementation|待实现|尚未实现",
            issue_line,
            flags=re.IGNORECASE,
        ):
            errors.append(f"{issue} must be identified as unimplemented/pending")
        missing = [fragment for fragment in fragments if fragment not in issue_line.lower()]
        if missing:
            errors.append(f"{issue} status is missing target scope {missing!r}")
    return errors


def _domain_contract_errors(block: str) -> list[str]:
    errors: list[str] = []
    domain_rows = _named_markdown_table_rows(
        block,
        ("Candidate closed admission domain", "Status"),
    )
    if domain_rows is None:
        errors.append("missing the named Core admission-domain table")
        domain_rows = []

    actual_domains = tuple(row[0] if row else "" for row in domain_rows)
    if actual_domains != PROPOSED_CORE_DOMAINS:
        errors.append(
            "the proposed Core admission domains must be the exact closed seven-item list; "
            f"expected {PROPOSED_CORE_DOMAINS!r}, got {actual_domains!r}"
        )
    for row in domain_rows:
        if len(row) != 2:
            errors.append(f"malformed Core admission-domain row: {row!r}")
        elif row[1].strip().lower() != PENDING_OWNER_STATUS.lower():
            errors.append(f"{row[0]!r} is not marked {PENDING_OWNER_STATUS!r}")

    requirements = {
        "proposal is not active/approved/ratified": r"not active, approved, or ratified",
        "Charter eventual sole list authority": (r"CHARTER\.md\s+§1\.10.{0,80}sole list authority"),
        "closed enumeration": r"enumeration is closed",
        "new approval for every added domain": (
            r"every (?:new|added) domain.{0,80}new Human Owner substantive\s+approval"
        ),
        "Owner replaces only consumer evidence": (
            r"replace only (?:the )?[“\"']?second-production-consumer[”\"']? evidence"
        ),
        "determinism remains required": r"cannot waive.{0,160}determinism",
        "low/zero LLM remains required": r"cannot waive.{0,200}low/zero LLM",
        "cross-time stability remains required": (
            r"cannot waive.{0,240}cross-time semantic stability"
        ),
        "RFC/substantive gate remains required": (
            r"cannot waive.{0,280}RFC/substantive-gate evidence"
        ),
        "other Charter criteria remain required": (
            r"cannot waive.{0,360}other current Charter admission constraint"
        ),
    }
    for description, pattern in requirements.items():
        if re.search(pattern, block, flags=re.IGNORECASE | re.DOTALL) is None:
            errors.append(f"missing rule: {description}")
    return errors


def _valid_domain_fixture() -> str:
    rows = "\n".join(f"| {domain} | {PENDING_OWNER_STATUS} |" for domain in PROPOSED_CORE_DOMAINS)
    return f"""
| Candidate closed admission domain | Status |
|---|---|
{rows}

These domains are proposed only: they are not active, approved, or ratified
Charter authority. If approved, CHARTER.md §1.10 becomes the sole list authority.
The enumeration is closed. Every added domain requires new Human Owner substantive
approval. Human Owner approval may replace only second-production-consumer evidence;
it cannot waive determinism, low/zero LLM content, cross-time semantic stability,
RFC/substantive-gate evidence, or any other current Charter admission constraint.
"""


def _positive_core_intelligence_duties(statement: str) -> list[str]:
    if re.search(r"\bcore\b", statement, flags=re.IGNORECASE) is None:
        return []

    positives: list[str] = []
    clauses = re.split(r"\s+\bbut\b\s+|;", statement, flags=re.IGNORECASE)
    verb_pattern = re.compile(
        r"\b(?:owns?|performs?|handles?|is\s+responsible\s+for)\b",
        flags=re.IGNORECASE,
    )
    preverb_negation = re.compile(
        r"\bnever\b|\bcannot\b|\bcan['’]t\b|\b(?:do|does|did)\s+not\b",
        flags=re.IGNORECASE,
    )

    for clause in clauses:
        verbs = list(verb_pattern.finditer(clause))
        for index, verb in enumerate(verbs):
            prefix_start = verbs[index - 1].end() if index else 0
            prefix = clause[prefix_start : verb.start()]
            if preverb_negation.search(prefix) is not None:
                continue

            duties_end = verbs[index + 1].start() if index + 1 < len(verbs) else len(clause)
            duties = clause[verb.end() : duties_end].lower()
            if re.match(r"\s*(?:neither\b|no\b)", duties) is not None:
                continue

            for duty in HOST_AGENT_INTELLIGENCE_DUTIES:
                if re.search(rf"\b{re.escape(duty)}\b", duties) is None:
                    continue
                duty_negated = re.search(
                    rf"\b(?:no|not|nor|neither)\b" rf"(?:\W+\w+){{0,3}}\W+{re.escape(duty)}\b",
                    duties,
                )
                if duty_negated is None and duty not in positives:
                    positives.append(duty)
    return positives


def _role_contract_errors(block: str) -> list[str]:
    rows = {row[0].lower(): " ".join(row[1:]) for row in _markdown_rows(block) if len(row) >= 2}
    requirements = {
        "core": ("deterministic", "no planning, reasoning, orchestration, or synthesis"),
        "host agent + skill": (
            "owns",
            "planning",
            "multi-hop reasoning",
            "orchestration",
            "interpretation",
            "synthesis",
        ),
        "gui": ("presentation", "no intelligence", "strict adapter", "gui-owned"),
        "current bridge": ("non-core", "gui-owned"),
        "gateway": (
            "optional future",
            "typed 1:1 projection",
            "#164",
            "unimplemented",
            "not a second semantic api",
            "no intelligence",
        ),
    }
    errors: list[str] = []
    for role, fragments in requirements.items():
        value = rows.get(role, "").lower()
        missing = [fragment for fragment in fragments if fragment not in value]
        if missing:
            errors.append(f"{role!r} role is missing {missing!r}")

    prose = " ".join(
        line.strip()
        for line in block.splitlines()
        if line.strip() and not line.strip().startswith("|")
    )
    for statement in re.split(r"(?<=[.!?])\s+", prose):
        positive_duties = _positive_core_intelligence_duties(statement)
        if positive_duties:
            errors.append(
                "role prose assigns Host Agent intelligence duties to Core: "
                + ", ".join(positive_duties)
            )
            break
    return errors


def _valid_role_fixture() -> str:
    return "\n".join(
        (
            "",
            "| Role | Authority boundary |",
            "|---|---|",
            "| Core | Deterministic tools; no planning, reasoning, orchestration, "
            "or synthesis. |",
            "| Host Agent + Skill | Owns planning, multi-hop reasoning, orchestration, "
            "interpretation, and synthesis. |",
            "| GUI | Presentation only; no intelligence; strict adapter stays " "GUI-owned. |",
            "| Current bridge | Non-Core and GUI-owned. |",
            "| Gateway | Optional future typed 1:1 projection under #164; "
            "unimplemented; not a second semantic API; no intelligence. |",
            "",
        )
    )


def _deprecation_errors(block: str) -> list[str]:
    errors: list[str] = []
    current_statement = _current_runtime_statement(block)
    target = re.search(r"^Target under #163:\s*(.+)$", block, flags=re.IGNORECASE | re.MULTILINE)
    compatibility = re.search(r"^Compatibility:\s*(.+)$", block, flags=re.IGNORECASE | re.MULTILINE)
    if current_statement is None:
        errors.append("missing Current runtime line")
    else:
        errors.extend(_current_synthesize_runtime_errors(current_statement))
    if target is None:
        errors.append("missing Target under #163 line")
    else:
        target_line = target.group(1).lower()
        for fragment in ("--synthesize", "deprecated no-op", "not yet implemented"):
            if fragment not in target_line:
                errors.append(f"#163 target line is missing {fragment!r}")
    if compatibility is None or "at least two major versions" not in compatibility.group(1).lower():
        errors.append("compatibility must retain the flag for at least two major versions")
    return errors


def _valid_deprecation_fixture() -> str:
    return """
Current runtime: --synthesize requests provider-backed LLM synthesis and applies the trust gate.

Target under #163: --synthesize becomes a deprecated no-op; this is not yet implemented.

Compatibility: retain the flag for at least two major versions.
"""


def _api_synthesize_table_errors(text: str) -> list[str]:
    errors: list[str] = []
    row_patterns = {
        "answer consumer guidance": r"^\| `answer` / `answer\.\*` \|[^\n]+$",
        "synthesize flag combination": r"^\| `--synthesize` \|[^\n]+$",
        "evidence plus synthesize combination": (
            r"^\| `--include-evidence --synthesize` \|[^\n]+$"
        ),
    }
    required_fragments = (
        *API_SYNTHESIZE_CURRENT_FRAGMENTS,
        API_SYNTHESIZE_TRANSITION_POINTER,
    )
    for description, pattern in row_patterns.items():
        matches = re.findall(pattern, text, flags=re.MULTILINE)
        if len(matches) != 1:
            errors.append(f"{description} must have exactly one API table row")
            continue
        lowered = matches[0].lower()
        missing = [fragment for fragment in required_fragments if fragment not in lowered]
        if missing:
            errors.append(f"{description} is missing current behavior/pointer {missing!r}")
        stale = [fragment for fragment in API_SYNTHESIZE_STALE_FRAGMENTS if fragment in lowered]
        if stale:
            errors.append(f"{description} retains stale synthesize semantics {stale!r}")
    return errors


def _valid_api_synthesize_table_fixture() -> str:
    pointer = API_SYNTHESIZE_TRANSITION_POINTER
    return (
        "| `answer` / `answer.*` | Current `--synthesize` provider-backed LLM synthesis "
        f"+ trust gate output; {pointer}. | Display current answer output. | **stable** |\n"
        "| `--synthesize` | Build evidence internally; add current provider-backed LLM "
        f"synthesis + trust gate answer; {pointer}. |\n"
        "| `--include-evidence --synthesize` | Add evidence pack + current provider-backed "
        f"LLM synthesis + trust gate answer; {pointer}. |\n"
    )


def _ci_inventory_errors(block: str) -> list[str]:
    lowered = block.lower()
    requirements = {
        "public blocker executes a core assertion": (
            "public hard blocker is green only when at least one core assertion executed"
        ),
        "all-skipped cannot be green": "all-skipped assertion sets are not green",
        "private-only evidence is advisory": "private-only assertions are advisory",
        "private-only evidence cannot block": (
            "cannot be the sole evidence for a tier 1 public blocker"
        ),
    }
    return [description for description, phrase in requirements.items() if phrase not in lowered]


def test_authority_surfaces_distinguish_current_behavior_from_ratified_target() -> None:
    charter = _read_authority("charter")
    agents = _read_authority("agents")
    architecture = _read_authority("architecture")

    assert "CHARTER.md（本文件，最高权威）" in charter
    assert "1. `CHARTER.md` owns constitutional invariants." in agents
    block = _marked_block(architecture, "CURRENT-TARGET-STATUS", "docs/ARCHITECTURE.md")
    assert _current_target_errors(block) == [], "; ".join(_current_target_errors(block))
    deprecated_current = block.replace(
        "`--synthesize` still has provider-backed LLM synthesis and trust-gate behavior,",
        "`--synthesize` is already a deprecated no-op,",
        1,
    )
    deprecated_current_errors = _current_target_errors(deprecated_current)
    assert any(
        "already deprecated/no-op" in error for error in deprecated_current_errors
    ), f"Architecture current-runtime drift escaped validation: {deprecated_current_errors!r}"


def test_closed_core_admission_domains_are_exact_owner_gated_and_preserve_other_criteria() -> None:
    valid = _valid_domain_fixture()
    assert _domain_contract_errors(valid) == []

    removed = valid.replace(f"| {PROPOSED_CORE_DOMAINS[0]} | {PENDING_OWNER_STATUS} |\n", "", 1)
    assert any(
        "exact closed seven-item list" in error for error in _domain_contract_errors(removed)
    )
    proposal_start = "\n\nThese domains are proposed only:"
    extra_row = f"\n| Workflow orchestration | {PENDING_OWNER_STATUS} |"
    extra = valid.replace(proposal_start, f"{extra_row}{proposal_start}", 1)
    assert any("exact closed seven-item list" in error for error in _domain_contract_errors(extra))
    unrecognized_status_extra = valid.replace(
        proposal_start,
        f"\n| Workflow orchestration | draft-only |{proposal_start}",
        1,
    )
    unrecognized_status_errors = _domain_contract_errors(unrecognized_status_extra)
    assert any(
        "exact closed seven-item list" in error for error in unrecognized_status_errors
    ), f"unrecognized-status domain row escaped validation: {unrecognized_status_errors!r}"
    weakened = valid.replace(
        "may replace only second-production-consumer evidence",
        "may replace every admission criterion",
        1,
    )
    assert any(
        "Owner replaces only consumer evidence" in error
        for error in _domain_contract_errors(weakened)
    )

    charter_section = _heading_section(_read_authority("charter"), "### §1.10")
    block = _marked_block(charter_section, "CORE-ADMISSION-DOMAINS", "CHARTER.md §1.10")
    assert _domain_contract_errors(block) == [], "; ".join(_domain_contract_errors(block))


def test_no_authority_surface_assigns_intelligence_to_core_gui_or_gateway() -> None:
    valid = _valid_role_fixture()
    assert _role_contract_errors(valid) == []
    drifted = valid.replace(
        "no planning, reasoning, orchestration, or synthesis",
        "owns planning, reasoning, orchestration, and synthesis",
        1,
    )
    assert _role_contract_errors(drifted) != []
    contradictory_prose = valid + "\nCore owns planning, reasoning, orchestration, and synthesis.\n"
    contradictory_errors = _role_contract_errors(contradictory_prose)
    assert any(
        "prose assigns Host Agent intelligence duties to Core" in error
        for error in contradictory_errors
    ), f"contradictory Core prose escaped validation: {contradictory_errors!r}"
    matrix_failures: list[str] = []
    valid_negatives = (
        "Core never owns planning.",
        "Core never handles reasoning.",
        "Core does not own orchestration.",
        "Core owns neither planning nor synthesis.",
        "Core owns no planning, reasoning, orchestration, interpretation, or synthesis.",
    )
    for statement in valid_negatives:
        negative_errors = _role_contract_errors(valid + f"\n{statement}\n")
        if negative_errors:
            matrix_failures.append(f"valid negative rejected: {statement!r}: {negative_errors!r}")

    positive_assignments = tuple(
        f"Core owns {duty}." for duty in HOST_AGENT_INTELLIGENCE_DUTIES
    ) + ("Core owns planning and synthesis.",)
    for statement in positive_assignments:
        positive_errors = _role_contract_errors(valid + f"\n{statement}\n")
        if not any(
            "prose assigns Host Agent intelligence duties to Core" in error
            for error in positive_errors
        ):
            matrix_failures.append(f"positive assignment accepted: {statement!r}")

    mixed_statement = "Core does not own planning but owns synthesis."
    mixed_errors = _role_contract_errors(valid + f"\n{mixed_statement}\n")
    if not any(
        "prose assigns Host Agent intelligence duties to Core: synthesis" in error
        for error in mixed_errors
    ):
        matrix_failures.append(
            f"mixed positive synthesis escaped: {mixed_statement!r}: {mixed_errors!r}"
        )

    assert matrix_failures == [], "; ".join(matrix_failures)

    apex = _heading_section(_read_authority("charter"), "## 北极星")
    assert "编排 / 多跳 / 推理 / 叙述合成由**宿主 agent**完成" in apex
    assert "GUI 的价值在终端做不到的**呈现与交互**，零智能、零编排" in apex

    architecture = _read_authority("architecture")
    block = _marked_block(architecture, "PLATFORM-ROLE-BOUNDARY", "docs/ARCHITECTURE.md")
    assert _role_contract_errors(block) == [], "; ".join(_role_contract_errors(block))


def test_deprecation_text_names_owner_issue_and_runtime_state() -> None:
    errors: list[str] = []
    valid_deprecation = _valid_deprecation_fixture()
    assert _deprecation_errors(valid_deprecation) == []
    contradictory_current = valid_deprecation.replace(
        "applies the trust gate.",
        "applies the trust gate; --synthesize is already deprecated.",
        1,
    )
    if not any(
        "already deprecated/no-op" in error for error in _deprecation_errors(contradictory_current)
    ):
        errors.append("Current-runtime already-deprecated claim escaped validation")

    valid_table_errors = _api_synthesize_table_errors(_valid_api_synthesize_table_fixture())
    if valid_table_errors:
        errors.append(
            "current synthesize rows with a named transition pointer were rejected: "
            f"{valid_table_errors!r}"
        )

    for authority_name, source in (("api", "docs/API.md"), ("skill", "SKILL.md")):
        text = _read_authority(authority_name)
        try:
            block = _marked_block(text, "SYNTHESIZE-TRANSITION", source)
        except AssertionError as exc:
            errors.append(str(exc))
            continue
        errors.extend(f"{source}: {error}" for error in _deprecation_errors(block))

    errors.extend(
        f"docs/API.md: {error}" for error in _api_synthesize_table_errors(_read_authority("api"))
    )

    assert errors == [], "; ".join(errors)


def test_ci_hard_check_inventory_cannot_call_all_skipped_private_assertions_green() -> None:
    valid = """
A public hard blocker is green only when at least one core assertion executed.
All-skipped assertion sets are not green. Private-only assertions are advisory and
cannot be the sole evidence for a Tier 1 public blocker.
"""
    assert _ci_inventory_errors(valid) == []
    drifted = valid.replace("are not green", "are green", 1)
    assert "all-skipped cannot be green" in _ci_inventory_errors(drifted)

    block = _marked_block(
        _read_authority("ci"),
        "PUBLIC-BLOCKER-EXECUTION",
        "docs/CI_HARD_CHECKS.md",
    )
    assert _ci_inventory_errors(block) == [], "; ".join(_ci_inventory_errors(block))
