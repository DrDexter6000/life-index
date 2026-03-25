# Agent Onboarding Guide: Life Index Installation with Web GUI

> **Document Purpose**: Step-by-step operational instructions for AI agents installing Life Index with the optional local Web GUI on behalf of users.
> **Audience**: External AI agents (not humans)
> **Scope**: Base installation, initialization, first-use verification, and local Web GUI verification
> **SSOT References**: `AGENT_ONBOARDING.md`, `SKILL.md`, `docs/API.md`, `docs/UPGRADE.md`

---

## 1. Goal

Install and initialize Life Index on the user's machine, verify the base installation is functional, then install and verify the optional local Web GUI so the user can open it in a browser.

This document is now a **smart Web entrypoint**. Your first job is to detect whether the machine needs a fresh install, a normal upgrade, a base-to-web upgrade, or a repair pass.

You are acting on behalf of a user. Your job is to execute the workflow safely, verify each stage, and report the result back clearly.

Before taking any action, read this entire document once.

---

## 2. Step 0 — Refresh Authority First, Then Detect Local State

Do **not** clone, recreate `.venv`, install web dependencies, run `serve`, or classify install state until you complete this gate.

### Step 0.1: Refresh authority documents first

Before trusting any local checkout, refresh these files from the current upstream repository and use the refreshed copies as the authority for the rest of the task:

- `AGENT_ONBOARDING_WEB.md`
- `AGENT_ONBOARDING.md`
- `docs/UPGRADE.md`
- `README.md`
- `bootstrap-manifest.json`

Treat local copies of these files as potentially stale.

### Step 0.2: Check user data first

Check whether the user already has Life Index data under:

- `~/Documents/Life-Index/`
- `~/Documents/Life-Index/Journals/`
- existing journal files under `Journals/YYYY/MM/*.md`

If real journal data exists, treat the machine as **not fresh install** unless strong evidence proves otherwise.

### Step 0.3: Identify the canonical checkout

Check whether there is already:

- a Life Index repository checkout
- `bootstrap-manifest.json`
- `.venv/`
- a reachable `life-index` CLI

#### Host-managed canonical checkout rule

If the host Agent platform provides a canonical skill-install directory, prefer that managed checkout.

If that canonical checkout exists, reuse it. Do **not** create or keep validating a duplicate checkout under a generic workspace path unless the canonical path is unavailable and the user explicitly approves a different location.

If multiple Life Index checkouts are detected, do **not** create another one. Report the duplicate-checkout state and prefer the host-managed canonical checkout or the user-designated checkout for repair/upgrade work.

### Step 0.4: Mandatory sync gate before any route decision

If a canonical checkout exists and network access is available, you **must** sync that checkout before doing base health checks, Web capability checks, or route classification.

Minimum rule:

1. fetch/pull the canonical checkout from the upstream repository
2. ensure `bootstrap-manifest.json` exists after sync
3. reinstall into `.venv` after sync using the Web-enabled editable install path when Web onboarding is requested

If checkout sync fails because of local conflicts, detached state, or unclear git state, do **not** treat the checkout as current. Switch to repair handling.

If network is unavailable, you may continue only after explicitly warning the user that freshness could not be verified.

### Step 0.5: Version/freshness is a mandatory gate

Use the refreshed `bootstrap-manifest.json`, local checkout state, and `life-index --version` output to determine whether the local install reflects the expected current version.

**Critical rule**:
- `life-index health` proves runtime health
- `life-index serve` proves Web capability
- neither proves checkout freshness

All three questions are separate:
1. is the checkout current?
2. is the base install healthy?
3. is the Web layer installed and working?

### Step 0.6: Check Web capability only after sync + reinstall

If a base install exists after sync, determine whether the Web layer already exists:

- can the venv path run `life-index serve`
- if it starts, does `http://127.0.0.1:8765/api/health` return HTTP 200 with `status = ok`

### Step 0.7: Only now decide the route

Use these rules:

#### Route A — Fresh Install + Web

Choose this only if:

- no existing journal data is found
- no reliable existing repo/venv install is found
- there is no meaningful prior install state to preserve

If selected, continue with the fresh-install flow in this document.

#### Route B — Upgrade Existing Web Install

Choose this if:

- base install exists after sync
- Web dependencies are installed after sync/reinstall
- the machine is already a Web user or was intended to be one

If selected, switch to `docs/UPGRADE.md` and use the Web GUI upgrade path.

#### Route C — Upgrade Base Install to Add Web Layer

Choose this if:

- base install exists after sync
- user data exists or `life-index health` works after sync
- but `life-index serve` is unavailable or Web deps are clearly missing

If selected, switch to `docs/UPGRADE.md` and use the Web GUI upgrade path to add `.[web]`.

#### Route D — Repair / Ambiguous State

Choose this if signals conflict, for example:

- journal data exists but repo/venv is missing
- `.venv` exists but base health fails badly after sync/reinstall
- Web dependencies look partial or broken after sync/reinstall
- multiple competing Life Index checkouts exist and the active one is unclear

If selected:

1. do **not** force a fake fresh install
2. use `docs/UPGRADE.md` as the repair baseline
3. if ambiguity remains, ask the user before cleanup that could discard local state

---

## 3. Workflow Overview

This document intentionally reuses the **base onboarding flow** in `AGENT_ONBOARDING.md`.

Execute `AGENT_ONBOARDING.md` as the default authority for:

- prerequisites
- repository clone
- virtual environment creation
- initialization (`life-index index`)
- health check
- first write
- first search
- final base verification

Then apply the **Web-specific substitutions and extra verification** in this document.

---

## 4. Base Onboarding Reuse Rule

Follow `AGENT_ONBOARDING.md` completely, **except** for the package install step.

### Replacement Rule for Step 4.3

Replace the base install command in `AGENT_ONBOARDING.md` Step 4.3 with the Web-enabled install command below.

**Linux/macOS/WSL**:
```bash
.venv/bin/pip install -e ".[web]"
```

**Windows**:
```powershell
.venv\Scripts\pip install -e ".[web]"
```

### Success Criteria

- Installation completes without errors
- Base package installs successfully
- Web dependencies install successfully (`fastapi`, `uvicorn`, `jinja2`, `markdown`, `python-multipart`, `httpx`)

### Failure Handling

- If installation fails, retry once
- If the error mentions missing build tools, capture the exact error and report it to the user
- If Web dependencies fail but base install succeeds, do **not** pretend the Web GUI is installed; report partial success clearly

---

## 5. Continue Base Verification Unchanged

After the replacement install step above, continue `AGENT_ONBOARDING.md` unchanged for:

1. initialization (`life-index index`)
2. health check
3. first write
4. first search

Do not skip those steps. The Web GUI is a convenience shell over the same local data, so base verification must pass first.

---

## 6. Web GUI Verification

After the base flow succeeds, verify the local Web GUI.

### Step 5.1: Start the Web GUI Server

Use the venv CLI path.

**Linux/macOS/WSL**:
```bash
.venv/bin/life-index serve --host 127.0.0.1 --port 8765
```

**Windows**:
```powershell
.venv\Scripts\life-index serve --host 127.0.0.1 --port 8765
```

### Success Criteria

- Command starts without dependency errors
- Output does not show `WEB_DEPS_MISSING`
- Server begins listening on `127.0.0.1:8765`

### Failure Handling

- If output says `Web GUI dependencies not installed`, return to the install step and reinstall with `.[web]`
- If port 8765 is already in use, either stop the conflicting process or retry with another localhost port and record it in the final report

### Step 5.1b: Keep the result truthful

For Web onboarding, the user should either be able to open the GUI immediately after onboarding, or be told explicitly that the server is no longer running.

Do **not** claim “the Web GUI is running” unless it is still reachable after your task ends.

If you only verified startup transiently, report that verification succeeded but provide exact restart instructions instead of claiming the service is still live.

---

### Step 5.2: Verify the Health Endpoint

With the server running, verify the Web health endpoint.

**Linux/macOS/WSL**:
```bash
.venv/bin/python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8765/api/health').read().decode())"
```

**Windows**:
```powershell
.venv\Scripts\python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8765/api/health').read().decode())"
```

### Success Criteria

- Request returns HTTP 200
- Response contains `status` with value `ok`

### Failure Handling

- If the request fails immediately, wait a few seconds and retry once
- If the server still does not respond, report the exact error and do not claim the Web GUI is verified

---

### Step 5.2b: Verify the Homepage, not just the API

After `/api/health` succeeds, also verify the homepage:

**Linux/macOS/WSL**:
```bash
.venv/bin/python -c "import urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8765/'); print(r.status)"
```

**Windows**:
```powershell
.venv\Scripts\python -c "import urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8765/'); print(r.status)"
```

### Success Criteria

- Request returns HTTP 200 for `/`
- This confirms the user-facing GUI shell is reachable, not only the API

### Failure Handling

- If `/api/health` works but `/` fails, do **not** report success; report that the Web API is alive but the user-facing GUI is not yet verified

---

### Step 5.2c: Web runtime / data-dir verification gate

Before claiming the Web GUI is safe to use for browse / search / write / edit, verify which data directory the running instance is actually reading.

#### Default safety rule

For manual Web acceptance, prefer a sandbox-first workflow instead of pointing the GUI directly at the real user directory.

Preferred commands:

**Linux/macOS/WSL**:
```bash
.venv/bin/python -m tools.dev.run_with_temp_data_dir --for-web
.venv/bin/python -m tools.dev.run_with_temp_data_dir --for-web --seed
```

**Windows**:
```powershell
.venv\Scripts\python -m tools.dev.run_with_temp_data_dir --for-web
.venv\Scripts\python -m tools.dev.run_with_temp_data_dir --for-web --seed
```

Use `--for-web --seed` when you need a realistic browser acceptance pass against copied user data. Treat that mode as a readonly simulation unless the user explicitly asks for another workflow.

#### Required checks after startup

After `life-index serve` starts, do **not** immediately continue to write/edit verification. First confirm runtime consistency from all of these signals:

1. startup output from `life-index serve`
2. `http://127.0.0.1:8765/api/runtime` (preferred) or `http://127.0.0.1:8765/api/health`
3. the page-level runtime banner / runtime panel in the Web GUI

You must confirm:

- the local URL is the one you intend to report
- `user_data_dir` matches the intended directory
- `journals_dir` matches the intended Journals location
- whether `life_index_data_dir_override` is true or false
- whether `readonly_simulation` is true or false

#### Stop conditions

Stop immediately and do **not** continue to write/edit verification if any of the following is true:

- the reported data directory is not the one you intended to use
- runtime signals disagree with each other (startup output vs API vs page banner)
- you cannot tell whether the instance is reading the real user directory or a sandbox
- manual acceptance needs a safer sandbox flow, but the current instance is pointed at the real user directory

If any stop condition triggers:

1. stop the current server
2. do **not** continue with write/edit actions
3. restart using the correct `LIFE_INDEX_DATA_DIR` or the sandbox helper above
4. re-run the runtime verification gate before proceeding

#### Continue conditions

Only continue with deeper Web verification or user-facing write/edit actions if all of the following are true:

- the local URL is correct
- `user_data_dir` is the intended directory
- `journals_dir` is the intended Journals directory
- runtime signals agree across startup output, API, and page UI
- if using `--for-web --seed`, `readonly_simulation=true` is visible

#### Cleanup / recovery reminder

If a sandbox was used only for acceptance, delete the temporary directory after verification.

If you accidentally wrote to the real user directory during testing or acceptance, clean up those temporary artifacts and run:

```bash
life-index index --rebuild
```

---

### Step 5.3: Record the Local Access URL

Record the final local URL for the user:

```text
http://127.0.0.1:8765
```

If you had to use another port, report the actual URL.

Also report whether the server is:

- still running now
- or already stopped, with the exact restart command

If the server is still running, also tell the user how to stop it.

---

## 7. Final Report Requirements

Your final report to the user must clearly separate:

### Base Installation Result

- whether base Life Index install succeeded
- whether initialization succeeded
- whether first write / first search succeeded

### Web GUI Result

- whether Web dependencies installed successfully
- whether `life-index serve` started successfully
- whether `/api/health` responded successfully
- whether `/` responded successfully
- the exact local URL to open in a browser
- whether the server is still running at report time
- the exact command to restart it
- the exact command to stop it

### If Anything Failed

- identify whether failure is in the base product or only in the optional Web GUI layer
- include the exact failing command and exact error
- do not collapse partial success into a fake “all good” summary

---

## 8. Scope Boundary

This document verifies that the Web GUI is **installed and reachable**.

It does **not** require you to perform a full browser walkthrough of dashboard / search / write / edit unless the user explicitly asks for that extra validation.

For onboarding, successful base verification + successful `serve` startup + successful `/api/health` + successful `/` reachability is the minimum acceptable Web verification.

---

## 9. Related Documents

- `AGENT_ONBOARDING.md` — Base install and initialization authority
- `docs/UPGRADE.md` — Upgrade guide for both base and Web GUI users
- `README.md` / `README.en.md` — User-facing quick-start prompts

---

## 10. Short User Prompts You May Suggest

When the user asks how to control the Web GUI after onboarding, prefer these short, platform-neutral prompts:

- Start: `启动 Life Index Web GUI，确保可访问，告诉我地址`
- Stop: `停止 Life Index Web GUI，并确认对应端口已释放`
