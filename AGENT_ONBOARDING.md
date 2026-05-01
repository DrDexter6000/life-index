# Agent Onboarding Guide: Life Index Installation

> **Document Purpose**: Step-by-step operational instructions for AI agents installing Life Index on behalf of users.
> **Audience**: External AI agents (not humans)
> **Scope**: CLI installation, initialization, repair, and first-use verification
> **SSOT References**: `bootstrap-manifest.json`, `SKILL.md`, `docs/API.md`, `docs/ARCHITECTURE.md`

---

## 1. Goal

Install and initialize Life Index on the user's machine, verify the installation is functional, and complete the first write/search cycle to confirm end-to-end operation.

This document is now a **smart entrypoint** rather than a fresh-install-only script. Your first job is to detect whether the machine is in a fresh install state, an upgrade state, or a partial/broken state.

You are acting on behalf of a user. Your job is to execute the installation workflow safely, verify each stage, and report the result back clearly.

Before taking any action, read this entire document once.

---

## 2. Step 0 — Refresh Authority First, Then Detect Local State

Do **not** clone, recreate `.venv`, run `health`, or classify fresh-install vs upgrade until you complete this gate.

### Step 0.1: Refresh authority documents first

Before trusting any local checkout, refresh `bootstrap-manifest.json` from the current upstream repository. Then treat that manifest as the version/authority anchor and refresh **every file listed in its `required_authority_docs` array** before proceeding. Treat local copies as potentially stale.

### Step 0.2: Check user data first (highest priority)

Check whether the user already has Life Index data:

- `~/Documents/Life-Index/`
- `~/Documents/Life-Index/Journals/`
- any existing journal files under `Journals/YYYY/MM/*.md`

**Rule**:
- If real journal data already exists, treat the machine as **not fresh install** unless strong evidence proves otherwise.
- Protect user data first. Do not assume it is safe to restart from zero.

### Step 0.3: Identify the canonical checkout

Check whether there is already a Life Index repository checkout with files such as:

- `SKILL.md`
- `pyproject.toml`
- `bootstrap-manifest.json`
- `.venv/`

#### Host-managed canonical checkout rule

If the host Agent platform already manages skills in a canonical directory, prefer that managed checkout over ad hoc working-directory clones.

If you discover multiple Life Index checkouts, do **not** silently pick a random one and do **not** create a third clone. Prefer the host-managed canonical checkout or the user-designated checkout, and if the active install location is still ambiguous, report the conflict and ask the user before cleanup.

### Step 0.4: Mandatory sync gate before any route decision

If a canonical checkout exists and network access is available, you **must** sync that checkout before doing health checks or route classification.

Minimum rule:

1. fetch/pull the canonical checkout from the upstream repository
2. ensure `bootstrap-manifest.json` exists after sync
3. reinstall into `.venv` after sync using the documented editable install path

If the checkout cannot be synced because of local conflicts, detached state, or other git problems, do **not** pretend the checkout is current. Switch to repair handling.

If network is unavailable, you may continue only after explicitly warning the user that you cannot verify freshness and may be operating on a stale checkout.

### Step 0.5: Version/freshness is a mandatory gate

Use the refreshed `bootstrap-manifest.json` plus local `life-index --version` output to determine whether the local checkout and installed package reflect the expected current version.

**Critical rule**:
- health only proves the installed system works
- freshness proves the installed system is current
- both gates must pass before you may report the install as current

Do **not** treat `.venv` existence, CLI reachability, or passing `life-index health` as evidence that the checkout is up to date.

### Step 0.6: Only now decide the route

Use these rules **after** authority refresh and checkout sync:

#### Route A — Fresh Install

Choose **Fresh Install** only if all of the following are true:

- no existing journal data is found
- no reliable existing repo/venv installation is found
- there is no sign of a partial prior install worth preserving

If Fresh Install is selected, continue with the normal onboarding steps in this document.

#### Route B — Upgrade Existing Install

Choose **Upgrade** if any of the following are true:

- existing journal data is found
- a canonical checkout exists and has just been successfully synced
- an existing install was found and reinstalled after sync

If Upgrade is selected, continue using this document as the operational guide.

Upgrade handling rules:

1. treat the existing checkout and user data as the baseline to preserve
2. do not create a parallel clone if a canonical checkout already exists
3. sync checkout → reinstall into `.venv` → **check for schema migration** → rerun verification in this document
4. do not claim success until freshness and health both pass

#### Post-upgrade schema migration check

After reinstall, check whether existing journals need schema migration:

```bash
.venv/bin/life-index migrate --dry-run
```

If `needs_migration > 0`:
- Run `life-index migrate --apply` to apply deterministic schema updates
- If the output includes `needs_agent` items, report these to the user — they require Agent-driven semantic enrichment (extracting abstract/mood from content)

#### Route C — Repair / Ambiguous State

Choose **Repair / Ambiguous** if signals conflict, for example:

- journal data exists but repo/venv is missing
- `.venv` exists but `life-index health` fails badly after sync/reinstall
- repo exists but checkout sync fails or install still looks partial/broken

If Repair / Ambiguous is selected:

1. do **not** pretend this is a clean fresh install
2. use this document's sync / reinstall / verification flow as the repair baseline
3. if the state is still unclear after basic inspection, ask the user before doing destructive cleanup

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
- If `pip` not found: Virtual environment may be corrupted, delete `.venv/` and recreate
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

If the user wants recurring automation (monthly/yearly reports, periodic index rebuilds), hand off to `references/schedule/SCHEDULE.md`.

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
**Fix**: Delete `.venv/` directory, recreate with `python3 -m venv .venv`, reinstall with `pip install -e .`

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
| `life-index smart-search --query "..."` | Smart search with LLM orchestration |
| `life-index smart-search --query "..." --no-llm` | Smart search (degraded, no LLM) |

---

**Document Version**: 2.1
**Last Updated**: 2026-05-01
**Authority Chain**: `bootstrap-manifest.json` → `AGENT_ONBOARDING.md` / `README.md` → domain SSOT docs such as `SKILL.md`, `docs/API.md`, `docs/ARCHITECTURE.md`, `tools/lib/AGENTS.md`
