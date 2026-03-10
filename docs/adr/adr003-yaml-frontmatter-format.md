# ADR-003: YAML Frontmatter 格式选择

---
status: accepted
date: 2026-03-10
---

## Context and Problem Statement

日志文件需要存储元数据（日期、地点、天气、标签等）。选择 YAML 还是 JSON 作为 frontmatter 格式？

## Decision Drivers

* 人类可读性
* 编辑友好度
* 工具兼容性
* Agent 解析便利性

## Considered Options

1. **纯 YAML 格式**
2. **纯 JSON 格式**
3. **YAML + JSON 数组混合格式**

## Decision Outcome

Chosen option: "**YAML + JSON 数组混合格式**", because 兼顾人类可读性和紧凑性。

### Consequences

* Good, because YAML 基础格式人可读性好
* Good, because JSON 数组格式紧凑
* Good, because 兼容 Jekyll/Obsidian 等工具
* Bad, because 格式混合可能造成困惑

## Pros and Cons of the Options

### 纯 YAML 格式

```yaml
mood:
  - 专注
  - 充实
tags:
  - 重构
  - 优化
```

* Good, because 标准 YAML 格式
* Bad, because 多行占用空间大

### 纯 JSON 格式

```json
{
  "mood": ["专注", "充实"],
  "tags": ["重构", "优化"]
}
```

* Good, because Agent 解析方便
* Bad, because 引号/括号多，编辑易出错
* Bad, because 不支持注释

### YAML + JSON 数组混合格式

```yaml
mood: ["专注", "充实"]
tags: ["重构", "优化"]
```

* Good, because 数组紧凑
* Good, because YAML 主体保持可读性
* Good, because 兼容现有工具
* Bad, because 格式混合

## More Information

参见 [AGENTS.md](../../AGENTS.md#日志文件格式) 日志文件格式章节。