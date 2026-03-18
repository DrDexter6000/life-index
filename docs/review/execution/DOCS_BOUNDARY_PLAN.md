# Docs Boundary Plan

> **Document role**: Define documentation authority, ownership, update propagation, and lifecycle rules for the review bundle and upstream SSOT docs
> **Audience**: Project Owner, reviewers, implementers, and future agents
> **Authority**: Review-scoped documentation governance artifact; does not replace upstream SSOT
> **Primary goal**: Ensure the `docs/review/` bundle stays maintainable, upgradable, and non-duplicative over time

---

## 1. Why this document exists

The biggest long-term risk of a rich review bundle is not that it gets written.

The biggest risk is that it becomes:

- stale
- duplicative
- contradictory to upstream docs
- unclear about who should update what

This document exists to prevent that.

It defines:

1. which documents have authority
2. which documents are derivative
3. how updates propagate
4. when review docs should be revised, archived, or retired

---

## 2. Documentation tiers

## Tier 1 — Upstream SSOT / hard authority

These documents own formal truth in their domains.

| Document | Owns | Must not own |
|:---|:---|:---|
| `docs/API.md` | tool parameters, outputs, errors, recovery contract | roadmap, review diagnosis, project planning |
| `docs/ARCHITECTURE.md` | architecture principles, ADR-style system reasoning | execution-phase planning, eval corpus management |
| `SKILL.md` | skill runtime flow, agent-facing usage guidance | long-horizon roadmap, governance planning |
| `docs/CHANGELOG.md` | historical changes already accepted into project history | future plan, speculative diagnosis |
| `pyproject.toml` | packaging, entrypoints, dependency truth | narrative system guidance |

### Tier 1 rule

If a Tier 1 document and a review document disagree, **Tier 1 wins**.

---

## Tier 2 — Review-scoped governance and execution docs

These documents live under `docs/review/` and exist to:

- diagnose current state
- define review-phase contracts
- organize evaluation
- guide later implementation work

These documents may:

- interpret upstream truth
- highlight gaps
- define provisional execution rules for review work

These documents must not:

- redefine official tool APIs
- silently replace runtime workflow truth
- become hidden ADRs that bypass `docs/ARCHITECTURE.md`

---

## Tier 3 — Execution evidence and review outputs

These are the most perishable documents in the bundle.

Examples:

- `docs/review/evals/PHASE1_CHECKLIST_REVIEW.md`
- `docs/review/evals/BASELINE_EVALUATION_REVIEW.md`
- future baseline run result docs

These documents do not define truth. They record:

- what was evaluated
- what was found
- what the current gap picture is

They should be updated or superseded as new review runs happen.

---

## 3. Ownership model

Every document in `docs/review/` should conceptually have four roles:

| Role | Meaning |
|:---|:---|
| Owner | The person/agent actively maintaining the document |
| Reviewer | The person/agent checking consistency and non-duplication |
| Upstream authority | The Tier 1 source(s) this document depends on |
| Successor path | Where this document’s conclusions should flow next |

### Default ownership rule

If no explicit owner is assigned:

- Owner = current implementer / active agent
- Reviewer = separate reviewer agent or human maintainer
- Upstream authority = the Tier 1 docs explicitly named in the file header

---

## 4. Update propagation rules

This is the most important section for keeping the bundle valid over time.

## Rule 1 — Upstream truth changes must trigger review-bundle audit

If any of these change materially:

- `docs/API.md`
- `docs/ARCHITECTURE.md`
- `SKILL.md`
- tool behavior in `tools/`

Then the owner must audit affected `docs/review/` files.

### Minimum audit questions

1. Does the review doc now contradict the upstream truth?
2. Does the review doc still describe the right boundary?
3. Is the review doc still useful, or has it become stale history?

---

## Rule 2 — Review docs never silently become permanent SSOT

If a review-phase conclusion becomes stable project truth, it must be promoted to the correct upstream home.

Examples:

- API truth → `docs/API.md`
- architecture truth → `docs/ARCHITECTURE.md`
- skill runtime workflow truth → `SKILL.md`
- permanent historical note → `docs/CHANGELOG.md`

Only after promotion should the review doc be updated to reference that upstream adoption.

---

## Rule 3 — Promotion before duplication

When a review document contains a conclusion that is now settled, do **not** copy-paste that truth into multiple places ad hoc.

Instead:

1. promote the settled truth to the correct Tier 1 document
2. update the review doc to say the conclusion has been adopted upstream
3. reduce the review doc to governance/evaluation context rather than duplicated truth text

---

## Rule 4 — Evaluation outputs should supersede, not stack forever

Evaluation result documents should not accumulate endlessly with no lifecycle.

When a newer baseline run supersedes an older one:

- keep the historical artifact
- mark it as superseded
- point to the newer result document

This keeps historical traceability without forcing readers to guess which result is current.

---

## 5. Recommended lifecycle per review document type

| Doc type | Expected lifespan | Maintenance rule |
|:---|:---|:---|
| `PROJECT_DIAGNOSIS_AND_ROADMAP.md` | medium | update only when project diagnosis or roadmap materially changes |
| `execution/*.md` contract docs | medium | update when upstream behavior or accepted boundaries change |
| `evals/*_CASES.md` corpora | medium-long | expand or refine when eval scope improves |
| checklist review / baseline result docs | short-medium | supersede with dated newer review results |

---

## 6. Recommended change flow

When project behavior changes, use this order:

1. Determine whether the change is:
   - API truth
   - architecture truth
   - skill/runtime truth
   - review-only execution/governance truth
2. Update the correct Tier 1 doc first **if the change is permanent project truth**
3. Audit affected review docs
4. Update the review docs so they:
   - reflect the new upstream truth
   - do not keep stale contradictory wording
5. If a review result is superseded, mark it clearly

---

## 7. Anti-duplication rules

The following are not allowed as steady-state behavior:

- a review doc redefining API parameter truth
- a review doc becoming the only place that describes accepted runtime workflow
- multiple docs carrying slightly different versions of the same settled rule
- leaving superseded review findings active without marking them stale

---

## 8. Practical maintenance checklist

Whenever the project is optimized, upgraded, or refactored, ask:

- [ ] Did any Tier 1 truth change?
- [ ] If yes, which `docs/review/` files now need audit?
- [ ] Has any review-phase conclusion now become permanent truth?
- [ ] If yes, was it promoted upstream?
- [ ] Does any review result doc need to be marked superseded?
- [ ] Are we keeping one current “active baseline” result and not multiple competing ones?

---

## 9. Current recommendation for this project

For the current Life Index state:

- keep `docs/review/` as a **review bundle namespace**
- treat it as a controlled staging area for:
  - diagnosis
  - contract clarification
  - evaluation design
  - baseline review outputs
- do not treat it as the final resting place of permanent API/workflow/architecture truth

That is how this bundle remains useful without becoming a second undocumented SSOT tree.

---

## 10. Bottom line

To keep this bundle valid over time:

1. **Tier 1 owns permanent truth**
2. **`docs/review/` owns diagnosis, provisional contracts, eval design, and review outputs**
3. **settled truths must be promoted upstream**
4. **review outputs must be superseded consciously, not left to drift**

That is the maintenance model that allows these documents to survive optimization, upgrades, and refactors without turning into noise.
