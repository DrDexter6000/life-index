# Product Boundary Review

Status: completed  
Priority: P0  
Owner: current CTO discussion track  
Scope: define the boundary between Life Index core product, host-agent / host-platform orchestration, and any future application layer  
Plan type: planning-only, no implementation in this pass  
Execution style: evidence-first, boundary-first, anti-expansion

## 1. Mission

Determine the cleanest product boundary for Life Index now that scheduler governance and release / upgrade governance have already been narrowed and formalized.

This review must answer three things clearly:

1. What Life Index core product actually is in v1.x
2. What belongs to agent or host-platform orchestration rather than core
3. What kinds of future "application layer" ideas may be explored later without silently redefining the product today

This plan is for decision quality first. It does **not** authorize code changes by itself.

## 2. Why this review is next

Two strategic topics were just settled:

- scheduler scope was narrowed to optional host-platform automation guidance
- release / version / upgrade policy was formalized around a repo-first, local-first, compatibility-biased model

Those two conclusions remove a lot of noise. What remains is the broader product question:

> Is Life Index primarily a journaling core with agent orchestration around it, or is it drifting toward a larger lifestyle application?

This question matters now because it affects:

- roadmap discipline
- future workflow design
- whether more orchestration logic should move into tools
- whether any future UI / app surface should be considered a thin shell or a new product layer

## 3. Highest-confidence working hypothesis

Current strongest hypothesis:

> Life Index v1.x should remain a **local-first personal journaling core** with **agent-first orchestration** and **no mandatory app layer**.  
> Any future application layer should be treated as an optional shell around the same durable data and explicit tool contracts, not as a replacement for the core product identity.

This hypothesis must still be tested against repo evidence and contradiction review.

## 4. Repo-grounded evidence already visible

## 4.1 Identity evidence from README

The README repeatedly defines Life Index as:

- not a knowledge base
- not an Agent memory cache
- a personal life archive / journaling system
- an Agent-first, Offline-must tool for recording life fragments

This is strong evidence that the product identity is intentionally narrow and human-centered, not a general-purpose assistant platform.

## 4.2 Architecture evidence from `docs/ARCHITECTURE.md`

The architecture doc states:

- Agent-first: do not build dedicated tools for things the agent can do directly
- data sovereignty: fully local storage and human-readable formats
- single-layer transparency: `用户 ↔ Agent ↔ 文件系统`
- no intermediate layer such as service process, API gateway, or database-centric runtime

It also defines a bounded feature surface:

### In scope

- natural-language journaling
- structured metadata extraction
- multi-dimensional index maintenance
- layered retrieval
- attachment management

### Out of scope

- cloud sync
- multi-user collaboration
- rich text editor
- real-time analytics dashboard

This is the strongest technical evidence that the product boundary is intentionally smaller than a general life-management application.

## 4.3 Workflow evidence from review docs

`docs/review/PROJECT_DIAGNOSIS_AND_ROADMAP.md` says the main challenge is not missing features but incomplete convergence from:

- a capable tool collection

into:

- a clear, stable, agent-native product contract

That same diagnosis says the current priority is:

- workflow clarity
- tool / agent boundary clarity
- reliable onboarding and distribution

not:

- broad feature expansion
- premature protocol or platform expansion

This is direct evidence that the next product move should clarify boundaries, not widen them.

## 4.4 Tool-boundary evidence from execution docs

`docs/review/execution/TOOL_RESPONSIBILITY_MATRIX.md` makes several product-shaping boundaries explicit:

- confirmation is caller-owned, not tool-owned
- search returns retrieval results, not final product meaning
- weather lookup is capability, not orchestration
- edit flows may require caller-composed multi-tool orchestration

This strongly suggests the current product model is:

- tools provide deterministic capabilities
- agents own interpretation, sequencing, confirmation, and user-facing meaning

That boundary is central to the broader product-boundary review.

## 4.5 Scheduler evidence from `references/schedule/SCHEDULE.md`

The schedule guide now explicitly says:

- it is an optional automation setup guide
- it depends on host-platform scheduling support
- Life Index itself does not contain native scheduler runtime
- users can skip automation and still fully use the product

This is now strong evidence that recurring automation belongs to the orchestration layer, not the core product runtime.

## 4.6 MCP evidence from reevaluation docs

`docs/review/execution/MCP_REEVALUATION.md` says:

- MCP migration is deferred
- current CLI-first architecture remains preferred
- protocol expansion should wait until the capability and workflow model are more stable

This is evidence that the product should not be redefined around protocol adapters or ecosystem fashion at this stage.

## 5. Product layers to define explicitly

This review should end with a clear three-layer model.

## 5.1 Layer A — Core product

Candidate meaning:

- durable user-owned journal data model
- atomic and reliable journaling tools
- indexing / retrieval primitives
- local storage conventions
- explicit CLI / tool contracts

Question to settle:

- Is this the full product in v1.x, with everything else treated as surrounding orchestration?

## 5.2 Layer B — Agent / host-platform orchestration

Candidate meaning:

- intent interpretation
- metadata extraction from natural language
- confirmation loops
- multi-step flow composition
- optional scheduler setup on host platforms
- post-install customization interactions

Question to settle:

- Which of these must remain outside core tools to preserve the agent-first model?

## 5.3 Layer C — Future application layer

Candidate meaning:

- any future GUI or app shell
- dashboards or timeline browsing shells
- convenience operators for less agent-centric environments
- packaging / integration layers that make the same core easier to access

Question to settle:

- What is a legitimate future shell, and what would incorrectly redefine Life Index into a different product?

## 6. Primary review questions

The review must end with explicit answers to all of these:

1. What single sentence best describes Life Index core product identity in v1.x?
2. Which user outcomes are product-native versus orchestration-composed?
3. Which currently documented workflows are core product experience, and which are agent-side operator recipes?
4. What kinds of future app-layer work are compatible with the current product identity?
5. What future directions would violate the repo's existing design floor?
6. Which contradictions in current docs should later be promoted into permanent clarification artifacts?

## 7. Decision criteria

Every boundary decision should be evaluated against the same grid.

### 7.1 Product-fit criteria

- does it preserve the journaling / archive identity?
- does it preserve the local-first promise?
- does it preserve the agent-first capability split?
- does it keep the system understandable to a new operator?

### 7.2 Complexity criteria

- does it introduce hidden runtime state?
- does it add background process burden?
- does it expand support burden across platforms?
- does it create a second product identity by accident?

### 7.3 Repo-consistency criteria

- aligns with README positioning
- aligns with `docs/ARCHITECTURE.md` boundaries
- aligns with scheduler deferral and optional automation stance
- aligns with MCP deferral and CLI-first reality
- aligns with tool responsibility review work

## 8. Strong provisional boundary model

## 8.1 Core product now

Life Index core product should likely be defined as:

- a personal life-journaling and retrieval system
- local-first and durable by design
- exposed through explicit atomic tools and a unified CLI
- optimized for agent-mediated usage, but not dependent on hidden resident services

## 8.2 Orchestration now

Agent / host-platform orchestration should likely own:

- user-intent interpretation
- semantic metadata derivation where the tool contract expects structured input
- confirmation handling
- multi-step flows that combine multiple tools
- optional recurring automation setup on supported platforms
- user-facing experience shaping around the tools

## 8.3 Future app layer later

A future application layer is likely acceptable only if it remains:

- a shell over the same local-first data model
- compatible with the same durable user-owned data and compatibility promises
- honest about when it is adding convenience rather than redefining the product
- non-authoritative over the core data and tool contracts

## 8.4 Future directions rejected by default

Unless later evidence is overwhelming, the following should remain rejected by default:

- turning Life Index into a general digital life manager
- adding hidden resident service infrastructure as the product center
- shifting product identity from life archive to assistant memory substrate
- building broad collaboration or cloud-centric product surfaces
- treating dashboards / app chrome as more important than the journaling core

## 9. Main tensions to resolve in this review

## 9.1 Engine vs product experience

The repo already has a capable engine, but not every documented workflow is equally central to product identity.

The review should distinguish:

- what the engine can support
- what the product should actively claim to be

## 9.2 Atomic tool ideal vs expanding convenience logic

`write_journal` and related flows still create pressure toward a "super entrypoint".

The review must preserve the line between:

- tool-owned deterministic execution

and:

- agent-owned reasoning, confirmation, and orchestration

## 9.3 Local journaling product vs future shell temptation

It is easy to imagine future UI, packaging, or dashboard work.

The review must decide whether those should be described as:

- optional shells around the same product

or:

- evidence that the product identity itself has changed

## 10. Target outcomes

By the end of this topic, the project should have enough clarity to later produce one or more permanent artifacts such as:

- a concise product-boundary memo
- a permanent architecture clarification section
- a roadmap note describing acceptable future shells versus out-of-scope product drift

This planning pass does **not** decide where that permanent wording must live yet.

## 11. Recommended execution order for the next round

1. confirm the three-layer model is the right framing
2. test the model against existing repo language and contradictions
3. write a short decision memo in permanent docs only after the wording is stable
4. update roadmap / architecture / README references only if the memo creates real clarification value

## 11.1 Task-level QA scenarios (test-first verification)

Each execution step above has a concrete verification procedure. These must pass before the step is considered complete.

### QA-1: Confirm the three-layer model is the right framing

**Tools**: Read, Grep

**Steps**:
1. Read `README.md` and extract all sentences that define what Life Index **is** and **is not**
2. Read `docs/ARCHITECTURE.md` sections 1 (Core Principles) and 4 (System Boundary)
3. Read `docs/review/PROJECT_DIAGNOSIS_AND_ROADMAP.md` section 0 (Executive Summary) and section 2 (Workflow / Tool Boundary)
4. Read `docs/review/execution/TOOL_RESPONSIBILITY_MATRIX.md` section 6 (Cross-tool boundary observations)
5. Read `references/schedule/SCHEDULE.md` section 1.2 (boundary statement)
6. Read `docs/review/execution/MCP_REEVALUATION.md` section 5 (Decision rationale)
7. For each source, classify every boundary-relevant statement into one of: Layer A (core product), Layer B (agent/host orchestration), Layer C (future app layer)
8. Check: does every statement fit cleanly into exactly one layer? Record any that span two layers or resist classification.

**Expected result**:
- Every boundary-relevant statement from the six source docs can be assigned to exactly one layer
- Zero statements require a fourth layer or fundamentally break the three-layer model
- If any statement resists classification, it is recorded as a tension to resolve in QA-2
- **Pass condition**: ≤ 2 statements resist clean classification AND none of them imply the model itself is wrong (only that wording needs tightening)

### QA-2: Test the model against existing repo language and contradictions

**Tools**: Read, Grep

**Steps**:
1. Grep across `README.md`, `README.en.md`, `docs/ARCHITECTURE.md`, `SKILL.md`, `AGENTS.md`, `docs/review/PROJECT_DIAGNOSIS_AND_ROADMAP.md` for phrases that could imply broader product scope than Layer A defines (search patterns: `"lifestyle"`, `"life manager"`, `"dashboard"`, `"app"`, `"platform"`, `"service"`, `"real-time"`, `"cloud"`, `"collaboration"`)
2. For each match, determine: (a) is this an explicit rejection of broader scope, (b) is this neutral language, or (c) does this imply Life Index claims to be something beyond journaling core?
3. Grep for `"产品"` / `"product"` across the same files to find all product-identity statements
4. Compare every product-identity statement against the one-sentence core identity from Section 8.1
5. Record contradictions where existing language implies a different product identity than the boundary model proposes

**Expected result**:
- All scope-broadening terms found in step 1 are either explicit rejections (category a) or neutral (category b)
- Zero category (c) matches remain unresolved
- All product-identity statements from step 3-4 are compatible with the proposed one-sentence identity, or contradictions are explicitly listed for promotion into permanent docs
- **Pass condition**: zero unresolved contradictions that would force changing the three-layer model itself

### QA-3: Write a short decision memo in permanent docs

**Tools**: file creation (any available mechanism: Write tool, text editor, or bash), file reading, Grep

**Target file**: `docs/PRODUCT_BOUNDARY.md` (new file)

**Steps**:
1. Create the decision memo containing: (a) one-sentence core product identity, (b) three-layer model definition, (c) Layer A responsibilities, (d) Layer B responsibilities, (e) Layer C acceptance criteria, (f) rejected-by-default directions, (g) SSOT references
2. Read back the created file to confirm content was written correctly
3. Verify the memo answers all six primary review questions from Section 6 of this plan
4. Grep `README.md`, `docs/ARCHITECTURE.md`, and `SKILL.md` for product-identity statements; verify none contradict the memo's one-sentence identity

**Expected result**:
- `docs/PRODUCT_BOUNDARY.md` exists and is < 200 lines
- All six review questions from Section 6 have explicit answers traceable in the memo
- Grep in step 4 finds zero contradictions between the memo and Tier-1 SSOT docs
- **Pass condition**: a reviewer can read the memo and confirm it covers sections (a) through (g) without missing content, and no Tier-1 SSOT doc contradicts it

Note: QA-3 checks memo-local quality only. Full exit criteria verification happens in QA-5 after all steps complete.

### QA-4: Update architecture / roadmap / README references

**Tools**: file reading, file editing (any available mechanism: Edit tool, text editor, or bash), Grep

**Target files** (only if clarification value is confirmed):
- `docs/ARCHITECTURE.md` — add a cross-reference to `docs/PRODUCT_BOUNDARY.md` in the "相关文档" (Related Documents) section
- `AGENTS.md` — add `docs/PRODUCT_BOUNDARY.md` to the "相关文档" (Related Documents) table
- `docs/review/PROJECT_DIAGNOSIS_AND_ROADMAP.md` — add a note in section 0 that product boundary has been formally defined

**Steps**:
1. Read each target file's relevant section
2. Check whether adding a cross-reference creates genuine clarification (not redundancy)
3. If yes, add the minimal cross-reference using any available file-editing mechanism
4. Grep the edited files for any wording that now contradicts the decision memo
5. Verify each edit via diff or re-read

**Expected result**:
- Each edit is ≤ 3 lines of new content
- No existing content is deleted or rewritten
- Grep in step 4 finds zero contradictions
- **Pass condition**: the diff for this step adds only cross-references, not new boundary definitions

### QA-5: Final exit criteria gate (run after QA-1 through QA-4)

**Tools**: file reading

**Steps**:
1. Read `docs/PRODUCT_BOUNDARY.md` (created in QA-3)
2. Read the QA-1 pass/fail record and any tension notes
3. Read the QA-2 contradiction list
4. Read the QA-4 diff summary
5. Check each of the seven exit criteria from Section 14 against the combined evidence:
   - (a) the three-layer model is explicit → confirmed by QA-1 pass
   - (b) core product identity is stated in one stable sentence → confirmed by QA-3 memo section (a)
   - (c) orchestration-owned responsibilities are clearly listed → confirmed by QA-3 memo section (d)
   - (d) future app-layer work has an explicit accept / reject boundary → confirmed by QA-3 memo sections (e) and (f)
   - (e) any remaining contradictions worthy of promotion are named → confirmed by QA-2 contradiction list
   - (f) the next permanent-doc step is smaller than "design the future app" → confirmed by QA-4 scope check
   - (g) all QA scenarios (QA-1 through QA-4) have recorded pass/fail results → confirmed by presence of recorded results

**Expected result**:
- All seven criteria are satisfied with traceable evidence from QA-1 through QA-4
- **Pass condition**: every criterion maps to a specific QA result; zero criteria are unsupported
- **Fail action**: if any criterion fails, record which QA step produced insufficient evidence and iterate on that step before re-running QA-5

## 12. Atomic commit strategy if execution is approved later

### Commit 1 — Decision memo

Purpose:

- add a concise permanent product-boundary statement

Target file:

- `docs/PRODUCT_BOUNDARY.md` (new file, < 200 lines)

Verification:

- QA-3 must pass before this commit is created
- Commit message: `docs: add product boundary decision memo`

Rule:

- no mixed roadmap cleanup
- no opportunistic README rewrite
- this commit touches exactly one new file

### Commit 2 — Architecture / roadmap alignment

Purpose:

- align the smallest number of permanent docs to the accepted boundary model

Target files:

- `docs/ARCHITECTURE.md` — add cross-reference in Related Documents section
- `AGENTS.md` — add entry to Related Documents table
- `docs/review/PROJECT_DIAGNOSIS_AND_ROADMAP.md` — add note in section 0

Verification:

- QA-4 must pass before this commit is created
- Each file diff adds ≤ 3 lines
- Commit message: `docs: add product boundary cross-references`

Rule:

- docs only
- keep wording narrow and non-redundant
- no content deletion or rewrite

### Commit 3 — Follow-up clarification only if needed

Purpose:

- tighten any doc that still implies broader product scope than intended

Trigger condition:

- only created if QA-2 found category (c) matches that were not resolved by Commits 1-2

Verification:

- grep the edited files for the specific contradiction terms found in QA-2
- each grep must return zero category (c) matches after the edit
- Commit message: `docs: resolve product scope contradictions in [file]`

Rule:

- only after contradictions are concrete and verified
- one commit per file if multiple files need tightening

### Final gate — QA-5

After all commits are staged or created, run QA-5 (final exit criteria gate) to confirm all seven Section 14 exit criteria are satisfied. No commit may be pushed until QA-5 passes.

## 13. Explicit guardrails

- Do not reopen scheduler runtime debate unless boundary review truly requires it.
- Do not reopen release/version policy unless boundary review truly conflicts with it.
- Do not turn future shell ideas into implicit implementation commitments.
- Do not confuse what the system can support with what the product should officially claim.
- Do not let review docs silently overrule README and architecture SSOT without deliberate promotion.
- Do not implement app-layer ideas before the product boundary is accepted.

## 14. Exit criteria

This review is complete only when all of the following are true:

- (a) the three-layer model is explicit (verified by QA-1 pass)
- (b) core product identity is stated in one stable sentence (verified by QA-3 memo section (a))
- (c) orchestration-owned responsibilities are clearly listed (verified by QA-3 memo section (d))
- (d) future app-layer work has an explicit accept / reject boundary (verified by QA-3 memo sections (e) and (f))
- (e) any remaining contradictions worthy of promotion are named (verified by QA-2 contradiction list)
- (f) the next permanent-doc step is smaller than "design the future app" (verified by QA-4 scope check)
- (g) all QA scenarios (QA-1 through QA-4) have recorded pass/fail results

All seven criteria are checked together in QA-5 (final exit criteria gate) after QA-1 through QA-4 complete.

## 15. Current recommended next step

Stay in planning mode.

Specifically:

1. review this boundary model against existing repo language
2. decide whether the three-layer framing should become the project's permanent strategic language
3. only then promote the smallest stable conclusion into permanent docs
