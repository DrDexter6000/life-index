# Distribution Strategy

> **Document role**: Define the preferred distribution path for Life Index and justify the decision
> **Audience**: Project owner, contributors, users
> **Authority**: Review-scoped execution document; defers to Tier 1 SSOT for runtime truth
> **Primary goal**: Establish a single, well-supported installation method and document why alternatives are deprioritized

---

## 1. Decision Statement

**Preferred distribution path**: Git clone + local virtual environment + editable pip install

This is the method documented in README.md and SKILL.md. No additional distribution mechanism is currently justified.

---

## 2. Current State

### What exists today

| Component | Status | Location |
|:---|:---|:---|
| Git repository | Active | https://github.com/DrDexter6000/life-index |
| Unified CLI | Implemented | `life-index` command via `pyproject.toml` entry point |
| Virtual environment setup | Documented | README.md, SKILL.md |
| Editable install | Supported | `pip install -e .` |
| Health check command | Implemented | `life-index health` |

### Installation flow (current)

```
User → Agent
  → git clone --depth 1 <repo>
  → cd life-index
  → python3 -m venv .venv
  → .venv/bin/pip install -e .
  → .venv/bin/life-index health
  → .venv/bin/life-index index
  → Ready to use
```

---

## 3. Alternative paths considered

### 3.1 PyPI package (`pip install life-index`)

**Status**: Not pursued

**Rationale**:
- Life Index is designed as an Agent Skill, not a general-purpose library
- The target user installs once per Agent instance, not per-project
- PyPI publication adds maintenance overhead (version management, release automation) without proportional user benefit
- Current git-based flow is acceptable for the intended audience

**Revisit condition**: If user base expands beyond Agent Skill use case to general Python users

---

### 3.2 Homebrew / system package managers

**Status**: Not pursued

**Rationale**:
- Adds platform-specific packaging complexity
- Life Index requires Python virtual environment isolation (fastembed, numpy dependencies)
- System package managers often lag on Python package versions
- Current cross-platform Python venv approach works on Windows, macOS, Linux

**Revisit condition**: If non-technical users request one-click installation without git

---

### 3.3 Docker container

**Status**: Not pursued

**Rationale**:
- Overkill for a local journaling tool
- Data persistence requires volume mounts, adding complexity
- Python venv is simpler for the target use case
- No server component that would benefit from containerization

**Revisit condition**: If multi-user deployment or cloud hosting becomes a goal

---

### 3.4 MCP (Model Context Protocol) Server

**Status**: Deferred

**Rationale**:
- See dedicated evaluation in [MCP_REEVALUATION.md](./MCP_REEVALUATION.md)
- Current CLI architecture is sufficient
- MCP adds installation friction for minimal benefit in single-user local context

**Revisit condition**: If multi-client interoperability becomes a real requirement

---

## 4. Preferred path justification

### Why git + venv + editable install wins

| Criterion | Git+Venv | PyPI | Homebrew | Docker | MCP |
|:---|:---|:---|:---|:---|:---|
| One-command install | Partial* | Yes | Yes | Yes | No |
| Zero configuration | Yes | Yes | Yes | No | No |
| Dependency isolation | Yes | Partial | Partial | Yes | Yes |
| Easy updates | Yes | Yes | Yes | Yes | Yes |
| Skill development friendly | Yes | No | No | No | No |
| Data/code separation | Yes | Yes | Yes | Yes | Yes |
| Cross-platform | Yes | Yes | No | Partial | Partial |
| Maintenance burden | Low | Medium | High | Medium | Medium |

*Partial: Requires git and Python pre-installed, but these are standard in Agent environments

### Key factors

1. **Development-friendly**: Users who want to customize or contribute can modify code in place
2. **Dependency control**: Editable install ensures all dependencies resolve correctly with the code version
3. **Update simplicity**: `git pull && pip install -e .` is straightforward
4. **Skill-native**: Aligns with how Agent Skills are typically distributed (git-based)

---

## 5. Installation variants

### Variant A: End user (recommended)

Documented in README.md "快速安装 - Life Index 普通用户":

```bash
git clone --depth 1 https://github.com/DrDexter6000/life-index.git
cd life-index
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/life-index health
.venv/bin/life-index index
```

Windows users substitute `.venv/bin/` with `.venv\Scripts\`.

### Variant B: Developer

Same as Variant A, but keep full git history and development files:

```bash
git clone https://github.com/DrDexter6000/life-index.git
cd life-index
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

### Variant C: Windows-friendly operator path

This is not a different distribution mechanism. It is the same preferred path with two usage notes derived from the fresh-install rehearsal:

1. Prefer `.venv\Scripts\life-index` over relying on shell activation during first-run validation
2. Prefer `write --data @file.json` over long inline JSON for first-write validation

These reduce first-run friction without adding a new distribution surface.

---

## 6. Future considerations

### When to reconsider PyPI

- User base grows beyond Agent Skill context
- Third-party tools want to depend on Life Index programmatically
- Automated CI/CD is established and maintenance burden becomes negligible

### When to reconsider MCP

- See [MCP_REEVALUATION.md](./MCP_REEVALUATION.md) for detailed criteria
- Summary: Only if multi-client interoperability becomes a concrete requirement

### When to add installers

- Non-technical user segment emerges that cannot use git
- Windows installer or macOS .app bundle requested by multiple users

---

## 7. SSOT references

| Truth | Location |
|:---|:---|
| Installation commands | `README.md` "快速安装" section |
| CLI usage | `SKILL.md` "Quick CLI Reference" section |
| Entry point definition | `pyproject.toml` `[project.scripts]` |
| Health check implementation | `tools/__main__.py` `health_check()` function |

---

## 8. Conclusion

**No change to distribution method is recommended at this time.**

The git + venv + editable install path is:
- Adequate for the current user base
- Well-documented in Tier 1 SSOT
- Low maintenance burden
- Reversible if future needs change

This document should be revisited if:
1. User feedback indicates installation friction is a barrier
2. New distribution mechanisms emerge that offer clear advantages
3. Project scope expands beyond Agent Skill use case

## 9. Verification note

Phase 3 fresh-install rehearsal evidence now exists in `docs/archive/review-2026-03/ONBOARDING_CHECKLIST.md`.

What the rehearsal validated:

- fresh virtual-environment install remains viable
- unified CLI (`life-index`) is the correct operator-facing entry point
- install → index → write → search works end to end on Windows

What the rehearsal also revealed:

- Windows CLI JSON output needed encoding-safe printing for `write` and `search`
- `health` needed to honor configured data directory overrides during isolated rehearsal

Those issues were narrow onboarding blockers, not reasons to change the preferred distribution path itself.
