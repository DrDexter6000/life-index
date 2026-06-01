# Agent Onboarding Guide: Life Index Installation

> **Document Purpose**: Step-by-step operational instructions for AI agents installing Life Index on behalf of users.
> **Audience**: External AI agents (not humans)
> **Scope**: CLI installation, initialization, repair, and first-use verification
> **Governance SSOT**: `CHARTER.md`
> **Install freshness anchor**: `bootstrap-manifest.json`; refresh every path listed in `required_authority_docs`

---

## 1. Goal

Install and initialize Life Index on the user's machine, verify the installation is functional, and complete the first write/search cycle to confirm end-to-end operation.

This document is now a **smart entrypoint** rather than a fresh-install-only script. Your first job is to detect whether the machine is in a fresh install state, an upgrade state, or a partial/broken state.

You are acting on behalf of a user. Your job is to execute the installation workflow safely, verify each stage, and report the result back clearly.

Before taking any action, read this entire document once.

---

## 2. Step 0 — Refresh Authority First, Then Run Bootstrap Detection

Do **not** clone, recreate `.venv`, run `health`, adopt a checkout, delete anything, or classify fresh-install vs upgrade until you complete this gate.

### Step 0.1: Refresh authority documents first

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
| `fresh_install` | No existing journal data found | Steps 4.1 → 4.3 → 5.1 → 5.4 |
| `upgrade` | Existing journal data found | Sync/reinstall as needed → run all `safe_next_steps` in order → Steps 5.1 → 5.4 |

If `safe_next_steps` is non-empty, run them in order before the route's verification steps. On `upgrade`, `life-index health` should appear as the final safe next step. If health returns `status: "unhealthy"` after sync/reinstall/migration checks, treat this as **Repair / Ambiguous State**:

1. do **not** pretend this is a clean fresh install;
2. use this document's sync / reinstall / verification flow as the repair baseline;
3. if state remains unclear after basic inspection, ask the user before destructive cleanup.

**Checkout adoption rule**: only adopt a checkout when `detected_state.checkout_assessment.safe_to_adopt` is `true`. A checkout with no dev signals is still not adoptable unless it came from a host-managed path or was explicitly user-designated.

---

## 3. Prerequisites

---

Before starting, verify these requirements are met:

| Requirement | Verification Command | Minimum Version |
|:---|:---|:---|
| Python | `python3 --version` or `python --version` | 3.11+ |
| Git | `git --version` | Any recent |
| Disk space | ~700MB available | For code, venv, and embedding model (torch ~190MB CPU-only, model ~80MB) |
| Network | Internet connection | For cloning and model download |

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
- Fall back to the standard repository-driven path in this document: `git clone` → `python -m venv .venv` → `pip install -e .` → `life-index index` → verification.
- Prefer the documented repository workflow over undocumented host-platform behavior.

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

---

### Step 4.3: Install Package (Editable Mode)

**Linux/macOS/WSL**:
```bash
.venv/bin/pip install -e .
```

**⚠️ WSL / headless Linux CPU-only optimization**:
If the target machine has no GPU (common for agent environments), install the CPU-only version of torch first to skip ~2GB of CUDA dependencies:
```bash
.venv/bin/pip install torch --index-url https://download.pytorch.org/whl/cpu
.venv/bin/pip install -e .
```

**Windows**:
```powershell
.venv\Scripts\pip install -e .
```

**Success Criteria**:
- Installation completes with "Successfully installed life-index"
- Dependencies installed (pyyaml, sentence-transformers, numpy)
- No red error messages

**Failure Handling**:
- If `pip` not found: verify the `.venv` platform layout first. Delete and recreate `.venv/` only after Step 0.3 confirms this is the intended install target and the existing venv is not a development venv from another platform.
- If dependency fails: Retry once, then report to user

---

## 5. Initialization Workflow

Execute these steps in order. Each step must succeed before proceeding.

After the required verification flow is complete, an **optional customization step** may follow. That step should follow the guardrails in this document plus the current configuration contracts in `docs/API.md` / `tools/lib/config.py`; the older review-scoped customization protocol is no longer the active reference.

### Optional Customization Step (Post-Verification)

After installation, first write, and first search verification all pass, the Agent may offer two optional customizations:

1. **专用触发词**：采用 `"/life-index" + "用户自定义触发词"` 的组合；如用户同意，Agent 可修改 `SKILL.md` 中的 trigger 列表与对应示例
2. **默认地址偏好**：如用户同意，Agent 可创建或更新 `~/Documents/Life-Index/.life-index/config.yaml` 中的 `defaults.location`

**Guardrails**:
- 不得移除 `/life-index`
- 不得重写与触发词无关的 workflow 段落
- 默认地址配置必须诚实区分“已保存”与“已验证生效”
- 如用户未明确要求个性化，不要在安装主流程中强行插入该步骤

### Step 5.1: Build Index (Initialization)

```bash
# Linux/macOS:
.venv/bin/life-index index

# Windows:
.venv\Scripts\life-index index
```

**What Happens**:
1. Creates `~/Documents/Life-Index/` directory structure
2. Downloads ~80MB embedding model (first run only, takes 1-3 minutes)
3. Initializes FTS5 and vector indexes

**Success Criteria**:
- Command completes without errors
- Progress shown for model download (if first run)
- Returns success message

**Expected Wait**: 1-3 minutes for model download on first run. Do not interrupt.

**Failure Handling**:
- If hangs >5 minutes: Report "model download timeout" to user
- If errors: Capture full output and report

---

### Step 5.2: Health Check

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

**Known Nuance**: Pre-init `health` may legitimately report "degraded" before initial indexing. This is expected and acceptable. The post-init health check (after Step 5.1) should show "healthy" or acceptable "degraded" state.

**Acceptable Warnings**:
- `virtual_env: "warning"` — Expected if running via full path
- `sentence_transformers: "warning"` — Optional; keyword search remains available when semantic dependencies are unavailable

**Post-Round 6 Note**:
The health response may include an `events` array with piggyback notifications (e.g., writing streak reminders, schema migration suggestions). These are informational and do not indicate errors. You may surface relevant events to the user at your discretion.

**Failure Handling**:
- If `status: "unhealthy"`: Capture all issues and report to user
- If `ModuleNotFoundError`: Venv not being used, return to Step 4

---

### Step 5.3: First Write

Create the first journal entry to verify write functionality.

Use the machine's current local date at execution time, formatted as `YYYY-MM-DD`.
Do **not** write placeholder text such as `System current time` or `{TODAY}` literally into the JSON payload.

**Linux/macOS**:
```bash
TODAY=$(date +%F)

.venv/bin/life-index write --data "{
  \"title\": \"First Journal Entry\",
  \"content\": \"Today I set up Life Index. Looking forward to recording my journey.\",
  \"date\": \"$TODAY\",
  \"topic\": [\"life\"],
  \"abstract\": \"Initial setup of Life Index journaling system.\",
  \"mood\": [\"hopeful\"],
  \"tags\": [\"setup\"],
  \"people\": [],
  \"project\": \"\",
  \"links\": [],
  \"entities\": []
}"
```

**Windows (Recommended: File-based)**:
```powershell
# Compute current local date first, then create JSON file (avoids escaping issues)
$today = Get-Date -Format 'yyyy-MM-dd'

$json = @"
{
  "title": "First Journal Entry",
  "content": "Today I set up Life Index. Looking forward to recording my journey.",
  "date": "$today",
  "topic": ["life"],
  "abstract": "Initial setup of Life Index journaling system.",
  "mood": ["hopeful"],
  "tags": ["setup"],
  "people": [],
  "project": "",
  "links": [],
  "entities": []
}
"@
$json | Out-File -FilePath "first-entry.json" -Encoding utf8
.venv\Scripts\life-index write --data @first-entry.json
```

**Success Criteria**:
- `success: true`
- `journal_path` returned with valid path
- File exists at `~/Documents/Life-Index/Journals/YYYY/MM/life-index_YYYY-MM-DD_001.md`
- If `needs_confirmation` is returned, include the confirmation message in your final report instead of inventing your own summary

**Failure Handling**:
- If JSON parse error: On Windows, use file-based input (`@file.json`)
- If missing required fields error: Include all fields shown in example
- If write fails: Capture error code and report

---

### Step 5.4: First Search

Verify the entry can be retrieved via search.

If this is the first search after a write, the command may first consume pending index updates and load search models/caches. A 10-30 second first run is expected behavior, not a failure.

```bash
# Linux/macOS:
.venv/bin/life-index search --query "First Journal"

# Windows:
.venv\Scripts\life-index search --query "First Journal"
```

**Success Criteria**:
- `success: true`
- Returned search payload includes at least one matching result
- The entry just written appears in the returned results

**Failure Handling**:
- If `total: 0`: Run `.venv/bin/life-index index` (or Windows equivalent) to rebuild index, then retry search
- If errors: Capture and report

---

### Step 5.5: Optional Customization (Post-Install Personalization)

Run this step **only after** Steps 5.1-5.4 succeed. This step is optional — skip if the user declines.

**A. Trigger phrase** — Suggest the user set a custom trigger phrase in the form `/life-index <their phrase>` (e.g., `/life-index 记日志: 今天状态不错`). If agreed, update the trigger list in `SKILL.md` — keep `/life-index`, keep examples consistent, do not touch unrelated sections.

**B. Default location** — Ask whether the user wants to override the default location (`Chongqing, China`). If agreed, write to `~/Documents/Life-Index/.life-index/config.yaml` using `config.example.yaml` as schema reference. You may report the preference was **saved** but must **not** claim it is runtime-active unless verified.

**Boundaries — Allowed**: edit `SKILL.md` triggers, create/update config.yaml. **Not allowed**: modify `tools/`, `docs/API.md`, `docs/ARCHITECTURE.md`, `pyproject.toml`, remove `/life-index` from triggers, or customize without explicit user approval.

---

### Step 5.6: Optional Automation Setup Handoff

Run this step **only after** Steps 5.1-5.5 complete. This step is optional.

If the user wants recurring automation (monthly/yearly reports, periodic index rebuilds), explain that Life Index has no built-in scheduler and should be orchestrated by the host platform's scheduling mechanism.

**Boundaries**: installation is already complete and separate from automation. Life Index has no built-in scheduler — automation depends on host-platform scheduling. User may enable only the tasks they want. Automation failure must not be reported as installation failure.

---

## 6. Success Criteria Summary

| Step | Success Indicator |
|:---|:---|
| Clone | Repository exists, `SKILL.md` present |
| Venv | `.venv/` directory created |
| Install | "Successfully installed life-index" message |
| Index | Command completes, model downloaded |
| Health | `success: true`, `status` not "unhealthy" |
| Schema Migration (upgrade only) | `migrate --dry-run` shows `needs_migration: 0` or user acknowledged `needs_agent` items |
| First Write | `success: true`, `journal_path` returned |
| First Search | `success: true`, `total` >= 1, entry found |
| Optional Customization | User-approved personalization applied or explicitly skipped |
| Optional Automation Setup | User either skipped automation or was correctly handed off to `SCHEDULE.md` after successful onboarding |

---

## 7. Common Failure Handling

### ModuleNotFoundError

**Cause**: Using system Python instead of venv Python
**Fix**: Use `.venv/bin/python` (Linux/macOS) or `.venv\Scripts\python` (Windows)

### JSON Parse Error (Windows)

**Cause**: PowerShell escaping issues
**Fix**: Use file-based input: `--data @file.json`

### Index Build Hangs

**Cause**: Downloading ~80MB embedding model
**Fix**: Wait 1-3 minutes, do not interrupt

### No Search Results

**Cause**: Index not built or corrupted
**Fix**: Run `life-index index` to rebuild

### Health Shows "degraded"

**Cause**: Data directory, search index, or embedding model is not fully initialized yet
**Fix**: If this happened before the initial `life-index index`, continue with indexing. If it still happens after indexing, include the issues list in the final report.

### Venv Corrupted

**Cause**: Python version change or interrupted install
**Fix**: First confirm the current checkout passed Step 0.3 and is the intended install target. Then confirm the venv layout matches the current platform. Only after both checks pass, delete `.venv/`, recreate it with `python3 -m venv .venv`, and reinstall with `pip install -e .`.

### Cross-Platform Venv Mismatch on WSL/Windows

**Cause**: A `.venv` created on Windows uses `.venv/Scripts/python.exe`; a `.venv` created on WSL/Linux uses `.venv/bin/python`. These layouts are not interchangeable.

**Fix**: Do not repair or delete the other platform's venv from the current platform. Treat the mismatch as evidence that you may be in a development checkout or the wrong install target. Return to Step 0.3, prefer the host-managed skill directory, or ask the user to confirm the intended install target.

### CUDA Dependencies Bloat on WSL/Linux

**Cause**: `pip install -e .` pulls full CUDA toolkit (~2GB) via torch dependency on Linux
**Fix**: On CPU-only environments, pre-install CPU-only torch first: `pip install torch --index-url https://download.pytorch.org/whl/cpu`, then `pip install -e .`

---

## 8. Final Report Format

Report back to the user using this structure. The entire report must be in one language: Chinese if onboarding came from `README.md`, English if from `README.en.md`, or the user's explicitly requested language.

```
## Life Index Installation Complete

**Status**: ✅ Success (or ❌ Failed with errors)

**Installation Location**: <full path to life-index directory>

**Data Directory**: ~/Documents/Life-Index/

**Health Check**: <healthy/degraded/unhealthy>
- Python version: <version>
- Virtual environment: <active/inactive>
- Dependencies: <all installed/missing: X>

**First Journal**: <path to first entry>
- Title: <title>
- Date: <date>
- Location: <location>
- Weather: <weather>

**Search Test**: <passed/failed>
- Query: "First Journal"
- Results found: <number>

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
- <whether `needs_confirmation` was returned by first write>
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
- Skip the health check or first write/search verification

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
| `life-index edit --journal "..." --set-weather "..."` | Edit existing entry |
| `life-index abstract --month YYYY-MM` | Generate monthly summary |
| `life-index weather --location "..."` | Query weather for location |
| `life-index migrate --dry-run` | Preview schema migration |
| `life-index migrate --apply` | Execute schema migration |
| `life-index entity --audit` | Entity graph quality audit |
| `life-index smart-search --query "..."` | Smart search deterministic scaffold; no LLM by default |
| `life-index smart-search --query "..." --use-llm` | Explicitly enable LLM orchestration |

---

**Document Version**: 2.3
**Last Updated**: 2026-06-01
**Authority Chain**: `CHARTER.md` governs project invariants. `bootstrap-manifest.json` governs install/upgrade/repair freshness and points to the current required authority documents through `required_authority_docs`.
