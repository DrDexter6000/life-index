---
name: life-index
description: "Personal life journaling system with dual-dimension indexing. Use when user says 'record journal', 'log this', 'search logs', 'generate summary', '记日志', '写日记', '搜索记录', '生成摘要'. Features: auto weather, semantic search, attachment handling."
user-invocable: true
disable-model-invocation: false
metadata: {"clawdbot":{"emoji":"📖","requires":{"bins":["python"]}}}
triggers:
  - "/life-index"
  - "记日志"
  - "写日记"
  - "记录一下"
  - "write journal"
  - "daily log"
  - "log this"
  - "record this"
---

# Life Index Agent Skill

> **完整工作流**: 详见 [INSTRUCTIONS.md](docs/INSTRUCTIONS.md) ｜ **工具参数与错误码**: 详见 [API.md](docs/API.md)

---

## Triggers

| 意图 | 触发词（中英文） |
|:---:|:---|
| 记录日志 | "记日志"、"记录一下"、"写日记"、"记下来"、"log this"、"record this"、"write journal"、"daily log" |
| 搜索日志 | "查找日志"、"搜索记录"、"找一下关于...的日记"、"search journal"、"find log" |
| 编辑日志 | "修改日志"、"补充日记"、"更新记录"、"edit journal"、"update log" |
| 生成摘要 | "生成摘要"、"月度总结"、"年度总结"、"generate summary"、"monthly report" |
| 生成日报 | "生成日报"、"今日总结"、"daily report" |
| 生成周报 | "生成周报"、"本周总结"、"weekly report" |
| 生成年报 | "生成年报"、"年度回顾"、"yearly report" |

---

## When to Use

1. **记录日志**：用户说"记录一下今天..."、"记日志..."、"log this..." → `write_journal`
2. **搜索日志**：用户说"查找关于...的日志"、"去年春天的记录"、"search for..." → `search_journals`
3. **编辑日志**：用户说"修改昨天的日志"、"补充一下那篇日记"、"edit..." → `edit_journal`
4. **生成摘要**：用户说"生成月度摘要"、"查看年度总结"、"generate summary..." → `generate_abstract`
5. **定时报告**：日报/周报/月报/年报 → 参考 [SCHEDULE.md](references/schedule/SCHEDULE.md)

---

## Quick CLI Reference

**⚠️ 执行前确保**：已在技能根目录（包含 `SKILL.md` 和 `tools/` 的目录）

```bash
# 记录日志（所有元数据字段必填，即使为空）
python -m tools.write_journal --data '{"title":"...","content":"...","date":"2026-03-14","topic":["work"],"abstract":"...","mood":[],"people":[],"project":"","tags":[],"links":[]}'

# 搜索日志
python -m tools.search_journals --query "关键词" --topic work --level 3
python -m tools.search_journals --query "学习" --semantic  # 语义搜索

# 编辑日志
python -m tools.edit_journal --journal "Journals/2026/03/life-index_2026-03-14_001.md" --set-location "Beijing"

# 生成摘要
python -m tools.generate_abstract --month 2026-03
python -m tools.generate_abstract --year 2026

# 查询天气
python -m tools.query_weather --location "Lagos,Nigeria"

# 构建索引
python -m tools.build_index           # 增量更新
python -m tools.build_index --rebuild # 全量重建
```

**不在技能根目录？** 参见下方 [Tool Invocation（工具调用）](#tool-invocation工具调用) 的多种方案。

---

## Project Structure（项目结构）

Life Index 采用模块化目录设计，所有工具位于 `tools/` 目录下：

```
life-index/                         # 技能根目录（目录名固定为 life-index/）
├── SKILL.md                       # [本文件] 技能定义、触发词、使用指南
├── pyproject.toml                 # Python 项目配置（依赖、入口点、工具链）
├── README.md                      # 项目介绍和快速开始
├── LICENSE                        # Apache-2.0 许可证
├── config.example.yaml            # 用户配置示例（需复制到数据目录）
│
├── tools/                         # [核心] 可执行工具目录
│   ├── write_journal/             # 写入日志工具
│   │   ├── __init__.py           # CLI 入口
│   │   ├── __main__.py           # python -m 执行入口
│   │   └── core.py               # 核心逻辑（天气查询、附件处理、索引更新）
│   │
│   ├── search_journals/           # 搜索日志工具（L1/L2/L3/语义搜索）
│   ├── edit_journal/              # 编辑日志工具（修改元数据、追加内容）
│   ├── generate_abstract/         # 生成摘要工具（月报/年报）
│   ├── build_index/               # 构建索引工具（FTS5 + 向量索引）
│   ├── query_weather/             # 查询天气工具
│   │
│   └── lib/                       # [共享库] 所有工具依赖的基础模块
│       ├── config.py             # 配置管理（数据目录、路径映射、模板）
│       ├── frontmatter.py        # YAML frontmatter 解析/格式化（SSOT）
│       ├── errors.py             # 错误码定义和恢复策略
│       ├── file_lock.py          # 文件锁（并发控制）
│       ├── metadata_cache.py     # SQLite 元数据缓存（L2搜索优化）
│       └── search_index.py       # FTS5 全文搜索索引
│
├── docs/                          # 文档目录（供 Agent 和人类阅读）
│   ├── INSTRUCTIONS.md           # [Agent必读] 详细工作流、工具参数、执行步骤
│   ├── API.md                    # 工具 API 详细文档
│   ├── HANDBOOK.md               # 架构设计、核心理念、决策记录
│   └── CHANGELOG.md              # 版本变更历史
│
├── references/                    # 参考文档
│   ├── WEATHER_FLOW.md           # 天气处理三层机制详解
│   ├── （错误码见 docs/API.md#错误码列表）
│   └── schedule/                 # 定时任务配置（日报/周报/月报）
│       └── SCHEDULE.md
│
├── tests/                         # 测试目录
│   ├── e2e/                      # 端到端测试（YAML 格式）
│   │   ├── phase1-core-workflow.yaml
│   │   ├── phase2-search-retrieval.yaml
│   │   └── phase3-edge-cases.yaml
│   └── unit/                     # 单元测试
│
└── AGENTS.md                      # [开发者文档] 代码库导航、模块职责、约定
```

**关键约定**：
- **技能代码目录**: `life-index/`（包含 tools/, docs/, 本文件 SKILL.md）
- **工具目录**: `life-index/tools/`（所有可执行模块）
- **用户数据目录**: `~/Documents/Life-Index/`（日志、附件、索引，与代码分离）
- **SSOT**: `tools/lib/` 是共享库的唯一事实来源，所有工具必须从中导入

## Core Constraints

### Tool Invocation（工具调用）

**前置要求**：执行工具前，必须先进入技能根目录（包含 `SKILL.md` 和 `tools/` 的目录）

**两种导航方式均可定位 tools/ 目录**：

**方式一：通过目录名 `life-index/` 定位**
```bash
cd ~/.claude/skills/life-index              # Claude Desktop
cd ~/.openclaw/workspace/skills/life-index  # OpenClaw
cd ~/.config/opencode/skills/life-index     # OpenCode
cd ~/.agents/skills/life-index              # 其他 Agent

python -m tools.write_journal --data '{...}'
```

**方式二：通过本文件 `SKILL.md` 定位**
```bash
# 找到本文件(SKILL.md)所在的目录，即为技能根目录
cd {skill_root}     # skill_root = 包含 SKILL.md 的目录

python -m tools.write_journal --data '{...}'
```

**禁止**：在其他目录执行、使用绝对路径调用脚本、直接 import 工具函数

### Cross-Platform Path Handling（跨平台路径）

如果 Life Index 运行在 WSL/Linux，而附件在 Windows 盘符：

在 `~/Documents/Life-Index/config.yaml` 中配置路径映射：
```yaml
path_mappings:
  "C:\\Users\\{username}": "/mnt/c/Users/{username}"
  "/mnt/c/Users/{username}": "C:\\Users\\{username}"
```

### Content Preservation (MUST)

**100% 保留用户原始输入**：
- 不修改段落结构
- 不改变标题层级
- 不转换列表格式
- 不添加序号标记
- **⚠️ 不修改文件名（不在中英文间添加空格）**

```markdown
# ❌ 错误
用户输入："1、完成A 2、完成B"
Agent 改成："1. 完成A\n2. 完成B"

# ❌ 错误（文件名被修改）
用户附件："C:\Users\test\Opus审计报告.txt"
Agent 改成："C:\Users\test\Opus 审计报告.txt"  ← 添加了空格

# ✅ 正确
用户输入什么，content 和附件路径就原封不动传递什么
```

### Guardrails

- **永不删除文件**：编辑只修改内容
- **数据隔离**：数据在 `~/Documents/Life-Index/`
- **天气处理**：详见 [WEATHER_FLOW.md](references/WEATHER_FLOW.md)
- **强制确认机制**：`write_journal` 返回后，**必须**检查并处理 `needs_confirmation` 字段（见下方"天气与地点确认"）

### 天气与地点确认（强制）

**⚠️ 这是常见错误点，必须遵守：**

调用 `write_journal` 后，工具会返回如下 JSON：
```json
{
  "success": true,
  "data": {
    "journal_path": "...",
    "needs_confirmation": true,
    "confirmation_message": "地点：Lagos, Nigeria；天气：晴天 33°C"
  }
}
```

**Agent 必须执行：**
1. **检查 `needs_confirmation`**：如果为 `true`，说明使用了默认地点或自动查询的天气
2. **展示确认信息**：向用户展示 `confirmation_message` 的内容
3. **询问确认**：明确询问用户"地点和天气是否正确？"
4. **等待用户回复**：不要假设正确，必须等待用户确认

**错误示例**（不要这样做）：
```
工具返回 success: true
→ Agent 直接结束对话："日志已保存"
❌ 错误：跳过了用户确认
```

**正确示例**：
```
工具返回 success: true, needs_confirmation: true
→ Agent：日志已保存。地点：Lagos, Nigeria；天气：晴天 33°C。是否正确？
→ 等待用户回复
✅ 正确：用户有机会纠正错误的地点/天气
```

---

## Required Metadata Fields

写入日志时，必须包含所有元数据字段（即使为空值）：

| 字段 | 类型 | 必填 | 说明 |
|------|------|:----:|------|
| title | string | ✅ | 日志标题 |
| content | string | ✅ | 日志正文（100%原样保留） |
| date | string | ✅ | ISO 8601 日期时间 |
| abstract | string | ✅ | ≤100字摘要（Agent生成） |
| topic | array | ✅ | 主题分类，必填（如["work"]） |
| mood | array | ✅ | 心情标签，必填，Agent语义提取1~3个（如["开心","专注"]） |
| tags | array | ✅ | 标签，必填，Agent语义提取关键词（可多个） |
| location | string | ❌ | 地点，默认"Chongqing, China"，Agent询问后可更改 |
| weather | string | ❌ | 天气，根据确认的地点自动查询 |
| people | array | ❌ | 相关人物，Agent语义提取，没有则留空 |
| project | string | ❌ | 关联项目，Agent语义提取，没有则留空 |
| links | array | ❌ | 相关链接 |
| attachments | array | ❌ | 附件路径（自动检测） |

**Agent 职责**：
1. **必填字段**：title, content, date, abstract, topic, mood, tags — 必须有值
2. **语义提取**：从用户内容中主动提取 mood（1~3个）、tags（关键词）、people、project
3. **默认值**：location 默认 "Chongqing, China"，Agent可主动询问用户确认更改
4. **空值处理**：people, project, links 未提取到时传空值（如 `"people": []`）
5. **摘要生成**：从 content 提取关键信息，生成 ≤100 字的 abstract
6. **必须确认地点和天气**：工具返回后，**必须**检查 `needs_confirmation` 字段，如果为 `true`，**必须**展示 `confirmation_message` 并询问用户确认

---

## Output Format

```json
{
  "success": true|false,
  "data": { ... },
  "error": { "code": "E0000", "message": "...", "recovery_strategy": "..." }
}
```

错误码详见 [API.md](docs/API.md#错误码列表)。

---

## ⚠️ Core Execution Checklist（执行检查清单）

> **关键步骤速查**：记录日志时必须按此顺序执行，跳过任何一步都可能导致错误。

### 记录日志标准流程

```
用户输入 → 步骤1 → 步骤2 → 步骤3 → 步骤4 → 完成
```

| 步骤 | 动作 | 关键检查点 | 常见错误 |
|:---:|:---|:---|:---|
| 1 | **解析意图** | 提取 title, content, date, topic | 遗漏 topic |
| 2 | **提取元数据** | 识别 mood(1-3个)、tags、people、project | mood 为空数组 |
| 3 | **生成摘要** | abstract ≤100字 | 摘要过长 |
| 4 | **调用工具** | `write_journal` 包含所有字段 | 缺少必填字段 |
| 5 | **检查确认** | `needs_confirmation` 为 true？ | ⚠️ **最常见错误：直接跳过** |
| 6 | **展示确认** | 展示 `confirmation_message` | 不展示直接结束 |
| 7 | **等待回复** | 询问用户"是否正确？" | 不询问 |

### 关键禁止事项

```markdown
❌ 不要：看到 success: true 就直接结束对话
✅ 必须：检查 needs_confirmation，如果为 true 必须询问确认

❌ 不要：一次问多个问题
✅ 必须："地点和天气是否正确？"（单次确认）

❌ 不要：假设用户知道内部概念（如"by-topic索引"）
✅ 必须：用人话说明（如"已归类到工作相关"）
```

### 快速故障排查

| 问题 | 原因 | 解决 |
|:---|:---|:---|
| 日志保存了但没确认地点 | 跳过步骤5 | 检查 needs_confirmation 字段 |
| 缺少 mood/tags | 步骤2未执行 | 从内容提取情绪词和关键词 |
| 附件未复制 | 路径格式错误 | 确保是完整路径（如 `C:\Users\...\file.txt`）|
| 天气查询失败 | API问题 | 使用网络搜索 Fallback |

---

## Related Documentation

| 文档 | 用途 |
|------|------|
| **[INSTRUCTIONS.md](docs/INSTRUCTIONS.md)** | 完整工作流步骤（执行顺序与策略） |
| [HANDBOOK.md](docs/HANDBOOK.md) | 项目愿景、架构设计、核心原则 |
| [API.md](docs/API.md) | 工具 API 接口详细文档 |
| [SCHEDULE.md](references/schedule/SCHEDULE.md) | 定时任务配置（日报/周报/月报） |
| [WEATHER_FLOW.md](references/WEATHER_FLOW.md) | 天气处理详细流程 |
| [API.md#错误码列表](docs/API.md#错误码列表) | 错误码定义 |

---

## Examples

**记录工作日志**：
```
用户：记录一下今天完成了搜索功能优化

Agent：
1. 解析：title="搜索功能优化", topic=["work"], abstract="完成搜索功能优化工作"
2. 调用 write_journal（自动填充地点="Chongqing, China"、查询天气）
3. 检查 needs_confirmation=true
4. 展示：日志已保存。地点：Chongqing, China；天气：Sunny。是否正确？
```

**搜索历史**：
```
用户：查找去年关于重构的日志

Agent：
调用：search_journals --query "重构" --date-from 2025-01-01 --date-to 2025-12-31
返回：找到 5 篇相关日志
```

**完整工作流（详细步骤）**: 详见 [INSTRUCTIONS.md](docs/INSTRUCTIONS.md#核心工作流)
