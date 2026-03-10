# ADR-001: Agent-First 架构设计

---
status: accepted
date: 2026-02-24
---

## Context and Problem Statement

Life Index v2 版本因过度工程化导致系统失效。如何设计一个简洁、可靠的架构，充分发挥 AI Agent 的能力？

## Decision Drivers

* Agent 具备自然语言理解和生成能力
* Agent 具备文件操作能力
* Agent 具备定时任务调度能力
* 系统应保持简洁，避免过度抽象

## Considered Options

1. **全工具化方案**：为每个功能开发专用工具
2. **Agent-First 方案**：仅开发必要的原子工具，其他由 Agent 完成
3. **混合方案**：部分功能开发工具，部分由 Agent 处理

## Decision Outcome

Chosen option: "**Agent-First 方案**", because 这是最能发挥 Agent 能力同时保持系统简洁的方案。

### Consequences

* Good, because 减少代码量，降低维护成本
* Good, because 充分利用 Agent 的自然语言能力
* Good, because 系统架构简洁透明
* Bad, because Agent 执行结果可能不如专用工具确定性强
* Bad, because 需要更完善的 Agent 指令设计

## Pros and Cons of the Options

### 全工具化方案

* Good, because 执行结果确定性强
* Bad, because 开发和维护成本高
* Bad, because 容易陷入过度工程化

### Agent-First 方案

* Good, because 代码量少，维护成本低
* Good, because 灵活性高，易于扩展
* Good, because 符合 Agent Skills 规范
* Bad, because 需要精心设计 Agent 指令

## More Information

参见 [HANDBOOK.md](../HANDBOOK.md#核心原则) 核心原则章节。