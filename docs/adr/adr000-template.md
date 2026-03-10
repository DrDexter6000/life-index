# ADR-000: 架构决策记录模板

---
status: accepted
date: 2026-03-10
---

## Context

Life Index 项目需要一种标准化的方式来记录和追溯架构决策。

## Decision

采用 MADR (Markdown Architectural Decision Records) 格式记录架构决策。

## Consequences

* Good, because 提供统一的决策记录格式
* Good, because 便于新贡献者理解历史背景
* Good, because 决策可追溯、可检索
* Bad, because 需要额外维护文档

## Template

```markdown
---
status: "{proposed | rejected | accepted | deprecated | superseded by ADR-XXX}"
date: YYYY-MM-DD
---

# ADR-{NNN}: {决策标题}

## Context and Problem Statement

{描述背景和问题}

## Decision Drivers

* {决策驱动因素 1}
* {决策驱动因素 2}

## Considered Options

* {选项 1}
* {选项 2}
* {选项 3}

## Decision Outcome

Chosen option: "{选项名称}", because {原因}.

### Consequences

* Good, because {正面影响}
* Bad, because {负面影响}

## Pros and Cons of the Options

### {选项 1}

* Good, because {优点}
* Bad, because {缺点}

## More Information

{附加信息}
```

## More Information

* [MADR 官方仓库](https://github.com/adr/madr)
* [ADR 官网](https://adr.github.io)