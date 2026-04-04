# AGENTS.md - Life Index 项目开发指南

> 本文档为 Life Index 项目开发、为 AI 编码代理提供项目上下文。
> **最后更新**: 2026-03-31 | **版本**: v2.0 | **状态**: 活跃维护

## 项目概述

**Life Index** 是一个 Agent-Native、local-first 的个人人生日志与检索系统。

- **CLI 原子工具**：write / search / edit / abstract / weather / index / backup
- 用户通过自然语言 + Agent 调用 Python CLI 工具

**核心理念**:
- **Agent-Native**：CLI 是 Agent 的母语。发挥 Agent 自然语言理解能力，仅在需要原子性/准确性时开发专用工具
- **本地优先**：所有数据存储在 `~/Documents/Life-Index/`
- **纯文本格式**：Markdown + YAML Frontmatter，永不过时

**关键架构决策**:
- **双管道并行检索架构**：关键词管道 ∥ 语义管道并行执行 + RRF 融合
- **数据物理隔离**：用户数据在 `~/Documents/Life-Index/`，项目代码在仓库目录
- **CLI 为 SSOT**：所有写入/读取操作通过 CLI（详见 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)）

---

## 文档导航

> **重要**：`docs/archive/` 目录包含历史开发文档，仅供考古参考。除非用户明确要求，Agent 不应阅读该目录内的文件，以避免浪费上下文和 token。

| 文档 | 内容 | 说明 |
|------|------|------|
| `SKILL.md` | Agent 技能定义、触发词、工具接口 | Agent 调用入口 |
| `AGENT_ONBOARDING.md` | 安装与初始化指南 | 面向 Agent 的安装流程 |
| `docs/ARCHITECTURE.md` | 架构设计、核心原则 | 技术 SSOT |
| `docs/API.md` | 工具 API 接口文档 | 参数、错误码、返回值 SSOT |
| `tools/lib/AGENTS.md` | 共享库开发指南 | `lib/` 模块约定 |
| `pyproject.toml` | 项目配置 | 依赖、版本、入口点 |
| `bootstrap-manifest.json` | Bootstrap authority | Onboarding 必须先刷新此文件 |
| `references/schedule/SCHEDULE.md` | 定时任务规范 | Agent cron 任务指南 |
| `docs/archive/` | 历史文档 | **不要主动阅读** |

---

## 构建与运行命令

### 依赖安装

```bash
# Python 3.11+ (核心运行环境)
pip install -e .  # 已包含语义搜索依赖（sentence-transformers）
```

### 核心工具命令

```bash
life-index write --data '{"title":"...","content":"...","date":"2026-03-07","topic":"work"}'
life-index search --query "关键词" --level 3
life-index edit --journal "Journals/2026/03/life-index_2026-03-07_001.md" --set-weather "晴天"
life-index abstract --month 2026-03
life-index weather --location "Lagos,Nigeria"
life-index backup --dest "D:/Backups/Life-Index"
life-index index           # 增量更新
life-index index --rebuild # 全量重建
life-index health          # 安装健康检查

# 开发者模式（无需安装）
python -m tools.write_journal --data '{...}'
python -m tools.search_journals --query "关键词"
```

---

## 模块结构

```
tools/                         # Core CLI/tool layer
├── write_journal/
├── search_journals/
├── edit_journal/
├── generate_abstract/
├── build_index/
├── query_weather/
├── backup/
├── dev/                       # 开发/验收辅助工具
└── lib/                       # 共享库（SSOT）→ 详见 tools/lib/AGENTS.md
```

---

## 代码风格指南

**命名约定**: 函数/变量 `snake_case` | 常量 `UPPER_SNAKE_CASE` | 类 `PascalCase`

**类型注解**: 必须使用

**路径处理**: 统一使用 `pathlib.Path`

**编码**: UTF-8

**JSON 输出格式**:
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

### 测试防污染规则（强制）

- **严禁**向真实用户数据目录写入测试数据
- 自动化测试必须使用临时目录（`tmp_path`、`LIFE_INDEX_DATA_DIR` override）
- 如因调试不得不在真实目录创建临时文件，任务结束前必须清理并 `life-index index --rebuild`
- 手工验收优先使用隔离沙盒：`python -m tools.dev.run_with_temp_data_dir`

---

## 开发部署：快速同步到实机

> **适用场景**：开发环境验证后，快速同步到本地 OpenClaw 实机测试环境。
> **目标路径**：`Z:\home\dexter\.openclaw\workspace\skills\life-index`（WSL）

### 部署流程

```bash
# 1. 进入部署目录（WSL）
cd /home/dexter/.openclaw/workspace/skills/life-index

# 2. Git 同步
git fetch origin && git reset --hard origin/main

# 3. 刷新虚拟环境（仅当 pyproject.toml 变更时）
.venv/bin/pip install -e .

# 4. 验证
.venv/bin/life-index health
```

### 保护规则

1. **不删除 `.venv/`**
2. **不触碰用户数据** — `~/Documents/Life-Index/` 物理隔离
3. **优先使用 git 同步**

---

## 设计底线

```
宁可功能简单，不可系统复杂
宁可人工维护，不可自动化陷阱
宁可牺牲性能，不可牺牲可靠性
```
