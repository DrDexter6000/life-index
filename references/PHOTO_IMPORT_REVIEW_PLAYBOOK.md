# Historical Photo Import Review Playbook

Use this playbook for the additive `media.photo_timeline` cold-start import flow.
The CLI remains the only write authority: GUI and host agents consume plans,
request confirmation, stream previews, run child batches, inspect status, and
request rollback. They never write `Journals/` or `attachments/` directly.

Source facts are immutable: content SHA-256, byte size, source-relative path,
capture-time authority, GPS, and provenance. Users may edit only journal
`title` / `date` / `topic` / `tags` / `content` and proposal or attachment
selection.

## Canonical flow

```bash
.venv/bin/life-index import plan --source media.photo_timeline --input <photo-dir> --json
.venv/bin/life-index import validate --source-root <photo-dir> --json
.venv/bin/life-index import stage --plan <review-plan.json> --source-root <photo-dir> --json
.venv/bin/life-index import confirm --plan <review-plan.json> --source-root <photo-dir> --json
.venv/bin/life-index import confirm --edit <review-edit.json> --import-id <parent_id> --expected-queue-revision <q> --json
.venv/bin/life-index import review --import-id <parent_id> [--offset 0] [--limit 20] [--state …] --json
.venv/bin/life-index import reviews [--after <import_id>] [--limit 20] --json
.venv/bin/life-index import status --import-id <parent_id> --json
.venv/bin/life-index import preview --import-id <parent_id> --attachment <att_id> [--proposal-id <pid>] --source-root <photo-dir> --output - --json
.venv/bin/life-index import run --import-id <parent_id> --source-root <photo-dir> --json
.venv/bin/life-index import rollback --import-id <child_batch_id> --json
```

`plan` is a recursive read-only scan that groups editable proposals by date.
`validate` proves a canonical readable directory and root identity. `stage`
creates a pending queue without copying bytes and rejects a duplicate actionable
source root with `IMPORT_REVIEW_ALREADY_STAGED`. `confirm` atomically persists
the review plan and parent job; `confirm --edit` applies one
`import_review_edit.v1` proposal edit by rebuilding selection from immutable
source facts.

`review` is a bounded, ledger-authoritative page that exposes no source locator.
`reviews` discovers parent jobs only, using an exclusive cursor. `status`
returns proposal states, derived counts, plan and queue revisions, recovery,
and ledger-derived restart-safe `batches[]`. `preview` is proposal-pinned,
read-only, and can read a deselected attachment after source revalidation.
`run` allows one active child and performs TOCTOU-safe copying.

Legacy `import run --plan … --confirm …` fixture/direct behavior is unchanged;
only `--import-id` enters the parent review-job path. After restart, rediscover
the parent with `import reviews`; confirm, run, and preview must receive the
current `--source-root` and revalidate the same root identity.

## Date, queue, and authority discipline

- Dates come only from trusted EXIF or explicit user confirmation. Offset-aware
  EXIF uses its local calendar date; naive EXIF remains camera-local. Never use
  file mtime or a `1970-01-01` sentinel. Missing/conflicting dates stay
  `pending` with blank journal date and target until a user-confirmed date.
- An EXIF offset must belong to the chosen capture tag, include an explicit
  sign and valid minutes, and remain within ±14:00. Never borrow a sibling
  tag's offset.
- `imported` and `batching` proposals are frozen. Pending, confirmed, and
  skipped proposals accept safe edits. An unsettled active child blocks
  confirmation with `IMPORT_BATCH_ALREADY_ACTIVE`.
- `queue_revision` is the parent-ledger client concurrency token and starts at
  1. It increments once per parent-visible atomic change and is separate from
  review-plan `plan_revision`. Proposal edit uses
  `--expected-queue-revision`; stale input returns retryable
  `IMPORT_REVIEW_REVISION_CONFLICT` with zero edit writes.
- Confirm follows durable intent → plan → finalize. Confirm, status, run, and
  rollback reconcile crash windows idempotently. A plan/ledger mismatch is
  fail-closed: report `recovery_required` and `authority_status`, and do not
  blindly retry run.

## Child rollback and restart truth

- Child IDs are monotonic `<parent_id>#batch-<seq>` and each child stores exact
  `proposal_ids`. A parent job cannot be rolled back as a whole.
- Under the parent lock, rollback first projects the exact child membership to
  `batching`, records the active child and recovery requirement, and only then
  starts deletion. It restores `confirmed` only after all owned artifacts are
  absent and child/manifest truth is durable `rolled_back`.
- A crash before child intent restores `imported`; a crash after durable child
  completion converges to `confirmed`. A first-attempt, pre-delete,
  non-retryable refusal restores `imported`.
- A hidden parent origin marker distinguishes that no-delete refusal from a
  retry that began in durable rollback recovery. It is not a GUI/status state
  or second store. Only linked child and manifest facts that both say
  non-retryable `rollback_failed`, with origin `committed`, may restore
  `imported`. Retry, legacy, missing, or untrusted origin stays fail-closed.
  Marker-only updates do not increment `queue_revision`.
- `batches[]` is the only GUI rollback-discovery authority. It is
  ledger-derived, locator-free, and stable oldest-first. It never exposes the
  manifest, source paths, journal paths, or manifest paths.
- `rollback_available` is true only when child and canonical linked manifest
  agree on `committed`, or agree on retryable `rollback_in_progress` /
  `rollback_failed`. Rolled back, non-retryable, malformed, missing,
  wrongly-linked, or state-divergent evidence fails closed. Retry always
  repeats ownership, identity, hash, and size validation.

## Rescan and warnings

- Rescan deduplication uses committed attachment hashes plus attachment hashes
  from authoritative confirmed, batching, or imported review proposals. A
  rolled-back proposal restored to confirmed remains excluded; same name with
  different bytes is distinct.
- `import review` reads persisted scan warnings after restart, including
  unsupported HEIC/HEIF preview limitations. It exposes only the safe fields
  `code`, `severity`, `runnable`, `format`, and `preview_available`; never
  expose adapter messages, filenames, source paths, or arbitrary extension
  fields.

For exact parameters, envelopes, and error codes, read `docs/API.md` when the
repository is available. In an installed skill without repository docs, use
the exact installed command's `--help` and do not guess options.
