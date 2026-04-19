# CN-001: Tool-Scoped Progressive Disclosure

**Status**: Draft
**Date**: 2026-04-18
**Scope**: Cross-cutting agent/tool interaction model
**Current adoption target**: Life Index Round 11
**Related**: `.strategy/cli/Round_10_Final_Review.md`, `.strategy/cli/Round_11_PRD.md`

---

## Context

Agent-native systems often accumulate too much guidance in one place.

在 Life Index 当前形态里，这个问题具体表现为：

1. **全局文档膨胀**
   - `SKILL.md` 同时承担工具发现、职责边界、场景路由、细粒度使用指南
   - 结果是：全局 prompt 越来越长，Agent 的注意力被分散

2. **局部知识无法按需披露**
   - 某个工具真正需要的细节，只在调用它的那个时刻才相关
   - 但如果这些细节都提前堆进全局文档，绝大多数调用都会白白承担 token 与注意力成本

3. **软规则难以测试**
   - 当“应该如何调用工具、遇到什么情况该如何处理”只写在 prose 里时，行为依赖模型记忆与理解
   - 这类规则不可验证、不可稳定回归，也难跨 Agent 复用

Round 10 终审把这个矛盾照得很清楚：

> 搜索质量已经不再只是 retrieval tuning 的问题，而是需要一个新的 agent/tool 协作边界。

因此，需要一种结构，把：

- 全局规则
- 工具契约
- 运行时局部提示
- Agent judgment

分开处理。

---

## Decision

采用 **Tool-Scoped Progressive Disclosure** 作为 agent/tool interaction 的推荐概念模型。

它的核心思想是：

> **让全局文档退回“薄路由 + 不变量”，让具体工具在被调用时再披露它自己的局部上下文。**

这不是“把更多 prompt 塞给 agent”，而是把上下文分层：

- 该静态存在的，放在 schema / contract 里
- 该确定性执行的，放在 CLI preprocessing 里
- 该按调用场景才相关的，放在 invocation-time hints 里
- 该由模型判断的，留给 agent reasoning

---

## The Four-Layer Model

| Layer | Name | What Lives Here | Boundary Rule |
|:---:|---|---|---|
| **L1** | **Schema Contract** | 参数类型、frontmatter schema、枚举、字段约束、response shape | 静态、机器可读；不承载 prose guidance |
| **L2** | **Deterministic Preprocessing** | 归一化、默认值补全、日期解析、结构化 `search_plan` 生成、硬校验 | 纯确定性；不处理歧义 judgment |
| **L3** | **Invocation-Time Hints** | 某个工具在当前调用时才需要披露的局部提示、ambiguity signal、edge-case note | 短、临时、单工具作用域；不预加载到全局 prompt |
| **L4** | **Agent Reasoning** | 歧义处理、追问用户、聚合判断、解释、跨工具编排 | 消费 L1–L3；拥有所有非确定性判断 |

---

## Boundary Rules

### Rule 1 — L1 不解释，只约束

Schema Contract 的职责是表达：

- 什么字段存在
- 类型是什么
- 哪些值合法
- 返回结构长什么样

它不承担：

- 使用策略
- 场景说明
- “最好怎么调用”

例如：

- `mood: list[str]` 属于 L1
- “心情应优先填写情绪词，不要写活动”不属于 L1，而应属于 L3 或文档说明

### Rule 2 — L2 只做 deterministic transformation

Deterministic Preprocessing 可以做：

- 日期归一化
- query normalization
- structured `search_plan` 生成
- 默认参数补全
- 必填项校验

但它不应该做：

- “用户大概想问什么”这种开放性判断
- 模糊语义推理
- 应该追问还是应该直接执行的策略选择

### Rule 3 — L3 是 tool-scoped，不是 global prompt 的延长线

Invocation-Time Hints 的本质不是把 `SKILL.md` 搬进工具输出，而是只在需要时提供当前工具的局部上下文。

它应满足：

- **只对当前调用有效**
- **只绑定一个工具/命令**
- **短小、描述性、非支配性**

例如：

- `0 results found; consider broadening date range`
- `aggregation requires agent judgement; search returns evidence set, not final answer`

不应写成：

- “你现在必须调用 search 三次”
- “你必须按以下 12 步推理”

那会让 hints 重新退化为冗长 system prompt。

### Rule 4 — L4 拥有 ambiguity judgment

只有 Agent Reasoning 层负责：

- 歧义解释
- 用户意图理解
- 多候选选择
- 聚合结论与不确定性表达

CLI 不应承担这类 open-ended responsibility。

---

## Relation to Existing Terms

Tool-Scoped Progressive Disclosure 不是凭空发明的新宇宙，而是已有概念的一个清晰子模式。

### Closest adjacent terms

| Term | Why it is close | Why it is not sufficient |
|---|---|---|
| **Context Engineering** | 它是总学科，强调“在正确的时机提供正确的上下文” | 太宽，不能直接指代这个具体结构 |
| **Progressive Disclosure** | 它准确描述了“按需披露”的 UX 原则 | 只说明原则，不说明 agent/tool 架构分层 |
| **Dynamic / Event-Driven Context Injection** | 很接近运行时注入机制 | 还没把“tool-scoped + thin global router”说完整 |
| **Tiered Skill Architecture** | 很接近“路由层 + 正文层”的结构 | 更常用于 skill loading，不一定覆盖 CLI runtime hints |
| **Just-In-Time Tooling / JIT Context** | 强调按需加载 | 更偏 tool discovery，不够聚焦 hint injection |

因此，这个概念最适合被理解为：

> **Context Engineering 下的一个可命名、可复用的具体子模式。**

---

## Recommended Use in Life Index

Life Index 当前最适合采用这套模型的地方是 `search_journals`。

### L1 — Schema Contract

- `tools/search_journals/schema.json`
- `docs/API.md` 中 search_journals 的参数/返回契约

### L2 — Deterministic Preprocessing

- query normalization
- 日期表达转结构化时间窗
- 主题/实体 hint 抽取
- `search_plan` 结构输出

### L3 — Invocation-Time Hints

search 返回中的：

- `hints`
- `ambiguity`
- （可选）`search_plan`

这些都属于当前调用才相关的局部上下文，不应提前塞进全局 `SKILL.md`。

### L4 — Agent Reasoning

Agent 决定：

- 当前 ambiguity 是否需要追问用户
- 这是不是一个 aggregation query
- 检索结果能否直接回答，还是只能作为 evidence set

---

## Consequences

### Positive

1. **全局 prompt 变短**
   - `SKILL.md` 可以显著收缩

2. **注意力更集中**
   - Agent 只在调用某工具时读取对应局部提示

3. **行为更可测试**
   - L2 / L3 能进入正式 contract 与 regression test

4. **职责边界更清晰**
   - CLI 不再承担开放性判断
   - Agent 不再被迫死记所有 scenario prose

5. **更适合渐进演化**
   - 先从 `search_journals` 引入，再推广到 write/edit/entity 等工具

### Tradeoffs

1. **需要新建一层概念与字段设计**
   - 这不是白拿的，需要正式定义 `hints / ambiguity / search_plan`

2. **需要抑制 hint 膨胀**
   - 如果每个工具都吐很多 hints，就会重新演变成 prompt flood

3. **需要明确 schema 与 hint 的边界**
   - 否则会出现“字段语义重复写两遍”的问题

---

## Anti-Patterns

以下做法都违背 CN-001：

1. **把每个场景都写进 `SKILL.md`**
2. **让 CLI 直接输出大段 prescriptive prompt**
3. **让 deterministic layer 处理模糊语义 judgment**
4. **把 invocation-time hints 设计成另一份 system prompt**
5. **把 schema、hint、reasoning 三层揉成一层 prose**

---

## Adoption Guidance

未来如果某个具体实现决策落地，应由 ADR 引用本概念文档，而不是直接修改 CN-001 取代具体 ADR。

例如：

- `ADR-012`: search_journals introduces `hints` field in Layer 3
- `ADR-013`: search_journals introduces structured `search_plan` in Layer 2

也就是说：

> **CN-001 负责定义语言与边界，ADR 负责记录某次具体实现决策。**

---

## Related

- `.strategy/cli/Round_10_Final_Review.md`
- `.strategy/cli/Round_11_PRD.md`
- `docs/API.md`
- `SKILL.md`
