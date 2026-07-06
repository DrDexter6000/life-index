# Entity Maintenance Playbook

This is the compact host-agent path for Entity Graph maintenance. It assumes
the CLI is deterministic and the host agent does the reading, grouping, and
user interview. Confirmed graph writes still require user judgment.

## Start Every Maintenance Task

1. Run `life-index health --json`.
2. If `data.upgrade_freshness.suggested_refresh_step` is present, execute it
   before reading graph signals or changing data.
3. Read `data.entity_maintenance.traffic_light`, `pending_count`, and
   `next_step.command`.

For repository-clone 运维纪律, follow `SKILL.md`; do not duplicate friction
logs or other notes into the product checkout.

Stop when the light is green and `pending_count` is zero.

## Answer With Profiles

For "about this person/project/entity" questions, resolve the entity ID and
read `<data>/Entities/<entity_id>.md` first. Follow the profile's `mentions`
pointers into journals; if the profile is missing or insufficient, run
`life-index abstract --entities --id ENTITY_ID --json`, then use `search`.
When search expands aliases or relationships, use the `entity_expansion`
attribution block to explain why a result matched.

## Audit

Use `life-index entity audit --json` for the full read-only facade. Treat
`zero_journal_reference_entities` as neutral facts, not problems. If the audit
returns a `next_step.command`, follow that command instead of inventing a
parallel repair path.

## Review

When human judgment is needed:

1. Run `life-index entity --review`.
2. Read evidence referenced by each queue item.
3. Group at most five items by person, place, project, or artifact.
4. Present reasoned recommendations to the user: Same, Different, Not-sure, or
   batch authorization for the items the user accepts.
5. Preview before writing:
   `life-index entity --review --action preview --id SOURCE_ID --target-id TARGET_ID`.
6. Apply only after user confirmation:
   `life-index entity --review --action merge_as_alias --id SOURCE_ID --target-id TARGET_ID`.

Use `keep_separate` when the user says two similar names are distinct:
`life-index entity --review --action keep_separate --id SOURCE_ID --target-id TARGET_ID`.

## Normalize

When the audit or health output points to schema normalization:

1. Preview with `life-index entity maintain --normalize --preview --json`.
2. Explain the planned type/kind changes and any review questions.
3. Apply only after user approval:
   `life-index entity maintain --normalize --apply --backup --json`.

## Delete

Deletion is a maintenance operation, not a direct primitive:

1. Preview with `life-index entity maintain --delete --id ENTITY_ID --preview --json`.
2. Confirm with the user that the entity and affected relationships are correct.
3. Apply with backup:
   `life-index entity maintain --delete --id ENTITY_ID --apply --backup --json`.

## Build Or Batch Import

For existing journals, use
`life-index entity build --from-journals --preview --json` and then review the
candidate evidence with the user.

For user-provided tables or structured notes, convert the material to a JSON or
YAML batch file, ask the user to confirm the parsed structure, then run:

1. `life-index entity build --from-batch FILE --preview --json`
2. `life-index entity build --from-batch FILE --apply --json`
3. `life-index entity --check`

Name conflicts go to review. Do not auto-merge them.

## Red Lines

- Tools do not contain LLM reasoning or interactive TUI behavior.
- Candidate items are suggestions; confirmed items are user judgments.
- No zero-human-judgment automatic merge.
- Use CLI primitives for writes; do not edit graph data silently.
