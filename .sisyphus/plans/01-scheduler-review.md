# Scheduler Review — Execution Plan

Status: open  
Priority: P0  
Owner: current CTO discussion track  
Plan type: planning-only, no implementation in this pass  
Execution style: ultrawork, evidence-first, TDD-oriented  
Primary artifact: scheduler scope decision memo and follow-up change plan

## 1. Mission

Determine whether Life Index should support any scheduler behavior in core, and if not, define the exact boundary between:

- Life Index core capabilities
- host-agent / host-platform orchestration
- documentation that is currently too expansive or internally inconsistent

This plan is for **decision quality first**. It does **not** authorize code changes by itself.

## 2. Working hypothesis

Current highest-confidence hypothesis:

> Life Index should **not** add a native persistent scheduler at this stage.  
> It should keep atomic tools schedulable from the outside, narrow official guidance to a small set of externally orchestrated workflows, and explicitly reject daemon/service-style scheduler growth in core.

This hypothesis must still be tested against repo evidence and contradiction review.

## 3. Why this review is urgent

Scheduler work is dangerous here because it can quietly transform Life Index from:

- an agent-first local journal skill

into:

- a background automation product with service lifecycle, retry semantics, delivery semantics, time zone semantics, and user-confusion risk.

That would conflict with the repo’s stated design floor:

- prefer simplicity over system growth
- avoid automation traps
- keep data local and behavior explicit

## 4. Repo-grounded evidence already available

## 4.1 Architecture-direction evidence

- `AGENTS.md` says Life Index is **agent-first** and warns against hidden service layers and automation traps.
- `README.md` repeats the design bottom line: simplicity, reliability, no automation bloat.
- Current plan file already correctly notes that the architecture rejects turning the project into a heavy automation platform.

## 4.2 Existing capability evidence

- Core tools already exist for the important outcomes:
  - `write_journal`
  - `search_journals`
  - `generate_abstract`
  - `build_index`
- `docs/review/evals/BASELINE_RUN_RESULTS.md` shows these tool areas are mature enough for diagnosis and, after later fixes recorded in that document, the unit baseline is green.
- The same baseline document confirms write-through indexing exists, which weakens the case for recurring native maintenance scheduling.

## 4.3 Contradiction evidence

`references/schedule/SCHEDULE.md` currently recommends a much more expansive scheduling story, including:

- daily report
- weekly report
- monthly report
- yearly report
- monthly index rebuild
- “digital life manager” framing

This creates pressure in the opposite direction from the architecture and README.

## 4.4 Most important current contradiction

The repo appears to say two different things:

1. **Core philosophy**: avoid automation traps; stay simple; keep orchestration external.
2. **Schedule guide**: configure a relatively rich recurring automation suite with reminder/report behavior.

This contradiction is the main subject of the review.

## 5. Review questions to settle

The review must end with explicit answers to all of these:

1. Should Life Index core own any scheduling runtime at all?
2. Which scheduled outcomes are legitimate and worth endorsing?
3. Which outcomes belong only to host-agent orchestration?
4. Which currently documented jobs should be narrowed, demoted, or removed?
5. Is any maintenance schedule still justified after write-through indexing?
6. If a future scheduler-adjacent change is allowed, what is the smallest acceptable next step?

## 6. Decision criteria

Every scheduler candidate must be evaluated against the same grid.

### 6.1 Product-fit criteria

- fit with agent-first philosophy
- fit with local-first design
- fit with “not a general automation system” positioning
- value to end users versus documentation-only support

### 6.2 Engineering criteria

- hidden state introduced
- retry and recovery burden
- time zone burden
- cross-platform reliability burden
- observability and debuggability burden
- testability burden
- support burden over time

### 6.3 Repo-consistency criteria

- aligns with README positioning
- aligns with architecture guardrails
- aligns with current tool boundaries
- aligns with write-through indexing reality

## 7. Candidate job families and default judgment

| Job family | Native core now | External orchestration now | Default judgment | Reason |
|---|---|---|---|---|
| Reminder / prompt delivery | No | Yes | Out of native scope | Delivery channel, timing, and interruption policy belong to the host environment |
| Daily / weekly reflective reports | No | Maybe | Optional orchestration pattern only | Valuable workflow, but composed from existing tools and prompt logic |
| Monthly / yearly abstract generation | Tool yes, scheduler no | Yes | Keep tool native, scheduling external | `generate_abstract` is already the atomic primitive |
| Index maintenance | Manual tool yes | Maybe, narrowly | Minimal external safety-net only | Write-through indexing reduced routine maintenance need |
| Background “digital life manager” flows | No | Yes, if user wants | Out of native scope | Too close to turning the product into a general automation platform |

## 8. Strong provisional recommendation

### 8.1 Native scope now

Keep native scope limited to:

- reliable atomic tools
- explicit CLI invocation
- documentation for safe external orchestration patterns

### 8.2 Out of native scope now

Do not add:

- built-in cron engine
- daemon/service process
- internal scheduler state
- retry queue subsystem
- push delivery subsystem
- reminder management UI or config surface
- hidden background maintenance loops

### 8.3 Documentation scope likely to remain

Potentially keep only a narrow documentation subset for:

- monthly or yearly abstract generation via external scheduler
- occasional rebuild or repair via external scheduler

Daily/weekly “reporting concierge” guidance should be treated as a likely demotion candidate unless strong product evidence justifies keeping it.

## 8.4 Second-round task ratings for current `SCHEDULE.md`

This section rates the currently documented scheduled jobs one by one.

### Rating scale

- **Keep recommended**: still fits the narrowed v1.x boundary and is worth endorsing publicly as an external orchestration pattern
- **Downgrade to optional example**: still valid as a pattern, but should not read like a default or core recommendation
- **Rewrite / remove**: current framing is misleading, obsolete, or too expansive for the v1.x boundary

| Current job in `SCHEDULE.md` | Rating | Reason |
|---|---|---|
| Daily report | Downgrade to optional example | Valuable for some users, but mostly an agent-composed push workflow rather than a core Life Index capability |
| Weekly report | Downgrade to optional example | Even more orchestration-heavy than daily; includes extra synthesis and can easily expand product scope |
| Monthly report | Keep recommended | Closest to core product value because it builds directly on existing summary capabilities and durable monthly review behavior |
| Yearly report | Keep recommended | Strong long-horizon journaling value and naturally aligned with archive/review use cases, but scheduling remains external |
| Monthly index rebuild | Keep recommended, but rewrite narrowly | Still defensible as repair/hygiene safety-net, but should be framed as optional maintenance/recovery rather than routine core experience |

## 8.5 Notes on jobs no longer worth endorsing in the old form

### Daily incremental index maintenance

- This is not in the top summary table anymore, but the schedule/scenario set still contains traces of the old daily maintenance idea.
- Given write-through indexing, daily maintenance should no longer be recommended as a standard recurring task.
- If mentioned at all, it should be described as historical/obsolete or as a superseded design.

## 8.6 Why monthly/yearly reports survive the cut

Monthly and yearly reports survive as recommended patterns because:

- they align with the journal product's natural review cadence
- they are already grounded in existing summary-generation capability
- they produce durable artifacts, not just transient pushes
- they feel like extensions of journaling, not replacement product identity

## 8.7 Why daily/weekly reports are demoted

Daily and weekly reports are demoted rather than deleted because they still have user value, but they carry more scope-expansion risk:

- they depend more heavily on push delivery and timing behavior
- they are more agent-style concierge experiences than journal-core primitives
- some current scenario details (hot news, extra advisory content, etc.) push them toward a broader life-management product

## 8.8 Why monthly rebuild remains but only narrowly

Monthly rebuild remains acceptable only as a narrow external safety-net because:

- it supports recovery, reconciliation, and hygiene
- it does not require adding scheduler runtime to core
- it should not be marketed as a normal daily-operational requirement
- write-through indexing means it exists for resilience, not for steady-state correctness on every ordinary day

## 8.9 Narrowed v1.x scheduler boundary after second-round rating

### Publicly endorse

- monthly report via external scheduling
- yearly report via external scheduling
- monthly rebuild / repair via external scheduling, with narrower language

### Keep only as optional recipes

- daily report
- weekly report

### Do not endorse as part of the active v1.x scheduler story

- daily incremental index maintenance
- “digital life manager” framing as the default interpretation of Life Index

## 8.10 Implication for future doc cleanup

If execution is approved later, the likely documentation changes should aim to:

- reduce the “6-task digital life manager” framing
- mark daily/weekly reports as optional host-platform recipes
- keep monthly/yearly review workflows as the strongest recommended schedule examples
- reframe monthly rebuild as maintenance/recovery guidance
- remove or archive obsolete daily index maintenance guidance

## 8.11 Third-round rewrite direction: reposition `SCHEDULE.md`

### New document role to target

`SCHEDULE.md` should be reframed as:

- an **optional automation setup guide**
- read by an agent after base onboarding succeeds
- used to help a user configure host-platform scheduling if the user explicitly wants it
- explicitly outside Life Index native runtime scope

This keeps it structurally parallel to onboarding, but narrower in authority:

- `AGENT_ONBOARDING.md` = install, initialize, verify base system
- `SCHEDULE.md` = optional post-onboarding automation setup on supported host platforms

### What this rewrite must preserve

- user freedom to enable daily and weekly reports if they want them
- strong recommendation of monthly/yearly review workflows
- availability of maintenance/rebuild as an optional external safety-net
- explicit statement that scheduling depends on host-agent/platform capability, not Life Index core

### What this rewrite must reject

- framing automation as mandatory for all users
- implying Life Index contains native scheduling runtime
- implying daily/weekly reports are default baseline product behavior
- implying maintenance jobs are routinely required for ordinary steady-state correctness

## 8.12 User choice model

### Product stance

The user must keep full choice over whether to enable recurring automation.

That means the narrowed scheduler story should explicitly support:

- no automation
- only monthly/yearly review automation
- daily/weekly plus monthly/yearly automation
- maintenance-only automation
- custom combinations

### Key rule

Governance should constrain architecture boundaries, not remove legitimate user options.

In practical terms:

- daily and weekly reports stay available
- they are simply classified as optional external recipes rather than default core behavior

## 8.13 Recommended placement in the user journey

### Placement rule

Automation setup should happen **after** successful onboarding verification, not during base installation steps.

Recommended sequence:

1. install
2. initialize
3. health
4. first write
5. first search
6. optional customization
7. optional automation setup

### Why this order is correct

- installation success stays separable from automation setup
- users can skip automation without feeling the product is incomplete
- automation failures do not get confused with base product failures
- the agent first proves the system works, then offers quality-of-life enhancements

## 8.14 Recommended automation setup interaction model

### Entry question

After onboarding and optional customization, the agent should be allowed to ask a short question such as:

- whether the user wants recurring reports or maintenance tasks configured now

### Supported user choices

The setup plan should allow a compact selection model such as:

- skip automation for now
- daily report only
- weekly report only
- daily + weekly
- monthly + yearly
- monthly rebuild only
- custom mix

### Required follow-up questions

If the user opts in, the setup flow should gather only the minimum required scheduling inputs:

- platform capability confirmed or not
- timezone
- delivery mode/channel where relevant
- selected task set

### “One-click” interpretation

The product can still feel one-click from the user perspective if the agent performs the setup on the host platform in one guided pass.

That does **not** require Life Index to own scheduler runtime itself.

## 8.15 Write-through and maintenance positioning after the rewrite

### Normal path

- write-through handles ordinary incremental freshness
- users should not be taught that frequent manual maintenance is part of normal usage

### Recovery / hygiene path

- on-demand rebuild remains necessary
- low-frequency scheduled rebuild/check can remain available as an optional safety-net
- daily maintenance should not be presented as a standard recommendation

### Plain-language guidance target

The eventual rewrite should make it easy for users and agents to understand:

- normal usage does not depend on constant maintenance jobs
- recovery and periodic hygiene are still legitimate in a local-first system

## 8.16 Draft rewrite structure for future `SCHEDULE.md`

If approved later, the target structure should likely become:

1. document role: optional automation setup guide
2. prerequisites: onboarding complete, host platform supports scheduling
3. user choice menu
4. recommended setups
   - monthly report
   - yearly report
   - monthly rebuild
5. optional recipes
   - daily report
   - weekly report
6. maintenance and recovery note
7. platform-specific templates
8. troubleshooting / capability checks

## 8.17 Decision summary after third-round refinement

- user choice is preserved
- daily/weekly are not deleted from the option space
- daily/weekly are not positioned as default baseline product commitments
- monthly/yearly remain the strongest recommended automation flows
- rebuild remains available as optional recovery/hygiene automation
- automation setup should be offered after onboarding, as a separate optional stage

## 8.18 Fourth-round segmented cleanup plan for future `SCHEDULE.md`

This section translates the current scheduler decisions into section-level cleanup instructions.

### Section map and cleanup decisions

| Current section / block | Decision | Why |
|---|---|---|
| Title + document role header | Rewrite | Must explicitly say optional automation setup guide, not broad scheduler mandate |
| Step 1.1 "Life Index 是什么" | Keep, lightly tighten | Still useful context, but should stay short and support the new optional-setup framing |
| Step 1.2 "为什么需要定时任务？" | Rewrite | Current wording says these scenarios "must" be proactive; that is too strong for optional automation |
| Step 1.3 core goal + task list | Rewrite heavily | Must replace "6 个定时任务" and "数字生活管家" framing with user-choice-based setup menu |
| Token budget block | Keep, move later | Still useful, but should sit near task templates rather than framing the whole document mission |
| Step 2 platform cron concepts | Keep | Good host-platform grounding; supports the external orchestration boundary |
| Task 1 daily report template | Downgrade | Keep as optional recipe, not default recommended setup |
| Task 2 weekly report template | Downgrade | Keep as optional recipe, not default recommended setup |
| Task 3 monthly report template | Keep, rewrite lightly | Should remain recommended, but wording should reflect optional opt-in setup |
| Task 4 yearly report template | Keep, rewrite lightly | Same as monthly report |
| Task 5 monthly rebuild template | Keep, rewrite narrowly | Must be framed as recovery/hygiene safety-net, not routine daily-health requirement |
| Step 3 self-analysis | Keep, tighten | Useful capability gate before setup |
| Step 4 decision flow | Rewrite | Should branch from user opt-in + platform support, not from assumption all tasks will be configured |
| Step 5 execution setup | Rewrite heavily | Must support selective setup instead of "create all 6 tasks" |
| Step 5.2 verification | Keep, tighten | Verification remains necessary after setup |
| Step 5.3 completion checklist | Rewrite | Should verify selected tasks only, not all tasks |
| Troubleshooting | Keep | Still relevant for host-platform setup |
| Appendix / related docs / quick reference | Keep, rewrite selectively | Preserve references but align quick-reference table with new recommended vs optional split |

## 8.19 New opening section target

The future opening should communicate four things immediately:

1. this document is optional
2. it is for post-onboarding setup
3. it depends on host-platform scheduling support
4. users may enable only the automation they actually want

## 8.20 New top-level section order target

Recommended future order:

1. document role and boundaries
2. prerequisites
   - onboarding complete
   - host platform supports scheduling
3. user choice menu
4. recommended setups
   - monthly report
   - yearly report
   - monthly rebuild
5. optional recipes
   - daily report
   - weekly report
6. capability checks
7. setup execution
8. verification
9. troubleshooting
10. references / scenario links

## 8.21 Concrete rewrite instructions by block

### Opening block

Rewrite to say:

- this guide helps an agent configure optional recurring automation for Life Index
- it is not part of native Life Index runtime
- it should be used only after base onboarding succeeds

### Value proposition block

Rewrite from:

- “these scenarios must be proactive”

to:

- “some users may want recurring review and maintenance workflows, which can be configured through host-platform scheduling”

### Task list block

Rewrite from:

- mandatory fixed multi-task package

to:

- selectable setup menu with recommended and optional groups

### Setup execution block

Rewrite from:

- “create all tasks”

to:

- “create the selected tasks only”

### Verification block

Rewrite from:

- all-tasks verification checklist

to:

- selected-task verification checklist

## 8.22 Section-level remove/archive candidates

If cleanup is approved later, the most likely remove/archive candidate is:

- obsolete daily index maintenance framing and any lingering all-6-tasks language tied to it

The likely downgrade candidates are:

- daily report scenario prominence
- weekly report scenario prominence

## 8.23 What must remain visible after cleanup

Even after narrowing, the final document should still make these points easy to see:

- users may enable daily/weekly if they want
- monthly/yearly remain strongly recommended review automations
- maintenance/rebuild remains valid but optional
- no user is required to enable automation to consider Life Index fully installed and usable

## 8.24 Pre-edit checkpoint for the future formal rewrite

Before editing the real `SCHEDULE.md`, confirm:

- the document role sentence is agreed
- the recommended vs optional split is agreed
- the setup flow placement after onboarding is agreed
- the selected-task verification model is agreed
- the old all-tasks framing is explicitly retired

## 9. TDD-oriented execution plan

This plan is TDD-oriented even though this pass is still planning-only.

If any follow-up implementation or documentation reduction is approved, execute in this order:

### Phase 0 — Contract-first clarification

Produce a short decision memo that states:

- what is in scope
- what is out of scope
- what is external-orchestration-only
- what docs are no longer normative

**Done when**: the decision memo removes ambiguity between architecture and schedule guidance.

### Phase 1 — Failing contract tests / review checks first

Before changing implementation or endorsed docs, define failing checks for the intended boundary.

Examples:

- documentation contract check: no repo doc should imply native scheduler support if none exists
- scope check: schedule docs must label host orchestration explicitly
- maintenance check: docs must not recommend obsolete daily indexing if write-through supersedes it

If these are implemented as tests or scripted validation later, they should fail first before content/code changes are made.

**Done when**: the target boundary is executable or at least review-checklist-verifiable before edits begin.

### Phase 2 — Narrowest artifact changes

Apply the minimum changes needed to make repo messaging internally consistent.

Expected first targets:

- decision memo / review artifact
- `references/schedule/SCHEDULE.md`
- `AGENT_ONBOARDING.md` handoff to optional automation setup, but only after `SCHEDULE.md` is rewritten and its role is stable

**Done when**: the docs say one consistent thing about scheduling.

### Required execution order inside Phase 2

1. rewrite `references/schedule/SCHEDULE.md`
2. then add the minimal onboarding handoff in `AGENT_ONBOARDING.md`

Reason:

- onboarding must point to a settled scheduler document, not a moving target
- the onboarding handoff should reuse the final recommended/optional split, not invent it independently
- this avoids writing onboarding text twice

### Phase 3 — Optional tool/runtime follow-up only if justified

Only consider code/runtime changes if the review uncovers a real missing primitive.

Examples of acceptable minimal follow-up:

- a safer explicit CLI example
- clearer abstract-generation invocation guidance
- a documentation-only operator checklist

Examples of unacceptable scope jump:

- scheduler runtime
- resident process
- reminder delivery engine

**Done when**: any follow-up stays atomic and does not expand product identity.

### Phase 4 — Re-verification

Re-check:

- architecture consistency
- doc consistency
- affected tests/checks
- any command examples referenced by changed docs

**Done when**: the narrowed scheduler story is both explicit and verifiable.

## 10. Ultrabork execution lanes

Use parallel lanes, but keep decision authority centralized.

### Lane A — Repo evidence lane

Collect direct evidence from:

- architecture docs
- README positioning
- schedule docs
- baseline results
- tool/module boundaries

Output: evidence table with contradictions and confidence labels.

### Lane B — External reference lane

Collect comparable examples from:

- local-first tools
- CLI-first tools
- agent/platform orchestration docs
- systems that deliberately keep scheduling outside core

Output: design-tradeoff reference set.

### Lane C — Decision memo lane

Translate evidence into:

- scope table
- endorsed vs optional vs rejected job families
- smallest acceptable next step

### Lane D — Follow-up execution lane

Only after review approval:

- define failing checks
- update docs
- re-verify

## 11. Prioritized candidate outcomes

### P0 — Most likely correct outcome

Publish or adopt a decision that:

- native scheduler is deferred
- external orchestration remains the official mechanism
- schedule docs are narrowed to a smaller endorsed set

### P1 — Secondary acceptable outcome

Keep broader schedule examples, but explicitly downgrade them from recommendation to optional host-platform recipes.

### P2 — Least likely acceptable outcome

Approve one narrow scheduler-adjacent capability, but only if it is still explicit, stateless, and non-resident.

### Rejected by default

- adding a persistent scheduler core
- adding daemon/service behavior
- adding reminder delivery infrastructure

## 12. Atomic commit strategy

If execution is approved later, use small commits with one intent each.

### Commit 1 — Decision contract

Purpose:

- add or update the scheduler decision memo / review artifact

Rule:

- no behavioral change
- no mixed doc cleanup

### Commit 2 — Failing checks

Purpose:

- add tests/checks/review assertions that encode the scheduling boundary

Rule:

- should fail before the next corrective change if the repo is still inconsistent

### Commit 3 — Doc boundary correction

Purpose:

- narrow `references/schedule/SCHEDULE.md` and related docs to match the approved scope

Rule:

- docs only
- no opportunistic rewrites

### Commit 4 — Minimal support fix, only if needed

Purpose:

- add the smallest missing explicit primitive or example required by the approved scope

Rule:

- no scheduler runtime
- no service layer

### Commit 5 — Verification polish

Purpose:

- update test snapshots/checklists/examples after all prior changes are green

Rule:

- only verification-aligned cleanup

## 13. Explicit guardrails

- Do not assume “scheduled outcome exists” means “native scheduler should exist.”
- Do not merge reminders, reports, abstracts, and maintenance into one feature bucket.
- Do not let `references/schedule/SCHEDULE.md` silently overrule architecture.
- Do not turn host-platform convenience into core product obligation.
- Do not introduce background statefulness unless the evidence is overwhelming.
- Do not implement before the decision memo is accepted.

## 14. Exit criteria

This review is complete only when all of the following are true:

- there is a final in-scope / out-of-scope table
- the repo contradiction is explicitly resolved
- endorsed external orchestration cases are clearly listed
- rejected native scheduler directions are clearly listed
- the next step is atomic, testable, and smaller than “build a scheduler”
- the commit strategy for any approved follow-up is explicit

## 15. Current recommended next step

The next step should remain **planning and decision**, not implementation.

Specifically:

1. finish evidence collection
2. confirm whether `references/schedule/SCHEDULE.md` should be narrowed or downgraded
3. publish a scheduler decision memo
4. only then decide whether a tiny doc/test follow-up is justified

## 16. Reviewer checklist

Before approving this plan, confirm:

- Is the no-native-scheduler default actually supported by repo evidence?
- Are daily/weekly reports being treated too generously?
- Is monthly rebuild still justified after write-through indexing?
- Is the plan atomic enough for ultrawork execution?
- Would every proposed commit still make sense in isolation?
