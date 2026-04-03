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

Before trusting any local checkout, refresh `bootstrap-manifest.json` from the current upstream repository first.

- `bootstrap-manifest.json`

Then treat that manifest as the version/authority anchor and refresh every file listed in its `required_authority_docs` array before proceeding.

At minimum, the refreshed authority set must include:

- `bootstrap-manifest.json`
- `AGENT_ONBOARDING.md`
- `SKILL.md`
- `docs/API.md`
- `docs/ARCHITECTURE.md`
- `tools/lib/AGENTS.md`
- `README.md`

You must treat local copies of these files as potentially stale.

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
3. sync checkout → reinstall into `.venv` → rerun verification in this document
4. do not claim success until freshness and health both pass

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
| Disk space | ~200MB available | For code, venv, and embedding model |
| Network | Internet connection | For cloning and model download |

**Action**: Run the verification commands. If any fail, stop and report the missing prerequisite to the user.

---

## 4. Repository Location

- **Primary**: `https://github.com/DrDexter6000/life-index`
- **Clone target**: User-specified skill directory, or current working directory if unspecified

---

## 5. Installation Steps

Execute these steps in order. Do not skip steps.

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

## 6. Virtual Environment Usage Rules

**CRITICAL**: All subsequent commands MUST use the venv Python/CLI, not system Python.

| Platform | Python Path | CLI Path |
|:---|:---|:---|
| Linux/macOS/WSL | `.venv/bin/python` | `.venv/bin/life-index` |
| Windows | `.venv\Scripts\python` | `.venv\Scripts\life-index` |

**Guardrail**: If you see `ModuleNotFoundError` at any point, you are likely using system Python instead of venv Python. Switch to the venv path.

---

## 7. Windows Path Preference

On Windows, the path separator is backslash (`\`), not forward slash (`/`). The executable directory is `Scripts`, not `bin`.

**Correct**: `.venv\Scripts\life-index`
**Incorrect**: `.venv/bin/life-index` (will fail on Windows)

---

## 8. Initialization Workflow

Execute these steps in order. Each step must succeed before proceeding.

After the required verification flow is complete, an **optional customization step** may follow. That step should follow the guardrails in this document plus the current configuration contracts in `docs/API.md` / `tools/lib/config.py`; the older review-scoped customization protocol is no longer the active reference.

### Step 7.1: Build Index (Initialization)

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

### Step 7.2: Health Check

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

**Known Nuance**: Pre-init `health` may legitimately report "degraded" before initial indexing. This is expected and acceptable. The post-init health check (after Step 7.1) should show "healthy" or acceptable "degraded" state.

**Acceptable Warnings**:
- `virtual_env: "warning"` — Expected if running via full path
- `sentence_transformers: "warning"` — Optional; keyword search remains available when semantic dependencies are unavailable

**Failure Handling**:
- If `status: "unhealthy"`: Capture all issues and report to user
- If `ModuleNotFoundError`: Venv not being used, return to Step 5

---

### Step 7.3: First Write

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
  \"links\": []
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
  "links": []
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

### Step 7.4: First Search

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

### Step 7.5: Optional Customization (Post-Install Personalization)

Run this step **only after** Steps 7.1-7.4 succeed.

This step is optional. If the user does not want customization, skip it and finish onboarding normally.

This step currently covers **only**:

1. trigger phrase customization
2. default location preference

Do **not** add a separate language-preference question during optional customization.
Report language should be determined by the onboarding entry context or the user's explicit request in the current conversation, not stored as a new customization setting.

#### Customization question A — trigger phrase

To improve Life Index trigger success rate in current Agent / LLM ecosystems, you should tell the user that they need to provide a custom trigger phrase.

State the current best-practice pattern clearly:

`"/life-index" + "user custom trigger phrase" + "journal content"`

Give concrete examples such as:

- `/life-index 记日志: 今天状态不错`
- `/life-index note this: 刚刚看到一篇文章很有启发`

Then ask the user to provide the trigger phrase they want to use. If they do not want to set one now, they may explicitly reply `skip` / `跳过`.

If the user agrees:

- you may update the trigger definitions in `SKILL.md`
- keep `/life-index` in the trigger list
- keep trigger examples and trigger table entries consistent with the edited trigger list
- do **not** rewrite unrelated workflow sections

#### Customization question B — default location preference

You may ask the user whether they want to save a different preferred default address instead of `Chongqing, China`.

If the user agrees:

- write the preference to `~/Documents/Life-Index/.life-index/config.yaml`
- use `config.example.yaml` as the schema reference
- preserve unrelated config fields if the file already exists
- use `City, Country` format

#### Important honesty rule

You may report that the preference was **saved**.

You must **not** claim that the new default location is already active at runtime unless you explicitly verified that behavior.

#### Strict boundaries for this step

**Allowed**:
- update the trigger list/examples in `SKILL.md`
- create or update `~/Documents/Life-Index/.life-index/config.yaml`

**Not allowed**:
- modify tool source code under `tools/`
- modify `docs/API.md`, `docs/ARCHITECTURE.md`, or `pyproject.toml`
- remove `/life-index` from the trigger list
- perform any customization without explicit user approval

---

### Step 7.6: Optional Automation Setup Handoff

Run this step **only after** Steps 7.1-7.5 complete successfully or optional customization is explicitly skipped.

This step is optional. If the user does not want recurring automation, skip it and finish onboarding normally.

This step does **not** mean Life Index contains native scheduling runtime.
It means the agent may, on supported host platforms, help the user configure optional recurring automation by following:

- `references/schedule/SCHEDULE.md`

#### Purpose of this handoff

Use this handoff only if the user wants post-onboarding quality-of-life automation such as:

- monthly report
- yearly report
- monthly rebuild / maintenance
- optional daily / weekly reports

#### Required interaction rule

Ask the user whether they want to continue with optional automation setup **after** installation verification is already complete.

Do not present automation as mandatory.

#### Required boundary rule

When handing off to `SCHEDULE.md`, keep the following distinctions explicit:

- installation success is already complete
- automation setup depends on host-platform scheduling support
- the user may enable only the tasks they want
- failure in automation setup must not be reported as installation failure

#### Strict boundaries for this step

**Allowed**:
- explain that optional automation setup is available
- ask whether the user wants to continue
- if the user agrees, follow `references/schedule/SCHEDULE.md`

**Not allowed**:
- claim Life Index has built-in scheduler runtime
- force the user to configure automation
- blur automation failure into installation failure
- duplicate the full scheduler guide inside onboarding instead of handing off to `SCHEDULE.md`

---

## 8. Success Criteria Summary

| Step | Success Indicator |
|:---|:---|
| Clone | Repository exists, `SKILL.md` present |
| Venv | `.venv/` directory created |
| Install | "Successfully installed life-index" message |
| Index | Command completes, model downloaded |
| Health | `success: true`, `status` not "unhealthy" |
| First Write | `success: true`, `journal_path` returned |
| First Search | `success: true`, `total` >= 1, entry found |
| Optional Customization | User-approved personalization applied or explicitly skipped |
| Optional Automation Setup | User either skipped automation or was correctly handed off to `SCHEDULE.md` after successful onboarding |

---

## 9. Common Failure Handling

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

---

## 10. Final Report Format

Report back to the user using this exact structure:

**Language rule for the entire report**:

- If the onboarding entry prompt came from `README.md`, the entire final report must be in Chinese
- If the onboarding entry prompt came from `README.en.md`, the entire final report must be in English
- If the user explicitly requests another report language in the current conversation, follow that explicit request
- The `How to Use Life Index Now` section must use the **same language as the rest of the final report**

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
- Trigger phrase: <if configured, report only in the combined form `/life-index [user custom trigger phrase]`; never report `/life-index` and the custom phrase as separate alternatives>
- Default location preference: <saved/skipped>
- Default location runtime verification: <verified/not verified/not attempted>

**How to Use Life Index Now**:
- Title: <localized equivalent of "开始使用 Life Index" in the same language as the report>
- Welcome line: <localized equivalent of "恭喜！🎉 Life Index 已经安装完成。" in the same language as the report>
- Best-practice line: <state clearly, in the same language as the report, that the current best practice is `/life-index + the user's chosen trigger phrase : the user's journal content`>
- Trigger line: <localized equivalent of "您当前的默认触发词是：`/life-index [user custom trigger phrase]`">
- Location line: <localized equivalent of "您当前的默认城市是：`[user default city, country]`">
- Intro line: <localized equivalent of "现在，您可以直接这样开始记录：">
- Logging example 1: `"/life-index [user custom trigger phrase]: 今天完成了 Life Index 的安装测试，感觉很顺利"` (localize the non-trigger content to match the report language)
- Logging example 2: `"/life-index [user custom trigger phrase]: 刚刚看到一篇文章很有启发：https://..."` (localize the non-trigger content to match the report language)
- Capability intro: <localized equivalent of "除了记录日志，您还可以继续让我帮您：">
- Capability 1: <localized equivalent of "搜索过去的记录">
- Capability 1 example: <localized equivalent of `例如：/life-index 搜索: 我上个月有多少次晚睡？`>
- Capability 2: <localized equivalent of "回顾某一段时间或某个主题">
- Capability 2 example: <localized equivalent of `例如：/life-index 回顾过去半年我关于 Life Index 的开发情况`>
- Capability 3: <localized equivalent of "修改刚记录的信息">
- Capability 3 example: <localized equivalent of "例如：更新地点、天气、标题，或补充内容">
- Closing line: <localized equivalent of "下面你可以直接开始记录您的第一篇日志啦🎉！">

**Notes**:
- <any warnings or non-blocking issues>
- <reminder about Windows path syntax if applicable>
- <whether `needs_confirmation` was returned by first write>
```

---

## 11. Guardrails (Strict)

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

## 12. Data Locations Reference

| Location | Path |
|:---|:---|
| Journals | `~/Documents/Life-Index/Journals/` |
| Attachments | `~/Documents/Life-Index/attachments/` |
| Index | `~/Documents/Life-Index/.index/` |
| Config (optional) | `~/Documents/Life-Index/.life-index/config.yaml` |

---

## 13. CLI Quick Reference

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

---

**Document Version**: 1.1
**Last Updated**: 2026-03-26
**Authority Chain**: `bootstrap-manifest.json` → `AGENT_ONBOARDING.md` / `README.md` → domain SSOT docs such as `SKILL.md`, `docs/API.md`, `docs/ARCHITECTURE.md`, `tools/lib/AGENTS.md`
