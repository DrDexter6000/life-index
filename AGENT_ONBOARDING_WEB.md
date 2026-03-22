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

## 2. Step 0 — Detect Local State Before Doing Anything

Do **not** clone, recreate `.venv`, or install web dependencies until you complete this detection gate.

### Step 0.1: Check user data first

Check whether the user already has Life Index data under:

- `~/Documents/Life-Index/`
- `~/Documents/Life-Index/Journals/`
- existing journal files under `Journals/YYYY/MM/*.md`

If real journal data exists, treat the machine as **not fresh install** unless strong evidence proves otherwise.

### Step 0.2: Check repo / venv / CLI state

Check whether there is already:

- a Life Index repository checkout
- `.venv/`
- a reachable `life-index` CLI

If `.venv` exists or the CLI appears installed, prefer the venv path and run `life-index health`.

### Step 0.3: Check Web capability only after base signals

If a base install exists, determine whether the Web layer already exists:

- can the venv path run `life-index serve`
- if it starts, does `http://127.0.0.1:8765/api/health` return HTTP 200 with `status = ok`

### Step 0.4: Decide the route

Use these rules:

#### Route A — Fresh Install + Web

Choose this only if:

- no existing journal data is found
- no reliable existing repo/venv install is found
- there is no meaningful prior install state to preserve

If selected, continue with the fresh-install flow in this document.

#### Route B — Upgrade Existing Web Install

Choose this if:

- base install exists
- Web dependencies appear installed
- the machine is already a Web user or was intended to be one

If selected, switch to `docs/UPGRADE.md` and use the Web GUI upgrade path.

#### Route C — Upgrade Base Install to Add Web Layer

Choose this if:

- base install exists
- user data exists or `life-index health` works
- but `life-index serve` is unavailable or Web deps are clearly missing

If selected, switch to `docs/UPGRADE.md` and use the Web GUI upgrade path to add `.[web]`.

#### Route D — Repair / Ambiguous State

Choose this if signals conflict, for example:

- journal data exists but repo/venv is missing
- `.venv` exists but base health fails badly
- Web dependencies look partial or broken

If selected:

1. do **not** force a fake fresh install
2. use `docs/UPGRADE.md` as the repair baseline
3. if ambiguity remains, ask the user before cleanup that could discard local state

### Step 0.5: Version is only a supporting signal

If you can determine the installed version, use it only to understand whether the machine is behind the current repo version.

Do **not** use version alone to decide fresh install vs upgrade.

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

### Step 5.3: Record the Local Access URL

Record the final local URL for the user:

```text
http://127.0.0.1:8765
```

If you had to use another port, report the actual URL.

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
- the exact local URL to open in a browser

### If Anything Failed

- identify whether failure is in the base product or only in the optional Web GUI layer
- include the exact failing command and exact error
- do not collapse partial success into a fake “all good” summary

---

## 8. Scope Boundary

This document verifies that the Web GUI is **installed and reachable**.

It does **not** require you to perform a full browser walkthrough of dashboard / search / write / edit unless the user explicitly asks for that extra validation.

For onboarding, successful base verification + successful `serve` startup + successful `/api/health` is sufficient.

---

## 9. Related Documents

- `AGENT_ONBOARDING.md` — Base install and initialization authority
- `docs/UPGRADE.md` — Upgrade guide for both base and Web GUI users
- `README.md` / `README.en.md` — User-facing quick-start prompts
