# Temporary Planning Index

Status: active working index for near-term CTO / product discussions.
Scope: lightweight discussion control surface only. Not SSOT. Not release docs. Not review bundle replacement.
Lifecycle: keep in `.sisyphus/plans/` while topics are active; archive or discard after conclusions are promoted elsewhere.

## Why this exists

This file prevents discussion drift while multiple high-priority strategic questions are open at the same time.

## Confirmed context

- Recent execution work has landed and the repository is currently in a clean pushed state.
- The onboarding date bug in verification docs has been fixed on `main`.
- Temporary local evidence is preserved separately in git stash and is not a current blocker.
- The current need is not more governance expansion; it is controlled discussion of the next product-defining topics.

## Current rule for this temporary workspace

- Keep the workspace small.
- One file per active top-level topic.
- Do not let these files silently become SSOT.
- Promote only stable conclusions into real docs.
- Archive only after a topic is actually closed.

## Active discussion priorities

### Closed recently

#### Scheduler review

- Conclusions have been promoted into formal docs.
- The temporary working file remains useful as local context until this workspace is archived.

Working file:
- `01-scheduler-review.md`

#### Release / version / upgrade model

- Conclusions have been promoted into formal docs.
- The temporary working file remains useful as local context until this workspace is archived.

Working file:
- `02-release-version-upgrade.md`

### P0 — Product boundary review

Reason:
- Scheduler and release governance are now settled enough that the next open question is broader product identity.
- The repo already contains strong boundary language, but it is distributed across README, architecture, review docs, workflow docs, and scheduling guidance.
- This topic now matters more than adding new features because it affects future roadmap, workflow scope, app-layer decisions, and how much orchestration should ever move into core.

Working file:
- `03-product-boundary-review.md`

Desired outcome:
- Define the clean boundary between Life Index core product, host-agent / host-platform orchestration, and any future application layer without reopening already-settled scheduler and release policy decisions.

## Parking lot (do not expand yet)

- Distribution strategy refinements beyond immediate release and upgrade questions
- Future roadmap ideas that depend on first closing the product-boundary review

## Discussion order

1. Scheduler review
2. Release / version / upgrade
3. Product boundary review

## Current scheduler execution order (locked for next steps)

When moving from scheduler planning into formal document edits, use this order:

1. rewrite `references/schedule/SCHEDULE.md` into the narrowed optional automation setup guide
2. then add the minimal `AGENT_ONBOARDING.md` handoff that offers optional automation setup after onboarding succeeds

Reason:

- onboarding should point to a stable scheduler guide
- the user-choice model and recommended/optional split must be settled in `SCHEDULE.md` first
- this prevents duplicated or contradictory onboarding wording

## Completion condition for this temporary workspace

This workspace can be archived only after:

- scheduler conclusions are captured
- release/version/upgrade conclusions are captured
- product-boundary conclusions are captured
- any durable outcomes are promoted into proper permanent docs or code-adjacent policy docs
