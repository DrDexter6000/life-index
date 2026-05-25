# ADR: edit_journal Append-Only Revision History

**Status**: Accepted
**Date**: 2026-05-25
**Scope**: `tools/edit_journal`, `tools/lib/revisions.py`

## Context

README P1 (Growth Rings) publicly promises:

> *Every journal you write stays — edits are tracked revisions, never silent overwrites. Your growth rings are preserved by design.*

Any `edit_journal` operation that loses prior body or frontmatter content falsifies this promise. The existing `edit_journal` implementation already calls `save_revision()` from `tools/lib/revisions.py` before overwriting the journal file, but this behavior has never been formalized as a contract with passing tests.

CHARTER constraints relevant to this decision:

- **§1.2 Plain Text Forever**: User data must be human-readable, tool-agnostic. Revision storage must also be plain text.
- **§1.6 Backward Compatibility**: Existing journal format and directory structure must not break. Revision storage must be additive.

## Decision

Adopt **sidecar revision files** as the append-only revision storage scheme. The existing `tools/lib/revisions.py` module already implements this pattern:

- Before any write, `edit_journal` saves the complete original file content to `{journal_parent}/.revisions/{stem}_{timestamp}.md`.
- Revision files are full Markdown copies of the original journal (frontmatter + body), human-readable by any text editor.
- Revision files are non-canonical backups — deleting them does not corrupt the current journal.

This is formalized as a hard contract: `edit_journal` MUST call `save_revision()` with the full original content before writing any changes. This obligation is enforced by contract tests.

## Storage Scheme Evaluation

### Scheme A: Sidecar `.revisions/{stem}_{timestamp}.md` (CHOSEN)

- **Location**: `{journal_parent}/.revisions/{stem}_{YYYYMMDD_HHMMSS_ffffff}.md`
- **Format**: Full Markdown copy of original journal (frontmatter + body)
- **Pros**: Already implemented; human-readable Markdown (§1.2 compliant); co-located with journal for easy discovery; no schema changes; additive and backward compatible (§1.6); deletable without data loss.
- **Cons**: Storage grows linearly with edits; revision files in same directory tree as journals.

### Scheme B: Git-like append-only log `.life-index/revisions/<journal-id>.log`

- **Format**: Append-only log file with timestamped entries
- **Pros**: Single file per journal; compact.
- **Cons**: Requires a centralized `.life-index/` directory outside `Journals/`, violating co-location principle; log format is less human-readable than individual Markdown files; requires parsing logic to reconstruct any single revision; introduces new directory convention.

### Scheme C: Embedded frontmatter `revisions: [{ts, diff_path}]`

- **Format**: Revision metadata embedded in journal frontmatter
- **Pros**: Self-contained; no external files.
- **Cons**: Modifies journal frontmatter schema (§1.6 risk); every edit rewrites frontmatter, increasing mutation surface; frontmatter bloats with many edits; violates "journals are user-authored content" principle by mixing system metadata into user-visible frontmatter.

### Scheme D: `.bak` shadow file per journal

- **Format**: Single `.bak` file per journal containing the previous version
- **Pros**: Simple; one file per journal.
- **Cons**: Only preserves one previous version (not true append-only history); `.bak` convention implies overwrite semantics; no timestamped history; cannot reconstruct growth-ring timeline.

### Selection Rationale

Scheme A is chosen because it is already implemented, fully compliant with §1.2 and §1.6, and requires no code changes to `edit_journal` or `revisions.py` — only formalization via ADR and contract tests. Schemes B, C, and D all introduce new conventions or violate existing constraints without providing compensating benefits.

## Backward Compatibility

- **No changes to journal file format**: Journals remain Markdown + YAML frontmatter.
- **No changes to directory structure**: `.revisions/` directories are already created by existing `save_revision()` calls.
- **No changes to CLI flags, output JSON, or error codes**: The revision path is already included in `edit_journal` response as `revision_path`.
- **Additive only**: New contract tests verify existing behavior; no functional code changes required.

## Consequences

### Positive

- Growth Rings promise (P1) is now contractually enforced with passing tests.
- Revision history is human-readable Markdown, readable by any text editor.
- Revision storage is deletable — users can prune old revisions without data integrity risk.
- No migration needed — existing revision files remain valid.

### Negative

- Storage grows linearly: each edit creates a full copy of the original journal.
- Revision files are stored in `Journals/` tree, which users may not expect.

### Risks

- Large journals with frequent edits may accumulate many revision files. Mitigation: revision pruning is a future capability, not blocked by this ADR.
- **Known risk: `.revisions/` files must be filtered by any `**/life-index_*.md` consumer.** Revision filenames follow the pattern `life-index_YYYY-MM-DD_NNN_YYYYMMDD_HHMMSS_NNNNNN.md`, which matches the broad `life-index_*.md` glob. `tools/search_journals/core.py:128` and `:144` use `**/life-index_*.md` recursive globs without explicitly filtering `.revisions/`. The current date-regex (`core.py:106`) incidentally rejects revision filenames on the second pass, but the year-only candidate set (`:128`) and any future glob added under `**/life-index_*.md` would leak revisions into the candidate set. This is a known follow-up risk; no code change is included in this ADR.

## Alternatives Considered

See Storage Scheme Evaluation above. Additionally:

- **Diff-based storage**: Store only diffs rather than full copies. Rejected because diffs are not human-readable without tooling (violates §1.2 spirit) and reconstruction is fragile.
- **Compressed archives**: Store revisions in `.zip` or `.tar`. Rejected because binary format violates §1.2.

## Migration Path

No migration required. The existing `save_revision()` implementation and `edit_journal` call site already conform to this ADR. The deliverable is:
1. This ADR document formalizing the decision.
2. Contract tests proving the behavior.
3. No code changes to production code.
