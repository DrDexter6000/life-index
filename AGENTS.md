# AGENTS.md - Life Index 项目开发指南

> 本文档为 Life Index 项目开发、为 AI 编码代理提供项目上下文。  
> **最后更新**: 2026-03-17 | **版本**: v1.1 | **状态**: 活跃维护

## 项目概述

**Life Index** 是一个 Agent Skill（技能包），提供个人生活日志记录能力。用户通过自然语言与 Agent 交互，Agent 调用 Python 原子工具完成日志的记录、搜索、编辑和摘要生成。

**核心理念**:
- **Agent-first**：发挥 Agent 自然语言理解和生成能力，仅在需要原子性/准确性时开发专用工具
- **本地优先**：所有数据存储在 `~/Documents/Life-Index/`
- **纯文本格式**：Markdown + YAML Frontmatter，永不过时

**关键架构决策**:
- **双管道并行检索架构** 关键词管道 ∥ 语义管道并行执行 + RRF 融合
- **数据物理隔离**：用户数据在 `~/Documents/Life-Index/`，项目代码在仓库目录

---

## 构建与运行命令

### 依赖安装

```bash
# Python 3.11+ (核心运行环境)
# pip install -e . 已包含语义搜索依赖（fastembed）
```

### 核心工具命令

```bash
# 推荐（pip install 后）
life-index write --data '{"title":"...","content":"...","date":"2026-03-07","topic":"work"}'
life-index search --query "关键词" --level 3
life-index edit --journal "Journals/2026/03/life-index_2026-03-07_001.md" --set-weather "晴天"
life-index abstract --month 2026-03
life-index weather --location "Lagos,Nigeria"
life-index index           # 增量更新

# 开发者模式（无需安装）
python -m tools.write_journal --data '{...}'
python -m tools.search_journals --query "关键词"
```

---

## 模块结构

> **详细模块说明**: 参见 [`tools/lib/AGENTS.md`](tools/lib/AGENTS.md)

```
tools/
├── write_journal/              # 写入日志模块
│   ├── __init__.py            # CLI入口
│   ├── __main__.py            # 模块执行入口
│   ├── core.py                # 核心协调逻辑
│   ├── attachments.py         # 附件处理
│   ├── index_updater.py       # 索引更新（v1.2 Write-Through）
│   ├── utils.py               # 通用工具函数
│   └── weather.py             # 天气查询集成
├── search_journals/            # 搜索日志模块（双管道并行检索）
│   ├── __init__.py            # CLI入口
│   ├── __main__.py            # 模块执行入口
│   ├── core.py                # 搜索协调逻辑（Pipeline A/B + RRF）
│   ├── l1_index.py            # 一级索引搜索（by-topic）
│   ├── l2_metadata.py         # 二级元数据搜索（SQLite缓存）
│   ├── l3_content.py          # 三级内容搜索（FTS全文搜索）
│   ├── ranking.py             # RRF融合排序算法
│   ├── semantic.py            # 语义搜索（fastembed向量相似度）
│   └── utils.py               # 搜索工具函数
├── edit_journal/              # 编辑日志模块
│   ├── __init__.py            # CLI入口
│   └── __main__.py            # 模块执行入口
├── generate_abstract/         # 生成摘要模块
│   ├── __init__.py            # CLI入口
│   └── __main__.py            # 模块执行入口
├── build_index/               # 构建索引模块
│   ├── __init__.py            # CLI入口
│   └── __main__.py            # 模块执行入口
├── query_weather/             # 查询天气模块
│   ├── __init__.py            # CLI入口
│   └── __main__.py            # 模块执行入口
└── lib/                       # 共享库（SSOT）→ 详见 `tools/lib/AGENTS.md`
    ├── AGENTS.md              # 共享库开发指南（SSOT）
    ├── config.py              # 配置管理（路径、模板、默认值）
    ├── frontmatter.py         # YAML frontmatter解析/格式化（SSOT）
    ├── errors.py              # 错误码定义（SSOT）
    ├── file_lock.py           # 跨平台文件锁
    ├── metadata_cache.py      # SQLite元数据缓存（L2搜索）
    ├── search_index.py        # FTS5全文搜索索引
    ├── semantic_search.py     # 向量嵌入语义搜索（fastembed）
    ├── vector_index_simple.py # 纯Python向量索引（Fallback）
    ├── logger.py              # 日志记录工具
    └── timing.py              # 性能计时工具
```

---

## 代码风格指南

### Python 代码规范

**命名约定**:
- 函数/变量: `snake_case`
- 常量: `UPPER_SNAKE_CASE`
- 类: `PascalCase`

**类型注解**: 必须使用类型注解

**路径处理**: 统一使用 `pathlib.Path`

**编码**: 所有文件使用 UTF-8 编码

### JSON 输出格式

```json
{
  "success": true,
  "data": { ... },
  "error": "错误信息（如有）"
}
```

---

## 日志文件格式

### 目录结构

```
~/Documents/Life-Index/
├── Journals/                    # 日志主目录
│   └── YYYY/MM/                 # 按年月组织
├── by-topic/                    # 主题索引
└── attachments/                 # 附件存储
```

### Markdown 格式

```yaml
---
title: "日志标题"
date: 2026-03-07T14:30:00
location: "Lagos, Nigeria"
weather: "晴天 28°C"
mood: ["专注", "充实"]
tags: ["重构", "优化"]
topic: ["work", "create"]
abstract: "100字内摘要"
---

# 日志标题

正文内容...
```

### Topic 分类（必填）

| Topic | 含义 |
|-------|------|
| `work` | 工作/职业 |
| `learn` | 学习/成长 |
| `health` | 健康/身体 |
| `relation` | 关系/社交 |
| `think` | 思考/反思 |
| `create` | 创作/产出 |
| `life` | 生活/日常 |

---

## 关键约束

### 工具调用规则

**必须通过 Bash CLI 调用工具**：
```bash
# ✅ 正确
python -m tools.write_journal --data '{...}'

# ❌ 错误 - 直接调用脚本
python tools/write_journal.py --data '{...}'
```

### 内容保留原则

- 用户原始输入的 `content` 必须 100% 原样传递
- 禁止修改段落结构、Markdown 标题、列表格式

### 数据隔离

- 用户数据: `~/Documents/Life-Index/`
- 项目代码: 仓库目录
- 两者物理隔离，不可混淆

---

## 相关文档

| 文档 | 内容 | SSOT 声明 |
|------|------|-----------|
| `SKILL.md` | Agent 技能定义、触发词、工具接口、工作流 | Agent 调用入口 |
| `docs/ARCHITECTURE.md` | 架构设计、核心原则、关键决策 | ADR 决策记录 |
| `docs/PRODUCT_BOUNDARY.md` | 产品边界、三层模型、默认拒绝方向 | 产品边界决策备忘录 |
| `docs/EXECUTION_PRIORITIES.md` | v1.x 执行优先级、roadmap guardrails、当前主线顺序 | 执行优先级备忘录 |
| `docs/API.md` | 工具 API 接口文档 | **SSOT**: 参数、错误码、返回值 |
| `docs/CHANGELOG.md` | 决策变更历史 | 版本演进 |
| `tools/lib/AGENTS.md` | 共享库开发指南 | **SSOT**: `lib/` 模块约定 |
| `pyproject.toml` | 项目配置 | **SSOT**: 依赖、版本、入口点 |

---

## 设计底线

```
宁可功能简单，不可系统复杂
宁可人工维护，不可自动化陷阱
宁可牺牲性能，不可牺牲可靠性
```
