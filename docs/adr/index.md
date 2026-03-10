# Architecture Decision Records

本目录记录 Life Index 项目的架构决策历史。

## 什么是 ADR？

ADR (Architecture Decision Record) 是一种轻量级的文档格式，用于记录架构决策的背景、选项、结果和影响。

## ADR 列表

| ADR | 标题 | 状态 | 日期 |
|-----|------|------|------|
| [ADR-000](adr000-template.md) | 架构决策记录模板 | Accepted | 2026-03-10 |
| [ADR-001](adr001-agent-first-architecture.md) | Agent-First 架构设计 | Accepted | 2026-02-24 |
| [ADR-002](adr002-single-layer-transparency.md) | 单层透明架构 | Accepted | 2026-02-24 |
| [ADR-003](adr003-yaml-frontmatter-format.md) | YAML Frontmatter 格式选择 | Accepted | 2026-03-10 |

## 如何添加新的 ADR

1. 复制 `adr000-template.md` 为 `adr{NNN}-{title}.md`
2. 填写各个章节
3. 更新本索引文件
4. 提交 PR 评审

## ADR 状态说明

| 状态 | 说明 |
|------|------|
| Proposed | 提议中，待讨论 |
| Accepted | 已接受，正在实施 |
| Rejected | 已拒绝 |
| Deprecated | 已废弃 |
| Superseded by ADR-XXX | 被 ADR-XXX 取代 |

## 参考资源

* [MADR 官方仓库](https://github.com/adr/madr)
* [ADR 官网](https://adr.github.io)
* [Michael Nygard 的 ADR 模板](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions)