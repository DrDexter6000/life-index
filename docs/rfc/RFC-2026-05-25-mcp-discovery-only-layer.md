---
type: process-rfc
status: accepted
created: 2026-05-25
title: MCP Discovery-Only Layer
related:
  - CHARTER.md §1.3 §1.4 §1.5 §1.9 §1.10
  - README.md §7 P2 (MCP discovery forward signal)
  - SKILL.md (current Agent skill surface)
  - docs/API.md (CLI contract)
  - MCP Spec 2025-11-25 (https://modelcontextprotocol.io/specification)
---

# RFC-2026-05-25: MCP Discovery-Only Layer

## §1 Rationale

### Background

Life Index CLI Core is a mature, tested, local-first personal journaling system with 20+
CLI commands, 2,400+ tests, and a CHARTER-protected architecture. The CLI is the Single
Source of Truth (§1.3) for all data operations.

In the current ecosystem, Agent platforms (Claude Desktop, Cursor, OpenClaw derivatives,
and other MCP-compatible hosts) have no standardized way to discover Life Index's
capabilities. Each Agent must be manually configured with SKILL.md triggers and CLI
invocation knowledge. README P2 already signals this as a forward-looking capability:
"MCP discovery layer · In Flight · planned 2026-Q3."

### Problem

Without a discovery mechanism:

1. **Onboarding friction**: Every Agent integration requires the user or Agent to
   manually parse SKILL.md, API.md, and CLI `--help` output to understand what
   capabilities exist.
2. **Capability staleness**: As CLI evolves (new commands, new parameters), Agent
   configurations drift out of sync.
3. **Trust-boundary ambiguity**: When an MCP host receives a tool list from Life Index,
   there is no clear signal about what is "safe discovery" vs "execution." A thin
   discovery layer that only describes capabilities (without executing them) reinforces
   the BYOL (Bring Your Own LLM) boundary from CHARTER §1.9.

### Goal

A thin, read-only MCP server that enables MCP-compatible Agent platforms to
**discover** Life Index CLI capabilities without introducing a parallel data path, LLM
dependency, or dynamic plugin architecture.

## §2 Non-Goals

This RFC **explicitly rejects**:

| Non-goal | Why rejected |
|---|---|
| **Parallel data path** | The MCP server MUST NOT read/write `~/Documents/Life-Index/` directly. All data operations go through `life-index` CLI subprocess. Violates CHARTER §1.3 (CLI as SSOT) and §1.4 (layer isolation). |
| **LLM integration** | The MCP server MUST NOT call any LLM, hold API keys, or initialize provider clients. Violates CHARTER §1.5 (L2/L3 boundary) and §1.9 (no default LLM path). |
| **Replacing SKILL.md as authority** | SKILL.md remains the canonical Agent skill surface. The MCP discovery layer is a machine-readable mirror, not a replacement. |
| **Plugin loader** | No dynamic module loading, no `importlib` discovery, no filesystem-scanning plugin registry. Violates CHARTER §1.10 (no plugin loader / dynamic entry-point registry). |
| **Dynamic discovery** | The capability list is derived from a static manifest or CLI `--help` output at server startup, not runtime introspection of filesystem contents. |
| **Entry-point registry** | No centralized registry of "available tools" beyond the static manifest. Each tool is individually declared, not auto-discovered. |

## §3 Design

### Overview

A thin Python MCP server (target: ≤200 LOC) that exposes three meta-tools via the MCP
Tools feature. The server is a **read-only discovery overlay** — it describes and proxies
CLI commands, but the CLI remains the sole execution engine.

```
┌──────────────────────────────────────────────┐
│ MCP Host (Claude Desktop / Cursor / ...)     │
│                                               │
│  tool/list → [write, search, smart-search,   │
│               edit, abstract, ...]            │
│  tools/call → life-index <command> ...         │
└──────────────┬───────────────────────────────┘
               │ MCP (JSON-RPC 2.0)
               │ stdin/stdout or SSE transport
┌──────────────▼───────────────────────────────┐
│ MCP Discovery Server (tools/mcp_discovery/)   │
│                                               │
│  list_capabilities()  → static manifest       │
│  describe_tool(name)  → parsed API.md contract│
│  invoke_tool(name,args) → subprocess CLI      │
└──────────────┬───────────────────────────────┘
               │ subprocess
┌──────────────▼───────────────────────────────┐
│ life-index CLI (L2 Core)                      │
│  write / search / smart-search / edit / ...  │
└──────────────────────────────────────────────┘
```

### Meta-Tool 1: `list_capabilities()`

Returns a JSON array of all CLI verbs with **names and one-line descriptions only**.
Full parameter schemas, return types, error codes, and usage examples are **not included**
— they are fetched on demand via `describe_tool(name)`. The capability list is sourced
from a static manifest file (`tools/mcp_discovery/capabilities.json`) or parsed from
`life-index --help` at server startup.

This is the progressive-disclosure design: `list_capabilities()` carries ~1KB regardless
of CLI surface size, and the full contract (dozens of KB unrolled across 24 tools) is
loaded only when the Agent needs a specific tool. This directly addresses the
progressive-disclosure concern raised in `docs/ARCHITECTURE.md` §ADR-004 (see §5).

```json
{
  "tools": [
    {
      "name": "write",
      "description": "Write a new journal entry with metadata (title, content, date, topic, mood, tags, location, weather, attachments)"
    },
    {
      "name": "search",
      "description": "Search journals by keyword (FTS5), with optional filters for topic, date range, people, mood"
    }
  ]
}
```

Current CLI help surface (derived from `python -m tools --help`):

| Verb | Category | Description |
|---|---|---|
| `write` | Core·Write | Write a new journal entry |
| `confirm` | Core·Write | Confirm a pending write |
| `search` | Core·Search | Keyword search (FTS5) with filters |
| `edit` | Core·Write | Edit existing journal metadata/content |
| `entity` | Entity | Entity graph management |
| `weather` | Utility | Query weather for a location |
| `index` | Index | Incremental/full index rebuild |
| `generate-index` | Index | Generate index tree (monthly/yearly/root) |
| `abstract` | Index | Alias for `generate-index` |
| `backup` | Utility | Backup journal data |
| `verify` | Utility | Data integrity verification |
| `timeline` | Navigation | Timeline summary stream |
| `on-this-day` | Navigation | Historical same-day review |
| `recall` | Search | Recall search with mode selection |
| `trajectory` | Observations | Typed observations such as weight, sleep, mood, location, project |
| `migrate` | System | Schema chain migration |
| `eval` | System | Search quality evaluation gate |
| `entity-graph-eval` | Entity | Entity graph ablation evaluation |
| `maintenance` | System | Maintenance cycle dry-run health checks |
| `smart-search` | Core·Search | Deterministic search scaffold; `--use-llm` for LLM orchestration |
| `aggregate` | Analytics | Aggregate metrics over time range |
| `analyze` | Analytics | Alias for `aggregate` |
| `health` | System | Installation health check and audit subcommands |
| `version` | System | Display version info |

This is 24 help entries: 22 unique commands plus 2 aliases (`abstract`, `analyze`).

### Meta-Tool 2: `describe_tool(name)`

Returns the full CLI contract for a specific tool: parameters, return schema, error
codes, and usage examples. Sourced from `docs/API.md` parsed sections.

```json
{
  "name": "search",
  "contract": {
    "parameters": {
      "query": { "type": "string", "required": true, "description": "Search query" },
      "topic": { "type": "string", "required": false, "description": "Filter by topic" },
      "level": { "type": "integer", "required": false, "default": 3, "description": "Search level: 1=index, 2=metadata, 3=full text" }
    },
    "returns": { "results": "...", "total_found": "...", "total_matches": "..." },
    "error_codes": ["E0301", "E0302"],
    "examples": ["life-index search --query \"关键词\" --level 3"]
  }
}
```

### Meta-Tool 3: `invoke_tool(name, args)`

Subprocesses `life-index <name> <args>` and returns the CLI JSON output **unchanged**.
The MCP server adds no transformation, validation, or enrichment. It is a transparent
proxy.

**Safety**: All `invoke_tool` calls are routed through the `life-index` CLI. The MCP
server has zero direct file access to `~/Documents/Life-Index/`. The MCP host's user
consent model (per MCP Spec §Security) governs when tools are actually invoked.

### Implementation Constraints

- **Language**: Python 3.11+ (same as Life Index baseline)
- **Dependency**: `mcp` Python SDK (lightweight, ~50KB) or raw JSON-RPC 2.0 over stdio
- **Transport**: stdio (primary, for local MCP hosts) with SSE as optional future transport
- **Location**: `tools/mcp_discovery/`
- **Code size**: Target ≤200 LOC for the server core
- **No persistent state**: The server holds no session state, no caches beyond startup-loaded manifest

## §4 Architectural Placement

### Recommended: `tools/mcp_discovery/`

```
tools/
├── mcp_discovery/
│   ├── __main__.py          # Entry point: python -m tools.mcp_discovery
│   ├── server.py            # MCP server core (≤200 LOC)
│   ├── capabilities.json    # Static capability manifest
│   └── AGENTS.md            # Agent instructions for this module
```

### Why L4-Only and Additive

| Question | Answer |
|---|---|
| **Which layer?** | L4 (Interface Layer). The MCP server is an interface — it exposes L2 capabilities to MCP hosts. It does not implement any new data operations. |
| **Is it L3?** | No. L3 (Intelligence Layer) handles LLM orchestration, semantic understanding, and narrative generation. The MCP discovery server does none of these — it is a protocol adapter, not an intelligence module. |
| **Does it modify L2?** | No. It is purely additive. No existing CLI tool, library, or contract is changed. |
| **Does it create a parallel data path?** | No. `invoke_tool` calls `life-index` CLI as a subprocess. Data flows: MCP Host → MCP Server → CLI subprocess → L1 Data. This is a **proxy**, not a parallel path. |
| **Does it violate §1.4 layer isolation?** | No. L4 → L2 calls are explicitly allowed by §1.5 ("L4 can pass through to L2 directly for daily high-frequency operations"). The MCP server is an L4 interface that calls L2 CLI. |
| **Does it violate §1.10?** | No. No plugin loader, no dynamic registry, no `importlib` discovery. Capabilities are from a static manifest. |

### Lifecycle

As an L4 component, the MCP discovery server has a 1-3 year lifecycle. It may be
replaced by future interface paradigms (direct tool-use protocols, WASM plugins,
etc.) without affecting L2/L1. This short lifecycle is a feature: the interface layer
should evolve with the ecosystem, while the core remains stable.

## §5 Relationship to Prior MCP ADR

### The Actual ADR-004: MCP 迁移评估 (ARCHITECTURE.md)

A prior MCP architectural decision exists, but not as a standalone `docs/adr/` file.
It is an **inline section** at `docs/ARCHITECTURE.md:198-218`, titled
**"ADR-004: MCP 迁移评估"**. The decision: **不迁移到 MCP，保持当前 CLI + SKILL.md 架构**
(Do not migrate to MCP; keep current CLI + SKILL.md architecture).

This RFC was drafted with an incomplete search scope — the author searched
`docs/adr/ADR-004-*.md` (file-path glob) and `grep MCP|mcp docs/adr/` but did not search
`docs/ARCHITECTURE.md`. That search missed the real MCP ADR. The prior draft's
unresolved-reference section was therefore factually incorrect and is hereby replaced.

The inline ADR-004 lists four rejection reasons. Below, each is restated verbatim and
engaged with how this discovery-only layer either addresses or accepts that concern.

#### Reason 1: Progressive Disclosure / Context Economy

> "MCP 要求在连接建立时一次性向 Agent 暴露所有 tool schema … 即使 Agent 只想写一篇日记，也必须加载全部 12 个工具的完整参数定义。相比之下，当前 SKILL.md 方案支持渐进式披露"

**How this RFC differs**: The discovery-only layer adopts progressive disclosure
by design. `list_capabilities()` returns **names plus one-line descriptions only**
(~1KB), not full schemas. Full parameter definitions, return types, and error codes
are behind `describe_tool(name)`, loaded on demand. This is structurally equivalent
to SKILL.md's "按需阅读对应 workflow 段落" pattern. See §3 for the schema design.

The concern applies to a **full-tool-list MCP server** where every tool schema is
announced at connection time. This RFC's `list_capabilities` is a capability index,
not a full schema dump. The MCP host sees 24 names + 1-line descriptions; the full
contract for any single tool is fetched only when the Agent actually needs it.

#### Reason 2: Single-User System Fit

> "Life Index 是单用户、低频调用的个人系统，MCP 的多客户端连接管理、工具发现协议等能力属于'大炮打蚊子'"

**How this RFC threads the concern**: This concern is **accepted as valid**. The
discovery-only layer does not adopt MCP for multi-client orchestration, connection
management, or high-frequency tool dispatch. It uses MCP **solely for capability
discovery** — the "Agent 不知道该工具存在" problem. Execution remains via CLI
subprocess, same as today. The MCP server is a thin (~200 LOC) protocol adapter,
not a multi-client execution framework.

The value-add is narrow: one-time discovery for Agent onboarding. After discovery,
the Agent knows what Life Index can do and can continue invoking the CLI directly
if it prefers. The MCP server does not replace the CLI workflow — it bootstraps it.

#### Reason 3: Low ROI

> "~10 小时工作量换取的体验提升对单用户不显著"

**How this RFC threads the concern**: The scope is smaller than a full MCP
migration. Building a thin discovery overlay (3 meta-tools, ~200 LOC, static
manifest) is an estimated 2-4 hours, not 10+. The ROI calculation shifts when:
(a) the server does not reimplement any CLI logic, (b) the capability manifest
is auto-generated from CLI `--help`, not manually maintained, and (c) the consumer
base includes any MCP-compatible host (Claude Desktop, Cursor, OpenClaw derivatives),
not just the original developer. README P2 already signals this as planned for
2026-Q3 — the RFC provides the architecture to deliver on that signal safely.

#### Reason 4: Protocol Stability

> "MCP 协议仍处于快速发展期，过早绑定可能引入不必要的迁移成本"

**How this RFC threads the concern**: The discovery-only layer is an **L4 interface
component with a 1-3 year lifecycle** (see §4). If the MCP protocol changes
substantially, the server can be replaced without affecting L2/L1. The 3-tool
surface (`list_capabilities`, `describe_tool`, `invoke_tool`) is minimal and
protocol-agnostic in concept — the same pattern could be reimplemented over a
future protocol (WASM plugins, direct tool-use protocols) with the same manifest.

Further, the `SKILL.md` path is preserved as the fallback authority. If MCP
becomes unreliable or undesirable, Agents continue to use SKILL.md + CLI exactly
as they do today. The discovery layer is an additive convenience, not a migration.

### ADR Number Collision (Lead Decision)

Two distinct decisions in the repository carry the number **ADR-004**:

| # | Location | Decision | Date |
|---|---|---|---|
| 1 | `docs/ARCHITECTURE.md:198-218` | "不迁移到 MCP" (Do not migrate to MCP) | Inline, no standalone date |
| 2 | `docs/adr/ADR-004-rrf-min-score.md` | RRF_MIN_SCORE = 0.008 | 2026-04-17 |

This is a governance hazard: two decisions sharing the same ADR number makes
cross-referencing ambiguous and damages the audit trail.

Options considered:
- **(a)** Renumber `ADR-004-rrf-min-score.md` to ADR-005 (the RRF ADR was
  accepted 2026-04-17, after the inline MCP ADR was authored).
- **(b)** Promote the inline `ARCHITECTURE.md` §ADR-004 to its own file
  (`docs/adr/ADR-004-mcp-migration.md`), freeing the inline section for
  architecture prose only, and renumber the RRF ADR to ADR-005.
- **(c)** Explicit governance note recording the collision with a one-time
  exemption.

**Lead decision (2026-05-25)**: adopt option (c), a one-time explicit governance
note, and do not renumber existing ADR files in this RFC. `docs/adr/ADR-005-*.md`
and later ADRs already exist, so renumbering `ADR-004-rrf-min-score.md` would
cascade into unrelated public ADR history. Future references must qualify the
target as either `ARCHITECTURE.md inline ADR-004 (MCP migration)` or
`docs/adr/ADR-004-rrf-min-score.md (RRF min score)`. Future ADRs must not reuse
existing numbers; if the inline MCP decision is promoted later, it should use a
new unambiguous ADR identifier or date-based filename.

### Summary: This RFC Does Not Reverse ADR-004

The inline ADR-004 rejected a **full MCP migration** (MCP server as the primary
tool execution surface, replacing CLI + SKILL.md). This RFC proposes a
**discovery-only overlay** that preserves CLI as SSOT, adds no parallel data path,
adopts progressive disclosure for tool schemas, and is an L4-only additive component.
The two designs differ in every dimension ADR-004's rejection reasons targeted.

This RFC is not an amendment to ADR-004 — it is a separate, narrower proposal that
coexists with the existing decision. If the owner determines that this RFC
materially reverses ADR-004, an explicit ADR amendment should be recorded.

## §6 CHARTER Amendments Needed

**None.** This RFC proposes no changes to CHARTER.md. The discovery layer is fully
compliant with all current CHARTER clauses:

| CHARTER Clause | Compliance |
|---|---|
| §1.1 Data Sovereignty | ✅ No cloud upload, no new persistence points |
| §1.2 Plain Text Forever | ✅ No new binary format; CLI output is JSON |
| §1.3 CLI as SSOT | ✅ MCP server proxies CLI; CLI remains sole authority |
| §1.4 Layer Isolation | ✅ L4 → L2 call path is explicitly allowed (§1.5) |
| §1.5 Deterministic/Intelligent Divide | ✅ Zero LLM code in server; execution is deterministic |
| §1.6 Backward Compatibility | ✅ No data format changes |
| §1.7 Three Bottom Lines | ✅ Simple (3 tools), reliable (CLI subprocess), no automation trap |
| §1.8 Long-Termism | ✅ Low migration cost (L4 component, replaceable) |
| §1.9 Agent-Native Module Principle | ✅ No bundled LLM; BYOL boundary preserved |
| §1.10 Module-Foundation Contract Boundary | ✅ No plugin loader, no dynamic registry, no L2 modification |
| §1.11 Recall-First Retrieval Truthfulness | ✅ `invoke_tool` returns CLI output unchanged; no filtering |

### Future CHARTER Consideration

If the MCP discovery layer proves valuable and multiple modules begin consuming it, a
future RFC could consider adding a "L4 Interface Protocol" section to CHARTER §2.1.
This is explicitly out of scope for the current RFC.

## §7 CHARTER Guards / Falsifiability

### Guards (what must hold for this to remain compliant)

1. **No direct data access**: The MCP server must never import `tools.lib.config`,
   open files in `~/Documents/Life-Index/`, or call any L2 internals directly. Only
   subprocess CLI calls are permitted.

2. **No LLM initialization**: The MCP server must never import LLM libraries
   (`openai`, `anthropic`, `sentence-transformers`), read API keys from environment
   or config, or make outbound HTTP requests to LLM providers.

3. **No dynamic discovery**: The capability manifest must be a static file loaded at
   startup. No `os.listdir()`, `glob`, `importlib`, or AST parsing of `tools/` to
   discover commands at runtime.

4. **CLI output passthrough**: `invoke_tool` must return CLI stdout unchanged. No
   transformation, filtering, truncation, or enrichment.

5. **No state accumulation**: The server must not maintain caches, sessions, or
   persistent state across connections.

### Falsifiability (how to prove this RFC is violated)

| Test | Command/Method | Expected if compliant | Violation signal |
|---|---|---|---|
| Direct data access | Source audit: `rg "tools\.lib\.config|USER_DATA_DIR|Documents/Life-Index" tools/mcp_discovery/` | No matches | Import or string literal referencing data paths |
| LLM dependency | Source audit: `rg "openai|anthropic|sentence.transformers" tools/mcp_discovery/` + `rg "openai|anthropic|sentence.transformers" pyproject.toml` | No matches | LLM library in deps or imports |
| Dynamic discovery | Code audit: check for `os.listdir`, `glob`, `importlib` in server module | Only static file reads | Runtime tool directory scanning |
| Output modification | `life-index search --query "test"` vs MCP `invoke_tool("search", {"query":"test"})` | Identical JSON output | Output differs |
| State persistence | Run server, call `list_capabilities`, restart server, call again | Same result | Cached result from prior session |

## §8 Alternatives Considered

### A. Do Nothing (Status Quo)

Agents continue to discover Life Index capabilities through SKILL.md and manual
configuration.

- **Pros**: Zero code cost, zero risk of CHARTER violation
- **Cons**: Onboarding friction remains; capability staleness as CLI evolves; README P2
  forward signal goes unfulfilled
- **Rejection reason**: Does not address the stated problem. README already commits to an
  MCP discovery layer ("In Flight · 2026-Q3"). This RFC provides the architecture to
  deliver on that commitment safely.

### B. Full MCP Server with Direct Tool Implementation

Implement each CLI tool as a native MCP tool handler with direct Python function calls.

- **Pros**: Lower latency (no subprocess overhead), richer input validation
- **Cons**: Creates parallel implementation of every CLI tool; violates CHARTER §1.3
  (CLI as SSOT); requires ongoing maintenance to keep MCP handlers in sync with CLI
- **Rejection reason**: Fundamental CHARTER violation. The CLI is SSOT — duplicating tool
  logic in an MCP handler creates a second truth source.

### C. MCP Server with LLM-Enhanced Tool Descriptions

Use an LLM to generate rich, context-aware tool descriptions and usage guidance.

- **Pros**: Better natural language tool descriptions for Agent consumption
- **Cons**: Violates CHARTER §1.5 (§1.9) — introducing LLM into what should be a
  deterministic interface layer; creates dependency on LLM provider availability
- **Rejection reason**: Mixed determinism. The MCP discovery layer's value is that it
  accurately reflects CLI capabilities. LLM-generated descriptions can hallucinate
  parameters or misrepresent tool behavior. If an Agent needs richer descriptions, it
  can use its own LLM to interpret the deterministic output — per the BYOL model.

### D. Static JSON Manifest Only (No MCP Server)

Publish a `capabilities.json` file that MCP hosts or Agents can read directly.

- **Pros**: Simplest implementation; no server process needed
- **Cons**: Not MCP-compatible (MCP requires a JSON-RPC server); each host would need
  custom code to parse and use the manifest
- **Rejection reason**: Does not achieve the goal of standardizing discovery for MCP
  hosts. The whole point is to use the MCP protocol so that compatible hosts can discover
  Life Index with zero custom integration code.

### E. MCP Server in a Separate Repository

Host the MCP discovery server as a standalone package in a separate repository.

- **Pros**: Clear separation of concerns; independent versioning
- **Cons**: Capability manifest must be manually synced with CLI changes; higher
  maintenance burden; discoverability for users (which repo has the MCP server?)
- **Rejection reason**: Adds synchronization risk. Co-locating the MCP server in the
  Life Index repository ensures that capability changes are visible in the same PR.

## §9 Substantive Gate

Per CHARTER §5 (as amended 2026-05-20), this RFC requires substantive gate review before
proceeding to implementation.

### Gate Questions

1. **Does this RFC introduce any CHARTER violation?**
   - **Answer**: No. All 11 CHARTER clauses are explicitly verified compliant in §6.

2. **Does this RFC require any CHARTER amendment?**
   - **Answer**: No. The discovery layer fits within existing architecture boundaries.

3. **Does this RFC have a real consumer?**
   - **Answer**: Yes. README P2 explicitly signals MCP discovery layer as planned for
     2026-Q3. MCP-compatible hosts (Claude Desktop, Cursor, OpenClaw derivatives) form
     the consumer base.

4. **Is the exit criterion falsifiable?**
   - **Answer**: Yes. §7 provides 5 specific falsifiability tests with concrete
     commands and expected outcomes.

5. **Does this RFC create technical debt or lock in future decisions?**
   - **Answer**: No. The MCP server is an L4 interface component with 1-3 year
     lifecycle. It can be replaced without affecting any lower layer.

### Gate Status

**Accepted by 主审_GPT under owner authorization on 2026-05-25.** The inline
`docs/ARCHITECTURE.md` ADR-004 has been identified and fully engaged in §5. The
ADR-004 number collision is resolved for this RFC by the one-time qualified-reference
decision above. Proceeding with a discovery-only MCP layer is authorized as a
narrow exception that does not reverse the existing "不迁移到 MCP" decision.

## §10 Acceptance Criteria

- [x] RFC reviewed by Life Index lead reviewer under owner authorization
- [x] ADR-004 number collision resolved for this RFC by qualified-reference note (see §5)
- [x] CHARTER compliance verified by independent audit (Opus review complete — see report)
- [x] No CHARTER amendments required (confirmed — see §6)
- [x] Implementation deferred to post-RFC-acceptance phase (stub not required in this pass)

### Post-Acceptance Implementation Criteria (for future task)

- [ ] `tools/mcp_discovery/` directory created with `__main__.py`, `server.py`, `capabilities.json`
- [ ] Server core ≤200 LOC
- [ ] `capabilities.json` manifest covers all 24 CLI help entries (22 unique commands plus 2 aliases)
- [ ] `invoke_tool` correctly subprocesses `life-index` CLI and returns output unchanged
- [ ] No imports of `tools.lib.config`, LLM libraries, or dynamic discovery mechanisms
- [ ] `python -m tools.mcp_discovery` starts JSON-RPC 2.0 server on stdio
- [ ] CHARTER §7 falsifiability tests all pass
- [ ] AGENTS.md for `tools/mcp_discovery/` documents the module
- [ ] README P2 MCP discovery status updated from "In Flight" to "Shipped"
