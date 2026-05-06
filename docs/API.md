# Life Index API 规范

> **本文档职责**: 工具接口规范 SSOT，所有工具的参数、返回值、错误码定义
> **目标读者**: Agent、开发者
> **SSOT 引用**: SKILL.md、AGENTS.md 应引用本文档，不重复定义参数

---

## 通用规范

### 调用方式

所有工具通过 Bash CLI 调用，返回 JSON 格式：

```bash
python -m tools.{tool_name} --data '{json_data}'
```

### 通用返回约定

当前源码的**错误返回**遵循统一结构：

```json
{
  "success": false,
  "error": {
    "code": "E0000",
    "message": "错误信息",
    "details": { ... },
    "recovery_strategy": "ask_user|skip_optional|continue_empty|fail|retry"
  }
}
```

当前源码的**成功返回**没有统一 `data` wrapper；通常采用工具自定义的顶层字段：

```json
{
  "success": true,
  "...tool_specific_fields": "...",
  "error": null
}
```

> 若未来要统一成功返回格式，应先修改源码，再回写本文档。

### 错误码分类

| 模块 | 代码范围 | 说明 |
|------|----------|------|
| 通用 | E00xx | 输入错误、权限错误 |
| 文件 | E01xx | 文件不存在、路径错误 |
| 写入 | E02xx | 写入失败、格式错误 |
| 搜索 | E03xx | 索引错误、查询错误 |
| 天气 | E04xx | API 失败、超时 |
| 编辑 | E05xx | 日志不存在、冲突 |
| 索引 | E06xx | 构建失败、损坏 |
| 迁移 | E08xx | Schema 迁移相关错误 |


## 错误码格式

格式：`E{module}{type}`

- **Module** (2位): 模块标识
- **Type** (2位): 错误类型

## 恢复策略

| 策略 | 说明 | Agent 行为 |
|------|------|-----------|
| `ask_user` | 需要用户干预 | 向用户展示错误并询问 |
| `skip_optional` | 可跳过的可选功能 | 跳过该功能，继续执行 |
| `continue_empty` | 无结果但可继续 | 返回空结果，不报错 |
| `fail` | 不可恢复 | 停止操作，报告错误 |
| `retry` | 可重试 | 自动重试一次，若仍失败则 `ask_user` |

## 错误码列表

### 通用错误 (E00xx)

| 代码 | 说明 | 恢复策略 |
|------|------|----------|
| E0000 | 未知错误 | fail |
| E0001 | 无效输入 | ask_user |
| E0002 | 权限不足 | fail |
| E0003 | 配置错误 | fail |

### 文件模块 (E01xx)

| 代码 | 说明 | 恢复策略 |
|------|------|----------|
| E0100 | 文件不存在 | ask_user |
| E0101 | 文件已存在 | ask_user |
| E0102 | 文件损坏 | fail |
| E0103 | 路径无效 | fail |
| E0104 | 路径遍历检测 | fail |
| E0105 | 目录不存在 | ask_user |

### 写入模块 (E02xx)

| 代码 | 说明 | 恢复策略 |
|------|------|----------|
| E0200 | 写入失败 | fail |
| E0201 | 序列号错误 | fail |
| E0202 | Frontmatter 无效 | fail |
| E0203 | 内容为空 | ask_user |
| E0204 | 日期格式无效 | ask_user |
| E0205 | 附件复制失败 | continue |

### 搜索模块 (E03xx)

| 代码 | 说明 | 恢复策略 |
|------|------|----------|
| E0300 | 索引不存在 | continue |
| E0301 | 搜索失败 | fail |
| E0302 | 查询为空 | ask_user |
| E0303 | 无结果 | continue_empty |

### 天气模块 (E04xx)

| 代码 | 说明 | 恢复策略 |
|------|------|----------|
| E0400 | 天气 API 失败 | skip_optional |
| E0401 | 天气 API 超时 | skip_optional |
| E0402 | 地点未找到 | ask_user |
| E0403 | 天气解析错误 | skip_optional |

### 编辑模块 (E05xx)

| 代码 | 说明 | 恢复策略 |
|------|------|----------|
| E0500 | 日志不存在 | ask_user |
| E0501 | 编辑冲突 | ask_user |
| E0502 | 字段不识别 | ask_user |
| E0503 | 无变更指定 | ask_user |

### 索引模块 (E06xx)

| 代码 | 说明 | 恢复策略 |
|------|------|----------|
| E0600 | 索引构建失败 | fail |
| E0601 | 索引损坏 | fail |
| E0602 | 向量存储错误 | continue |
| E0603 | FTS 索引错误 | continue |

## JSON 返回示例

```json
{
  "success": false,
  "error": {
    "code": "E0400",
    "message": "天气 API 请求失败",
    "details": {
      "location": "Lagos, Nigeria",
      "reason": "connection_timeout"
    },
    "recovery_strategy": "skip_optional",
    "suggestion": "请手动输入天气信息，或稍后重试"
  }
}
```

---

## write_journal

### 端点

```bash
python -m tools.write_journal --data '<json>'
```

### 参数

| 名称 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| title | string | ❌ | 自动生成/调用方补齐 | 日志标题（≤20字） |
| content | string | ⚠️ workflow 通常要求 | - | 日志正文（原样保留） |
| date | string | ✅ | - | 日期（ISO 8601: YYYY-MM-DD） |
| location | string | ❌ | 默认地点兜底 | 地点；若正文中已明确写出地点，优先采用正文信息；仅在正文和入参都未提供时才使用默认地点 |
| weather | string | ❌ | 自动查询/手动兜底 | 天气描述；若正文中已明确写出天气，优先采用正文信息 |
| mood | array | ❌ | [] | 心情标签 |
| people | array | ❌ | [] | 相关人物 |
| topic | array | ❌ | 调用方补齐/LLM 提炼 | 主题分类（7类之一） |
| project | string | ❌ | "" | 关联项目 |
| tags | array | ❌ | [] | 标签 |
| summary | string | ❌ | 调用方补齐/LLM 提炼 | 摘要（≤100字，**Agent生成**）；`abstract` 为向后兼容别名 |
| links | array | ❌ | [] | 相关链接 |
| related_entries | array | ❌ | [] | 关联日志相对路径（如 `Journals/2026/03/xxx.md`） |
| attachments | array | ❌ | [] | 附件列表；输入阶段支持本地路径自动检测，也支持显式对象输入；写入后以 frontmatter `attachments` 作为唯一 SSOT |

### 附件对象格式

#### 输入阶段（调用 `write_journal` 时）

```json
{
  "source_path": "C:/Users/xxx/file.png",
  "description": "附件说明",
  "content_type": "image/png",
  "size": 12345
}
```

或：

```json
{
  "source_url": "https://example.com/file.png",
  "description": "附件说明",
  "content_type": "image/png",
  "size": 12345
}
```

> `content_type` / `size` 在输入阶段均为可选；如果调用方未提供，系统会在本地文件复制或 URL 下载阶段尽力自动推断。

#### 写入后 stored attachment 对象（frontmatter `attachments`）

```json
{
  "filename": "file.png",
  "rel_path": "../../../attachments/2026/03/file.png",
  "description": "附件说明",
  "original_name": "file.png",
  "auto_detected": false,
  "source_url": "https://example.com/file.png",
  "content_type": "image/png",
  "size": 12345
}
```

> 对于本地附件，`source_url` 通常为 `null` / 缺省；对于 legacy journals，读取侧应允许 `content_type` 与 `size` 缺省，并按文件扩展名做兼容推断。

### 附件输入契约说明

- 聊天 / Agent 场景下，Life Index **保留自动从 `content` 中识别本地文件路径** 的能力
- 因此类似下面的输入仍然有效：

```text
/life-index 记日志：今天……
附件路径：C:\Users\me\Desktop\photo.png
```

- 也支持显式 `attachments` 对象输入
- 显式 `attachments` 对象既支持本地文件：`source_path`，也支持远程文件：`source_url`
- 当提供 `source_url` 时，系统会先下载远程文件，再按 Life Index 附件归档流程写入 frontmatter `attachments`
- **不要求**额外魔法词或强制 DSL 语法
- 推荐表达方式是把附件路径单独成段，以提升 Agent 解析稳定性，但这只是推荐，不是强制要求

### 附件存储契约说明

- 新 journal 写入时，附件信息仅写入 frontmatter `attachments`
- 不再自动向正文追加 `## Attachments` / `## 附件` 区块
- 读取侧应兼容：
  - legacy string attachment entries
  - structured attachment objects

### 返回值

```json
{
  "success": true,
  "write_outcome": "success_pending_confirmation",
  "journal_path": "C:/Users/.../Documents/Life-Index/Journals/2026/03/life-index_2026-03-10_001.md",
  "updated_indices": ["C:/Users/.../Documents/Life-Index/by-topic/主题_work.md"],
  "attachments_processed": [...],
  "attachments_detected_count": 1,
  "attachments_processed_count": 1,
  "attachments_failed_count": 0,
  "location_used": "Beijing, China",
  "location_auto_filled": false,
  "weather_used": "Sunny 25°C",
  "weather_auto_filled": true,
  "needs_confirmation": true,
  "confirmation": {
    "location": "Beijing, China",
    "weather": "Sunny 25°C",
    "related_candidates": [],
    "journal_path": "C:/Users/.../Documents/Life-Index/Journals/2026/03/life-index_2026-03-10_001.md",
    "supports_related_entry_approval": true
  },
  "related_candidates": [],
  "new_entities_detected": [],
  "entity_candidates": [
    {
      "text": "乐乐妈",
      "source": "content",
      "kind": "person",
      "matched_entity_id": "wife-001",
      "suggested_action": "confirm_match",
      "risk_level": "low"
    }
  ],
  "confirmation_message": "日志已保存至：C:/Users/.../Documents/Life-Index/Journals/...",
  "error": null,
  "metrics": {"total_ms": 142.5}
}
```

### Round 7 新增返回字段

- `entity_candidates`：write-time candidate layer 输出。来自 frontmatter + 正文中的实体候选匹配；只作为候选，不直接写回 `entity_graph.yaml`
- `new_entities_detected`：向后兼容字段；语义比 `entity_candidates` 更粗糙，后续调用方应优先消费 `entity_candidates`

### 当前源码校验语义

- `write_journal()` 当前源码只对 `date` 做硬校验
- `content` 在产品 / workflow 语义上通常应提供，但并非这里定义的同级硬校验项
- `title` / `topic` / `abstract` 更准确地说是 **Agent / Web workflow 负责补齐**，不是 `write_journal()` 当前源码的硬必填

### 写入与确认语义

- `needs_confirmation` 应视为当前写入协议中的正常后续步骤，而不是可忽略的偶发分支
- 任何 `success: true` 的写入结果都必须进入地点确认环节；Agent / Web 不得自行判断“这次可以不问”
- 正文中明确写出的地点/天气优先级最高，Agent 不得再用默认地点或自动查询结果覆盖
- `location_auto_filled` 用于解释地点来源，不再作为是否执行确认环节的决策条件
- 如果用户要求修正地点/天气，后续应进入 correction flow，而不是把原写入描述为失败
- `confirmation` 是 machine-readable 的确认载荷；`confirmation_message` 是面向人类的展示文本
- `confirmation.supports_related_entry_approval: true` 表示调用方可在确认阶段直接批准候选 `related_candidates` 并写回 `related_entries`

### 写入结果解读（Agent / Web 调用方）

| 字段 | 值 | 含义 | 调用方行为 |
|:---|:---:|:---|:---|
| `success` | true/false | 日志是否成功写入 | false → 告知用户写入失败 |
| `needs_confirmation` | true/false | 是否需要用户确认地点/天气 | true → 展示确认信息，等待用户回复 |
| `index_status` | complete/degraded/not_started | 索引更新状态 | degraded → 告知用户“已保存，但搜索可能暂时找不到” |
| `side_effects_status` | complete/degraded/not_started | 附件/摘要等副作用状态 | degraded → 告知用户“已保存，但部分信息未更新” |
| `weather_auto_filled` | true/false | 天气是否自动填充 | true → 在确认信息中标注“自动获取” |
| `attachments_detected_count` | int | 从正文自动检测到的本地附件路径数量 | 向用户反馈检测结果 |
| `attachments_processed_count` | int | 成功归档的附件数量 | 向用户反馈成功归档数量 |
| `attachments_failed_count` | int | 检测到但处理失败的附件数量 | >0 时提示用户检查失败附件 |

**降级状态处理示例**：

```json
{
  "success": true,
  "index_status": "degraded"
}
```

建议调用方表述：

> 日志已保存，但索引更新遇到问题，新日志可能暂时无法被搜索到。

### confirm 子命令

```bash
python -m tools.write_journal confirm --journal "Journals/2026/03/life-index_2026-03-10_001.md" --location "Beijing, China" --weather "Sunny 25°C" --approve-related "Journals/2026/03/other.md"
```

- `confirm` 会调用 `apply_confirmation_updates()`
- 可同时修正 `location` / `weather`
- 可通过重复 `--approve-related` 参数批准多个候选关联日志并写回
- 可通过重复 `--approve-related-id` / `--reject-related-id` 传入候选 ID（需同时携带 `candidate_context` 才能稳定解析）
- 可通过重复 `--reject-related` 参数显式标记拒绝的候选关联日志
- 内部统一委托到 `edit_journal`，不另起一套写入逻辑

### confirm 返回值

```json
{
  "success": true,
  "confirm_status": "complete",
  "journal_path": "Journals/2026/03/life-index_2026-03-10_001.md",
  "applied_fields": ["location", "weather", "related_entries"],
  "ignored_fields": [],
  "approved_related_entries": ["Journals/2026/03/other.md"],
  "requested_related_entries": ["Journals/2026/03/other.md"],
  "approved_candidate_ids": [1],
  "rejected_related_entries": ["Journals/2026/03/skip.md"],
  "rejected_candidate_ids": [2],
  "approval_summary": {
    "approved": [
      {
        "candidate_id": 1,
        "rel_path": "Journals/2026/03/other.md",
        "title": "Other"
      }
    ],
    "rejected": [
      {
        "candidate_id": 2,
        "rel_path": "Journals/2026/03/skip.md",
        "title": "Skip"
      }
    ]
  },
  "relation_summary": {
    "source_entry": {
      "rel_path": "Journals/2026/03/life-index_2026-03-10_001.md",
      "related_entries": ["Journals/2026/03/other.md"],
      "backlinked_by": []
    },
    "approved_related_context": [
      {
        "rel_path": "Journals/2026/03/other.md",
        "backlinked_by": ["Journals/2026/03/life-index_2026-03-10_001.md"]
      }
    ]
  },
  "changes": {},
  "error": null
}
```

- `confirm_status`：确认执行语义状态。`complete` = 全部请求字段都已写回；`partial` = 仅部分字段生效；`noop` = 请求已处理但没有实际变化；`failed` = 确认失败
- `applied_fields`：这次确认中实际发生写回的字段
- `ignored_fields`：本次请求里提供了，但最终未发生变化的字段（例如与原值相同）
- `approved_related_entries`：本次真正写回成功的关联日志
- `requested_related_entries`：调用方请求批准写回的关联日志列表
- `approved_candidate_ids`：本次被成功解析并批准的候选 ID
- `rejected_related_entries`：本次显式拒绝的候选关联日志列表
- `rejected_candidate_ids`：本次被成功解析并拒绝的候选 ID
- `approval_summary`：为 GUI/service 准备的批准/拒绝摘要；每项都包含 `candidate_id/rel_path/title`
- `relation_summary`：确认完成后的新鲜关联关系摘要，避免调用方再额外跑一次 search 才知道 `related_entries/backlinked_by` 当前状态
- `relation_summary.source_entry.backlinked_by`：有哪些日志当前指向本条日志
- `relation_summary.approved_related_context[*].backlinked_by`：每个本次批准关联日志当前被哪些日志反向链接
- `changes`：来自底层 `edit_journal` 的变更明细，结构类似 `{"location": {"old": "旧值", "new": "新值"}}`
- `error`：失败时为结构化错误对象，格式与 `tools/lib/errors.py` 中的 `LifeIndexError.to_json()` 一致（含 `code/message/details/recovery_strategy/suggestion`）
- 参数命名映射：CLI 使用 `--approve-related` / `--approve-related-id` / `--reject-related` / `--reject-related-id`，schema 使用 `approve_related` / `approve_related_id` / `reject_related` / `reject_related_id`，底层 helper 使用 `approved_related_entries` / `approved_related_candidate_ids` / `rejected_related_entries` / `rejected_related_candidate_ids`

### 附件检测与处理语义

- `attachments_detected_count`：从最终 `content` 中自动检测到的本地附件路径数量
- `attachments_processed_count`：成功归档到 Life Index `attachments/` 目录的附件数量
- `attachments_failed_count`：检测到但处理失败的附件数量
- Agent / Web 成功反馈必须显式消费这些字段，不得把附件处理结果留给模型自行猜测

### 写入成功 / 降级 / 修复语义

- `journal_path` 可被成功返回时，应优先理解为**核心 journal 已 durably saved**
- `needs_confirmation: true` 表示“写入成功但仍需确认/修正”，**不等于写入失败**
- 索引、附件、补充信息等 side effects 若处于降级状态，应报告为“已保存，但仍有后续修复或可见性问题”，不应抹掉核心写入成功这一事实
- Agent 必须保留这三种区别：
  1. 写入失败
  2. 写入成功，但仍需 confirmation / correction
  3. 写入成功，但 side effects / index visibility 不完整

### write_outcome 值定义

`write_outcome` 是 Round 5 新增的顶层字段。Agent 只需读这一个字段即可判断下一步动作，无需组合检查 `success` + `needs_confirmation` + `index_status` + `side_effects_status`。

| 值 | 含义 | Agent 应做什么 |
|---|---|---|
| `success` | 全部完成 | 告知用户成功 |
| `success_pending_confirmation` | 日志已保存，地点/天气待确认 | 展示 `confirmation_message` 并等待用户回复 |
| `success_degraded` | 日志已保存，但索引/附件等后续操作部分失败 | 告知用户已保存但存在降级，建议后续修复 |
| `failed` | 写入失败 | 查看 `error` 字段的 `recovery_strategy` 决定下一步 |

推导规则（`derive_write_outcome()`）：
1. `success == false` → `failed`
2. `needs_confirmation == true` → `success_pending_confirmation`（即使同时降级，确认优先）
3. `index_status == "degraded"` 或 `side_effects_status == "degraded"` → `success_degraded`
4. 以上均否 → `success`

### Tool hard-required vs workflow-required

- `docs/API.md` 描述的是 **tool contract / 运行时硬契约**
- 某些字段（如 `title` / `abstract` / `topic` / `mood` / `tags`）在产品 workflow 中通常应由 Agent 或 Web 层补齐
- 但这不自动等同于 `write_journal()` 当前源码层面的硬校验必填
- 如两者需要同时表述，应优先区分：
  1. **tool hard-required**（工具自身拒绝缺失）
  2. **workflow-required**（调用方在进入工具前应补齐）

### 错误码

| 代码 | 说明 | 恢复策略 |
|------|------|----------|
| E0001 | 必填参数缺失 | ask_user |
| E0203 | content 为空 | ask_user |
| E0204 | 日期格式无效 | ask_user |
| E0205 | 附件复制失败 | continue |
| E0400 | 天气 API 失败 | skip_optional |

---

## search_journals

### 端点

```bash
python -m tools.search_journals [options]
```

### 参数

| 名称 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| query | string | ❌ | - | 搜索关键词 |
| topic | string | ❌ | - | 按主题过滤 |
| project | string | ❌ | - | 按项目过滤 |
| tags | string | ❌ | - | 按标签过滤（逗号分隔） |
| date_from | string | ❌ | - | 起始日期 (YYYY-MM-DD) |
| date_to | string | ❌ | - | 结束日期 (YYYY-MM-DD) |
| location | string | ❌ | - | 按地点过滤 |
| weather | string | ❌ | - | 按天气过滤 |
| mood | string | ❌ | - | 按心情过滤（逗号分隔） |
| people | string | ❌ | - | 按人物过滤（逗号分隔） |
| level | int | ❌ | 3 | 搜索层级: 1=索引, 2=元数据, 3=全文 |
| use-index | flag | ❌ | false | 使用 FTS 索引加速 |
| semantic | flag | ❌ | false | 启用语义搜索 |
| semantic-weight | float | ❌ | 0.4 | 语义搜索权重 (0-1) |
| fts-weight | float | ❌ | 0.6 | FTS 搜索权重 (0-1) |
| limit | int | ❌ | 10 | 返回结果数量限制 |
| offset | int | ❌ | 0 | 结果偏移量（分页起始位置） |
| year | int | ❌ | - | L0 预过滤：限定年份（如 2026），先缩小候选集再进入搜索管道 |
| month | int | ❌ | - | L0 预过滤：限定月份（需配合 --year） |

### 返回值

```json
{
  "success": true,
  "query_params": {
    "query": "重构",
    "level": 3,
    "semantic": true
  },
  "merged_results": [
    {
      "path": "C:/Users/.../Documents/Life-Index/Journals/2026/03/life-index_2026-03-06_001.md",
      "rel_path": "Journals/2026/03/life-index_2026-03-06_001.md",
      "title": "搜索功能重构",
      "date": "2026-03-06",
      "rrf_score": 0.85
    }
  ],
  "entity_hints": [
    {
      "matched_term": "老婆",
      "entity_id": "wife-001",
      "entity_type": "person",
      "expansion_terms": ["王某某", "乐乐妈", "老婆"],
      "reason": "alias_match"
    }
  ],
  "total_found": 5,
  "total_available": 56,
  "has_more": true,
  "semantic_available": true,
  "performance": {"total_time_ms": 45}
}
```

### Round 7 新增返回字段

- `entity_hints`：search 对 query 中实体命中结果的结构化解释字段
- 每个 hint 包含：`matched_term` / `entity_id` / `entity_type` / `expansion_terms` / `reason`
- `entity_hints` 属于 read-only suggestion layer，不会修改 query 语义本身；它与 `query_params.expanded_query` 互补存在

### Round 11 新增返回字段

#### `search_plan` — 结构化查询理解

L2 Deterministic Preprocessing 的输出，描述 query 在进入检索之前被 CLI 如何结构化理解。**caller-facing field**，供 Agent / Web / 上层 orchestrator 消费。

| 子字段 | 类型 | 说明 |
|--------|------|------|
| `raw_query` | string | 原始查询文本 |
| `normalized_query` | string | 标准化后查询（去标点、trim、全角转半角） |
| `intent_type` | string enum | 查询意图：`recall` / `count` / `compare` / `summarize` / `unknown` |
| `query_mode` | string enum | 查询模式：`keyword` / `natural_language` / `mixed` |
| `keywords` | string[] | 从 query 提取的关键词列表 |
| `date_range` | object \| null | 解析出的时间范围：`{since, until, source}` |
| `topic_hints` | string[] | 推断的主题映射（work/health/learn 等） |
| `entity_hints_used` | array | 使用的实体 hint 列表 |
| `expanded_query` | string | 扩展后的查询文本 |
| `pipelines` | object | 启用的管道：`{keyword: bool, semantic: bool}` |

> `search_plan` 不替用户下最终结论，只记录 query 被如何理解。

#### `ambiguity` — 歧义信号报告

CLI 对"存在多个合理解释 / 需要上层 judgment"的结构化声明。**报告 signal，不替 Agent 裁决**。

| 子字段 | 类型 | 说明 |
|--------|------|------|
| `has_ambiguity` | boolean | 是否存在歧义信号 |
| `items` | array | 歧义信号列表 |
| `items[].type` | string | 歧义类型枚举（见下表） |
| `items[].severity` | string | `low` / `medium` / `high` |
| `items[].reason` | string | 为什么认为这里有歧义 |
| `items[].candidates` | string[] | 可选的多种解释 |

歧义类型枚举：

| type | severity | 说明 |
|------|----------|------|
| `aggregation_requires_agent_judgement` | high | count/compare/summarize 需要 Agent 判断最终答案 |
| `time_range_interpretation` | medium | 相对时间表达存在多种解释窗口 |
| `entity_resolution_multiple_candidates` | medium | 实体解析返回多个候选 |
| `query_too_broad` | low | query 过宽，结果可能不可信 |

#### `hints` — 调用时局部提示

L3 Invocation-Time Hints，提供与本次调用相关的局部提示。**不变成长篇 prescriptive prompt，不替代 SKILL.md**。

| 子字段 | 类型 | 说明 |
|--------|------|------|
| `type` | string | 提示类型（如 `retrieval_boundary`、`refinement_suggestion`、`time_range_parsed`） |
| `severity` | string | `low` / `medium` / `high` |
| `message` | string | 提示内容（≤ 120 字符） |

> 单次调用 hints ≤ 5 条。

#### 三者边界

| 字段 | 所属层 | 作用 | 不做什么 |
|------|--------|------|----------|
| `search_plan` | L2 | 记录 query 被如何结构化理解 | 不替用户下最终结论 |
| `ambiguity` | L2→L4 边界 | 报告歧义信号 | 不替 Agent 裁决 |
| `hints` | L3 | 提供调用时局部提示 | 不变成长篇 prescriptive prompt |

> 当前搜索结果中的 `path` 经常是绝对路径；上层调用方不应直接把它拼进 Web 路由。

### 错误码

| 代码 | 说明 | 恢复策略 |
|------|------|----------|
| E0302 | 查询为空 | ask_user |
| E0303 | 无结果 | continue_empty |
| E0300 | 索引不存在 | continue |

### caller-facing 解释语义

- `search_journals` 返回结果列表表示 retrieval execution 成功，不等于 Agent 已完成最终用户答案
- `E0303` 或空结果应解释为“执行成功但没有匹配结果”，不应解释为执行失败
- 工具 failure 与空结果必须在调用方叙述中严格区分
- Web / Agent 调用方如需做自然语言总结，应基于**同一次 retrieval 返回的结果集**进行解释；不应在上层路由中再维护第二套并行检索 / merge / ranking 真相

---

## smart_search

### 端点

```bash
life-index smart-search --query "..." [options]
python -m tools.smart_search --query "..." [options]
```

### 参数

| 名称 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| query | string | ✅ | - | 自然语言搜索查询 |
| no-llm | flag | ❌ | false | 强制降级模式（纯双管道，不调用 LLM） |
| explain | flag | ❌ | false | 在输出中包含 Agent 决策详情 |

### 返回值

```json
{
  "success": true,
  "query": "我和女儿之间有哪些珍贵的回忆？",
  "results": [...],
  "total_found": 3,
  "agent_decisions_summary": "5 decisions made",
  "mode": "llm_orchestrated"
}
```

### 说明

- `SmartSearchOrchestrator` 三段式流程：前置改写 → 中间调用 search 原语 → 后置筛选 + 摘要
- 降级模式 (`--no-llm` 或 LLM 不可用) 下等价于 `search --level 3`
- Data Minimization：候选仅送 title + abstract + snippet（≤200 chars），最多 15 条
- 实现详见 `docs/ARCHITECTURE.md` §5.8

---

## edit_journal

### 端点

```bash
python -m tools.edit_journal --journal "<path>" [options]
```

### 参数

| 名称 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| journal | string | ✅ | - | 日志文件路径 |
| set-title | string | ❌ | - | 设置标题 |
| set-date | string | ❌ | - | 设置日期 |
| set-location | string | ❌ | - | 设置地点 |
| set-weather | string | ❌ | - | 设置天气 |
| set-mood | string | ❌ | - | 设置心情（逗号分隔） |
| set-people | string | ❌ | - | 设置人物（逗号分隔） |
| set-tags | string | ❌ | - | 设置标签（逗号分隔） |
| set-project | string | ❌ | - | 设置项目 |
| set-topic | string | ❌ | - | 设置主题（逗号分隔） |
| set-abstract | string | ❌ | - | 设置摘要 |
| set-links | string | ❌ | - | 设置外部链接（逗号分隔） |
| set-related-entries | string | ❌ | - | 设置关联日志相对路径（逗号分隔） |
| append-content | string | ❌ | - | 追加内容到正文 |
| replace-content | string | ❌ | - | 替换整个正文 |
| dry-run | flag | ❌ | false | 模拟运行 |

### 编辑规则

- 只要修改 `location`，就必须同时提交新的 `weather`
- 推荐顺序：先调用 `query_weather` 获取天气；如果失败，允许 Agent 手动联网查询天气后再继续编辑
- 如果最终拿不到新的天气，本次地点修改不得成功写入
- 调用前必须先解决 target selection 与 mutation intent；`edit_journal` 不负责替调用方猜测编辑目标或变更类型

### 地点 / 天气耦合语义

- `edit_journal` 是**确定性修改工具**，不负责自动刷新天气
- `query_weather` 负责天气能力查询，不负责 journal mutation
- 因此只修改 `location` 时，Agent / caller 必须显式承担“先查天气、再同时提交 location + weather”的 orchestration
- 如果天气刷新失败，Agent 必须诚实区分“journal edit 状态”和“weather refresh 状态”，不能暗示天气已经同步正确

### caller-facing 成功 / 失败语义

- `edit_journal` success 应理解为请求的 deterministic mutation 已成功应用
- 如果 edit 前置条件尚未满足（例如 coupled-field prerequisite 未解决），正确行为是先澄清或补齐，再调用工具
- 对于 location/weather 这类耦合修改，调用方必须区分“编辑失败”与“语义对齐尚未完成”

### 返回值

```json
{
  "success": true,
  "write_outcome": "success_pending_confirmation",
  "journal_path": "C:/Users/.../Documents/Life-Index/Journals/2026/03/life-index_2026-03-10_001.md",
  "changes": {
    "location": {"old": "Chongqing, China", "new": "Beijing, China"},
    "weather": {"old": "Sunny", "new": "Cloudy"}
  },
  "content_modified": false,
  "indices_updated": [],
  "error": null
}
```

### 错误码

| 代码 | 说明 | 恢复策略 |
|------|------|----------|
| E0500 | 日志不存在 | ask_user |
| E0502 | 字段不识别 | ask_user |
| E0503 | 无变更 | ask_user |
| E0504 | 修改地点时缺少天气 | ask_user |

---

## query_weather

### 端点

```bash
python -m tools.query_weather --location "<location>" [options]
```

### 参数

| 名称 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| location | string | ❌ | "Chongqing, China" | 地点名称 |
| lat | float | ❌ | - | 纬度 |
| lon | float | ❌ | - | 经度 |
| date | string | ❌ | "today" | 日期 (YYYY-MM-DD) |

### 返回值

```json
{
  "success": true,
  "date": "2026-03-10",
  "location": {"lat": 39.9, "lon": 116.4},
  "weather": {
    "code": 2,
    "description": "Partly cloudy (多云)",
    "simple": "多云",
    "temperature_max": 18.5,
    "temperature_min": 8.2,
    "precipitation": 0.0
  },
  "error": null
}
```

### 错误码

| 代码 | 说明 | 恢复策略 |
|------|------|----------|
| E0400 | API 请求失败 | skip_optional |
| E0401 | API 超时 | skip_optional |
| E0402 | 地点未找到 | ask_user |

### 天气失败后的兜底

- `query_weather` 是首选天气来源
- 如果 `query_weather` 失败，Agent 可手动联网查询天气并将结果提供给 `edit_journal`
- 对于地点修改场景，只有 `query_weather` 和 Agent 手动查询都失败时，才允许把本次修改判定为失败
- `query_weather` 是 capability tool，不是 recovery orchestrator；失败后的流程判断由 Agent / caller 负责

---

## generate_index

> ⚡ 别名：`life-index abstract`（向后兼容）

### 端点

```bash
python -m tools.generate_index [options]
life-index generate-index [options]
```

### 参数

| 名称 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| month | string | ❌ | - | 生成月度索引 (YYYY-MM)，输出 `index_YYYY-MM.md` |
| year | int | ❌ | - | 生成年度索引 (YYYY)，输出 `index_YYYY.md` |
| all-months | flag | ❌ | false | 与 year 一起使用，批量生成全年月度索引 |
| rebuild | flag | ❌ | false | 全量重建三层索引树（月→年→根） |
| dry-run | flag | ❌ | false | 预览模式 |

### 返回值

月度索引：

```json
{
  "success": true,
  "type": "monthly",
  "year": 2026,
  "month": 3,
  "output_path": "~/Documents/Life-Index/Journals/2026/03/index_2026-03.md",
  "journal_count": 15,
  "message": "月度索引已生成"
}
```

全量重建：

```json
{
  "success": true,
  "monthly_indexes_rebuilt": 12,
  "yearly_indexes_rebuilt": 1,
  "root_index_rebuilt": true,
  "errors": []
}
```

---

## build_index

### 端点

```bash
python -m tools.build_index [options]
```

### 参数

| 名称 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| rebuild | flag | ❌ | false | 全量重建索引 |
| validate | flag | ❌ | false | 验证索引完整性 |
| check | flag | ❌ | false | 索引一致性诊断（只读，不修改任何文件） |
| fts-only | flag | ❌ | false | 仅更新 FTS 索引 |
| vec-only | flag | ❌ | false | 仅更新向量索引 |
| stats | flag | ❌ | false | 显示索引统计信息 |
| json | flag | ❌ | false | 以 JSON 格式输出结果 |

### 返回值

**构建/重建模式**：

```json
{
  "success": true,
  "fts": {
    "success": true,
    "added": 45,
    "updated": 0,
    "removed": 0
  },
  "vector": {
    "success": true,
    "added": 45,
    "updated": 0
  },
  "duration_seconds": 1.2
}
```

**`--check` 模式**：

```json
{
  "healthy": true,
  "fts_count": 53,
  "vector_count": 53,
  "file_count": 53,
  "issues": []
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| healthy | bool | 三者（FTS/向量/文件）完全一致时为 true |
| fts_count | int | FTS 索引中的条目数 |
| vector_count | int | 向量索引中的条目数 |
| file_count | int | Journals/ 下实际日志文件数 |
| issues | string[] | 不一致描述列表；空列表表示健康 |

退出码：healthy → 0, unhealthy → 1（便于 CI 集成）

---

## health

### 端点

```bash
python -m tools health [options]
```

### 参数

| 名称 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| data-audit | flag | ❌ | false | 数据目录清洁度审计 |

### 返回值

**标准模式**：

```json
{
  "success": true,
  "data": {
    "status": "healthy|degraded|unhealthy",
    "checks": [ ... ],
    "issues": [ ... ]
  },
  "events": [ ... ]
}
```

**`--data-audit` 模式**：

```json
{
  "success": true,
  "data": {
    "file_count": 53,
    "anomalies": [
      {
        "type": "revision_file",
        "severity": "warning",
        "description": "Revision file found outside .revisions/: ...",
        "path": "Journals/2026/03/life-index_2026-03-01_001_20260418_120000_000000.md"
      }
    ],
    "distribution": {"2026-03": 12, "2026-04": 8}
  }
}
```

| 异常类型 | 严重级 | 说明 |
|---------|--------|------|
| revision_file | warning | 编辑修订文件遗留在 Journals/ 目录（非 .revisions/） |
| naming | info | 非 `life-index_`/`index_`/`monthly_report_` 开头的 .md 文件 |
| distribution | info | 某月日志数 > 3x 月均值 |

---

## backup

### 端点

```bash
python -m tools.backup [options]
```

### 参数

| 名称 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| dest | string | 条件必填 | - | 备份目标目录；create/list 模式需要 |
| full | flag | ❌ | false | 执行全量备份 |
| dry-run | flag | ❌ | false | 模拟运行，不实际复制文件 |
| list | flag | ❌ | false | 列出指定备份目录下的备份记录 |
| restore | string | ❌ | - | 从指定备份目录恢复 |

### 返回值

创建备份示例：

```json
{
  "success": true,
  "backup_path": "D:/backup/life-index-backup-20260325_120000",
  "files_backed_up": 42,
  "files_skipped": 10,
  "errors": [],
  "manifest_path": "D:/backup/.life-index-backup-manifest.json"
}
```

### 说明

- `backup` 属于数据安全与 operator 工具，不改变 journal/frontmatter 契约
- 恢复前应先由调用方确认目标目录与覆盖风险

---

## entity

### 端点

```bash
python -m tools.entity [options]
```

### 参数

| 名称 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--list` | flag | ❌ | false | 列出实体图谱中的所有实体 |
| `--type` | string | ❌ | - | 按类型过滤（如 `person`, `place`, `concept`） |
| `--add` | string | ❌ | - | 添加新实体（JSON 格式） |
| `--resolve` | string | ❌ | - | 解析实体名称歧义 |
| `--update` | flag | ❌ | false | 更新实体属性（需 `--id` 和 `--add-alias`） |
| `--audit` | flag | ❌ | false | 执行实体质量审计 |
| `--stats` | flag | ❌ | false | 输出图谱统计 |
| `--check` | flag | ❌ | false | 执行图谱完整性检查 |
| `--review` | flag | ❌ | false | 打开 Review Hub（风险优先审订队列） |
| `--merge` | string | ❌ | - | 合并实体（需 `--id` 和 `--target-id`） |
| `--delete` | flag | ❌ | false | 删除指定实体（需 `--id`） |
| `--id` | string | 条件必填 | - | 源实体 ID |
| `--target-id` | string | 条件必填 | - | 目标实体 ID（用于 merge） |
| `--add-alias` | string | ❌ | - | 为实体添加别名（配合 `--update`） |
| `--action` | enum | ❌ | - | `merge_as_alias` / `keep_separate` / `skip` / `preview` |
| `--export` | enum | ❌ | - | 导出格式：`csv` / `xlsx`（配合 `--review`） |
| `--import` | string | ❌ | - | 从文件导入审订结果（配合 `--review`） |
| `--output` | string | ❌ | - | 指定输出文件路径（配合 `--review --export`） |
| `--seed` | flag | ❌ | false | 从 journal frontmatter 冷启动图谱 |

### 主要操作模式

#### `entity --audit`

执行实体质量审计：

```bash
life-index entity --audit
```

返回（标准 envelope）：

```json
{
  "success": true,
  "data": {
    "audit_date": "2026-04-09",
    "total_entities": 42,
    "issues": [
      {
        "type": "possible_duplicate",
        "severity": "high",
        "entities": ["妈妈", "母亲"],
        "entity_ids": ["p001", "p002"],
        "confidence": 0.9,
        "evidence": "alias overlap: ...",
        "suggested_action": "merge"
      },
      {
        "type": "orphan_entity",
        "severity": "medium",
        "entity_id": "p003",
        "primary_name": "旧同事A",
        "message": "实体 '旧同事A' 在日志中零引用",
        "suggested_action": "archive"
      }
    ],
    "summary": {"high": 1, "medium": 1, "low": 0}
  },
  "error": null
}
```

#### `entity --stats`

输出图谱统计：

```bash
life-index entity --stats
```

返回：

```json
{
  "success": true,
  "data": {
    "total_entities": 42,
    "by_type": {"person": 15, "place": 8, "concept": 19},
    "total_aliases": 23,
    "total_relationships": 56,
    "top_referenced": [
      {"entity_id": "p001", "incoming_count": 12}
    ],
    "top_cooccurrence": [
      {"entities": ["p001", "p002"], "cooccurrence": 5}
    ]
  },
  "error": null
}
```

#### `entity --check`

执行图谱完整性检查：

```bash
life-index entity --check
```

返回：

```json
{
  "success": true,
  "data": {
    "total_entities": 42,
    "issues": [
      {
        "type": "dangling_relationship",
        "severity": "high",
        "entity_id": "p001",
        "target": "p999",
        "relation": "friend",
        "description": "Entity p001 references non-existent target p999"
      },
      {
        "type": "duplicate_lookup",
        "severity": "medium",
        "name": "小明",
        "entity_ids": ["p001", "p002"],
        "description": "Name '小明' resolves to multiple entities: ['p001', 'p002']"
      }
    ],
    "summary": {
      "dangling_relationships": 1,
      "duplicate_lookups": 1,
      "schema_issues": 0
    }
  },
  "error": null
}
```

#### `entity --review`

打开 Review Hub，返回风险优先审订队列：

```bash
life-index entity --review
```

返回：

```json
{
  "success": true,
  "data": {
    "queue": [
      {
        "item_id": "review-1",
        "risk_level": "high",
        "category": "possible_duplicate",
        "description": "alias overlap: ...",
        "action_choices": ["merge_as_alias", "keep_separate", "skip"],
        "entity_ids": ["p001", "p002"],
        "suggested_action": "merge"
      }
    ],
    "total": 1
  },
  "error": null
}
```

#### `entity --merge`

合并实体。`--merge` 需要一个参数值（当前实现中该值未被使用，实际 source 以 `--id` 为准）：

```bash
life-index entity --merge p001 --id p001 --target-id p002
```

返回：

```json
{
  "success": true,
  "action": "merge_as_alias",
  "source_id": "p001",
  "target_id": "p002",
  "transferred_names": ["旧名字", "别名A"]
}
```

#### `entity --delete --id ENTITY_ID`

删除实体。执行前会报告引用该实体的其他实体：

```bash
life-index entity --delete --id p003
```

返回：

```json
{
  "success": true,
  "data": {
    "deleted_id": "p003",
    "deleted_name": "旧同事A",
    "cleaned_refs": [
      {"entity_id": "p001", "relation": "colleague"}
    ]
  },
  "error": null
}
```

#### `entity --seed`

从现有 journal frontmatter 中冷启动实体图谱：

```bash
life-index entity --seed
```

### Agent 使用约束

- **review / merge / delete 是高风险操作**，必须在调用前明确目标实体和确认策略
- `--audit` 结果中的 `suggested_action` 仅为建议，最终合并/删除决策需用户确认
- `--seed` 会从 journal frontmatter 冷启动/补充 `entity_graph.yaml`；已有实体不会被修改。首次启用或批量补充前建议备份现有图谱
- `--check` 应在 `--audit` 之前运行，作为快速健康检查
- `--merge` 的接口设计有历史包袱：必须传一个参数值，但实际 source 由 `--id` 指定

---

## Topic 分类定义

| Topic | 含义 | 示例场景 |
|-------|------|----------|
| `work` | 工作/职业 | 项目进展、会议、职业发展 |
| `learn` | 学习/成长 | 读书笔记、课程学习、技能提升 |
| `health` | 健康/身体 | 运动、饮食、体检、医疗 |
| `relation` | 关系/社交 | 家人、朋友、社交活动 |
| `think` | 思考/反思 | 人生感悟、决策思考、复盘 |
| `create` | 创作/产出 | 文章、代码、设计作品 |
| `life` | 生活/日常 | 日常琐事、娱乐、购物 |

---

## 配置文件

配置文件位置：`~/Documents/Life-Index/.life-index/config.yaml`

详见 [config.example.yaml](../config.example.yaml)

### 当前与 onboarding customization 相关的配置说明

- 用户可在 `config.yaml` 中记录 `defaults.location`
- onboarding agent 可在安装完成后的 optional customization step 中写入该偏好
- 但是否被当前运行时写入链路自动消费，应以实际验证结果为准；Agent 不得在未验证时声称其已生效

---

## dev helper: run_with_temp_data_dir

### 端点

```bash
python -m tools.dev.run_with_temp_data_dir [--seed] [--for-web] [--name LABEL] [--cleanup-now] [--json]
```

### 用途

- 为手工调试 / Web GUI 验收创建隔离的临时 `LIFE_INDEX_DATA_DIR`
- `--seed` 表示先复制当前真实用户数据，再基于副本做仿真验收
- `--for-web` 表示输出 Web GUI 验收模式所需的启动提示、清单与验收后建议

### 关键结构化输出字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `temp_root` | string | 临时沙盒根目录 |
| `data_dir` | string | 实际注入 `LIFE_INDEX_DATA_DIR` 的目录 |
| `source_data_dir` | string \| null | 当使用 `--seed` 时的数据复制来源 |
| `seeded` | boolean | 是否复制了真实用户数据 |
| `for_web` | boolean | 是否处于 Web GUI 验收模式 |
| `readonly_simulation` | boolean | `--for-web --seed` 时为 `true`，表示复制数据后的只读仿真验收，不会回写真实用户目录 |
| `mode` | string | 当前模式；典型值：`generic` / `web_acceptance` |
| `serve_command` | string | 推荐的 `life-index serve` 启动命令 |
| `browser_url` | string | 推荐打开的浏览器地址 |
| `safe_to_delete_after` | boolean | 当前临时沙盒在验收完成后是否可安全删除 |
| `shell_snippet` | string | 可直接复用的启动 shell 片段 |
| `acceptance_checklist` | string[] | Web GUI 验收建议检查项 |
| `post_acceptance_actions` | string[] | 验收后的建议动作 |
| `next_steps` | string[] | 调用 helper 后建议按顺序执行的下一步 |
| `cleanup_command` | string | 建议的临时沙盒清理命令 |
| `summary` | object | 创建 / seeded / cleaned 统计 |

### Agent / 开发者使用约定

- 手工 Web GUI 验收优先使用：`python -m tools.dev.run_with_temp_data_dir --for-web`
- 若要基于当前真实数据做仿真验收，使用：`python -m tools.dev.run_with_temp_data_dir --for-web --seed`
- `--for-web --seed` **不会回写真实用户目录**；如需保留变更，必须人工确认后再迁回

---

## CLI version / bootstrap authority

### 端点

```bash
life-index --version
life-index version
```

### 用途

- 暴露当前已安装 package version
- 暴露当前 checkout 所携带的 `bootstrap-manifest.json`
- 供 onboarding / upgrade / repair 流程做 freshness gate 使用

### 返回值

```json
{
  "package_version": "1.0.0",
  "bootstrap_manifest": {
    "repo_version": "1.0.0",
    "onboarding_schema_version": "2.0",
    "manifest_schema": 1,
    "requires_checkout_sync": true,
    "target_ref": "main",
    "release_channel": "stable",
    "required_authority_docs": [
      "bootstrap-manifest.json",
      "AGENT_ONBOARDING.md",
      "AGENT_ONBOARDING_WEB.md",
      "SKILL.md",
      "docs/API.md",
      "docs/PRODUCT_BOUNDARY.md",
      "tools/lib/AGENTS.md",
      "docs/UPGRADE.md",
      "README.md"
    ]
  }
}
```

### 说明

- `life-index health` 只回答运行时健康，不回答 checkout freshness
- `life-index --version` 用于 freshness / authority 校验
- onboarding agent 不得用 `health` 替代 `--version` / manifest freshness gate

---

## Web runtime freshness fields

### `/api/health`

- `status`
- `version`
- `bootstrap_manifest`
- `runtime`

### `/api/runtime`

- `package_version`
- `bootstrap_manifest`
- `user_data_dir`
- `journals_dir`
- `life_index_data_dir_override`
- `readonly_simulation`

### 说明

- `/api/health` 与 `/api/runtime` 现在都可用于 Web onboarding / acceptance 时确认运行实例对应的 package version 与 bootstrap authority

---

## Round 6 新增能力

### `life-index migrate` — Schema 迁移工具

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `--dry-run` | flag | true | 扫描并报告，不修改文件 |
| `--apply` | flag | false | 执行确定性迁移 |
| `--version` | int | latest | 目标 schema 版本 |
| `--json` | flag | true | JSON 输出 |

**dry-run 输出**：

```json
{
  "total_scanned": 42,
  "version_distribution": {"1": 5, "2": 37},
  "needs_migration": 5,
  "outdated_files": [{"path": "...", "current_version": 2, "removed_fields": ["sentiment_score", "themes"]}]
}
```

**apply 输出**：

```json
{
  "migrated_count": 5,
  "already_current": 37,
  "failed_count": 0,
  "failed_files": [],
  "needs_agent": [{"path": "...", "items": ["abstract/summary missing — needs Agent extraction"]}],
  "deterministic_changes": [{"path": "...", "changes": ["removed sentiment_score", "removed themes"]}]
}
```

**错误码**：E0800（迁移路径不存在）、E0801（文件解析失败）、E0802（迁移执行失败）、E0803（文件写入失败）

### `life-index entity` — 实体图谱管理

Entity 管理工具在 Round 6 引入，现已成为独立一级命令。完整参数、操作模式、返回值结构和 Agent 约束见上文 `## entity` 章节。

### Response: `events` 字段

所有 CLI 命令的 JSON 响应均可包含 `events` 字段（搭便车事件通知）。

| 事件类型 | 触发条件 | 严重级 |
|---------|---------|--------|
| `no_journal_streak` | 连续 7+ 天未记日志 | info |
| `monthly_review_due` | 上月 report 文件缺失 | info |
| `entity_audit_due` | entity_graph.yaml 30+ 天未修改 | low |
| `schema_migration_available` | 存在旧 schema 版本日志 | info |
| `index_stale` | 日志比索引更新 | low |

### Response: `_trace` 字段

运行时诊断数据（下划线前缀表示内部字段）。

```json
{
  "_trace": {
    "trace_id": "a1b2c3d4",
    "command": "write",
    "total_ms": 1823.5,
    "steps": [
      {"step": "write_journal", "ms": 1340.2, "status": "ok"},
      {"step": "auto_index", "ms": 483.3, "status": "degraded", "detail": "vector index skipped"}
    ]
  }
}
```
- agent 仍需区分：runtime health ≠ checkout freshness；但 runtime API 现在会显式暴露 freshness 相关元数据
