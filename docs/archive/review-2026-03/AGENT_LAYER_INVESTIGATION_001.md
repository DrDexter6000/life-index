# Agent-Layer Investigation #001

> **日期**: 2026-03-18
> **调查项**: Agent-layer confirmation/clarification correctness
> **原Tier**: C
> **结果Tier**: B
> **状态**: 已完成 — 文档gap已修复

---

## 1. 调查背景

Baseline诊断（`BASELINE_RUN_RESULTS.md`）反复指出：

> Agent-layer workflow proof remains weaker than tool-layer proof
> Many important workflow expectations live at the agent/tool boundary

本次调查旨在验证Agent行为是否有足够的文档+工具支持。

---

## 2. 验证范围

从`WORKFLOW_EVAL_CASES.md`中选取3个高风险case：

| Case | 验证点 | 风险等级 |
|:---|:---|:---:|
| WF-03 | Agent是否在`needs_confirmation`后进入确认流程 | 高 |
| WF-02 | Agent是否在ambiguous intent时先clarify再调用工具 | 高 |
| WF-10 | Agent是否正确描述"saved with degraded enrichment" | 中 |

---

## 3. 验证结果

### WF-03: Confirmation Flow Handling

| 检查项 | 结果 |
|:---|:---:|
| 工具返回 `needs_confirmation: true` | ✅ |
| SKILL.md 明确要求检查此字段 | ✅ Line 134-154 |
| SKILL.md 明确说明后续行为 | ✅ "展示 → 等待回复" |

**判定**: 通过

---

### WF-02: Ambiguous Intent Clarification

| 检查项 | 结果 |
|:---|:---:|
| CANONICAL_WORKFLOWS.md 有明确指导 | ✅ |
| SKILL.md 有明确指导 | ❌ 缺失 |
| Agent主要读取的文档 | SKILL.md |

**判定**: 文档位置gap — 关键指导存在于review文档而非Tier 1 SSOT

---

### WF-10: Degraded State Description

| 检查项 | 结果 |
|:---|:---:|
| 工具返回 `index_status` / `side_effects_status` | ✅ |
| 工具在weather失败时正确反映状态 | ⚠️ 部分正确 |
| SKILL.md 指导如何解读这些字段 | ❌ 缺失 |

**判定**: 文档gap — 缺少字段解读指导

---

## 4. 发现的Gap

| Gap | 类型 | 处理 |
|:---|:---|:---|
| SKILL.md缺少ambiguous intent指导 | 文档位置 | ✅ 已上提到SKILL.md |
| SKILL.md缺少degraded state字段说明 | 文档缺失 | ✅ 已新增到SKILL.md |
| weather失败不反映在`side_effects_status` | 实现/语义 | 待定（需确认设计意图） |

---

## 5. 已执行的修复

1. **SKILL.md更新**:
   - 新增"意图澄清（强制）"章节
   - 新增"写入结果解读"章节，包含`index_status`/`side_effects_status`字段说明

2. **CANONICAL_WORKFLOWS.md标注**:
   - 添加"已采纳"状态标注
   - 明确运行时指导以SKILL.md为准

---

## 6. 遗留问题

### 待确认：Weather失败与`side_effects_status`的关系

**现象**: Weather查询失败时，`side_effects_status`仍为`complete`而非`degraded`

**可能解释**:
1. 设计意图：weather不属于"副作用"，仅属于可选enrichment
2. 实现gap：应反映但未反映

**建议**: 后续由Owner确认设计意图，再决定是否需要调整

---

## 7. 结论

Agent-layer核心行为已有文档+工具支持。主要问题是关键指导存在于review文档而非Tier 1 SSOT。

**修复后状态**:
- WF-03: 通过
- WF-02: 通过（文档已补充）
- WF-10: 通过（文档已补充）

Investigation Item #1 从Tier C升级到Tier B。

---

## 8. 后续建议

1. 继续Investigation #3 (Retrieval quality) 或 Investigation #4 (Failure-injection)
2. 或等待新的runtime-observed gap