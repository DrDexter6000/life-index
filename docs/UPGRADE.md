# Life Index Upgrade Guide

> **Document role**: Define the supported upgrade path for Life Index v1.x.
> **Audience**: End users, operators, and agents performing upgrades on behalf of users.
> **Authority**: Active upgrade guidance for repo-first releases; version semantics remain defined in `docs/VERSION_POLICY.md`.

---

## 1. Scope

This document explains how to upgrade an existing Life Index installation during the v1.x series.

It focuses on the supported operator path, recovery for common upgrade problems, and the minimum validation required after an upgrade.

---

## 2. Supported Upgrade Anchor for v1.x

The supported upgrade model for current Life Index releases is:

- **repo-first**
- **release-tagged when formal releases are cut**
- **editable install inside a local virtual environment**

In practical terms, users upgrade an existing repository checkout rather than switching to a different distribution mechanism.

---

## 3. Supported Upgrade Workflow

### Step 1 — Back up user data

Before upgrading, back up:

- `~/Documents/Life-Index/`

This protects journals, attachments, configuration, and any user-owned content before version changes are applied.

### Step 2 — Update the repository

Update the local checkout to the intended release tag or approved target revision.

Typical repo-first operator flow:

```bash
git pull
```

If a specific release tag is required, check out that target explicitly instead of blindly following the moving branch tip.

### Step 3 — Reinstall the current code into the venv

**Linux/macOS/WSL**:

```bash
.venv/bin/pip install -e .
```

**Windows**:

```powershell
.venv\Scripts\pip install -e .
```

This ensures the current checked-out code and dependency set are aligned.

### Step 4 — Run health check

**Linux/macOS/WSL**:

```bash
.venv/bin/life-index health
```

**Windows**:

```powershell
.venv\Scripts\life-index health
```

### Step 5 — Refresh index state

Run the standard index command after upgrade:

**Linux/macOS/WSL**:

```bash
.venv/bin/life-index index
```

**Windows**:

```powershell
.venv\Scripts\life-index index
```

### Step 6 — Rebuild only when needed

Use rebuild flow only when at least one of these is true:

- release notes explicitly require it
- `health` indicates a search/index problem
- search validation after upgrade still looks wrong

Preferred rebuild command:

```bash
python -m tools.build_index --rebuild
```

### Step 7 — Validate against existing data

Run at least one known search against an existing journal entry and confirm the expected result still appears.

---

## 4. Minimum Post-Upgrade Validation Checklist

Every supported upgrade should pass this minimum checklist:

1. `life-index health` succeeds and does not report an unhealthy state
2. one known search against existing data returns expected results
3. if release notes mention retrieval/index/search changes, `life-index index` has been run
4. if health or search still looks wrong, rebuild flow has been considered or executed

---

## 5. Stronger Optional Validation Checklist

For cautious operators, or for releases that touched retrieval/indexing behavior, use this stronger checklist as well:

1. confirm the current config can still be read
2. perform one small write test
3. perform one search for the newly written entry

This stronger check is optional unless release notes say otherwise.

---

## 6. Recovery Rule for Broken Virtual Environments

If the virtual environment is stale or broken after:

- Python version changes
- interrupted install
- dependency resolution failure

then recover with this approach:

1. remove `.venv/`
2. recreate the virtual environment
3. reinstall with `pip install -e .`
4. continue from the standard post-upgrade validation flow

---

## 7. When Release Notes Must Override the Default Flow

Release notes should be treated as authoritative when they explicitly require:

- rebuild of indexes
- additional compatibility checks
- special migration actions
- temporary operator workarounds for a specific release

If release notes say more than this document, follow the release notes for that release.

---

## 8. Relationship to Other Release Documents

Use this document together with:

- `docs/VERSION_POLICY.md` for patch/minor/major semantics
- `docs/CHANGELOG.md` for release history and release-facing upgrade notes
- distribution strategy documentation for the rationale behind the current repo-first model
