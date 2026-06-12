# Agent Onboarding Guide: Life Index Installation

> **Document Purpose**: Step-by-step operational instructions for AI agents installing Life Index on behalf of users.
> **Audience**: External AI agents (not humans)
> **Scope**: CLI installation, initialization, repair, and first-use verification
> **Governance SSOT**: `CHARTER.md`
> **Install freshness anchor**: `bootstrap-manifest.json`; refresh every path listed in `required_authority_docs`

---

## 1. Goal

Install and initialize Life Index on the user's machine by mechanically executing the `bootstrap --json` gate and its `safe_next_steps`. Do not attempt to independently detect or reclassify the install state.

This document is a **bootstrap-driven execution script**, not a decision tree. The `route` and `safe_next_steps` returned by `bootstrap --json` are the sole authority for what happens next.

You are acting on behalf of a user. Your job is to execute the installation workflow safely, run only the steps that `bootstrap` prescribes, and report the result back clearly.

Before taking any action, read this entire document once.

---

## 2. Step 0 — Refresh Authority First, Then Run Bootstrap Detection

Do **not** recreate `.venv`, run `health`, adopt a checkout, delete anything, or classify fresh-install vs upgrade until you complete this gate. (Cloning a fresh copy is **not** forbidden — on a blank machine it is the only way to obtain authority at all; see Step 0.1.)

### Step 0.1: Refresh authority documents first

**First decide which case you are in:**

- **No local Life Index checkout or command exists yet** (blank machine): you cannot refresh files you do not have. Skip the refresh in this sub-step and go straight to Step 4.1 to clone — **a fresh clone of the upstream default branch IS an up-to-date authority refresh**. After cloning, return to Step 0.2.
- **A local checkout already exists**: refresh it before trusting it, as described below.

Before trusting any local checkout, refresh `bootstrap-manifest.json` from the current upstream repository. Treat that manifest as the version/authority anchor and refresh **every file listed in its `required_authority_docs` array** before proceeding. Treat local copies as potentially stale.

This is the upstream freshness gate. `life-index bootstrap` does **not** perform network freshness checks; it only compares the installed package version against the local manifest version as `install_in_sync`.

### Step 0.2: Run bootstrap detection

If you already have a usable Life Index command:

```bash
life-index bootstrap --json
```

If you are running from a checkout before installation:

```bash
python -m tools bootstrap --json
```

Windows PowerShell and Linux/macOS shells both support the two command forms above when the relevant executable or checkout is available.

If neither command is available, continue to Step 4.1 for a fresh clone/install, then return here after Step 4.3.

If you discovered a checkout during authority refresh, assess it explicitly:

```bash
# Random discovered checkout; default is deliberately conservative.
life-index bootstrap --checkout-path <discovered-path> --json

# Host-managed skill directory exposed by the agent platform.
life-index bootstrap --checkout-path <host-managed-path> --checkout-origin host_managed --json

# User explicitly selected this checkout as the intended install target.
life-index bootstrap --checkout-path <user-selected-path> --checkout-origin user_designated --json
```

**Data safety invariant**: `bootstrap` is read-only. It never deletes existing journal data under `~/Documents/Life-Index/`, never repairs a checkout, never creates a venv, never runs migrations, and never modifies indexes. Phrases like "fresh install", "clean slate", or "start from scratch" do **not** authorize deleting existing journal data.

### Step 0.3: Read `needs_human` first

If `needs_human` is non-empty, relay each item to the user and wait for resolution before proceeding with adoption, cleanup, deletion, repair, or install-target decisions. Common codes:

| `code` | Meaning | Correct action |
|---|---|---|
| `AMBIGUOUS_CHECKOUT` | A checkout looks complete but was only discovered, not positively authorized | Use a host-managed skill directory, ask the user to designate the target, or clone fresh |
| `DEV_DIR_FOUND` | The checkout has development-directory signals | Do not adopt or repair it from this workflow; use a host-managed skill directory or ask the user |
| `INVALID_CHECKOUT` | The checkout is missing required files | Delete/reclone only if it is inside the agent-managed install target; otherwise ask |
| `MIGRATION_CHECK_FAILED` | Migration scan failed and cannot be treated as "no migration needed" | Run `life-index migrate --dry-run` manually and inspect output before proceeding |

### Step 0.4: Read the route and safe next steps

| `route` | Meaning | Proceed to |
|---|---|---|
| `fresh_install` | No existing journal data found | Execute `safe_next_steps` in order, then optional verification |
| `upgrade` | Existing journal data found | Execute `safe_next_steps` in order only |

If `safe_next_steps` is non-empty, run them in order and no others. On `upgrade`, `safe_next_steps` typically contains only `life-index health`. Do **not** append additional steps (index, write, search) beyond what `safe_next_steps` lists.

If `safe_next_steps` is empty, onboarding completes immediately after Step 0.

If health returns `status: "unhealthy"` after running the safe next steps, treat this as **Repair / Ambiguous State**:

1. do **not** pretend this is a clean fresh install;
2. collect `issues` and report them to the user; do not auto-repair;
3. if state remains unclear after basic inspection, ask the user before destructive cleanup.

**Checkout adoption rule**: only adopt a checkout when `detected_state.checkout_assessment.safe_to_adopt` is `true`. A checkout with no dev signals is still not adoptable unless it came from a host-managed path or was explicitly user-designated.

### Step 0.5: Bootstrap results are the sole authority — no second-guessing

- **Forbidden**: After `bootstrap --json` returns a `route`, do not reclassify fresh/upgrade/repair based on `health` output, index state, or any other local signal.
- **Forbidden**: Do not interpret `route: "upgrade"` combined with "pre-init degraded" as a reason to run the full fresh-install workflow.
- **Allowed**: Only after all `safe_next_steps` complete, if the state is still ambiguous, report to the user and ask for direction. Do not independently take repair / delete / rebuild actions.

---

## 3. Prerequisites

---

Before starting, verify these requirements are met:

| Requirement | Verification Command | Minimum Version |
|:---|:---|:---|
| Python | `python3 --version` or `python --version` | 3.11+ (tested through 3.14) |
| `python3-venv` / `ensurepip` | `python3 -m venv --help` succeeds | Required for Step 4.2; often **absent on minimal Linux / WSL / headless agent images** |
| Git | `git --version` | Any recent |
| Disk space | ~150MB base (no ML stack) | `[semantic]` adds ~500MB–1GB (CPU torch) or ~2–3GB (CUDA torch); semantic model cache downloads only when enabled |
| Network | Internet connection | For cloning and optional background semantic model download |

**Action**: Run the verification commands. If any fail, stop and report the missing prerequisite to the user.

---

## 4. Installation Steps

Execute these steps in order. Do not skip steps.

**Venv path reference** — All commands MUST use venv Python/CLI, never system Python. If you see `ModuleNotFoundError`, you are using the wrong Python.

| Platform | Python | CLI | Notes |
|:---|:---|:---|:---|
| Linux/macOS/WSL | `.venv/bin/python` | `.venv/bin/life-index` | Forward slashes, `bin/` |
| Windows | `.venv\Scripts\python` | `.venv\Scripts\life-index` | Backslashes, `Scripts\` |

**Cross-platform venv rule**:
- A Windows venv (`.venv/Scripts/python.exe`) cannot be used or repaired from WSL/Linux.
- A Linux/WSL venv (`.venv/bin/python`) cannot be used or repaired from Windows PowerShell.
- If the checkout contains only the other platform's venv layout, do **not** call it corrupted and do **not** delete it. Return to Step 0.3 and confirm whether you are looking at a development checkout or the wrong install target.

**Platform Command Fallback Rule**:
- If the host Agent platform provides its own skill install / add / setup commands, you may try them first only if the user explicitly asked for that platform-specific path.
- If those commands fail, are unavailable, or do not clearly complete the installation, do **not** get stuck there.
- Fall back to the standard repository-driven path in this document: `git clone` → `python -m venv .venv` → `pip install -e .`, then return to Step 0.2 to run `bootstrap --json` and follow `safe_next_steps`.
- Prefer the documented repository workflow over undocumented host-platform behavior.
- **Decision summary**: user explicitly requested a host-platform install path → try the host command, and on any failure fall back to `git clone`. User did not specify → use `git clone` directly (the documented default).

**Canonical Path Guardrail**:
- If the host platform already manages a canonical skill checkout, do **not** create a duplicate checkout in a generic workspace root.
- Reuse and repair the canonical checkout first.
- If no canonical checkout exists, either use the user-specified target directory or the platform's documented skill-install location.

### Step 4.1: Clone Repository

If the host platform provides a documented canonical skill-install directory and no managed checkout exists yet, clone into that location.

Otherwise use the generic form below:

```bash
git clone --depth 1 https://github.com/DrDexter6000/life-index.git <target-directory>/life-index
cd <target-directory>/life-index
```

**Success Criteria**:
- Repository cloned without errors
- Current working directory is now the repository root
- `SKILL.md` and `pyproject.toml` exist in this directory

**Failure Handling**:
- If clone fails: Check network, retry once, then report to user
- If files missing: Delete partial clone and retry

---

### Step 4.2: Create Virtual Environment

Only create a virtual environment after Step 0.3 has confirmed the current directory is the intended install target. If `.venv/` already exists, do not delete it unless it belongs to the confirmed install target and matches the current platform.

```bash
python3 -m venv .venv
```

**Success Criteria**:
- `.venv/` directory created
- No errors in output

**Failure Handling**:
- If Python not found: Try `python -m venv .venv` (Windows) or `py -3 -m venv .venv`
- If permission denied: Report to user with exact error
- If `ensurepip is not available` (or `python3 -m venv` fails on a missing venv module): first try the system package — `sudo apt install python3-venv` (or your distro's equivalent). **In a no-sudo / headless agent environment**, create the venv without pip and bootstrap pip from the official PyPA installer:
  ```bash
  python3 -m venv --without-pip .venv
  .venv/bin/python -c "import urllib.request; urllib.request.urlretrieve('https://bootstrap.pypa.io/get-pip.py', '/tmp/get-pip.py')"
  .venv/bin/python /tmp/get-pip.py
  ```
  Use only the official `bootstrap.pypa.io` source; do not fetch get-pip from third-party mirrors.

---

### Step 4.3: Install Package (Editable Mode)

**Linux/macOS/WSL**:
```bash
.venv/bin/pip install -e .
```

**⚠️ Optional semantic stack on CPU-only WSL / headless Linux**:
Base `pip install -e .` is lightweight and does **not** pull torch. Only if the user opts into semantic search (`[semantic]`) on a GPU-less machine (common for agent environments), install CPU-only torch first to skip ~2GB of CUDA dependencies, then install with the extra:
```bash
.venv/bin/pip install torch --index-url https://download.pytorch.org/whl/cpu
.venv/bin/pip install -e '.[semantic]'
```

**Windows**:
```powershell
.venv\Scripts\pip install -e .
```

**Success Criteria**:
- Installation completes with "Successfully installed life-index"
- Dependencies installed (pyyaml, numpy, jieba, rapidfuzz, Pillow)
- Semantic search is optional: `pip install -e '.[semantic]'` adds sentence-transformers
- No red error messages

**Failure Handling**:
- If `pip` not found: verify the `.venv` platform layout first. Delete and recreate `.venv/` only after Step 0.3 confirms this is the intended install target and the existing venv is not a development venv from another platform.
- If dependency fails: Retry once, then report to user

---

## 5. Initialization & Verification Workflow

This section is **conditional** on `bootstrap --json` output. Do not execute any step unless it appears in `safe_next_steps` or is explicitly required for the returned `route`.

### 5.0 Pre-rule

- Run **only** the steps listed in `safe_next_steps`, in array order.
- If `safe_next_steps` is empty, onboarding is complete after Step 0.
- `safe_next_steps` may contain `life-index index`, `life-index health`, `life-index migrate --dry-run`, etc. Execute them exactly as listed.

### Step 5.1: Build Index (Only if in `safe_next_steps`)

```bash
# Linux/macOS:
.venv/bin/life-index index

# Windows:
.venv\Scripts\life-index index
```

**What Happens**:
1. Creates / updates the FTS5 keyword search index in the foreground
2. Starts semantic / vector indexing in the background when supported
3. Returns before model loading or embedding work blocks the onboarding flow

**Success Criteria**:
- Command completes without errors
- Keyword / FTS indexing succeeds
- Semantic status is reported as `building`, `ready`, `disabled`, or `failed`
- No foreground model download is required for onboarding success

**Expected Wait**: The foreground command should return promptly after FTS work. Do not wait for semantic model download in the onboarding foreground path.
Installation succeeds when keyword search is ready. Do not wait for `semantic_status: ready`.

**Failure Handling**:
- If semantic status is `failed`: report it as non-blocking unless `safe_next_steps` explicitly requires semantic readiness
- If errors: Capture full output and report

---

### Step 5.2: Health Check (Only if in `safe_next_steps`)

```bash
# Linux/macOS:
.venv/bin/life-index health

# Windows:
.venv\Scripts\life-index health
```

**Success Criteria**:
- `success: true`
- `status` is "healthy" or "degraded" (not "unhealthy")
- No critical errors in the returned `issues` list

**Known Nuance**: Pre-init `health` may legitimately report "degraded" before initial indexing. This is expected and acceptable.

**Acceptable Warnings**:
- `virtual_env: "warning"` — Expected if running via full path
- `sentence_transformers: "warning"` — Semantic search is optional; keyword search remains available. Record as `semantic_status: "building"` or `"disabled"`, not a failure.

**Post-Round 6 Note**:
The health response may include an `events` array with piggyback notifications (e.g., writing streak reminders, schema migration suggestions). These are informational and do not indicate errors. You may surface relevant events to the user at your discretion.

**Failure Handling**:
- If `status: "unhealthy"`: Capture all issues and report to user
- If `ModuleNotFoundError`: Venv not being used, return to Step 4

---

### Step 5.3: Optional Sandboxed Keyword-Only Smoke Test (Non-blocking)

This step is **optional** and does **not** affect onboarding success. Run it only if you want to verify the CLI pipe is functional.

Do not write a smoke journal into the user's real `~/Documents/Life-Index/` directory. Use a temporary sandbox through `LIFE_INDEX_DATA_DIR`, create one disposable Markdown file inside that sandbox, build only the keyword index, then search with `--no-semantic`.

**Linux/macOS**:
```bash
SMOKE_DIR=$(mktemp -d)
TODAY=$(date +%F)
export LIFE_INDEX_DATA_DIR="$SMOKE_DIR"
mkdir -p "$LIFE_INDEX_DATA_DIR/Journals/${TODAY:0:4}/${TODAY:5:2}"
cat > "$LIFE_INDEX_DATA_DIR/Journals/${TODAY:0:4}/${TODAY:5:2}/life-index_${TODAY}_001.md" <<EOF
---
title: Smoke Test Entry
date: $TODAY
topic: test
---
Temporary sandbox onboarding smoke keyword.
EOF

.venv/bin/life-index index --fts-only --json
.venv/bin/life-index search --query "smoke" --no-semantic
rm -rf "$SMOKE_DIR"
unset LIFE_INDEX_DATA_DIR
```

**Windows (PowerShell)**:
```powershell
$smokeDir = Join-Path $env:TEMP ("life-index-onboarding-smoke-" + [guid]::NewGuid())
$today = Get-Date -Format 'yyyy-MM-dd'
$env:LIFE_INDEX_DATA_DIR = $smokeDir
$journalDir = Join-Path $smokeDir ("Journals\{0}\{1}" -f $today.Substring(0,4), $today.Substring(5,2))
New-Item -ItemType Directory -Force -Path $journalDir | Out-Null
@"
---
title: Smoke Test Entry
date: $today
topic: test
---
Temporary sandbox onboarding smoke keyword.
"@ | Set-Content -LiteralPath (Join-Path $journalDir ("life-index_{0}_001.md" -f $today)) -Encoding UTF8

.venv\Scripts\life-index index --fts-only --json
.venv\Scripts\life-index search --query "smoke" --no-semantic
Remove-Item -LiteralPath $smokeDir -Recurse -Force
Remove-Item Env:\LIFE_INDEX_DATA_DIR
```

**Smoke Test Reporting**:
- If it passes: mention it in the final report as "CLI pipe verified with temporary sandbox keyword-only search"
- If it fails: mention it as "optional sandbox smoke test failed" but do **not** mark onboarding as failed
- If cleanup fails: report the sandbox path; do **not** touch the user's real data directory

---

### Step 5.4: Optional Customization (Post-Verification)

Run this step **only after** all `safe_next_steps` complete. This step is optional — skip if the user declines.

**A. Trigger phrase** — Suggest the user set a custom trigger phrase in the form `/life-index <their phrase>` (e.g., `/life-index 记日志: 今天状态不错`). If agreed, update the trigger list in `SKILL.md` — keep `/life-index`, keep examples consistent, do not touch unrelated sections.

**B. Default location** — Ask whether the user wants to override the default location (`Chongqing, China`). If agreed, write to `~/Documents/Life-Index/.life-index/config.yaml` using `config.example.yaml` as schema reference. You may report the preference was **saved** but must **not** claim it is runtime-active unless verified.

**Boundaries — Allowed**: edit `SKILL.md` triggers, create/update config.yaml. **Not allowed**: modify `tools/`, `docs/API.md`, `docs/ARCHITECTURE.md`, `pyproject.toml`, remove `/life-index` from triggers, or customize without explicit user approval.

---

### Step 5.5: Optional Automation Setup Handoff

Run this step **only after** all `safe_next_steps` and optional customization complete. This step is optional.

If the user wants recurring automation (monthly/yearly reports, periodic index rebuilds), explain that Life Index has no built-in scheduler and should be orchestrated by the host platform's scheduling mechanism.

**Boundaries**: installation is already complete and separate from automation. Life Index has no built-in scheduler — automation depends on host-platform scheduling. User may enable only the tasks they want. Automation failure must not be reported as installation failure.

---

## 6. Success Criteria Summary

| Step | Success Indicator | Applicable Route |
|:---|:---|:---|
| Authority Refresh | `bootstrap-manifest.json` + `required_authority_docs` refreshed | all |
| Bootstrap Gate | `route` returned, `needs_human` handled | all |
| Safe Next Steps | All `safe_next_steps` completed or passed | all |
| Health (if in safe_next_steps) | `success: true`, `status` not "unhealthy" | all |
| Semantic Status | `ready` / `building` / `disabled` / `failed` (reported, non-blocking) | all |
| Keyword Status | `ready` (FTS5 is the core capability) | all |
| Optional Smoke Test | `write`+`search` pass or fail (does not affect success) | fresh_install only |
| Schema Migration (upgrade) | `migrate --dry-run` shows `needs_migration: 0` or user acknowledged | upgrade only |
| Optional Customization | User-approved personalization applied or explicitly skipped | all |
| Optional Automation Setup | User either skipped automation or was correctly handed off to `SCHEDULE.md` after successful onboarding | all |

---

## 7. Common Failure Handling

### ModuleNotFoundError

**Cause**: Using system Python instead of venv Python
**Fix**: Use `.venv/bin/python` (Linux/macOS) or `.venv\Scripts\python` (Windows)

### JSON Parse Error (Windows)

**Cause**: PowerShell escaping issues
**Fix**: Use file-based input: `--data @file.json`

### Semantic Index Still Building

**Cause**: Semantic / vector indexing is optional and may build in the background
**Fix**: Report `semantic_status`; do not block onboarding or retry foreground model loading

### No Search Results

**Cause**: Index not built or corrupted; or keyword-only search legitimately returned zero matches
**Fix**: If `safe_next_steps` includes `index`, run it. Otherwise, report the empty result to the user without auto-rebuilding.

### Health Shows "degraded"

**Cause**: Data directory, search index, or embedding model is not fully initialized yet
**Fix**: If `safe_next_steps` includes `index`, run it, then re-run health. If `safe_next_steps` does not include `index`, report the health issues to the user and do not auto-run index. A degraded status with acceptable warnings is still a passing result.

### Venv Corrupted

**Cause**: Python version change or interrupted install
**Fix**: First confirm the current checkout passed Step 0.3 and is the intended install target. Then confirm the venv layout matches the current platform. Only after both checks pass, delete `.venv/`, recreate it with `python3 -m venv .venv`, and reinstall with `pip install -e .`.

### Cross-Platform Venv Mismatch on WSL/Windows

**Cause**: A `.venv` created on Windows uses `.venv/Scripts/python.exe`; a `.venv` created on WSL/Linux uses `.venv/bin/python`. These layouts are not interchangeable.

**Fix**: Do not repair or delete the other platform's venv from the current platform. Treat the mismatch as evidence that you may be in a development checkout or the wrong install target. Return to Step 0.3, prefer the host-managed skill directory, or ask the user to confirm the intended install target.

### CUDA Dependencies Bloat on WSL/Linux (only with `[semantic]`)

**Cause**: Base `pip install -e .` does **not** pull torch. Only the optional `[semantic]` extra pulls torch, which defaults to the full CUDA build (~2GB) on Linux.
**Fix**: If semantic search is needed on a CPU-only environment, pre-install CPU-only torch first: `pip install torch --index-url https://download.pytorch.org/whl/cpu`, then `pip install -e '.[semantic]'`. If semantic search is not needed, plain `pip install -e .` avoids the ML stack entirely.

---

## 8. Final Report Format

Report back to the user using this structure. The entire report must be in one language: Chinese if onboarding came from `README.md`, English if from `README.en.md`, or the user's explicitly requested language.

```
## Life Index Installation Complete

**Status**: ✅ Success (or ❌ Failed with errors)

**Route**: <fresh_install / upgrade>

**Installation Location**: <full path to life-index directory>

**Data Directory**: ~/Documents/Life-Index/

**Health Check**: <healthy/degraded/unhealthy>
- Python version: <version>
- Virtual environment: <active/inactive>
- Dependencies: <all installed/missing: X>

**Semantic Status**: <ready / building / disabled / failed>
**Keyword Status**: <ready / degraded / failed>

**Safe Next Steps Executed**: <list of steps run from safe_next_steps>

**Optional Smoke Test**: <passed/failed/skipped>
- If passed: "CLI pipe verified with temporary sandbox keyword-only search"
- If failed: "Optional smoke test failed — does not affect installation success"

**Customization**:
- Trigger phrase: <report as combined form `/life-index [user phrase]` only; never separate>
- Default location preference: <saved/skipped>
- Default location runtime verification: <verified/not verified/not attempted>

**How to Use Life Index Now**:
<Write a brief human-facing usage guide in the report language. Must include:
- The user's combined trigger phrase: `/life-index [custom phrase]`
- Their default city
- 1-2 concrete usage examples with the trigger phrase
- Mention search, review, and edit capabilities
Keep it concise — this is a welcome message, not a manual.>

**Notes**:
- <any warnings or non-blocking issues>
- <reminder about Windows path syntax if applicable>
- <whether semantic search is still building or disabled>
```

---

## 9. Guardrails (Strict)

### Do NOT:
- Modify any files outside the installation workflow
- Delete user data in `~/Documents/Life-Index/` if it exists
- Install additional dependencies not specified in `pyproject.toml`
- Require `gh` CLI or any GitHub-specific tools
- Create MCP server configurations (not supported)
- Modify repository source code during installation, except the explicitly allowed trigger-surface edits in `SKILL.md` during optional customization
- Skip the health check when it is present in `safe_next_steps`
- Treat `write`/`search` as mandatory install success gates
- Wait for `semantic_status: ready` before declaring installation success
- Re-interpret bootstrap `route` based on local state

### Do:
- Keep all user data in `~/Documents/Life-Index/` (separate from code)
- Use venv paths exclusively for all commands
- Report exact error messages on failure
- Verify each step before proceeding
- Clean up partial installations on failure (if requested by user)
- Stop immediately if prerequisites are missing or a command fails twice in the same step
- Keep customization clearly separate from installation success/failure
- Report honestly whether default-location customization was only saved or also runtime-verified
- In both `Customization` and `How to Use Life Index Now`, represent the trigger only as the combined form `/life-index [user custom trigger phrase]`; never present `/life-index` and the custom phrase as separate alternatives
- Keep the `How to Use Life Index Now` section human-facing, concise, and aligned to the fixed delivery structure above
- Keep the entire final report in one language; do not mix English section headings with a Chinese usage guide or vice versa
- Do not ask the user for a persistent language preference during optional customization unless the product later adds an actual stored language setting

---

## 10. Data Locations Reference

| Location | Path |
|:---|:---|
| Journals | `~/Documents/Life-Index/Journals/` |
| Attachments | `~/Documents/Life-Index/attachments/` |
| Index | `~/Documents/Life-Index/.index/` |
| Config (optional) | `~/Documents/Life-Index/.life-index/config.yaml` |

---

## 11. CLI Quick Reference

| Command | Purpose |
|:---|:---|
| `life-index health` | Installation health check |
| `life-index index` | Build/update search index |
| `life-index index --rebuild` | Full index rebuild |
| `life-index write --data '{...}'` | Write new journal entry |
| `life-index search --query "..."` | Search journals |
| `life-index search --query "..." --no-semantic` | Keyword-only search (no model load) |
| `life-index edit --journal "..." --set-weather "..."` | Edit existing entry |
| `life-index abstract --month YYYY-MM` | Generate monthly summary |
| `life-index weather --location "..."` | Query weather for location |
| `life-index migrate --dry-run` | Preview schema migration |
| `life-index migrate --apply` | Execute schema migration |
| `life-index entity --audit` | Entity graph quality audit |
| `life-index smart-search --query "..."` | Smart search deterministic scaffold; no LLM by default |
| `life-index smart-search --query "..." --use-llm` | Explicitly enable LLM orchestration |

---

**Document Version**: 2.6
**Last Updated**: 2026-06-12
**Authority Chain**: `CHARTER.md` governs project invariants. `bootstrap-manifest.json` governs install/upgrade/repair freshness and points to the current required authority documents through `required_authority_docs`.
