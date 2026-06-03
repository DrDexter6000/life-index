# Agent Bridge — P1 Vertical Slice (Hermes) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the thinnest end-to-end slice of RFC-2026-06-03's L3/L4 intelligence-handoff contract: a deterministic `agent_bridge` (L3) that resolves a brain (P0→P1→P2→deterministic-only) and, for P1, routes a CLI-produced smart-search scaffold to the user's own running Hermes (`localhost:8642`, OpenAI-compatible) and hands the result back through the CLI validate/apply gate — proving "GUI uses your trusted agent as its brain" without building the GUI.

**Architecture:** `tools/agent_bridge/` is an **L3** package. Brain *resolution* (which endpoint) is pure/deterministic; the single LLM call happens only in L3 via the `openai` SDK against an OpenAI-compatible endpoint. It reads brain config from a `brain` section (config-compatible with the existing `llm` section / `LIFE_INDEX_LLM_*` env). Any state-changing result is a *proposal* returned to the caller, which re-invokes the `life-index` CLI for validation — the bridge never writes `~/Documents/Life-Index/`.

**Tech Stack:** Python 3.11+, OpenAI-compatible transport, `pytest`, `subprocess` to the `life-index` CLI. Preflight fact: `pyproject.toml` does **not** currently declare `openai`; Task 3 must add/declare an explicit optional dependency (preferred: an `agent-bridge` extra) or intentionally gate the import with a clear "install the optional SDK" error. Do not assume the SDK is already present.

**Decisions locked (per RFC + CHARTER, stated not assumed):**
- **No refactor of smart-search.** `agent_bridge` ships its own config-compatible resolver; smart-search untouched (§1.10 — don't consolidate to shared until ≥2 proven consumers).
- **P1 consumer = a thin probe harness, not the GUI.** GUI build is out of RFC scope (§10); the greenfield GUI consumes `agent_bridge` later.
- **Scope = P1 slice only.** P2 (raw provider), full onboard capability-detection SOP, and the deterministic-only degrade matrix are a follow-up plan; this plan stubs the seams but proves P1.

**Constraints:** Implement in a git worktree (RFC_WORKFLOW step 3, not main). Must keep `tests/contract/test_layer_invariants.py` green (L2 never imports `tools.agent_bridge` or LLM providers). Touches no L2 contract.

**Governance / packaging boundary:** Task 0 modifies `CHARTER.md`, so it is a governance change. Keep the CHARTER + charter-history amendment in a separate commit from runtime/test implementation. Do not push any package containing CHARTER/governance changes without explicit owner ack for that package. Runtime commits may follow artifact policy only when they do not include governance files.

**Preflight facts verified on 2026-06-03:**
- `python -m tools smart-search --help` exposes `--include-evidence`.
- `tools/agent_bridge/` does not yet exist.
- `CHARTER.md` does not yet contain the RFC-2026-06-03 §1.9 interpretation block.
- `pyproject.toml` does not yet declare `openai`.

---

## File Structure

| File | Responsibility | Created/Modified |
|---|---|---|
| `tools/agent_bridge/__init__.py` | Package marker + public exports | Create |
| `tools/agent_bridge/config.py` | Deterministic `brain` config resolution (env + `USER_CONFIG`), `data_exposure_ack` enforcement | Create |
| `tools/agent_bridge/resolve.py` | Deterministic brain-source resolution order P0→P1→P2→deterministic-only | Create |
| `tools/agent_bridge/client.py` | OpenAI-compatible transport: send a scaffold prompt, return text (the only LLM touch) | Create |
| `tools/agent_bridge/handoff.py` | Orchestrates: take CLI scaffold dict → resolve brain → call → return proposal envelope | Create |
| `tools/agent_bridge/__main__.py` | `python -m tools.agent_bridge` CLI for the probe harness | Create |
| `tests/unit/test_agent_bridge_config.py` | Resolution + ack-gate unit tests | Create |
| `tests/unit/test_agent_bridge_resolve.py` | P0/P1/P2/degrade ordering unit tests | Create |
| `tests/contract/test_layer_invariants.py` | Add `tools.agent_bridge` to L3 disallowed-imports for L2; add agent_bridge-specific invariants | Modify |
| `tests/integration/test_agent_bridge_p1_hermes.py` | Env-gated real-Hermes P1 round-trip probe | Create |
| `pyproject.toml` | Optional dependency declaration for the OpenAI-compatible client, or an intentional documented no-dependency gate | Modify |
| `CHARTER.md` | Append §1.9 增量解释条款 (exact text from RFC §6) | Modify |
| `docs/charter-history/CHARTER-§1.9-rfc-2026-06-03-handoff-interpretation.md` | Archive the amendment | Create |

---

## Task 0: CHARTER §1.9 增量解释条款 + archival

**Files:**
- Modify: `CHARTER.md` (append interpretation block immediately after §1.9 「合宪示例」, before §1.10)
- Create: `docs/charter-history/CHARTER-§1.9-rfc-2026-06-03-handoff-interpretation.md`

- [ ] **Step 1: Locate §1.9 end.** Open `CHARTER.md`, find the `### §1.10` heading. The insertion point is the blank line immediately before it.

- [ ] **Step 2: Insert the interpretation block** (verbatim from RFC-2026-06-03 §6 "拟新增条款"):

```markdown

**§1.9 解释补充（RFC-2026-06-03）— 智能交接的 sanctioned 实现**

§1.9 所称「calling agent 负责语言合成」与「无 calling agent 用户的 provider opt-in fallback」，其 sanctioned 实现由 RFC-2026-06-03 定义为确定性解析顺序 **P0→P1→P2→deterministic-only**：
- **P0** = in-context calling agent（默认，本条不变）；
- **P1** = 经用户自有 agent 端点抵达**同一** calling agent（仍属「calling agent」，非新增 LLM 持有）；
- **P2** = §1.9 既有 provider opt-in fallback。

本补充**不改变** §1.9 任何核心规则 / 禁止项 / 默认路径：默认仍 P0；模块默认仍不持 LLM；L2 仍零 LLM；无 provider 仍以确定性输出满足合宪判断。它仅锁定「**P1/P2 是被允许的实现、不得倒置为默认路径**」这一解释。
```

- [ ] **Step 3: Archive.** Create `docs/charter-history/CHARTER-§1.9-rfc-2026-06-03-handoff-interpretation.md` containing: the inserted block, the date `2026-06-03`, `RFC-2026-06-03`, and a one-line note "additive interpretation; owner-authorized via CHARTER §5; does not weaken §1.9".

- [ ] **Step 4: Verify invariant tests still pass** (no code touched, sanity only):

Run: `python -m pytest tests/contract/test_layer_invariants.py -q`
Expected: all pass (CHARTER text change does not affect import scans).

- [ ] **Step 5: Commit**

```bash
git add CHARTER.md docs/charter-history/
git commit -m "docs(charter): add §1.9 handoff-interpretation clause (RFC-2026-06-03)"
```

---

## Task 1: `brain` config resolution (deterministic)

**Files:**
- Create: `tools/agent_bridge/__init__.py` (empty package marker)
- Create: `tools/agent_bridge/config.py`
- Test: `tests/unit/test_agent_bridge_config.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_agent_bridge_config.py
import sys
from pathlib import Path
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))


def _clear_env(mp):
    for k in ("LIFE_INDEX_LLM_API_KEY", "LIFE_INDEX_LLM_BASE_URL", "LIFE_INDEX_LLM_MODEL",
              "LIFE_INDEX_BRAIN_MODE", "LIFE_INDEX_BRAIN_ENDPOINT"):
        mp.delenv(k, raising=False)


def test_resolve_brain_config_reads_brain_section(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setattr("tools.lib.config.USER_CONFIG", {
        "brain": {"mode": "host_agent", "endpoint": "http://localhost:8642/v1",
                  "transport": "openai", "data_exposure_ack": True}
    })
    from tools.agent_bridge.config import resolve_brain_config
    cfg = resolve_brain_config()
    assert cfg.mode == "host_agent"
    assert cfg.endpoint == "http://localhost:8642/v1"
    assert cfg.data_exposure_ack is True


def test_brain_falls_back_to_llm_section(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setattr("tools.lib.config.USER_CONFIG", {
        "llm": {"api_key": "k", "base_url": "http://localhost:8642/v1", "model": "hermes"}
    })
    from tools.agent_bridge.config import resolve_brain_config
    cfg = resolve_brain_config()
    assert cfg.endpoint == "http://localhost:8642/v1"
    assert cfg.model == "hermes"


def test_env_overrides_config(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setattr("tools.lib.config.USER_CONFIG", {})
    monkeypatch.setenv("LIFE_INDEX_BRAIN_ENDPOINT", "http://localhost:8642/v1")
    monkeypatch.setenv("LIFE_INDEX_BRAIN_MODE", "host_agent")
    from tools.agent_bridge.config import resolve_brain_config
    cfg = resolve_brain_config()
    assert cfg.endpoint == "http://localhost:8642/v1"
    assert cfg.mode == "host_agent"


def test_ack_required_raises_without_ack(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setattr("tools.lib.config.USER_CONFIG", {
        "brain": {"mode": "host_agent", "endpoint": "http://x/v1", "data_exposure_ack": False}
    })
    from tools.agent_bridge.config import resolve_brain_config, require_ack, AckRequiredError
    cfg = resolve_brain_config()
    import pytest
    with pytest.raises(AckRequiredError):
        require_ack(cfg)
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/unit/test_agent_bridge_config.py -q`
Expected: FAIL (module `tools.agent_bridge.config` not found).

- [ ] **Step 3: Implement**

```python
# tools/agent_bridge/__init__.py
"""L3 agent bridge: resolve a brain and hand off CLI scaffolds. Never writes user data."""
```

```python
# tools/agent_bridge/config.py
from __future__ import annotations
import os
from dataclasses import dataclass
from tools.lib import config as _cfg


class AckRequiredError(RuntimeError):
    """Raised when a provider-backed (P1/P2) brain is selected without data_exposure_ack."""


@dataclass(frozen=True)
class BrainConfig:
    mode: str            # auto | in_context | host_agent | byol | deterministic_only
    endpoint: str | None
    transport: str       # openai | acp
    api_key: str | None
    model: str | None
    data_exposure_ack: bool


def resolve_brain_config() -> BrainConfig:
    user = getattr(_cfg, "USER_CONFIG", {}) or {}
    brain = dict(user.get("brain", {}))
    llm = dict(user.get("llm", {}))  # config-compatible fallback (no smart-search refactor)

    endpoint = (os.environ.get("LIFE_INDEX_BRAIN_ENDPOINT")
                or brain.get("endpoint")
                or os.environ.get("LIFE_INDEX_LLM_BASE_URL")
                or llm.get("base_url"))
    mode = (os.environ.get("LIFE_INDEX_BRAIN_MODE") or brain.get("mode") or "auto")
    transport = brain.get("transport", "openai")
    api_key = (os.environ.get("LIFE_INDEX_LLM_API_KEY") or brain.get("api_key") or llm.get("api_key"))
    model = (os.environ.get("LIFE_INDEX_LLM_MODEL") or brain.get("model") or llm.get("model"))
    ack = bool(brain.get("data_exposure_ack", False))
    return BrainConfig(mode=mode, endpoint=endpoint, transport=transport,
                       api_key=api_key, model=model, data_exposure_ack=ack)


def require_ack(cfg: BrainConfig) -> None:
    if not cfg.data_exposure_ack:
        raise AckRequiredError(
            "P1/P2 brain requires explicit data_exposure_ack=true before sending journal data."
        )
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/unit/test_agent_bridge_config.py -q`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add tools/agent_bridge/__init__.py tools/agent_bridge/config.py tests/unit/test_agent_bridge_config.py
git commit -m "feat(agent_bridge): deterministic brain config resolution + ack gate"
```

---

## Task 2: brain-source resolution order (deterministic)

**Files:**
- Create: `tools/agent_bridge/resolve.py`
- Test: `tests/unit/test_agent_bridge_resolve.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_agent_bridge_resolve.py
import sys
from pathlib import Path
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
from tools.agent_bridge.config import BrainConfig
from tools.agent_bridge.resolve import resolve_source


def _cfg(mode="auto", endpoint=None, api_key=None, ack=False):
    return BrainConfig(mode=mode, endpoint=endpoint, transport="openai",
                       api_key=api_key, model="m", data_exposure_ack=ack)


def test_p0_when_in_context():
    assert resolve_source(_cfg(), in_context_agent=True) == "P0"


def test_p1_when_host_endpoint_and_ack():
    assert resolve_source(_cfg(endpoint="http://localhost:8642/v1", api_key="k", ack=True),
                          in_context_agent=False) == "P1"


def test_p2_label_when_byol_endpoint():
    # P1 vs P2 differ only by intent; both are endpoints. mode pins it when set.
    assert resolve_source(_cfg(mode="byol", endpoint="https://api.openai.com/v1", api_key="k", ack=True),
                          in_context_agent=False) == "P2"


def test_degrade_when_no_endpoint():
    assert resolve_source(_cfg(endpoint=None), in_context_agent=False) == "deterministic_only"


def test_degrade_when_no_ack():
    assert resolve_source(_cfg(endpoint="http://x/v1", api_key="k", ack=False),
                          in_context_agent=False) == "deterministic_only"


def test_explicit_in_context_mode_forces_p0():
    assert resolve_source(_cfg(mode="in_context"), in_context_agent=False) == "P0"
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/unit/test_agent_bridge_resolve.py -q`
Expected: FAIL (`tools.agent_bridge.resolve` not found).

- [ ] **Step 3: Implement**

```python
# tools/agent_bridge/resolve.py
from __future__ import annotations
from tools.agent_bridge.config import BrainConfig


def resolve_source(cfg: BrainConfig, *, in_context_agent: bool) -> str:
    """Deterministic resolution. Returns one of: P0, P1, P2, deterministic_only.

    Order: explicit mode override -> P0 (in-context) -> P1/P2 (endpoint+ack) -> degrade.
    P1 vs P2 is an intent label: mode='byol' marks P2; otherwise an endpoint is P1.
    """
    if cfg.mode == "in_context":
        return "P0"
    if cfg.mode == "deterministic_only":
        return "deterministic_only"
    if in_context_agent and cfg.mode in ("auto", "host_agent"):
        return "P0"
    usable_endpoint = bool(cfg.endpoint and cfg.api_key and cfg.data_exposure_ack)
    if usable_endpoint:
        return "P2" if cfg.mode == "byol" else "P1"
    return "deterministic_only"
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/unit/test_agent_bridge_resolve.py -q`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add tools/agent_bridge/resolve.py tests/unit/test_agent_bridge_resolve.py
git commit -m "feat(agent_bridge): deterministic P0/P1/P2/degrade resolution order"
```

---

## Task 3: OpenAI-compatible transport (the single L3 LLM touch)

**Files:**
- Create: `tools/agent_bridge/client.py`
- Modify: `pyproject.toml`
- Test: covered by Task 5 integration probe (transport is thin; unit-mocking the SDK adds little value and the integration probe is the real gate).

- [ ] **Step 1: Declare the optional SDK dependency.** Add an `agent-bridge` optional extra in `pyproject.toml`, then include it in `all`:

```toml
agent-bridge = [
    "openai>=1.0.0",
]

all = [
    "life-index[dev,agent-bridge]",
]
```

If the implementation deliberately avoids declaring the dependency, document that decision in this plan before coding and make `client.py` raise a clear `AgentBridgeDependencyError` when `openai` is missing. Do not leave a silent undeclared import.

- [ ] **Step 2: Implement transport wrapper**

```python
# tools/agent_bridge/client.py
from __future__ import annotations
from tools.agent_bridge.config import BrainConfig, require_ack


def synthesize(cfg: BrainConfig, system_prompt: str, user_prompt: str) -> str:
    """Send a scaffold prompt to an OpenAI-compatible endpoint; return the text.

    This is the ONLY place agent_bridge performs an LLM call (L3). Requires ack.
    """
    require_ack(cfg)
    from openai import OpenAI  # imported lazily; agent_bridge is L3 so this is allowed
    client = OpenAI(api_key=cfg.api_key, base_url=cfg.endpoint)
    resp = client.chat.completions.create(
        model=cfg.model or "default",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return resp.choices[0].message.content or ""
```

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml tools/agent_bridge/client.py
git commit -m "feat(agent_bridge): OpenAI-compatible transport (single L3 LLM touch)"
```

---

## Task 4: layer-invariant coverage (the boundary guard)

**Files:**
- Modify: `tests/contract/test_layer_invariants.py`

- [ ] **Step 1: Add `tools.agent_bridge` to the L2-disallowed-L3 set.** In `DISALLOWED_L3_IMPORTS` (around line 67), add `"tools.agent_bridge"`:

```python
DISALLOWED_L3_IMPORTS = {
    "tools.smart_search",
    "tools.search_journals.orchestrator",
    "tools.agent_bridge",
}
```

- [ ] **Step 2: Add agent_bridge-specific invariants** (append near the recall block, ~line 222):

```python
# --- RFC-2026-06-03: agent_bridge is L3 (LLM allowed) but must subprocess L2 ---

AGENT_BRIDGE_ROOT = REPO_ROOT / "tools" / "agent_bridge"


def _agent_bridge_files() -> list[Path]:
    if not AGENT_BRIDGE_ROOT.exists():
        return []
    return sorted(AGENT_BRIDGE_ROOT.rglob("*.py"))


def test_agent_bridge_does_not_import_l2_internals() -> None:
    """agent_bridge must reach L2 only via the CLI subprocess, never import L2 internals."""
    disallowed = {"tools.search_journals", "tools.write_journal", "tools.edit_journal",
                  "tools.entity", "tools.build_index"}
    offenders: list[str] = []
    for path in _agent_bridge_files():
        for imported in _imported_modules(path):
            if any(imported == d or imported.startswith(f"{d}.") for d in disallowed):
                offenders.append(f"{path.relative_to(REPO_ROOT).as_posix()}: {imported}")
    assert offenders == [], f"agent_bridge imports L2 internals (use subprocess): {offenders}"


def test_agent_bridge_does_not_write_user_data() -> None:
    """agent_bridge must never reference the user data dir (proposals go via CLI)."""
    offenders: list[str] = []
    for path in _agent_bridge_files():
        content = path.read_text(encoding="utf-8")
        if "Documents/Life-Index" in content or "USER_DATA_DIR" in content:
            offenders.append(path.relative_to(REPO_ROOT).as_posix())
    assert offenders == [], f"agent_bridge references user data dir: {offenders}"
```

- [ ] **Step 3: Run the full invariant suite**

Run: `python -m pytest tests/contract/test_layer_invariants.py -q`
Expected: PASS (existing + 2 new). `agent_bridge` importing `openai` is allowed (it is not in `L2_PRODUCTION_ROOTS`); L2 importing `tools.agent_bridge` would now fail the disallowed-L3 test.

- [ ] **Step 4: Commit**

```bash
git add tests/contract/test_layer_invariants.py
git commit -m "test(layer-invariants): cover agent_bridge L3 boundary (RFC-2026-06-03)"
```

---

## Task 5: P1 handoff + real-Hermes round-trip probe (the spike's exit criterion)

**Files:**
- Create: `tools/agent_bridge/handoff.py`
- Create: `tools/agent_bridge/__main__.py`
- Create: `tests/integration/test_agent_bridge_p1_hermes.py`

- [ ] **Step 1: Implement handoff orchestration**

```python
# tools/agent_bridge/handoff.py
from __future__ import annotations
import json
import subprocess
import sys
from tools.agent_bridge.config import resolve_brain_config
from tools.agent_bridge.resolve import resolve_source
from tools.agent_bridge import client


def _cli_smart_search(query: str) -> dict:
    """Subprocess the L2 CLI for a deterministic scaffold. No L2 internals imported."""
    out = subprocess.run(
        [sys.executable, "-m", "tools", "smart-search", "--query", query, "--include-evidence"],
        capture_output=True, text=True, check=True,
    )
    return json.loads(out.stdout)


def _build_prompts(scaffold: dict) -> tuple[str, str]:
    instr = scaffold.get("agent_instructions", {})
    system = "You are the user's trusted assistant. " + " ".join(instr.get("steps", []))
    user = json.dumps({
        "query": scaffold.get("query"),
        "filtered_results": scaffold.get("filtered_results", []),
        "evidence_pack": scaffold.get("evidence_pack", {}),
        "answer_scaffold": scaffold.get("answer_scaffold", {}),
    }, ensure_ascii=False)
    return system, user


def handoff_search(query: str, *, in_context_agent: bool = False) -> dict:
    """Run smart-search scaffold -> resolve brain -> (maybe) synthesize. Returns a proposal envelope."""
    scaffold = _cli_smart_search(query)
    cfg = resolve_brain_config()
    source = resolve_source(cfg, in_context_agent=in_context_agent)
    envelope = {"source": source, "query": query, "scaffold": scaffold, "synthesis": None}
    if source in ("P1", "P2"):
        system, user = _build_prompts(scaffold)
        envelope["synthesis"] = client.synthesize(cfg, system, user)
    # P0 / deterministic_only: caller (in-context agent or GUI) consumes scaffold directly.
    return envelope
```

```python
# tools/agent_bridge/__main__.py
from __future__ import annotations
import argparse
import json
from tools.agent_bridge.handoff import handoff_search


def main() -> int:
    p = argparse.ArgumentParser(prog="agent-bridge")
    p.add_argument("--query", required=True)
    p.add_argument("--in-context", action="store_true")
    args = p.parse_args()
    env = handoff_search(args.query, in_context_agent=args.in_context)
    print(json.dumps(env, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Write the env-gated integration probe**

```python
# tests/integration/test_agent_bridge_p1_hermes.py
"""P1 spike exit criterion: real Hermes round-trip.

Skipped unless LIFE_INDEX_BRAIN_ENDPOINT points at a reachable Hermes and
LIFE_INDEX_BRAIN_ACK=1 is set (explicit data-exposure acknowledgement for the probe).
"""
import os
import sys
from pathlib import Path
import urllib.request
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

ENDPOINT = os.environ.get("LIFE_INDEX_BRAIN_ENDPOINT", "")


def _hermes_reachable() -> bool:
    if not ENDPOINT or os.environ.get("LIFE_INDEX_BRAIN_ACK") != "1":
        return False
    try:
        base = ENDPOINT.rsplit("/v1", 1)[0]
        urllib.request.urlopen(base, timeout=1.5)
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _hermes_reachable(), reason="Hermes endpoint not reachable / ack not set")
def test_p1_round_trip_via_real_hermes(monkeypatch):
    monkeypatch.setattr("tools.lib.config.USER_CONFIG", {
        "brain": {"mode": "host_agent", "endpoint": ENDPOINT, "transport": "openai",
                  "api_key": os.environ.get("LIFE_INDEX_LLM_API_KEY", "local"),
                  "model": os.environ.get("LIFE_INDEX_LLM_MODEL", "hermes"),
                  "data_exposure_ack": True},
    })
    from tools.agent_bridge.handoff import handoff_search
    env = handoff_search("我和家人有哪些温暖的回忆？", in_context_agent=False)
    assert env["source"] == "P1"
    assert env["scaffold"]["smart_search_mode"] == "deterministic_scaffold"
    assert isinstance(env["synthesis"], str) and env["synthesis"].strip() != ""


def test_degrade_path_no_endpoint(monkeypatch):
    """Always-on: with no brain configured, handoff degrades to scaffold-only (no LLM)."""
    for k in ("LIFE_INDEX_BRAIN_ENDPOINT", "LIFE_INDEX_LLM_BASE_URL", "LIFE_INDEX_BRAIN_MODE"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr("tools.lib.config.USER_CONFIG", {})
    from tools.agent_bridge.handoff import handoff_search
    env = handoff_search("test query", in_context_agent=False)
    assert env["source"] == "deterministic_only"
    assert env["synthesis"] is None
    assert env["scaffold"]["smart_search_mode"] == "deterministic_scaffold"
```

- [ ] **Step 3: Run the degrade test (always runs) + confirm P1 skips cleanly when Hermes absent**

Run: `python -m pytest tests/integration/test_agent_bridge_p1_hermes.py -q`
Expected: `test_degrade_path_no_endpoint` PASS; `test_p1_round_trip_via_real_hermes` SKIPPED (no live Hermes in CI).

- [ ] **Step 4: Manual P1 spike against your running Hermes** (the actual proof; run locally, not CI):

```bash
# Ensure Hermes API server is up: hermes config set API_SERVER_ENABLED true
export LIFE_INDEX_BRAIN_ENDPOINT="http://localhost:8642/v1"
export LIFE_INDEX_LLM_API_KEY="<your hermes API_SERVER_KEY>"
export LIFE_INDEX_LLM_MODEL="hermes"
export LIFE_INDEX_BRAIN_ACK=1
python -m pytest tests/integration/test_agent_bridge_p1_hermes.py::test_p1_round_trip_via_real_hermes -v
# OR drive the harness directly:
LIFE_INDEX_BRAIN_MODE=host_agent python -m tools.agent_bridge --query "我和家人有哪些温暖的回忆？"
```
Expected: a JSON envelope with `"source": "P1"` and a non-empty `"synthesis"` produced by *your* Hermes (its persona/memory), proving the GUI's brain can be the user's trusted agent.

- [ ] **Step 5: Commit**

```bash
git add tools/agent_bridge/handoff.py tools/agent_bridge/__main__.py tests/integration/test_agent_bridge_p1_hermes.py
git commit -m "feat(agent_bridge): P1 handoff + real-Hermes round-trip probe (RFC-2026-06-03)"
```

---

## Task 6: full regression + RFC checkbox update

- [ ] **Step 1: Run full contract + unit suites**

Run: `python -m pytest tests/contract tests/unit/test_agent_bridge_config.py tests/unit/test_agent_bridge_resolve.py -q`
Expected: all PASS (layer invariants green; agent_bridge units green).

- [ ] **Step 2: Update RFC-2026-06-03 §10** — tick the now-satisfied implementation boxes: `agent_bridge` L3 created, `brain` schema + ack, layer-invariant test, P1 real-Hermes probe, deterministic_only degrade. Leave P2 / full onboard SOP unticked (follow-up plan).

- [ ] **Step 3: CHANGELOG `[Unreleased]`** — add a user-facing line: "Agent Bridge (P1): the desktop/GUI path can now use your own running agent (e.g. Hermes) as its brain."

- [ ] **Step 4: Commit**

```bash
git add docs/rfc/RFC-2026-06-03-l3l4-intelligence-handoff-contract.md CHANGELOG.md
git commit -m "docs(rfc): mark RFC-2026-06-03 P1 slice implemented; changelog"
```

---

## Out of scope (follow-up plan)

- **P2** raw-provider / local-model path hardening + provider-exposure UX.
- **Onboard capability-detection SOP** (`§3.7`): auto-detect Hermes/OpenClaw, write `brain` config, probe round-trip, re-probe-on-upgrade degrade.
- **OpenClaw ACP transport** adapter (P1 for OpenClaw hosts).
- **GUI itself** — consumes `agent_bridge.handoff` once built.
- **Return-path apply**: wiring synthesized proposals back through `life-index write/edit confirm` is demonstrated conceptually here; the full proposal→validate→apply loop for write/edit is its own slice.

## Self-review notes

- Spec coverage: RFC §3.1 (resolution) → Task 2; §3.2 transport → Task 3; §3.3 scaffold payload → Task 5 handoff; §3.4 validate/apply gate → noted (subprocess CLI; full write/edit loop deferred); §3.5 boundary → Task 4; §3.6 config → Task 1; §6 charter → Task 0; §7 guards (ack, no user-data write, L2 no-import) → Tasks 1/4/5. P2 + §3.7 onboard explicitly deferred.
- No placeholders: every code/test step shows real code and exact commands.
- Type consistency: `BrainConfig` fields and `resolve_source`/`handoff_search`/`synthesize` signatures are consistent across Tasks 1→5.
