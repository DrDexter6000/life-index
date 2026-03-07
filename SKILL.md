---
name: life-index
description: "个人日志管理系统 - 记录、检索、回顾生活点滴。当用户需要记录日记、搜索历史日志、查看月度/年度摘要时使用。"
---

# Life Index Skill

> 个人日志管理系统
> 版本: 0.1.0
> 触发时机: 用户表达记录/搜索日志意图时

---

## 前置检查

**执行任何操作前，确认以下事项：**

1. **当前任务**是否与 Life Index 直接相关？
   - ✅ 正确：记录/搜索用户日志、维护索引、生成摘要
   - ❌ 错误：优化 Agent 自身记忆系统、配置平台级功能

2. **如发现不匹配**：立即停止操作，向用户说明情况，请求澄清。

---

## When to Use

### 记录日志意图

**触发条件**（满足任一）：
- 关键词: "/log"、"记一下"、"记录一下"、"写日记"
- 语义模式: "今天..."、"刚才..."、"我觉得..."、"我发现..."
- 任何带有回顾、反思、事件描述的陈述

### 搜索日志意图

**触发条件**（满足任一）：
- 关键词: "搜索..."、"查找..."、"帮我找..."
- 语义模式: "之前写的..."、"回顾一下..."、"关于...的日志"

### 编辑日志意图

**触发条件**：
- 关键词: "修改..."、"补充..."、"更新昨天的日志"

### 生成摘要意图

**触发条件**：
- 关键词: "月度摘要"、"年度总结"、"生成摘要"

---

## 定时任务

Life Index 支持定时生成日报、周报、月报、年报，以及向量索引自动维护。

详见：[docs/SCHEDULE.md](docs/SCHEDULE.md)

---

## 分类体系

### Topic（必填，预定义7类）

| Topic | 含义 | 示例场景 |
|-------|------|---------|
| `work` | 工作/职业 | 项目开发、会议、任务完成 |
| `learn` | 学习/成长 | 读书笔记、课程学习、技能提升 |
| `health` | 健康/身体 | 运动、体检、疾病记录 |
| `relation` | 关系/社交 | 家人互动、朋友聚会 |
| `think` | 思考/反思 | 人生感悟、决策分析 |
| `create` | 创作/产出 | 写文章、设计稿、作品 |
| `life` | 生活/日常 | 购物、娱乐、日常琐事 |

### Project（选填）

动态项目名称，驼峰命名，如 `Life-Index`、`WebGame`。

### Tags（选填）

自由标签，如 `#重构`、`#会议`、`#灵感`。

---

## Required Inputs

### write-journal

| 字段 | 必填 | 说明 |
|------|------|------|
| `title` | ✅ | 日志标题（≤20字） |
| `content` | ✅ | 日志正文内容 |
| `date` | ✅ | 日期（YYYY-MM-DD，默认当天） |
| `topic` | ✅ | 主题分类（预定义7类） |
| `location` | ❌ | 地点（如 "Lagos, Nigeria"） |
| `weather` | ❌ | 天气描述 |
| `mood` | ❌ | 心情标签数组（如 ["专注", "充实"]） |
| `people` | ❌ | 相关人物数组 |
| `project` | ❌ | 关联项目 |
| `tags` | ❌ | 标签数组 |
| `abstract` | ❌ | 100字内摘要（可自动生成） |
| `attachments` | ❌ | 附件列表，每项包含 source_path 和 description |

### search-journals

| 字段 | 必填 | 说明 |
|------|------|------|
| `query` | ❌ | 搜索关键词 |
| `topic` | ❌ | 按主题过滤 |
| `project` | ❌ | 按项目过滤 |
| `tags` | ❌ | 按标签过滤（逗号分隔） |
| `date_from` | ❌ | 起始日期 (YYYY-MM-DD) |
| `date_to` | ❌ | 结束日期 (YYYY-MM-DD) |
| `level` | ❌ | 搜索层级: 1=索引, 2=元数据, 3=全文（默认3） |
| `semantic` | ❌ | 是否启用语义搜索（默认 false） |

### edit-journal

| 字段 | 必填 | 说明 |
|------|------|------|
| `journal_path` | ✅ | 日志文件路径 |
| `updates` | ❌ | 要更新的 frontmatter 字段 |
| `append_content` | ❌ | 追加到正文的内容 |

### query-weather

| 字段 | 必填 | 说明 |
|------|------|------|
| `location` | ❌ | 地点名称（如 "Lagos"） |
| `lat` | ❌ | 纬度 |
| `lon` | ❌ | 经度 |
| `date` | ❌ | 日期 (YYYY-MM-DD，默认当天) |

### generate-abstract

| 字段 | 必填 | 说明 |
|------|------|------|
| `month` | ❌ | 生成月度摘要，格式 YYYY-MM（如 "2026-03"） |
| `year` | ❌ | 生成年度摘要，格式 YYYY（如 2026） |
| `all-months` | ❌ | 与 year 一起使用，批量生成全年各月摘要 |
| `dry-run` | ❌ | 预览模式，不实际写入文件 |

---

## Step-by-Step Workflow

### 工作流1: 记录日志

#### Step 1: 语义解析与信息提取

从用户输入中提取：
- `content`: 核心事件描述
- `mood`: 心情标签（推断）
- `topic`: 主题分类（推断）
- `project`: 关联项目（推断）

#### Step 2: 确认地点和天气

如用户未提供地点/天气：
```
请问今天的地点是哪里？天气如何？
（例如：Lagos, Nigeria，晴天）
```

#### Step 3: 分支处理

| 分支 | 条件 | 动作 |
|-----|------|------|
| A | 用户提供完整地址+天气 | 直接使用 |
| B | 仅提供地点 | 常识补全国家 → 调用 query-weather |
| C | 均未提供 | 默认 `Lagos, Nigeria` → 调用 query-weather |

**常识映射表**：
| 用户输入 | 补全结果 |
|---------|---------|
| Lagos | Lagos, Nigeria |
| 北京 | Beijing, China |
| Tokyo | Tokyo, Japan |
| Shanghai | Shanghai, China |
| New York | New York, USA |
| London | London, UK |

#### Step 4: 组装数据并调用工具

```bash
python tools/write_journal.py --data '{"title":"...","content":"...","date":"2026-03-07","topic":"work",...}'
```

#### Step 5: 向用户确认

```
已为您记录 {date} {location} {weather} 的日志，标记为 {topic}/{project}
```

---

### 工作流2: 检索日志

#### Step 1: 解析查询意图

识别查询类型：
- `time_range`: "2月份的日志"
- `metadata`: "关于 Life-Index 的"
- `fulltext`: "提到重构的"
- `compound`: 组合多个条件

#### Step 2: 选择搜索层级

| 层级 | 适用场景 |
|------|---------|
| Level 1 | 有明确 topic/project/tag |
| Level 2 | 有时间/地点等元数据 |
| Level 3 | 需要全文检索（默认） |

#### Step 3: 执行搜索

```bash
python tools/search_journals.py --topic work --query "重构" --level 3
```

#### Step 4: 结果呈现

```
找到 {N} 篇相关日志：
- 2026-02-24: 重构项目架构
- 2026-02-25: 重构后的测试

是否需要查看详细内容？
```

---

### 工作流3: 编辑日志

#### Step 1: 定位日志

根据日期或标题找到目标日志文件。

#### Step 2: 确认修改

展示当前内容，明确修改范围。

#### Step 3: 执行编辑

```bash
python tools/edit_journal.py --journal "Journals/2026/03/..." --set-location "Lagos, Nigeria"
```

---

### 工作流4: 生成摘要

#### Step 1: 确定类型

询问用户需要月度摘要还是年度摘要。

#### Step 2: 执行生成

```bash
# 月度摘要
python tools/generate_abstract.py --month 2026-03

# 年度摘要
python tools/generate_abstract.py --year 2026
```

#### Step 3: 返回结果

告知摘要文件路径和统计信息。

---

## Output Format

所有工具返回 JSON 格式：

```json
{
  "success": true,
  "data": { ... },
  "error": "错误信息（如有）"
}
```

---

## Guardrails

- **永不删除文件**：编辑操作只修改内容，不删除日志文件
- **数据隔离**：所有数据存储在用户目录 `~/Documents/Life-Index/`
- **最小权限**：仅请求必要的网络（天气 API）和文件系统权限
- **输入验证**：日期格式必须为 ISO 8601，路径必须经过安全检查
- **敏感信息**：不在日志中存储密码、密钥等敏感信息

---

## 禁止事项

❌ **不要一次性问多个问题**
```
错误: "地点在哪？天气如何？心情怎么样？"
正确: "地点和天气是？"（单次确认）
```

❌ **不要假设用户知道系统内部概念**
```
错误: "已更新 by-topic 索引"
正确: "已帮您归类到工作相关"
```

❌ **不要在工具调用失败后静默忽略**
```
错误: （天气查询失败，直接跳过）
正确: "天气查询暂时不可用，请告诉我今天的天气"
```

---

## Error Handling

| 场景 | 处理方式 |
|------|---------|
| 文件不存在 | 返回明确的错误信息，建议检查路径 |
| 网络失败 | 天气查询失败时允许日志继续写入（天气字段留空） |
| 权限不足 | 提示用户检查目录权限 |
| 格式错误 | 返回具体的验证错误信息 |
| 附件复制失败 | 记录原始路径，在正文中标注 |
| 索引更新失败 | 主流程继续，记录警告待后续修复 |

---

## Directory Structure

```
~/Documents/Life-Index/           # 用户数据目录（运行时创建）
├── Journals/                     # 日志文件存储
│   └── YYYY/MM/                  # 按年月分层
│       ├── life-index_YYYY-MM-DD_XXX.md
│       └── monthly_abstract.md   # 月度摘要
├── by-topic/                     # 主题索引
│   ├── 主题_work.md
│   ├── 项目_Life-Index.md
│   └── 标签_重构.md
└── attachments/                  # 附件存储
    └── YYYY/MM/
```

---

## Installation

```bash
# 通过 ClawHub 安装
clawhub install life-index

# 或通过 npx 临时使用
npx clawhub@latest install life-index
```

---

## Examples

### 示例 1：记录工作日志

**用户**：记录一下今天完成了 Life Index 的搜索功能优化

**Agent**：
1. 解析：title="完成搜索功能优化", topic="work", project="Life-Index"
2. 确认：地点和天气是？
3. 获取天气（自动）
4. 调用 write-journal
5. 返回：日志已保存至 Journals/2026/03/life-index_2026-03-07_001.md

### 示例 2：搜索历史日志

**用户**：查找去年关于重构的日志

**Agent**：
1. 解析：query="重构", date_from="2025-01-01", date_to="2025-12-31"
2. 调用 search-journals
3. 返回：找到 5 篇相关日志，按日期排序展示

### 示例 3：生成月度摘要

**用户**：生成上个月的摘要

**Agent**：
1. 确定时间：2026年2月
2. 调用 generate-abstract --month 2026-02
3. 返回：月度摘要已保存至 Journals/2026/02/monthly_abstract.md

### 示例 4：记录带附件的日志

**用户**：今天完成了设计稿，见附件

**Agent**：
1. 确认附件路径和描述
2. 组装数据（含 attachments 字段）
3. 调用 write-journal
4. 附件自动复制到 attachments/2026/03/