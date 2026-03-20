# MCP Reevaluation

> **Document role**: Evaluate whether Life Index should adopt the Model Context Protocol (MCP)
> **Audience**: Project owner, architecture reviewers
> **Authority**: Review-scoped decision document; defers to `docs/ARCHITECTURE.md` ADR-004 for historical context
> **Primary goal**: Make an explicit go / no-go / defer decision with clear criteria for future reconsideration

---

## 1. Decision Statement

**Status**: **DEFER**

Life Index will not migrate to MCP at this time. The current CLI architecture remains the preferred approach.

This decision is reversible and should be revisited if specific trigger conditions are met.

---

## 2. Current Architecture

Life Index exposes functionality through:

| Layer | Implementation |
|:---|:---|
| CLI entry point | `life-index` command (unified) |
| Module execution | `python -m tools.{module}` |
| Return format | JSON via stdout |
| Invocation context | Bash tool from Agent environment |

This architecture is documented in `docs/API.md` and `SKILL.md`.

---

## 3. What is MCP

Model Context Protocol (MCP) is a protocol for exposing tools to AI systems via a standardized server interface. Key characteristics:

- Tools are exposed through a server process
- Clients (Agents) connect via stdio or HTTP
- Tool schema is declared and discoverable
- Multiple clients can share the same tool server

---

## 4. Evaluation Criteria

### 4.1 Criteria for adoption

| Criterion | Weight | Current Assessment |
|:---|:---|:---|
| Multi-client interoperability | High | Not needed |
| Reduced installation friction | Medium | MCP increases friction |
| Ecosystem alignment | Medium | Neutral |
| Maintenance burden | High | MCP adds complexity |
| Protocol stability | High | Still evolving |

### 4.2 MCP benefits (theoretical)

| Benefit | Applicability to Life Index |
|:---|:---|
| Standardized tool schema | Low value; current JSON interface is sufficient |
| Multi-client support | Not applicable; single-user local tool |
| Discovery mechanism | Low value; tools are explicitly documented |
| Ecosystem integration | Unclear; no current demand |

### 4.3 MCP costs (actual)

| Cost | Impact |
|:---|:---|
| Additional dependency | `mcp` Python package |
| Configuration complexity | `mcp.json` or similar configuration required |
| Server process management | Background process lifecycle |
| Installation steps | More complex than current pip install |
| Protocol version drift | Ongoing maintenance as MCP evolves |

---

## 5. Decision rationale

### 5.1 Why defer

1. **Overkill for use case**
   - Life Index is a local, single-user journaling tool
   - MCP shines in multi-client, multi-tool scenarios
   - Current CLI approach is simpler and sufficient

2. **Installation friction increases**
   - Current: `pip install -e .` → ready
   - MCP: Install package + configure MCP client + register server
   - The user explicitly noted concern about "大炮打蚊子" (overkill)

3. **No multi-client requirement**
   - Life Index is designed for one user, one Agent
   - No scenario where multiple clients need to share the same journal instance

4. **Protocol maturity**
   - MCP is still evolving
   - Early adoption risks breaking changes
   - Better to wait for stability

5. **Existing architecture works**
    - Unit tests pass (755 passed, 4 skipped)
    - Health check command validates installation
    - No reported issues with current CLI approach

6. **Recent Phase 3 friction did not justify protocol expansion**
   - Fresh-install rehearsal surfaced narrow Windows CLI/output issues
   - Those issues were resolved locally in the existing CLI path
   - This strengthens the case for fixing product-readiness gaps in the current architecture instead of adding an MCP layer

### 5.2 What would change the decision

**Go criteria** (any one sufficient):

| Trigger | Rationale |
|:---|:---|
| Multi-client use case emerges | User wants to access same journal from multiple Agents simultaneously |
| Agent platform mandates MCP | Primary Agent platform drops support for Bash-based tools |
| MCP becomes de facto standard | Ecosystem converges on MCP as universal tool interface |
| Significant ecosystem benefit | Major tools/libraries only available via MCP |

**Timeline for reconsideration**: 6-12 months or upon trigger event.

---

## 6. Historical context

This evaluation builds upon `docs/ARCHITECTURE.md` ADR-004:

> **ADR-004: MCP 迁移评估**
> 
> **决策**: 暂不迁移到 MCP，保持当前 CLI 架构。
> 
> **原因**:
> - 收益/成本比低：~10 小时工作量换取的体验提升对个人用户不显著
> - MCP 协议仍处于快速发展期
> - 当前 CLI 方案在低频场景下完全胜任
> 
> **后续行动**:
> - 短期：保持 CLI 架构，关注 MCP 发展
> - 中期（6-12 月）：若 MCP 成为标准，考虑可选 MCP Server
> - 长期：若平台全面转向 MCP，再启动迁移

This document confirms ADR-004 remains valid. No change to the decision.

---

## 7. Implementation note (if ever needed)

If the decision changes to "go" in the future, the implementation approach would be:

1. Create `tools/mcp_server.py` as optional entry point
2. Wrap existing tool modules in MCP tool decorators
3. Maintain backward compatibility with CLI
4. Document both paths (CLI for simple use, MCP for multi-client)

**Not in scope now**: No code changes, no MCP dependencies, no configuration files.

---

## 8. SSOT references

| Truth | Location |
|:---|:---|
| Historical MCP decision | `docs/ARCHITECTURE.md` ADR-004 |
| Current CLI interface | `docs/API.md` |
| Tool entry points | `pyproject.toml` `[project.scripts]` |
| Health check implementation | `tools/__main__.py` |

---

## 9. Conclusion

**MCP adoption is deferred.**

The current CLI architecture is:
- Simpler to install and configure
- Sufficient for the single-user, local use case
- Well-tested and stable
- Documented in Tier 1 SSOT

Revisit this decision if:
1. Multi-client interoperability becomes a concrete requirement
2. Primary Agent platform mandates MCP
3. 6-12 months have passed and protocol has stabilized

This is a narrow, local, reversible decision that preserves optionality without incurring costs now.

### Current recommendation in one line

**Fix onboarding and distribution friction inside the current CLI-first architecture before adding any protocol adapter layer.**
