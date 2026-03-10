# ADR-002: 单层透明架构

---
status: accepted
date: 2026-02-24
---

## Context and Problem Statement

传统应用架构通常包含数据库、服务进程、API 网关等中间层。这些中间层增加了系统复杂度，也引入了潜在的故障点。对于个人日志管理场景，是否需要这些中间层？

## Decision Drivers

* 系统应保持简洁，易于理解和维护
* 数据应为人可读，不依赖特定软件
* Agent 具备直接操作文件系统的能力
* 避免"过度工程化"陷阱

## Considered Options

1. **传统架构**：数据库 + 服务层 + API
2. **单层透明架构**：用户 ↔ Agent ↔ 文件系统
3. **混合架构**：部分功能使用数据库

## Decision Outcome

Chosen option: "**单层透明架构**", because 这是最简洁且满足需求的方案。

### Consequences

* Good, because 架构极简，易于理解
* Good, because 数据为人可读（Markdown + YAML）
* Good, because 无中间层故障点
* Good, because 便于跨平台迁移
* Bad, because 大数据量下搜索性能可能受限
* Bad, because 无法支持复杂查询

## Pros and Cons of the Options

### 传统架构

* Good, because 支持复杂查询
* Good, because 性能可扩展
* Bad, because 增加部署和维护复杂度
* Bad, because 数据依赖特定数据库
* Bad, against 单用户场景过度设计

### 单层透明架构

* Good, because 架构极简
* Good, because 数据完全开放
* Good, because 无额外依赖
* Bad, because 搜索依赖文件系统

## More Information

参见 [HANDBOOK.md](../HANDBOOK.md#核心原则) 单层透明原则。