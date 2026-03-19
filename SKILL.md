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

> **工具参数与错误码**: 详见 [API.md](docs/API.md)

---

## Triggers & When to Use

| 意图 | 触发词 | 工具 |
|:---:|:---|:---|
| 记录日志 | "记日志"、"记录一下"、"写日记"、"记下来"、"log this"、"record this"、"write journal" | `write_journal` |
| 搜索日志 | "查找日志"、"搜索记录"、"找一下关于...的日记"、"search journal"、"find log" | `search_journals` |
| 编辑日志 | "修改日志"、"补充日记"、"更新记录"、"edit journal"、"update log" | `edit_journal` |
| 生成摘要 | "生成摘要"、"月度总结"、"年度总结"、"generate summary" | `generate_abstract` |
| 定时报告 | 日报/周报/月报/年报 | 参考 [SCHEDULE.md](references/schedule/SCHEDULE.md) |

---

## Quick CLI Reference

**⚠️ 所有命令须在技能根目录（本文件所在目录）下执行。所有 Python/CLI 命令必须通过虚拟环境调用。**

**跨平台 venv 路径规则**：
- **Linux/macOS/WSL**: `.venv/bin/life-index` 或 `.venv/bin/python`
- **Windows**: `.venv\Scripts\life-index` 或 `.venv\Scripts\python`（首次排障/验证时优先显式使用此路径）

```bash
# 统一 CLI（推荐）
.venv/bin/life-index write --data '{"title":"...","content":"...","date":"2026-03-14","topic":["work"],"abstract":"...","mood":[],"people":[],"project":"","tags":[],"links":[]}'
.venv/bin/life-index search --query "关键词" --topic work --level 3
.venv/bin/life-index search --query "学习"  # 语义搜索默认启用
.venv/bin/life-index edit --journal "Journals/2026/03/life-index_2026-03-14_001.md" --set-location "Beijing"
.venv/bin/life-index abstract --month 2026-03
.venv/bin/life-index weather --location "Lagos,Nigeria"
.venv/bin/life-index index           # 增量更新
.venv/bin/life-index index --rebuild # 全量重建
.venv/bin/life-index health          # 安装健康检查

# Windows 首次写入更稳妥的方式
.venv\Scripts\life-index write --data @first-entry.json

# 开发者模式
.venv/bin/python -m tools.write_journal --data '{...}'
.venv/bin/python -m tools.search_journals --query "关键词"
.venv/bin/python -m tools.edit_journal --journal "..."
.venv/bin/python -m tools.generate_abstract --month 2026-03
.venv/bin/python -m tools.query_weather --location "Lagos,Nigeria"
.venv/bin/python -m tools.build_index
```

**故障恢复**: 如果命令报 `ModuleNotFoundError` 或 venv 异常，运行 `.venv/bin/life-index health` 诊断。若 health 命令本身失败，说明 venv 损坏，删除 `.venv/` 后重新创建：`python3 -m venv .venv && .venv/bin/pip install -e .`

**Fresh install 提示**:
- 如果在首次执行 `.venv/bin/life-index index` 之前先运行 `health`，看到 `status: "degraded"` 且数据目录/索引不存在，这是正常现象
- 完成 `index` 初始化后再次运行 `health`，预期应恢复为健康状态
- Windows 首次 `write --data '{...}'` 如遇 JSON 转义麻烦，优先使用 `--data @file.json`

---

## Project Structure

```
life-index/                         # 技能根目录
├── SKILL.md                       # [本文件] 技能定义
├── tools/                         # 可执行工具目录
│   ├── write_journal/             # 写入日志（天气查询、附件处理、索引更新）
│   ├── search_journals/           # 搜索日志（L1/L2/L3 + 语义搜索）
│   ├── edit_journal/              # 编辑日志（修改元数据、追加内容）
│   ├── generate_abstract/         # 生成摘要（月报/年报）
│   ├── build_index/               # 构建索引（FTS5 + 向量索引）
│   ├── query_weather/             # 查询天气
│   └── lib/                       # 共享库（SSOT）
├── docs/                          # API.md, ARCHITECTURE.md, CHANGELOG.md
└── references/                    # WEATHER_FLOW.md, SCHEDULE.md
```

**关键约定**：
- **虚拟环境**: 所有命令通过 `.venv/bin/`（Windows: `.venv\Scripts\`）前缀调用
- **用户数据目录**: `~/Documents/Life-Index/`（日志、附件、索引，与代码物理隔离）
- **跨平台路径**: 自动处理（Agent 传原始路径即可，工具自动转换 Windows↔WSL）
- **健康检查**: 遇到异常时先运行 `.venv/bin/life-index health` 诊断

---

## Core Constraints

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
- **数据隔离**：数据在 `~/Documents/Life-Index/`，与代码分离
- **天气处理**：详见 [WEATHER_FLOW.md](references/WEATHER_FLOW.md)

```markdown
❌ 不要：假设用户知道内部概念（如"by-topic索引"）
✅ 必须：用人话说明（如"已归类到工作相关"）

❌ 不要：一次问多个问题
✅ 必须："地点和天气是否正确？"（单次确认）
```

### 天气与地点确认（强制）

**⚠️ 最常见错误点：看到 `success: true` 就直接结束对话**

调用 `write_journal` 后，检查返回的 `needs_confirmation` 字段：
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

```
❌ 错误：工具返回 success: true → Agent 直接结束："日志已保存"

✅ 正确：工具返回 needs_confirmation: true
→ Agent：日志已保存。地点：Lagos, Nigeria；天气：晴天 33°C。是否正确？
→ 等待用户回复
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
| topic | array | ✅ | 主题分类（见下方 Topic 表） |
| mood | array | ✅ | 心情标签，Agent语义提取1~3个（如["开心","专注"]） |
| tags | array | ✅ | 标签，Agent语义提取关键词（可多个） |
| location | string | ❌ | 地点；用户未指定时默认 "Chongqing, China"，写入后必须走地点/天气确认 |
| weather | string | ❌ | 天气，根据确认的地点自动查询 |
| people | array | ❌ | 相关人物，Agent语义提取，没有则留空 |
| project | string | ❌ | 关联项目，Agent语义提取，没有则留空 |
| links | array | ❌ | 相关链接 |
| attachments | array | ❌ | 附件（自动检测 content 中的本地文件路径；也可显式传递 `{"source_path":"...","description":"..."}` 对象） |

### Topic 分类（必填）

| Topic | 含义 | 示例场景 |
|-------|------|----------|
| `work` | 工作/职业 | 项目进展、会议、职业发展 |
| `learn` | 学习/成长 | 读书笔记、课程学习、技能提升 |
| `health` | 健康/身体 | 运动、饮食、体检、医疗 |
| `relation` | 关系/社交 | 家人、朋友、社交活动 |
| `think` | 思考/反思 | 人生感悟、决策思考、复盘 |
| `create` | 创作/产出 | 文章、代码、设计作品 |
| `life` | 生活/日常 | 日常琐事、娱乐、购物 |

### Agent 职责

1. **必填字段**：title, content, date, abstract, topic, mood, tags — 必须有值
2. **语义提取**：从用户内容中主动提取 mood（1~3个）、tags（关键词）、people、project
3. **地点默认规则**：用户未提及地点时，工具默认使用 "Chongqing, China"；写入成功后 Agent 必须展示确认信息并等待用户确认或修正
4. **空值处理**：people, project, links 未提取到时传空值（如 `"people": []`）
5. **摘要生成**：从 content 提取关键信息，生成 ≤100 字的 abstract
6. **必须确认**：工具返回后检查 `needs_confirmation`，为 `true` 时展示并询问用户

---

## Workflows

### 意图澄清（强制）

当用户请求可能被解读为多种操作时，**必须先澄清再调用工具**：

| 歧义类型 | 示例 | 正确处理 |
|:---|:---|:---|
| 写入 vs 编辑 | "把今天晚饭记进去，或者如果有了就补进去" | 先询问：是新建日志还是修改已有日志？ |
| 编辑目标不明确 | "把那篇写深圳的日志改一下" | 先搜索确认目标，再执行编辑 |
| 修改范围不清 | "更新一下昨天的日志" | 先确认要修改哪些字段 |

❌ 错误：猜测用户意图，直接调用工具
✅ 正确：明确意图后再调用工具

### 工作流1: 记录日志

| 步骤 | 动作 | 关键检查点 | 常见错误 |
|:---:|:---|:---|:---|
| 1 | **解析意图** | 提取 title, content, date, topic | 遗漏 topic |
| 2 | **提取元数据** | 识别 mood(1-3个)、tags、people、project | mood 为空数组 |
| 3 | **生成摘要** | abstract ≤100字 | 摘要过长 |
| 4 | **调用工具** | `write_journal` 包含所有字段；location 缺失时允许工具使用默认 Chongqing, China | 误以为必须写前补问地点 |
| 5 | **检查确认** | `needs_confirmation` 为 true？ | ⚠️ **最常见错误：直接跳过** |
| 6 | **展示确认** | 展示 `confirmation_message` | 不展示直接结束 |
| 7 | **等待回复** | 询问用户"是否正确？" | 不询问 |

### 安装后的可选个性化（Agent-first）

安装与首次验证完成后，Agent 可按 `AGENT_ONBOARDING.md` 的 optional customization step 询问用户是否要做两项个性化设置：

1. **专用触发词**：采用 `"/life-index" + "用户自定义触发词"` 的组合；如用户同意，Agent 可修改本文件中的 trigger 列表与对应示例
2. **默认地址偏好**：如用户同意，Agent 可创建或更新 `~/Documents/Life-Index/.life-index/config.yaml` 中的 `defaults.location`

约束：
- 不得移除 `/life-index`
- 不得重写与触发词无关的 workflow 段落
- 默认地址配置必须诚实区分“已保存”与“已验证生效”

**写入结果解读**：

`write_journal` 返回以下状态字段，Agent必须正确解读：

| 字段 | 值 | 含义 | Agent行为 |
|:---|:---:|:---|:---|
| `success` | true/false | 日志是否成功写入 | false → 告知用户写入失败 |
| `needs_confirmation` | true/false | 是否需要用户确认地点/天气 | true → 展示确认信息，等待用户回复 |
| `index_status` | complete/degraded/not_started | 索引更新状态 | degraded → 告知用户"已保存，但搜索可能暂时找不到" |
| `side_effects_status` | complete/degraded/not_started | 附件/摘要等副作用状态 | degraded → 告知用户"已保存，但部分信息未更新" |
| `weather_auto_filled` | true/false | 天气是否自动填充 | true → 在确认信息中标注"自动获取" |

**降级状态处理示例**：
```
success: true, index_status: degraded
→ "日志已保存，但索引更新遇到问题，新日志可能暂时无法被搜索到。"
```

### 工作流2: 检索日志

**双管道并行检索架构**:

```
            用户查询
         ┌────┴────┐
  ┌──────▼──────┐  ┌──────▼──────┐
  │ Pipeline A  │  │ Pipeline B  │
  │  关键词管道  │  │  语义管道   │
  │             │  │             │
  │ L1 索引过滤  │  │ 向量相似度   │
  │ L2 元数据过滤│  │ (多语言嵌入) │
  │ L3 FTS5 匹配 │  │             │
  └──────┬──────┘  └──────┬──────┘
         └────┬────┘
    RRF 融合排序 (k=60)
            │
        最终结果
```

**查询意图 → 参数映射**:

| 用户意图 | 推荐参数 |
|:---|:---|
| "关于工作的日志" | `--topic work` |
| "去年的记录" | `--date-from 2025-01-01 --date-to 2025-12-31` |
| "跟团团有关的" | `--people 团团` |
| "关于重构的" | `--query "重构"` |
| "开心的回忆" | `--mood 开心` |
| "LifeIndex项目" | `--project LifeIndex` |
| 精确关键词匹配 | `--query "关键词" --no-semantic` |

**步骤**:
1. **解析查询意图**：从用户表述中识别过滤条件
2. **执行搜索**：`search_journals`（双管道自动启用）
3. **呈现结果**：展示日志列表（按 RRF 分数排序）

### 工作流3: 编辑日志

1. **定位日志**：根据日期或标题找到目标文件
2. **确认修改**：展示当前内容，明确修改范围
3. **执行编辑**：`edit_journal`
4. **如修改地点**：需先调用 `query_weather` 获取新天气，再同时更新 location 和 weather

### 工作流4: 生成摘要

1. **确定类型**：月度摘要（`--month YYYY-MM`）或年度摘要（`--year YYYY`）
2. **执行生成**：`generate_abstract`
3. **返回结果**：告知文件路径和统计信息

### 工作流5: 索引维护

| 场景 | 操作 |
|:---|:---|
| 日常写入 | 无需手动维护（Write-Through 自动更新） |
| 搜索结果异常/缺失 | `.venv/bin/life-index index --rebuild` 全量重建 |
| 首次安装 | `.venv/bin/life-index index` 初始化索引 |
| 手动编辑过日志文件 | `.venv/bin/life-index index` 增量更新 |

---

## Related Documentation

| 文档 | 用途 |
|------|------|
| [API.md](docs/API.md) | 工具 API 接口、参数详情、错误码与恢复策略 |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | 架构设计、核心原则、关键决策 |
| [SCHEDULE.md](references/schedule/SCHEDULE.md) | 定时任务配置（日报/周报/月报） |
| [WEATHER_FLOW.md](references/WEATHER_FLOW.md) | 天气处理详细流程与故障 Fallback |

---

## Examples

**记录工作日志**：
```
用户：记录一下今天完成了搜索功能优化

Agent：
1. 解析：title="搜索功能优化", topic=["work"], abstract="完成搜索功能优化工作"
2. 提取：mood=["专注"], tags=["搜索", "优化"], people=[], project=""
3. 调用 write_journal（自动填充地点="Chongqing, China"、查询天气）
4. 检查 needs_confirmation=true
5. 展示：日志已保存。地点：Chongqing, China；天气：Sunny。是否正确？
```

**搜索历史**：
```
用户：查找去年关于重构的日志

Agent：
调用：search_journals --query "重构" --date-from 2025-01-01 --date-to 2025-12-31
返回：找到 5 篇相关日志
```
