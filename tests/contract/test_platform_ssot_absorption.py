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
EXPECTED_ARCHITECTURE_TARGET_STATUSES = {
    "#163": "recall/eval correction and provider-backed synthesis retirement: unimplemented.",
    "#162": "transactional write, side-effect, and freshness repair: unimplemented.",
    "#165": "backup, restore, and recovery proof: unimplemented.",
    "#164": "optional Gateway typed 1:1 projection: unimplemented.",
}
EXPECTED_SYNTHESIZE_TRANSITION_LINES = {
    "Current runtime": (
        "`--synthesize` requests provider-backed LLM synthesis and applies the trust gate "
        "when its runtime prerequisites are available."
    ),
    "Target under #163": (
        "`--synthesize` becomes a deprecated no-op; this is not yet implemented."
    ),
    "Compatibility": (
        "retain the accepted flag for at least two major versions after the #163 transition "
        "is implemented."
    ),
}
ARCHITECTURE_FORBIDDEN_CURRENT_STATE_PATTERNS = (
    r"\balready\s+(?:a\s+)?deprecated\b",
    r"\bdeprecated\s+no-op\b",
    r"\balready\s+been\s+retired\b",
    r"\bno\s+longer\s+does\s+anything\b",
)
FORBIDDEN_DOMAIN_WAIVER_PATTERNS = {
    "determinism": r"\b(?:may|can)\s+waive\s+(?:the\s+)?determinism\b",
    "low/zero LLM content": r"\b(?:may|can)\s+waive\s+(?:the\s+)?low/zero llm content\b",
    "cross-time semantic stability": (
        r"\b(?:may|can)\s+waive\s+(?:the\s+)?cross-time semantic stability\b"
    ),
    "RFC/substantive-gate evidence": (
        r"\b(?:may|can)\s+waive\s+(?:the\s+)?rfc/substantive-gate evidence\b"
    ),
    "other current Charter constraints": (
        r"\b(?:may|can)\s+waive\s+(?:(?:any|all)\s+)?other current charter "
        r"(?:admission )?constraints?\b"
    ),
}
API_SYNTHESIZE_TRANSITION_POINTER = "see the named `--synthesize` transition authority block"
API_SYNTHESIZE_STALE_FRAGMENTS = (
    "deterministic scaffold",
    "deterministic answer scaffold",
)
EXPECTED_ROLE_BOUNDARIES = {
    "Core": (
        "Deterministic tools; no planning, reasoning, orchestration, interpretation, "
        "or synthesis."
    ),
    "Host Agent + Skill": (
        "Owns planning, multi-hop reasoning, orchestration, interpretation, and synthesis."
    ),
    "GUI": "Presentation only; no intelligence; strict adapter stays GUI-owned.",
    "Current bridge": "Non-Core and GUI-owned.",
    "Gateway": (
        "Optional future typed 1:1 projection under #164; unimplemented; not a second "
        "semantic API; no intelligence."
    ),
}
ROLE_DUTY_TOKENS = frozenset(
    {
        "plan",
        "plans",
        "planned",
        "planning",
        "reason",
        "reasons",
        "reasoned",
        "reasoning",
        "orchestrate",
        "orchestrates",
        "orchestrated",
        "orchestrating",
        "orchestration",
        "interpret",
        "interprets",
        "interpreted",
        "interpreting",
        "interpretation",
        "synthesize",
        "synthesizes",
        "synthesized",
        "synthesizing",
        "synthesis",
        "planner",
        "reasoner",
        "orchestrator",
        "interpreter",
        "synthesizer",
        "synthesiser",
    }
)


def _read_authority(name: str) -> str:
    return AUTHORITY_PATHS[name].read_text(encoding="utf-8")


def _normalize_contract_text(value: str) -> str:
    return " ".join(value.casefold().split())


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


def _single_named_table_rows(
    block: str,
    header: tuple[str, ...],
    table_name: str,
) -> tuple[list[tuple[str, ...]], list[str]]:
    markdown_rows = _markdown_rows(block)
    table_count = markdown_rows.count(header)
    errors: list[str] = []
    if table_count != 1:
        errors.append(f"expected exactly one named {table_name} table, found {table_count}")

    named_rows = _named_markdown_table_rows(block, header)
    rows = named_rows or []
    if named_rows is not None and markdown_rows != [header, *rows]:
        errors.append(
            f"parallel/unexpected {table_name} table rows outside the named {table_name} table"
        )
    return rows, errors


def _current_runtime_statement(block: str) -> str | None:
    match = re.search(
        r"^Current runtime:\s*.*?(?=\n\s*\n|\Z)",
        block,
        flags=re.IGNORECASE | re.MULTILINE | re.DOTALL,
    )
    return match.group(0).strip() if match is not None else None


def _exact_labeled_line_errors(block: str, expected_lines: dict[str, str]) -> list[str]:
    errors: list[str] = []
    for label, expected in expected_lines.items():
        matches = re.findall(
            rf"^{re.escape(label)}:\s*(.*?)\s*$",
            block,
            flags=re.IGNORECASE | re.MULTILINE,
        )
        if len(matches) != 1:
            errors.append(f"expected exactly one {label!r} line, found {len(matches)}")
        elif _normalize_contract_text(matches[0]) != _normalize_contract_text(expected):
            errors.append(f"{label!r} line must exactly match {expected!r}; got {matches[0]!r}")
    return errors


def _architecture_current_synthesize_errors(statement: str) -> list[str]:
    normalized = _normalize_contract_text(statement).replace("trust-gate", "trust gate")
    errors = [
        f"Current runtime is missing {fragment!r}"
        for fragment in CURRENT_SYNTHESIZE_RUNTIME_FRAGMENTS
        if fragment not in normalized
    ]
    if any(
        re.search(pattern, normalized) for pattern in ARCHITECTURE_FORBIDDEN_CURRENT_STATE_PATTERNS
    ):
        errors.append(
            "Current runtime must not claim --synthesize is already deprecated/no-op/retired"
        )
    return errors


def _current_target_errors(block: str) -> list[str]:
    errors: list[str] = []
    lowered = block.lower()
    current_statement = _current_runtime_statement(block)
    if current_statement is None:
        errors.append("missing an explicit Current runtime label")
    else:
        errors.extend(_architecture_current_synthesize_errors(current_statement))
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
    actual_status_lines = tuple(
        _normalize_contract_text(line)
        for line in block.splitlines()
        if re.match(r"^\s*-\s*#\d+\b", line)
    )
    expected_status_lines = tuple(
        _normalize_contract_text(f"- {issue} — {status}")
        for issue, status in EXPECTED_ARCHITECTURE_TARGET_STATUSES.items()
    )
    if actual_status_lines != expected_status_lines:
        errors.append(
            "Architecture target issue status lines must exactly match the four ratified "
            f"unimplemented targets; got {actual_status_lines!r}"
        )
    return errors


def _domain_contract_errors(block: str) -> list[str]:
    domain_rows, errors = _single_named_table_rows(
        block,
        ("Candidate closed admission domain", "Status"),
        "Core admission-domain",
    )

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
    normalized = _normalize_contract_text(block)
    for criterion, pattern in FORBIDDEN_DOMAIN_WAIVER_PATTERNS.items():
        if re.search(pattern, normalized):
            errors.append(f"Human Owner approval must not affirmatively waive {criterion}")
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


def _role_contract_errors(block: str) -> list[str]:
    expected_boundaries = {
        _normalize_contract_text(role): _normalize_contract_text(boundary)
        for role, boundary in EXPECTED_ROLE_BOUNDARIES.items()
    }
    header = ("Role", "Authority boundary")
    role_rows, errors = _single_named_table_rows(block, header, "role")

    parsed_rows: list[tuple[str, str]] = []
    for row in role_rows:
        if len(row) != 2:
            errors.append(f"malformed role row: {row!r}")
            continue
        parsed_rows.append((row[0], row[1]))

    expected_roles = set(expected_boundaries)
    normalized_roles = [_normalize_contract_text(role) for role, _ in parsed_rows]
    duplicates = sorted({role for role in normalized_roles if normalized_roles.count(role) > 1})
    unexpected = sorted({role for role in normalized_roles if role not in expected_roles})
    missing_roles = sorted(expected_roles - set(normalized_roles))
    if duplicates:
        errors.append("duplicate role rows: " + ", ".join(duplicates))
    if unexpected:
        errors.append("unexpected role rows: " + ", ".join(unexpected))
    if missing_roles:
        errors.append("missing role rows: " + ", ".join(missing_roles))

    rows_by_role: dict[str, str] = {}
    for role, boundary in parsed_rows:
        rows_by_role.setdefault(_normalize_contract_text(role), boundary)
    for role, expected_boundary in EXPECTED_ROLE_BOUNDARIES.items():
        normalized_role = _normalize_contract_text(role)
        value = rows_by_role.get(normalized_role)
        if value is None:
            continue
        if _normalize_contract_text(value) != expected_boundaries[normalized_role]:
            errors.append(
                f"{role!r} role boundary must exactly match {expected_boundary!r}; "
                f"got {value!r}"
            )

    prose = "\n".join(
        line.strip()
        for line in block.splitlines()
        if line.strip() and not line.strip().startswith("|")
    )
    prose_tokens = set(re.findall(r"[a-z]+", prose.casefold()))
    prose_duties = sorted(ROLE_DUTY_TOKENS & prose_tokens)
    if prose_duties:
        errors.append(
            "role duties are allowed only in the named role table: " + ", ".join(prose_duties)
        )
    return errors


def _valid_role_fixture() -> str:
    rows = [f"| {role} | {boundary} |" for role, boundary in EXPECTED_ROLE_BOUNDARIES.items()]
    return "\n".join(
        (
            "",
            "| Role | Authority boundary |",
            "|---|---|",
            *rows,
            "",
        )
    )


def _deprecation_errors(block: str) -> list[str]:
    return _exact_labeled_line_errors(block, EXPECTED_SYNTHESIZE_TRANSITION_LINES)


def _valid_deprecation_fixture() -> str:
    lines = [f"{label}: {value}" for label, value in EXPECTED_SYNTHESIZE_TRANSITION_LINES.items()]
    return "\n" + "\n\n".join(lines) + "\n"


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

    current_statement = _current_runtime_statement(block)
    assert current_statement is not None
    architecture_state_cases = [
        (
            "current runtime retired/no-effect paraphrase",
            block.replace(
                current_statement,
                current_statement
                + " --synthesize has already been retired and no longer does anything.",
                1,
            ),
        )
    ]
    for issue in ("#163", "#162", "#165", "#164"):
        issue_line = next(line for line in block.splitlines() if issue in line)
        contradiction = (
            "Implemented, not unimplemented." if issue == "#163" else "Already implemented."
        )
        architecture_state_cases.append(
            (
                f"{issue} contradictory implementation status",
                block.replace(issue_line, f"{issue_line} {contradiction}", 1),
            )
        )
    escaped_architecture_states = [
        description
        for description, drifted_block in architecture_state_cases
        if not _current_target_errors(drifted_block)
    ]
    assert (
        escaped_architecture_states == []
    ), "Architecture current/target state drift escaped validation: " + ", ".join(
        escaped_architecture_states
    )


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

    alternate_table = valid + f"""
| Alternate admission domain | Status |
|---|---|
| Workflow orchestration | {PENDING_OWNER_STATUS} |
"""
    domain_drift_cases = [
        ("second alternate domain table", alternate_table),
        ("determinism waiver", valid + "\nHuman Owner approval may waive determinism.\n"),
        (
            "low/zero LLM waiver",
            valid + "\nHuman Owner approval may waive low/zero LLM content.\n",
        ),
        (
            "cross-time stability waiver",
            valid + "\nHuman Owner approval may waive cross-time semantic stability.\n",
        ),
        (
            "RFC/substantive-gate waiver",
            valid + "\nHuman Owner approval may waive RFC/substantive-gate evidence.\n",
        ),
        (
            "other Charter constraints waiver",
            valid
            + "\nHuman Owner approval may waive any other current Charter admission constraint.\n",
        ),
    ]
    escaped_domain_drift = [
        description
        for description, drifted_block in domain_drift_cases
        if not _domain_contract_errors(drifted_block)
    ]
    assert escaped_domain_drift == [], "domain-contract drift escaped validation: " + ", ".join(
        escaped_domain_drift
    )

    charter_section = _heading_section(_read_authority("charter"), "### §1.10")
    block = _marked_block(charter_section, "CORE-ADMISSION-DOMAINS", "CHARTER.md §1.10")
    assert _domain_contract_errors(block) == [], "; ".join(_domain_contract_errors(block))


def test_no_authority_surface_assigns_intelligence_to_core_gui_or_gateway() -> None:
    valid = _valid_role_fixture()
    assert _role_contract_errors(valid) == []
    core_row = f"| Core | {EXPECTED_ROLE_BOUNDARIES['Core']} |"
    structural_cases = (
        (
            "duplicate Core row",
            valid.replace(core_row, f"{core_row}\n{core_row}", 1),
            "duplicate role rows",
        ),
        ("duplicate role table", valid + valid, "exactly one named role table"),
        (
            "unexpected role row",
            valid.replace(core_row, f"{core_row}\n| Runtime | Transport only. |", 1),
            "unexpected role rows",
        ),
        (
            "parallel role prose",
            valid + "\nHost Agent owns planning while Core owns synthesis.\n",
            "role duties are allowed only in the named role table",
        ),
        (
            "parallel role table",
            valid + "\n| Component | Responsibility |\n"
            "|---|---|\n"
            "| Core | Owns synthesis. |\n",
            "parallel/unexpected role table",
        ),
    )
    missed_structural_drift: list[str] = []
    for description, drifted_block, expected_error in structural_cases:
        drift_errors = _role_contract_errors(drifted_block)
        if not any(expected_error in error for error in drift_errors):
            missed_structural_drift.append(
                f"{description}: expected {expected_error!r}, got {drift_errors!r}"
            )
    assert missed_structural_drift == [], "; ".join(missed_structural_drift)

    drifted = valid.replace(
        "no planning, reasoning, orchestration, interpretation, or synthesis",
        "owns planning, reasoning, orchestration, interpretation, and synthesis",
        1,
    )
    assert _role_contract_errors(drifted) != []

    apex = _heading_section(_read_authority("charter"), "## 北极星")
    assert "编排 / 多跳 / 推理 / 叙述合成由**宿主 agent**完成" in apex
    assert "GUI 的价值在终端做不到的**呈现与交互**，零智能、零编排" in apex

    architecture = _read_authority("architecture")
    block = _marked_block(architecture, "PLATFORM-ROLE-BOUNDARY", "docs/ARCHITECTURE.md")
    assert _role_contract_errors(block) == [], "; ".join(_role_contract_errors(block))


def test_role_contract_rejects_appended_contradictions_and_external_duty_verbs() -> None:
    valid = _valid_role_fixture()
    drift_cases = (
        (
            "Core appended synthesis/interpretation ownership",
            valid.replace(
                "or synthesis. |",
                "or synthesis. Also owns synthesis/interpretation. |",
                1,
            ),
        ),
        (
            "GUI appended planning ownership",
            valid.replace(
                "strict adapter stays GUI-owned. |",
                "strict adapter stays GUI-owned. Owns planning. |",
                1,
            ),
        ),
        (
            "Gateway appended reasoning duty",
            valid.replace(
                "not a second semantic API; no intelligence. |",
                "not a second semantic API; no intelligence. Handles reasoning. |",
                1,
            ),
        ),
        ("external plans verb", valid + "\nCore plans requests.\n"),
        ("external orchestrates verb", valid + "\nCore orchestrates tools.\n"),
        ("external synthesizes verb", valid + "\nCore synthesizes answers.\n"),
        ("external planner noun", valid + "\nCore is the planner.\n"),
        ("external reasoner noun", valid + "\nCore is the reasoner.\n"),
        ("external orchestrator noun", valid + "\nCore is the orchestrator.\n"),
        ("external interpreter noun", valid + "\nGUI is the interpreter.\n"),
        ("external synthesizer noun", valid + "\nGateway is the synthesizer.\n"),
        ("external synthesiser noun", valid + "\nGateway is the synthesiser.\n"),
    )
    escaped_drift = [
        description
        for description, drifted_block in drift_cases
        if not _role_contract_errors(drifted_block)
    ]
    assert escaped_drift == [], "role-contract drift escaped validation: " + ", ".join(
        escaped_drift
    )


def test_deprecation_text_names_owner_issue_and_runtime_state() -> None:
    errors: list[str] = []
    valid_deprecation = _valid_deprecation_fixture()
    assert _deprecation_errors(valid_deprecation) == []
    contradictory_current = re.sub(
        r"^Current runtime:[^\n]+$",
        lambda match: f"{match.group(0)} --synthesize is already deprecated.",
        valid_deprecation,
        count=1,
        flags=re.MULTILINE,
    )
    if not _deprecation_errors(contradictory_current):
        errors.append("Current-runtime already-deprecated claim escaped validation")

    state_drift_specs = (
        (
            "Current runtime",
            "--synthesize has already been retired and no longer does anything.",
        ),
        ("Target under #163", "It is already implemented."),
        ("Target under #163", "It is implemented, not unimplemented."),
    )
    for label, contradiction in state_drift_specs:
        drifted = re.sub(
            rf"^{re.escape(label)}:[^\n]+$",
            lambda match: f"{match.group(0)} {contradiction}",
            valid_deprecation,
            count=1,
            flags=re.MULTILINE,
        )
        if not _deprecation_errors(drifted):
            errors.append(f"{label} contradiction escaped validation: {contradiction}")

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
