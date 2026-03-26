# AGENTS.md - Life Index 项目开发指南

> 本文档为 Life Index 项目开发、为 AI 编码代理提供项目上下文。  
> **最后更新**: 2026-03-25 | **版本**: v1.2 | **状态**: 活跃维护

## 项目概述

**Life Index** 是一个 Agent-first、local-first 的个人人生日志与检索系统。当前项目同时包含：

- **Layer A / Core**：CLI 原子工具（write / search / edit / abstract / weather / index / backup）
- **Layer C / Optional Shell**：可选本地 Web GUI（dashboard / search / write / journal / edit / settings）

用户既可以通过自然语言 + Agent 调用 Python 原子工具，也可以通过浏览器访问同一份本地数据。

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
life-index backup --dest "D:/Backups/Life-Index"
life-index index           # 增量更新
life-index serve           # 启动本地 Web GUI

# 开发者模式（无需安装）
python -m tools.write_journal --data '{...}'
python -m tools.search_journals --query "关键词"
```

---

## 模块结构

> **详细模块说明**: 参见 [`tools/lib/AGENTS.md`](tools/lib/AGENTS.md)

```
tools/                         # Core CLI/tool layer
├── write_journal/
├── search_journals/
├── edit_journal/
├── generate_abstract/
├── build_index/
├── query_weather/
├── backup/                    # 数据备份工具
├── dev/                       # 开发/验收辅助工具（含 run_with_temp_data_dir）
└── lib/                       # 共享库（SSOT）→ 详见 `tools/lib/AGENTS.md`

web/                           # Optional local Web GUI shell
├── routes/                    # dashboard/search/write/journal/edit/settings/api
├── services/                  # Web-only thin adapters over tools/
├── templates/                 # Jinja2 templates
├── static/                    # CSS / static assets
└── __main__.py                # `life-index serve` 入口
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

### 测试防污染规则（强制）

- **严禁**为了开发 / 测试目的，默认向真实用户数据目录 `~/Documents/Life-Index/` 写入临时日志、临时附件或其它测试污染物
- 自动化测试必须优先使用临时目录（如 `tmp_path`、`LIFE_INDEX_DATA_DIR` override、isolated fixture）
- 如果因人工验收 / E2E 调试 **不得不** 在真实用户数据目录下创建临时日志或附件，执行该操作的 Agent / 开发者必须在任务结束前：
  1. 明确记录创建了哪些文件
  2. 删除所有临时日志与临时附件
  3. 执行 `life-index index --rebuild` 刷新 metadata cache / search index
- **禁止**把测试样例、占位内容、坏附件引用、pytest 临时路径、"测试日志" 之类内容留在用户真实日志目录中
- 如无法确认某篇日志是否为真实用户记录，默认不得删除，必须先列清单并请求用户确认
- 进行手工 Web GUI 验收 / 调试时，优先使用隔离沙盒工具：`python -m tools.dev.run_with_temp_data_dir --for-web`（如需复制当前数据结构可加 `--seed`；此模式属于复制数据后的只读仿真验收，不会回写真实用户目录）

---

## 相关文档

| 文档 | 内容 | SSOT 声明 |
|------|------|-----------|
| `bootstrap-manifest.json` | Bootstrap authority / freshness manifest | **Authority anchor**: onboarding 必须先刷新并按其中 `required_authority_docs` 获取权威文档 |
| `SKILL.md` | Agent 技能定义、触发词、工具接口、工作流 | Agent 调用入口 |
| `docs/ARCHITECTURE.md` | 架构设计、核心原则、关键决策 | ADR 决策记录 |
| `docs/PRODUCT_BOUNDARY.md` | 产品边界、三层模型、执行优先级、默认拒绝方向 | 产品边界决策备忘录 |
| `docs/API.md` | 工具 API 接口文档 | **SSOT**: 参数、错误码、返回值 |
| `docs/CHANGELOG.md` | 决策变更历史 | 版本演进 |
| `tools/lib/AGENTS.md` | 共享库开发指南 | **SSOT**: `lib/` 模块约定 |
| `pyproject.toml` | 项目配置 | **SSOT**: 依赖、版本、入口点 |
| `docs/web-gui/README.md` | Web GUI 当前文档入口 | Web GUI 当前态索引 |

---

## 设计底线

```
宁可功能简单，不可系统复杂
宁可人工维护，不可自动化陷阱
宁可牺牲性能，不可牺牲可靠性
```
