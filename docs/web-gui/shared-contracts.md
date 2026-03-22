# Web GUI Shared Contracts

This document is the single-source reference for cross-phase contracts that were previously duplicated across multiple planning docs.

---

## 1. Journal Route Path Contract

### Canonical Web route path

- **`journal_route_path`** = path relative to `JOURNALS_DIR`
- Example: `2026/03/life-index_2026-03-07_001.md`

### Why normalization is required

Current tool/source outputs are not fully uniform. Depending on source, a journal path may appear as:

- absolute path: `C:/Users/.../Documents/Life-Index/Journals/2026/03/...`
- `USER_DATA_DIR`-relative path: `Journals/2026/03/...`

### Rule

Web services/routes must normalize raw path values into `journal_route_path` before:

- rendering links
- constructing redirects
- passing route params
- generating edit/view URLs

### Forbidden

- Do **not** render `/journal/{raw_path}` directly from tool output
- Do **not** expose raw absolute paths in user-facing route links

---

## 2. CSRF Contract

### Canonical contract

- cookie name: `csrf_token`
- hidden form field name: `csrf_token`

### Pattern

Use route-level **double-submit cookie** validation:

1. GET route generates token
2. GET route sets `csrf_token` cookie
3. Form includes hidden `csrf_token` field
4. POST route compares cookie token and submitted token
5. mismatch/missing → HTTP 403

### Forbidden

- Do **not** silently switch to `_csrf_token`
- Do **not** introduce a separate session-based middleware contract unless all dependent docs are updated together

---

## 3. Frontmatter Body Contract

### Canonical rule

`tools.lib.frontmatter.parse_journal_file()` returns helper keys including:

- `_body`
- `_file`

### Rule

When Web docs/services refer to journal body content from parsed frontmatter, they must use:

- `parsed["_body"]`

not:

- `parsed["body"]`

### Applies to

- word count logic
- journal rendering
- edit diff computation
- prefill/edit body hydration

---

## 4. Tool Return Shape Reality Check

### Error shape

Current source standardizes **error** responses as:

```json
{
  "success": false,
  "error": { ... }
}
```
```

### Success shape

Current source does **not** standardize all successful tool responses behind a shared `data` wrapper.

Instead, success payloads typically expose tool-specific top-level fields, for example:

- `journal_path`
- `merged_results`
- `duration_seconds`
- `changes`

### Rule

Web planning docs must describe **current source reality**, not a hypothetical future normalized response shape.

---

## 5. Route vs Service Responsibility Boundary

### Route may do

- request parsing
- response shaping
- CSRF validation
- path validation
- temp upload handling needed for HTTP transport

### Route must not do

- direct journal persistence business logic
- frontmatter mutation business logic
- index update orchestration

Those belong in services and/or existing `tools/` modules.

---

## 6. Usage rule for phase docs

Individual phase/subplan docs should:

- link to this file
- only restate a contract when the phase modifies or extends it
- avoid re-defining the same contract text in full
