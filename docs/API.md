# Life Index API 规范

> **本文档职责**: 工具接口规范 SSOT，所有工具的参数、返回值、错误码定义
> **目标读者**: Agent、开发者
> **SSOT 引用**: SKILL.md、AGENTS.md 应引用本文档，不重复定义参数

---

## 通用规范

### 模块消费稳定契约（CHARTER §1.10）

Life Index CLI 向 L3/L4 模块提供**确定性、稳定、可组合的基础能力**。模块消费者可依赖以下四维契约：

| 维度 | 说明 | 稳定性承诺 |
|------|------|-----------|
| **JSON Shape** | 返回结构的顶层字段名称与类型；错误返回统一包含 `success` / `error`，成功返回采用工具自定义顶层字段 + `error: null` | 稳定：字段名称与顶层结构不变，不假设统一 `data` wrapper |
| **字段语义** | 每个字段的精确含义与枚举值 | 稳定：语义不变，允许新增字段 |
| **错误码** | `E{module}{type}` 分类与 `recovery_strategy` 语义 | 稳定：已有错误码不退化，允许新增 |
| **关键 SLO** | 核心延迟与质量指标 | 稳定：不恶化 ≥3%（退化 ≥3% 需附 RFC） |

**关键 SLO 基准**（CHARTER §4.5）：

| 指标 | 目标 | 基线 |
|------|------|------|
| `search` p95 延迟 | ≤ 500ms | ~20ms (keyword-only) |
| `smart-search` 默认路径 p95 | ≤ 8s | 降级模式 ≤ 500ms |
| Gold Set Recall@5 | ≥ 最新冻结基线 | 见 `tests/eval/baselines/` 最新冻结 baseline |
| Gold Set P@5 | ≥ 最新冻结基线 | 见 `tests/eval/baselines/` 最新冻结 baseline |
| Gold Set MRR@5 | ≥ 最新冻结基线 | 见 `tests/eval/baselines/` 最新冻结 baseline |

> Round 17 冻结基线（keyword-only, 85 queries）：Recall@5=0.3836 / P@5=0.3565 / MRR@5=0.2716 仅作为**历史地板**参考。当前回归门控应以 `tests/eval/baselines/` 中最新冻结 baseline 为准，详见 CHARTER §4.5。

**模块消费约束**：
- 模块应通过 CLI JSON-in/JSON-out 或 `tools.*` 公开 API 消费 L2 基元
- 模块不得假设 CLI core 内部实现细节（如 SQLite 表结构、向量索引格式、jieba 配置）
- 模块不得绕过 CLI 直接读写 `~/Documents/Life-Index/` 下的用户数据文件
- 模块-local 过程状态（cursor、checkpoint、中间产物）应存放在模块自己的物理目录，不进入用户数据目录

面向未来高级模块的开发者契约见
[`RFC-2026-05-15: Advanced Module Developer Contract`](./rfc/RFC-2026-05-15-advanced-module-developer-contract.md)。

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
| Web | E07xx | Web GUI / URL 下载 / LLM 提供方 / 地理定位相关错误 |
| 迁移 | E08xx | **Reserved / 未实现** — Schema 迁移错误码已预留，但当前 runtime 不发射结构化 E08xx 码 |

## v1.1.1 Observability Contract

> **适用版本**: v1.1.1+
> **范围**: Phase A (Sub-PRD-1) — provenance envelope、step diagnostics、cache version governance

Phase A 为 JSON 输出生成命令引入三层可观测性契约，全部 additive，不破坏 v1.1.0 客户端兼容。

### Provenance Envelope

六个生成 JSON 的命令在输出顶层附加 `schema_version` 与 `provenance` 字段：

| 命令 | `generator` 值 | 备注 |
|------|---------------|------|
| `search` | `search` | 取代旧 `schema_version: "m16.search.v0"` |
| `index` | `index` | 取代旧 `schema_version: "m16.index.v0"`（若存在） |
| `eval` | `eval` | 新增 |
| `entity` | `entity` | 取代旧 `schema_version: "m16.entity.v0"` |
| `maintenance` | `maintenance` | 取代旧 `schema_version: "m16.maintenance.v0"` |
| `trajectory` | `trajectory` | 取代旧 `schema_version: "m26.trajectory.v0"` |

**顶层字段**：

```json
{
  "schema_version": "v1.1.1",
  "provenance": {
    "source_hash": "sha256:abc...",
    "tool_version": "1.1.1",
    "generated_at": "2026-05-23T10:00:00+00:00",
    "generator": "search|index|eval|entity|maintenance|trajectory",
    "params_hash": "sha256:def...",
    "fixture_version": null
  }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `schema_version` | string | 固定为 `"v1.1.1"` |
| `provenance.source_hash` | string | 输入数据稳定 SHA-256（journal + entity_graph + 配置） |
| `provenance.tool_version` | string | Life Index package 版本（来自 `pyproject.toml`） |
| `provenance.generated_at` | string | ISO 8601 UTC 时间戳 |
| `provenance.generator` | string enum | 生成该输出的命令标识 |
| `provenance.params_hash` | string | 命令参数集稳定 SHA-256（时间相关 flag 除外） |
| `provenance.fixture_version` | string \| null | 仅 `eval` 使用，标识 eval baseline fixture 版本 |

**兼容策略**: v1.1.0 客户端可安全忽略未知顶层字段；字段语义 additive-only。

### Step Diagnostics (`--explain`)

`search --explain`、`smart-search --explain`、`index --explain` 在输出顶层附加 `diagnostics` 字段：

```json
{
  "diagnostics": {
    "input_count": 1234,
    "filter_drops": {},
    "cache_hits": 800,
    "cache_misses": 400,
    "latency_ms": {
      "total": 45
    },
    "fallback_path": null
  }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `input_count` | int | 输入候选总数 |
| `filter_drops` | object | 过滤丢弃统计（当前保留为空对象占位） |
| `cache_hits` | int | 缓存命中数 |
| `cache_misses` | int | 缓存未命中数 |
| `latency_ms` | object | 各阶段耗时（键因命令而异） |
| `fallback_path` | string \| null | 降级路径标识，如 `"semantic"` |

**边界**: `diagnostics` 仅 `--explain` 请求时出现；不 `--explain` 时不存在。`latency_ms` 子键集合可能扩展，消费者应容忍未知键。

### Cache Version Governance

新增文件 `.life-index/cache/_version.json`：

```json
{
  "schema_version": "v1.1.1",
  "tool_version": "1.1.1",
  "created_at": "2026-05-23T10:00:00+00:00",
  "source_hash": "sha256:...",
  "invalidation_history": []
}
```

**CLI 入口**：

| 命令 | 行为 | 副作用 |
|------|------|--------|
| `index --cache-dry-run` | 评估当前 cache 是否需要重建，返回 `would_rebuild` / `reasons` | **零写入** |
| `health --cache-audit --json` | 返回 cache 版本只读审计状态 | **零写入** |

**失效策略**: `source_hash` mismatch 或 `schema_version` mismatch → 建议全量重建；cache 为派生产物，重建无损，不做 migration。

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
| E0005 | 文件锁获取超时 | retry |
| E0006 | 文件锁获取失败 | retry |

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
| E0504 | 修改地点时缺少天气 | ask_user |

### 索引模块 (E06xx)

| 代码 | 说明 | 恢复策略 |
|------|------|----------|
| E0600 | 索引构建失败 | fail |
| E0601 | 索引损坏 | fail |
| E0602 | 向量存储错误 | continue |
| E0603 | FTS 索引错误 | continue |

### Web 模块 (E07xx)

| 代码 | 说明 | 恢复策略 |
|------|------|----------|
| E0700 | Web GUI 通用错误 | ask_user |
| E0701 | URL 附件下载失败 | skip_optional |
| E0702 | URL 文件类型被拒绝 | ask_user |
| E0703 | 所有 LLM 提供方不可用 | skip_optional |
| E0704 | LLM 元数据提取失败 | skip_optional |
| E0705 | 浏览器地理定位失败 | skip_optional |
| E0706 | Nominatim 反向地理编码失败 | skip_optional |
| E0707 | Web GUI 依赖未安装 | fail |

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
| topic | array | ❌ | 调用方补齐 | 主题分类（7类之一）；LLM 提炼需显式 opt-in |
| project | string | ❌ | "" | 关联项目 |
| tags | array | ❌ | [] | 标签 |
| summary | string | ❌ | 调用方补齐 | 摘要（≤100字，**Agent生成**）；`abstract` 为向后兼容别名 |
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

<!-- M16-CONTRACT: search -->

### M16 Public JSON Contract: search

#### JSON Shape / Top-Level Fields

| Field | Type | Always Present | Description |
|-------|------|----------------|-------------|
| `success` | bool | yes | Whether the search executed successfully |
| `schema_version` | string | yes | `"v1.1.1"` — top-level output schema version (replaces `m16.search.v0`) |
| `provenance` | object | yes | Provenance envelope；详见 [v1.1.1 Observability Contract](#v111-observability-contract) |
| `diagnostics` | object | no | 仅 `--explain` 时出现；详见 [v1.1.1 Observability Contract](#v111-observability-contract) |
| `query_params` | object | yes | Echo of all input parameters |
| `merged_results` | array | yes | Unified result list across all levels |
| `l1_results` | array | yes | Level-1 (index-only) results |
| `l2_results` | array | yes | Level-2 (metadata) results |
| `l3_results` | array | yes | Level-3 (full-text) results |
| `semantic_results` | array | yes | Semantic pipeline results (empty if unavailable) |
| `entity_hints` | array | yes | Entity graph match hints for the query |
| `total_found` | int | yes | Number of results in this response |
| `total_available` | int | yes | Total results available (may exceed page) |
| `has_more` | bool | yes | Whether more results exist beyond current page |
| `semantic_available` | bool | yes | Whether semantic pipeline was available |
| `performance` | object | yes | Timing breakdown (`total_time_ms`, etc.) |
| `warnings` | array | yes | Non-fatal warnings |
| `index_status` | object | yes | Index freshness or pending-writes observability |
| `search_plan` | object\|null | yes | Structured query understanding (Round 11) |
| `ambiguity` | object | yes | Ambiguity signal report |
| `hints` | array | yes | Invocation-time hints (≤5) |
| `semantic_policy` | string | no | Effective semantic policy when applicable |
| `semantic_fallback_used` | string | no | Fallback reason if semantic degraded |
| `semantic_effective_policy` | string | no | Final effective semantic policy |
| `entity_graph_status` | object | no | Entity graph resolution status |

#### Field Semantics

- `success`: retrieval execution success, not "Agent has answered the user". Empty results (`E0303`) are still `success: true`.
- `merged_results`: primary result list consumers should use; items have `path`, `rel_path`, `title`, `date`, `rrf_score`.
- `query_params`: exact echo of all CLI inputs, including defaults filled in.
- `performance.total_time_ms`: end-to-end search wall-clock time in milliseconds.
- `index_status`: two mutually exclusive paths — `freshness` (no pending writes) or `pending_before_search`/`auto_updated`/`pending_consumed` (writes in queue).
- `search_plan.intent_type`: `recall` / `count` / `compare` / `summarize` / `unknown`.
- `ambiguity.has_ambiguity`: signal only; Agent decides final interpretation.

#### Error Behavior / Error Codes

Errors use the structured unified format: `{success: false, error: {code, message, details, recovery_strategy}}`.

| Code | Meaning | Recovery Strategy |
|------|---------|-------------------|
| E0300 | Index does not exist | continue |
| E0301 | Search failed | fail |
| E0302 | Query is empty | ask_user |
| E0303 | No results | continue_empty |

Note: `E0303` / empty results indicate successful execution with no matches; callers must not treat this as a search failure.

#### SLO / Performance Expectation

- **p95 latency ≤ 500ms** (keyword-only path). Baseline: ~20ms.
- SLO is a monitoring target, not a unit-test gate.

#### schema_version Policy

`search` emits a top-level `schema_version` field set to `"m16.search.v0"`. Schema versioning remains additive-only in sub-structures:
- `evidence_pack.schema_version = "1.0.0"` (when `--include-evidence` used on smart-search, which internally calls search).
- Top-level field names and types are stable; new fields may be added without a version bump.
- A `schema_version` bump will accompany any backward-incompatible change.

<!-- /M16-CONTRACT -->

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
| --no-index | flag | ❌ | false | 禁用 FTS 索引（默认启用 FTS） |
| --no-semantic | flag | ❌ | false | 禁用语义搜索（默认启用） |
| --semantic-policy | enum | ❌ | fallback | 语义搜索策略: fallback=仅零结果时启用, hybrid=并行融合 |
| --semantic-weight | float | ❌ | 1.0 | 语义搜索权重 (默认: 1.0) |
| --fts-weight | float | ❌ | 1.0 | FTS 搜索权重 (默认: 1.0) |
| --limit | int | ❌ | 20 | 返回结果数量限制；显式传入时覆盖默认截断 |
| --offset | int | ❌ | 0 | 结果偏移量（分页起始位置） |
| --read-top | int | ❌ | 0 | 读取前 N 条结果的完整正文（默认 0 不读取） |
| --explain | flag | ❌ | false | 输出搜索评分详情与 `diagnostics` 诊断块 |
| --diagnose | flag | ❌ | false | 输出最近搜索行为诊断摘要并退出 |
| --diagnose-days | int | ❌ | 7 | 诊断回看天数 |
| --enable-source-tier | flag | ❌ | false | 启用 source-tier 排名加权（gbrain Phase B）。开启后，搜索结果会按文档 frontmatter 丰富度（topic/people/tags/related_entries）进行额外加权；默认关闭以保持行为不变 |
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

### `index_status` — 索引状态可观测性

搜索返回值包含 `index_status` 字段，提供索引更新状态的机读信号。存在两条互斥路径：

#### No-pending freshness 路径（无待消费写入）

当 pending 队列为空时，`index_status` 包含 `freshness` 子字段：

```json
{
  "index_status": {
    "freshness": {
      "fts_fresh": true,
      "vector_fresh": true,
      "overall_fresh": true,
      "issues": []
    }
  }
}
```

- `freshness`：`check_full_freshness()` 的完整报告
- `auto_updated`：若索引 stale 触发了增量构建，为 `true`；否则为 `false`（仅 stale 时出现）

#### Pending-writes 路径（有待消费写入）

当 pending 队列非空时，`index_status` 包含 pending 可观测性字段：

```json
{
  "index_status": {
    "pending_before_search": true,
    "auto_updated": true,
    "pending_consumed": true
  },
  "pending_consumed": true
}
```

| 子字段 | 类型 | 成功值 | 失败值 | 说明 |
|--------|------|--------|--------|------|
| `pending_before_search` | bool | `true` | `true` | 搜索开始时 pending 队列非空。此字段仅在该路径存在，值**始终为 `true`**（成功/失败均不变） |
| `auto_updated` | bool | `true` | `false` | 增量索引构建是否成功执行 |
| `pending_consumed` | bool | `true` | `false` | pending 队列是否已清空 |

- 顶层 `pending_consumed`（bool）同时保留，作为向后兼容的快速判断字段
- 构建失败时，`warnings` 数组中追加 `pending_index_update_failed: {error}` 条目，pending 队列保留以供下次搜索重试

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

<!-- M16-CONTRACT: smart-search -->

### M16 Public JSON Contract: smart-search

#### JSON Shape / Top-Level Fields

| Field | Type | Always Present | Description |
|-------|------|----------------|-------------|
| `success` | bool | yes | Whether the search executed successfully |
| `schema_version` | string | yes | `"m16.smart_search.v0"` — top-level output schema version |
| `query` | string | yes | User's original query |
| `rewritten_query` | string | yes | LLM-rewritten query (equals original in degraded mode) |
| `filtered_results` | array | yes | LLM post-filtered results (or raw results in degraded mode) |
| `summary` | string | yes | LLM-generated 2-3 sentence summary (empty in degraded mode) |
| `citations` | array | yes | Document title list from LLM filtering |
| `agent_decisions_summary` | string | conditional | Summary string when `--explain` not passed |
| `agent_decisions` | array | conditional | Detailed decision list when `--explain` passed |
| `agent_unavailable` | bool | yes | `true` when LLM is unavailable (degraded mode) |
| `diagnostics` | object | no | 仅 `--explain` 时出现；确定性诊断块，详见 [v1.1.1 Observability Contract](#v111-observability-contract) |
| `performance` | object | yes | Timing breakdown (`total_time_ms`, conditional sub-fields) |
| `answer` | object | no | Additive: synthesized answer with trust-gate fields |
| `evidence_pack` | object | no | Additive: retrieval evidence (requires `--include-evidence`) |
| `aggregate_result` | object | no | Additive: deterministic aggregate output when aggregate intent detected |
| `events` | array | no | Piggyback event notifications |

#### Field Semantics

- `success`: retrieval execution success. Evidence pack or answer synthesis failure does not affect this.
- `filtered_results`: primary result list for consumers. Items have `title`, `path`, `date`, `rrf_score`.
- `agent_unavailable`: diagnostic signal; UI should infer degraded state from `answer`/`summary` presence.
- `performance`: non-stable; sub-fields may expand. Consumers should tolerate unknown keys.
- `answer.confidence`: trust-gate calibrated (not LLM self-assessment). Values: `high` / `medium` / `low`.
- `aggregate_result`: computed by `tools.aggregate.core.run_aggregate`; LLM never computes counts.

#### Error Behavior / Error Codes

Errors use the structured unified format: `{success: false, error: {code, message, details, recovery_strategy}}`.

Evidence pack uses best-effort failure: `success: true`, no `evidence_pack`, but `performance.evidence_build_ms` and `performance.evidence_error` present.

#### SLO / Performance Expectation

- **Default path p95 ≤ 8s**. Degraded mode p95 ≤ 500ms.
- SLO is a monitoring target, not a unit-test gate.

#### schema_version Policy

`smart-search` emits a top-level `schema_version` field set to `"m16.smart_search.v0"`. Schema versioning is additive-only:
- `evidence_pack.schema_version = "1.0.0"` (when `--include-evidence` is used).
- Top-level field names and types are stable; new fields may be added without a version bump.
- A `schema_version` bump will accompany any backward-incompatible change.

<!-- /M16-CONTRACT -->

### 端点

```bash
life-index smart-search --query "..." [options]
python -m tools.smart_search --query "..." [options]
```

### 参数

| 名称 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| query | string | ✅ | - | 自然语言搜索查询 |
| use-llm | flag | ❌ | false | 显式启用 LLM 编排（query rewrite / filter / summary / synthesis） |
| no-llm | flag | ❌ | false | 向后兼容 no-op；默认已是纯确定性模式 |
| explain | flag | ❌ | false | 在输出中包含 Agent 决策详情与 `diagnostics` 诊断块 |
| include-evidence | flag | ❌ | false | 在输出中包含 evidence pack |
| format-entity-annotated | flag | ❌ | false | 与 `--include-evidence` 同用时，增加人类可读的 `formatted_evidence` |
| synthesize | flag | ❌ | false | 生成引用支撑的自然语言答案（需要 `--use-llm`） |

### 返回值

**默认输出**（无额外标志）：

```json
{
  "success": true,
  "query": "我和女儿之间有哪些珍贵的回忆？",
  "rewritten_query": "我和女儿之间有哪些珍贵的回忆？",
  "filtered_results": [
    {"title": "...", "path": "...", "date": "...", "rrf_score": 0.85}
  ],
  "summary": "Found 3 journal entries about memories with your daughter.",
  "citations": ["女儿生日", "亲子时光"],
  "agent_decisions_summary": "3 decisions made",
  "agent_unavailable": false,
  "performance": {
    "total_time_ms": 142.5,
    "rewrite_time_ms": 30.0,
    "filter_time_ms": 50.0,
    "search_time_ms": 45.0,
    "total_available": 3
  }
}
```

#### 默认输出字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `success` | bool | 搜索是否成功执行 |
| `query` | string | 用户原始查询 |
| `rewritten_query` | string | LLM 改写后的查询（降级模式下等于原始查询） |
| `filtered_results` | list[dict] | LLM 后置筛选的结果列表（降级模式下为原始检索结果） |
| `summary` | string | LLM 生成的 2-3 句结果摘要（降级模式下为空） |
| `citations` | list[string] | LLM 筛选阶段返回的文档标题列表 |
| `agent_decisions_summary` | string | CLI 默认输出的 Agent 决策数量摘要；传递 `--explain` 时替换为 `agent_decisions` |
| `agent_unavailable` | bool | `true` 表示 LLM 不可用，搜索已降级为纯双管道模式 |
| `performance` | object | 性能指标（详见下方 `performance` 子字段表） |

#### `--explain` 输出变化

当传递 `--explain` 时，`agent_decisions_summary`（string）被替换为 `agent_decisions`（list[dict]），包含每个 LLM 决策阶段的详细记录。未传递 `--explain` 时，输出包含 `agent_decisions_summary`（如 `"3 decisions made"`），不含 `agent_decisions`。

#### `performance` 子字段

| 子字段 | 类型 | 条件 | 说明 |
|--------|------|------|------|
| `total_time_ms` | float | 始终 | 总搜索耗时（毫秒） |
| `rewrite_time_ms` | float | LLM 改写发生时 | 查询改写阶段耗时 |
| `filter_time_ms` | float | LLM 后筛发生时 | 后置筛选阶段耗时 |
| `search_time_ms` | float | 始终 | 底层检索耗时 |
| `total_available` | int | 始终 | 检索到的总结果数 |
| `evidence_build_ms` | float | evidence 构建尝试时（`--include-evidence` 或 `--synthesize`） | Evidence pack 构建耗时 |
| `evidence_error` | string | evidence 构建失败且 `--include-evidence` 时 | 构建失败错误信息 |
| `synthesis_ms` | float | 答案合成尝试时（`--synthesize`） | 答案合成耗时 |

> **稳定性说明**: `performance` 子字段集合可能在未来扩展。调用方应容忍未知键。

#### Consumer Guidance（字段消费指引）

| 字段 | Agent 消费者 | GUI 消费者 | 稳定性 |
|------|-------------|-----------|--------|
| `success` | 必须检查 | 必须检查 | **stable** |
| `query` | 引用 | 展示 | **stable** |
| `filtered_results` | 主要结果 | 展示 | **stable** |
| `summary` | 可读摘要 | 展示 | **stable** |
| `citations` | 引用来源 | 可点击链接 | **stable** |
| `answer` / `answer.*` | 优先展示 | 优先展示 | **stable** |
| `evidence_pack` | 按需 | 按需 | **stable** |
| `formatted_evidence` | 可展示 | 可展示 | **stable additive** — 仅 `--include-evidence --format-entity-annotated` 时出现 |
| `aggregate_result` | aggregate/count/trend queries | aggregate/count/trend display | **stable additive** - deterministic `aggregate` result; LLM never computes counts |
| `evidence_pack.items[].entity_matches` | 按需 | 按需 | **stable**，实体匹配溯源；消费者应容忍缺失字段 |
| `rewritten_query` | 不需要 | 不需要 | **internal** — LLM 改写产物，消费者应使用 `query` |
| `agent_unavailable` | 不需要 | 不需要 | **internal** — 诊断信号，UI 应从 `answer`/`summary` 存在性推断 |
| `agent_decisions_summary` | 不需要 | 不需要 | **internal** — 仅调试用 |
| `agent_decisions` | 不需要 | 不需要 | **internal** — 仅 `--explain` 时出现 |
| `performance.*` | 不需要 | 可选（高级） | **non-stable** — 性能分析用，子字段可能扩展 |

> **稳定性定义**: `stable` = 字段语义承诺不变；`internal` = 仅用于调试/诊断，可能在未来移除或改名；`non-stable` = 子字段集合可能扩展，消费者应容忍未知键。

### 说明

- 默认不启用 LLM；传递 `--use-llm` 后，`SmartSearchOrchestrator` 执行三段式 LLM 编排：前置改写 → 中间调用 search 原语 → 后置筛选 + 摘要
- Clear aggregate/count/trend intents may short-circuit into deterministic `aggregate` and add top-level `aggregate_result`; existing smart-search fields remain present.
- `aggregate_result` is computed by `tools.aggregate.core.run_aggregate`; LLM must not compute the count.
- 默认模式、`--no-llm`、或 `--use-llm` 但 LLM 不可用时，`agent_unavailable: true`，等价于确定性检索结果
- Data Minimization：候选仅送 title + abstract + snippet（≤200 chars），最多 15 条
- 实现详见 `docs/ARCHITECTURE.md` §5.8

### Aggregate Result（`aggregate_result`）

当 `smart-search` 通过确定性路由检测到 aggregate/count/trend 意图时（如 "过去60天我有多少天晚睡" 或 "统计一下我今年写日志的频率趋势"），返回值增加顶层 `aggregate_result` 字段。

> **确定性路由**: 路由使用正则模式匹配，不依赖 LLM。`tools.aggregate.core.run_aggregate` 是唯一的计算器。LLM 永远不计算计数。

`aggregate_result` 的值是 `run_aggregate` 的完整输出，包含 `command`、`unit`、`range`、`predicate`、`result`（含 `count`、`denominator`、`exactness`、`confidence`）、`buckets`、`matched_entries`、`excluded_entries`、`unknown_entries`、`evidence_paths`、`limitations`、`performance`、`claim_envelope`、`evidence_pack`。

#### 当前支持的自动路由模式

| 模式 | 匹配条件 | 路由到 |
|------|----------|--------|
| 晚睡计数 | "过去N天" + 聚合信号（多少/统计/count） + "晚睡" | `unit=day`, `predicate=entry_time_after=22:00`, `range=<anchor-N+1>..<anchor>` |
| 写日志频率趋势 | "今年" + 写日志关键词 + 聚合信号（频率/趋势/统计） | `unit=month`, `predicate=journal_count`, `range=<year-01-01>..<anchor>` |

> `LIFE_INDEX_TIME_ANCHOR=YYYY-MM-DD` 环境变量用于覆盖当前日期锚点（测试用）。未设置时使用 `date.today()`。

#### Additive 契约

- `aggregate_result` 是**纯增量的**：不存在时不影响现有字段
- 所有现有 smart-search 必需字段（`success`、`query`、`filtered_results` 等）始终保留
- 非 aggregate 意图的查询**不会**包含 `aggregate_result`
- `aggregate_result` 出现时，smart-search 短路到 deterministic aggregate；normal search 不执行，但既有输出字段仍以空列表/空字符串形式保留
- `aggregate_result.claim_envelope` 与 `aggregate_result.evidence_pack` 是 additive 子字段；它们不表示完整 Index Tree API 或 batch/cursor 平台已经实现

### Evidence Pack（`--include-evidence`）

默认行为（不传递 `--include-evidence`）下，返回值**不包含** `evidence_pack` 字段。

当传递 `--include-evidence` 时，返回值增加 `evidence_pack` 字段，结构如下：

| 字段 | 类型 | 说明 |
|------|------|------|
| `evidence_pack.query_context` | object | 查询上下文，含 `query`、`expanded_query`、`search_plan`、`entity_hints` |
| `evidence_pack.items` | array | 检索证据项列表，每项含 `document`（文档引用）、`scores`（评分明细）、`snippet`（片段）、`entity_matches`（实体匹配溯源，仅匹配时出现） |
| `evidence_pack.semantic_candidates` | array | 纯语义候选列表（未进入主结果集的语义召回项） |
| `evidence_pack.total_available` | int | 总可用结果数 |
| `evidence_pack.has_more` | bool | 是否还有更多结果 |
| `evidence_pack.no_confident_match` | bool | **检索层级信号**：底层搜索管道是否未找到高置信度匹配。这是检索质量指标，不是答案质量信号。调用方不应将其等同于 `answer.confidence` 的判断依据 |
| `evidence_pack.diagnostics` | object | **确定性检索诊断**。不依赖 LLM，从已有搜索结果字段推导。详见下方 Diagnostics 子节 |
| `evidence_pack.schema_version` | string | 证据包 schema 版本。当前为 `"1.0.0"`。旧 payload 反序列化时默认 `"1.0.0"` |
| `performance.evidence_build_ms` | float | evidence pack 构建耗时（毫秒） |

> **Forward-compatibility**: Evidence pack 的每个对象可能包含未在本文档中列出的额外字段（来自内部 `extra` 字典）。调用方应容忍未知字段，不应做严格 schema 校验。所有 9 个内部 dataclass（`ScoreBreakdown`、`DocumentRef`、`EntityMatch`、`EvidenceItem`、`SemanticCandidate`、`QueryContext`、`PipelineComposition`、`EvidenceDiagnostics`、`EvidencePack`）均携带 `extra` 字典；`from_dict()` 将未知键保留到 `extra`，`to_dict()` 将其重新发出。这提供了零开销的前向兼容机制。

#### Validation Behavior

`tools/evidence/types.py` 提供可选的 `validate_evidence_pack(pack: EvidencePack) -> None` 校验函数。

- 调用方可选择在消费前调用，以拒绝无效域值。
- 无效值（如不在已知集合中的 `confidence`、`provenance`、`retrieval_outcome`、`primary_pipeline`）抛出 `ValueError`。
- 当前闭合集合：`confidence` = `high` / `medium` / `low`；`provenance` = `keyword` / `semantic` / `hybrid`；`retrieval_outcome` = `ok` / `weak_results` / `no_confident_match` / `zero_results`；`primary_pipeline` = `none` / `fts` / `semantic` / `hybrid`。
- 未知 `schema_version` 发出 `UserWarning`，**不**抛出异常，以保留前向兼容。
- `extra` 字典中的字段完全绕过校验，不检查、不丢弃、不修改。
- 校验不修改输入对象。

#### Diagnostics（`evidence_pack.diagnostics`）

当 `--include-evidence` 请求 evidence pack 时，`diagnostics` 字段始终存在。纯确定性推导，不调用 LLM、不访问文件系统、不触发额外搜索。

**字段结构：**

| 子字段 | 类型 | 说明 |
|--------|------|------|
| `retrieval_outcome` | string enum | 检索质量分类（见下表） |
| `outcome_reason` | string | 当前分类的具体原因（见下表） |
| `notes` | string[] | 上下文观察（如置信度分布、截断信息）。为空时省略 |
| `suggestions` | string[] | 改善检索的可操作建议。为空时省略 |
| `pipeline_composition` | object | 参与本次检索的管道组成。见下方 Pipeline Composition 子节 |

**`retrieval_outcome` 枚举值：**

| 值 | 含义 | 触发条件 |
|----|------|----------|
| `ok` | 检索正常，有高或中置信度结果 | 至少一个 item confidence 为 `high` 或 `medium` |
| `weak_results` | 有结果但质量较弱 | 全部 low confidence 且 `no_confident_match` 为 false；或 S1-A 语义-only moderate-confidence 场景 |
| `no_confident_match` | 搜索核心标记无高置信匹配 | `no_confident_match` 为 true，且不属于 S1-A 语义-only moderate-confidence 场景 |
| `zero_results` | 无任何检索结果 | `merged_results` 为空 |

**`outcome_reason` 枚举值：**

| 值 | 对应 outcome | 说明 |
|----|-------------|------|
| `confident_results_present` | `ok` | 存在 medium/high 置信度结果 |
| `all_items_low_confidence_full_recall` | `weak_results` | 全部 low，total 等于 items 数（已全量召回） |
| `low_confidence_with_potential_under_recall` | `weak_results` | 全部 low，total > items 数（可能还有更多未召回） |
| `semantic_only_moderate_confidence_no_fts_support` | `weak_results` | S1-A：`no_confident_match` 为 true，但结果全来自语义管道且存在 medium/high confidence，FTS 管道未提供匹配 |
| `all_items_low_confidence` | `no_confident_match` | `no_confident_match` flag 且全部 low |
| `search_core_flagged_no_confident` | `no_confident_match` | `no_confident_match` flag 但存在 medium/high，且非语义-only 场景 |
| `no_matches_found` | `zero_results` | 两个管道均无结果 |
| `results_truncated_before_delivery` | `zero_results` | total_available > 0 但 items 为空 |

> `outcome_reason` 值为描述性文本，可能在不升级 `schema_version` 的情况下扩展。调用方不应将其视为闭合枚举进行严格校验。

**S1-A 分类语义（语义-only moderate-confidence）：**

当搜索核心设置 `no_confident_match=true` 时，诊断层做进一步细分：

- 若所有结果 confidence 均为 `low` → 仍归类为 `no_confident_match`（`all_items_low_confidence`）
- 若存在 `medium`/`high` confidence 结果，且**所有结果均来自语义管道**（无 FTS 支撑）→ 归类为 `weak_results`（`semantic_only_moderate_confidence_no_fts_support`）。这表示结果在语义上相关，但缺乏关键词确认，是可行动的降级状态
- 若存在 `medium`/`high` confidence 结果，且有 FTS 支撑（hybrid 或纯 FTS）→ 仍归类为 `no_confident_match`（`search_core_flagged_no_confident`）

**Pipeline Composition（`pipeline_composition`）：**

| 子字段 | 类型 | 说明 |
|--------|------|------|
| `primary_pipeline` | string enum | `none` / `fts` / `semantic` / `hybrid` |

`primary_pipeline` 的判定规则（从 `merged_results` 的 `source` 字段确定性推导）：

| 值 | 条件 |
|----|------|
| `none` | `merged_results` 为空，或所有 item 的 `source` 均不含 `fts` 或 `semantic` |
| `fts` | 至少一个 item 的 `source` 含 `fts`，且无任何 item 的 `source` 含 `semantic` |
| `semantic` | 至少一个 item 的 `source` 含 `semantic`，且无任何 item 的 `source` 含 `fts` |
| `hybrid` | 至少一个 item 的 `source` 含 `fts`，且至少一个 item 的 `source` 含 `semantic`（含 `fts,semantic` 合并 source） |

**Consumer Guidance（消费指引）：**

| `retrieval_outcome` | Agent 行为 | GUI 行为 |
|---------------------|-----------|----------|
| `ok` | 正常消费 `filtered_results` 和 `answer` | 正常展示结果 |
| `weak_results` | 向用户说明结果置信度较低，建议调整查询；可参考 `suggestions` | 显示弱结果提示，提供 `suggestions` 给用户 |
| `no_confident_match` | 明确告知用户未找到高置信匹配；参考 `suggestions` 建议换词或加过滤 | 显示"未找到精确匹配"提示 |
| `zero_results` | 如实报告无结果；参考 `suggestions` 建议放宽条件 | 显示空结果页面和 `suggestions` |

> `notes` 是观察性描述，`suggestions` 是可操作建议。两者均为 `string[]`；为空时序列化输出可能省略该字段。

**诊断示例（`weak_results`）：**

```json
{
  "evidence_pack": {
    "diagnostics": {
      "retrieval_outcome": "weak_results",
      "outcome_reason": "all_items_low_confidence_full_recall",
      "notes": [
        "All 3 items have low confidence.",
        "total_available equals item count (full recall, weak quality)."
      ],
      "suggestions": [
        "Query may be too vague or match tangential content.",
        "Try adding time range or entity filters."
      ]
    }
  }
}
```

#### Entity Match Provenance（`evidence_pack.items[].entity_matches`）

当 `entity_hints` 中的实体匹配到某个 evidence item 的文本字段时，该 item 会包含 `entity_matches` 数组。未匹配到任何实体的 item 不包含此字段。

**字段结构：**

| 子字段 | 类型 | 说明 |
|--------|------|------|
| `entity_id` | string | 实体唯一标识 |
| `entity_type` | string | 实体类型（如 `person`、`place`、`project`、`event`、`concept`） |
| `matched_terms` | array\<string\> | 匹配到的实体术语（已去重）。来源包括 `entity_hints[].matched_term` 和 `entity_hints[].expansion_terms` 中的别名，仅包含在 item 文本中实际出现的术语 |
| `match_sources` | array\<string\> | 匹配来源字段（如 `title`、`snippet`、`metadata`、`abstract`，已排序去重） |
| `query_matched_term` | string | 可选，原始 query 中触发匹配的术语 |

**特性：**
- 纯确定性推导：从已有 `entity_hints`（含 `matched_term` 和 `expansion_terms`）和搜索结果字段（`title`、`snippet`、`abstract`、`metadata`）推导，不调用 LLM、不访问文件系统
- `matched_terms` 仅包含在 item 文本中实际出现的术语（来自 `matched_term` 或 `expansion_terms`），不会包含未出现的候选词
- `query_matched_term` 始终保留原始 `matched_term`，即使 item 中只匹配到了 `expansion_terms` 里的别名
- 当 `entity_matches` 为空数组时，序列化输出中省略此字段
- 旧 payload（无 `entity_matches`）仍可正常反序列化

**匹配语义（S1-C 实测确认）：**

- **大小写不敏感**：实体图谱查找（`resolve_via_runtime`）、确定性查询扩展（`expand_query_with_entity_graph`、`resolve_query_entities`）以及证据实体匹配溯源（`_build_entity_matches`）均使用大小写归一化进行匹配。`life index` 与 `Life Index` 和 `LIFE INDEX` 等效。原始实体名称/别名在输出（`matched_terms`、`primary_name`、`aliases`）中保留原始大小写
- **ASCII 边界匹配**：ASCII 实体名/别名使用大小写不敏感的字母数字边界匹配；短别名不会匹配到无关单词内部。例如 `LI` 不匹配 `life`，`Ali` 不匹配 `Alibaba` / `Align` / `Ali_note`
- **下划线语义**：`_` 被视为 ASCII word character，因此 `my_LI_project` 不匹配 `LI`。这是为了避免代码式标识符、文件名片段或标签中的短别名误报
- **非 ASCII 子串匹配**：中文等非 ASCII 术语保留子串匹配行为；系统当前不引入中文分词边界。调用方应将极短中文别名视为可能产生误报的高风险别名
- **路径隐私**：Evidence Pack 的 `document.path` 是相对文档引用或被省略；消费者不得依赖绝对文件系统路径，系统也不应通过 `evidence_pack.items[].document.path` 暴露本机绝对路径
- **abstract + metadata 双重归因**：`metadata.abstract`（或 `metadata.summary`）的文本同时出现在 `abstract` 和 `metadata` 两个来源字段中，导致 `match_sources` 可能包含 `["abstract", "metadata"]` 双重归因。这是确定性文本扫描的正常结果，不代表独立匹配
- **`metadata` 源聚合**：`metadata` 源字段由 frontmatter 中所有字符串值（含列表元素）拼接而成，覆盖 `location`、`weather`、`people`、`tags` 等全部元数据字段

#### 最佳努力失败行为

Evidence pack 采用**最佳努力（best-effort）**策略：

- 若 evidence 构建失败，搜索本身仍返回 `success: true`
- 返回值**不携带** `evidence_pack` 字段
- `performance` 中记录 `evidence_build_ms` 和 `evidence_error`（错误信息）
- 调用方不应将 `evidence_pack` 缺失等同于搜索失败

### Answer Synthesis（`--synthesize`）

默认行为（不传递 `--synthesize`）下，返回值**不包含** `answer` 字段。

当传递 `--synthesize` 时，若 LLM 可用且搜索结果非空且 LLM 成功生成答案，返回值增加 `answer` 字段，结构如下：

| 字段 | 类型 | 说明 |
|------|------|------|
| `answer.answer_text` | string | 回答用户查询的自然语言文本（2-4 句） |
| `answer.citations` | string[] | 引用的文档相对路径列表（不含绝对路径），经 trust gate 验证 |
| `answer.confidence` | string | 置信度：`high` / `medium` / `low`，经 trust gate 校准（非 LLM 自评） |
| `answer.confidence_reason` | string | 置信度判定原因，由 orchestrator 根据 validated citations 和 evidence context **计算生成**（非 LLM 设定） |
| `answer.limitations` | string[] | 答案局限性列表，由 orchestrator 根据 citation 验证结果**计算生成**（非 LLM 设定） |
| `answer.evidence_summary` | string | 已验证引用的 evidence 摘要（title; source; confidence），无有效引用时为空字符串 |

> **信任边界**: `confidence_reason`、`limitations`、`evidence_summary` 由 orchestrator 在 trust gate 之后根据 validated citations 和 evidence context **计算生成**，LLM 不可直接设定。

**含 `answer` 的返回示例：**

```json
{
  "success": true,
  "query": "我和女儿之间有哪些珍贵的回忆？",
  "rewritten_query": "女儿 珍贵回忆 亲子时光",
  "filtered_results": [...],
  "summary": "...",
  "citations": [],
  "agent_unavailable": false,
  "answer": {
    "answer_text": "日记中记录了多次与女儿相处的珍贵时刻...",
    "citations": ["Journals/2026/03/life-index_2026-03-06_001.md"],
    "confidence": "medium",
    "confidence_reason": "Answer supported by moderate-confidence evidence.",
    "limitations": [],
    "evidence_summary": "女儿生日; source: fts; confidence: medium"
  },
  "performance": {
    "total_time_ms": 250.0,
    "rewrite_time_ms": 30.0,
    "filter_time_ms": 50.0,
    "search_time_ms": 45.0,
    "total_available": 3,
    "evidence_build_ms": 20.0,
    "synthesis_ms": 105.0
  }
}
```

#### 内部 Evidence 消费

当 `--synthesize` 启用时，orchestrator 会**内部构建 EvidencePack**（即使未传 `--include-evidence`），并将其中的 provenance/source/score 以及有界 `entity_matches` 摘要等安全字段注入 synthesis prompt，以提升答案质量。若 evidence 构建失败，synthesis 回退为仅使用 `filtered_results`，不导致搜索失败。

#### Trust Gate（引用验证 + 置信度校准）

LLM 返回的 citations 和 confidence 不会直接透传，而是经过 trust gate 校验：

**引用验证（Citation Validation）：**

- 数字引用（如 `[1]`）映射到当前 `filtered_results` 对应序号的相对路径
- 字符串引用仅当匹配 `filtered_results` 或 evidence context 中的已知相对路径时保留
- 绝对路径始终丢弃
- 不在已知路径集中的字符串引用（幻觉路径）被丢弃
- 若所有引用均无效但 `answer_text` 有效，保留答案但 `citations` 为空、`confidence` 被强制降为 `low`

**置信度校准（Confidence Calibration）：**

- 最终 confidence 不高于 evidence 支撑强度
- 校准规则（按优先级）：
  - 无有效引用 → 最高 `low`
  - 引用的 evidence 包含 `high` confidence → 最高 `high`
  - 引用的 evidence 包含 `medium`（无 high）→ 最高 `medium`
  - 其他情况 → 最高 `low`
- LLM 可以降低 confidence（比 evidence 更保守），但不能提升至 evidence 上限以上
- 无 evidence context 时，有效 `filtered_results` 引用视为弱支撑，最高 `medium`；无有效引用仍为 `low`
- 若 evidence context 存在但为空或未覆盖被引用路径，视为 evidence 已检查但未提供支撑，最高 `low`

#### 合成失败行为

Answer synthesis 采用**最佳努力（best-effort）**策略：

- 若未传 `--use-llm`、或 LLM 初始化失败，`answer` 字段不存在，搜索结果正常返回
- 若搜索结果为空，`answer` 字段不存在
- 若 LLM 返回格式错误或合成过程异常，`answer` 字段不存在，搜索本身不受影响
- 若内部 evidence 构建失败但 synthesis 仍尝试执行：`answer` 仍可能生成（基于 `filtered_results`），不视为搜索失败
- `--synthesize` 不要求 `--include-evidence`；两者独立控制
- `--synthesize` 内部构建 evidence 不等于输出包含 `evidence_pack`；后者仍需 `--include-evidence`

#### 组合标志语义

| 标志组合 | 行为 |
|----------|------|
| （无标志） | 确定性结果；不进行 LLM rewrite/filter/summary |
| `--include-evidence` | 添加 evidence_pack |
| `--use-llm` | 启用 LLM rewrite/filter/summary |
| `--use-llm --synthesize` | 内部构建 evidence；添加 answer（prompt 含 provenance/source/score 以及有界 `entity_matches` 摘要） |
| `--include-evidence --use-llm --synthesize` | 添加 evidence_pack + answer（answer prompt 含 provenance/source/score 以及有界 `entity_matches` 摘要） |
| `--synthesize` 或 `--no-llm --synthesize` | `--synthesize` 静默忽略（无 LLM） |

### Aggregate Delegation（自动聚合路由）

当 smart-search 检测到明确的聚合/计数/趋势意图时，会自动委派给确定性 `aggregate` 原语计算，而非通过 LLM 自由计数。路由为纯确定性模式匹配（无 LLM），发生在正常检索管线之前。

**触发条件（确定性，无 LLM）**：

| 查询模式 | 路由参数 | 示例 |
|----------|----------|------|
| "过去N天" + 聚合信号 + "晚睡/late sleep" | `unit=day`, `predicate=entry_time_after=22:00` | "过去60天我有多少天晚睡" |
| "过去N天" + 聚合信号 + "多少篇/条日志/日记/记录" | `unit=entry`, `predicate=journal_count` | "过去90天有多少篇日志" |
| "过去N天" + 聚合信号 + "多少天写日志/有记录" | `unit=day`, `predicate=journal_count` | "过去90天有多少天写日志" |
| "past/last N days" + "how many/count" + "journal entries/logs" | `unit=entry`, `predicate=journal_count` | "past 30 days how many journal entries" |
| "今年" + "写日志" + 聚合/趋势信号 | `unit=month`, `predicate=journal_count` | "统计一下我今年写日志的频率趋势" |
| "过去N天" + 聚合信号 + 引号词 + "提到/mention" | `unit=entry`, `predicate=term_presence=TERM` | `过去60天有多少次提到"OpenClaw"` |
| "过去N天" + 聚合信号 + 引号词 + "多少天提到" | `unit=day`, `predicate=term_presence=TERM` | `过去60天有多少天提到"OpenClaw"` |
| "past/last N days" + "how many" + 引号词 + "mention" | `unit=entry`, `predicate=term_presence=TERM` | `past 60 days how many entries mention "OpenClaw"` |
| "past/last N days" + "how many days" + 引号词 + "mention" | `unit=day`, `predicate=term_presence=TERM` | `past 60 days how many days mention "OpenClaw"` |
| "今年/this year" + 聚合信号 + 引号词 + "提到/mention" | `unit=entry`, `predicate=term_presence=TERM` | `今年有多少次提到"OpenClaw"` |
| "过去N天" + 聚合信号 + `field=value` or `field:value` | `unit=entry`, `predicate=field_equals=FIELD:VALUE` | "过去60天有多少篇 topic=work 的日志" |
| "过去N天" + 聚合信号 + "多少天" + `field=value` or `field:value` | `unit=day`, `predicate=field_equals=FIELD:VALUE` | "过去60天有多少天 topic=work 的日记" |
| "今年/this year" + 聚合信号 + `field=value` or `field:value` | `unit=entry`, `predicate=field_equals=FIELD:VALUE` | "今年有多少篇 topic=health 的日志" |
| "past/last N days" + "how many/count" + `field=value` or `field:value` | `unit=entry`, `predicate=field_equals=FIELD:VALUE` | "past 30 days count journal entries where topic=work" |
| "past/last N days" + "how many days" + `field=value` or `field:value` | `unit=day`, `predicate=field_equals=FIELD:VALUE` | "past 30 days how many days topic=health journal" |

**委派行为**：

- 使用 `LIFE_INDEX_TIME_ANCHOR=YYYY-MM-DD` 环境变量（若存在）确定时间锚点；否则使用 `date.today()`
- 路由成功时，`aggregate` 为唯一计算器（`tools.aggregate.core.run_aggregate`），不经过 LLM rewrite/filter/synthesis 管线
- 正常检索字段（`filtered_results`、`summary` 等）保留但为空值
- `agent_unavailable` 继续表示 LLM 客户端是否不可用；它不是 aggregate 路由是否跳过 LLM 的标志

**`field_equals` 自动路由限制**：

- 仅支持显式 `field=value` 或 `field:value` 语法（field 必须匹配 `[A-Za-z_][A-Za-z0-9_]*`）；不支持模糊自然语言字段提取
- value 可选地用单引号、双引号或弯引号包围，路由会自动去除引号；未加引号的 value 在第一个空白处结束，加引号的 value 可包含空格
- 不含时间范围（"过去N天" 或 "今年/this year"）的查询不触发 `field_equals` 路由
- 不含聚合信号（"多少"/"count"/"how many" 等）的查询不触发路由
- 单位（`entry` vs `day`）由 "篇/条/个" vs "天" 或英文 "entries" vs "days" 决定

#### `aggregate_result` 输出字段

仅在 smart-search 委派到 `aggregate` 时出现。结构与 `aggregate` 命令输出一致（见 aggregate 章节）。关键字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `aggregate_result.command` | string | 固定为 `"aggregate"` |
| `aggregate_result.range` | object | 解析后的日期范围 `{"since", "until"}` |
| `aggregate_result.predicate.type` | string | 谓词类型，如 `entry_time_after`、`journal_count` |
| `aggregate_result.result.count` | int | 计算结果计数 |
| `aggregate_result.result.exactness` | enum | `exact` / `approximate` / `partial` / `not_measurable` |
| `aggregate_result.limitations` | array | 局限性说明（如"日志写入时间不等于实际入睡时间"） |
| `aggregate_result.claim_envelope` | object | 证据化结论外壳；结构同 aggregate 命令 |
| `aggregate_result.evidence_pack` | object | aggregate 专用证据包；结构同 aggregate 命令 |

**示例**：

```json
{
  "success": true,
  "query": "过去60天我有多少天晚睡",
  "rewritten_query": "过去60天我有多少天晚睡",
  "filtered_results": [],
  "summary": "",
  "citations": [],
  "agent_decisions": [],
  "agent_unavailable": true,
  "aggregate_result": {
    "success": true,
    "command": "aggregate",
    "predicate": {"type": "entry_time_after", "threshold": "22:00", "definition": "..."},
    "range": {"since": "2026-03-15", "until": "2026-05-13"},
    "result": {
      "count": 7,
      "denominator": 60,
      "exactness": "partial",
      "confidence": "high",
      "min_count": 7,
      "max_count": 11,
      "unknown_count": 4,
      "unknown_bucket_count": 4,
      "count_semantics": "partial_lower_bound"
    },
    "limitations": ["No reliable time-of-day field was available for one or more journal entries."]
  },
  "performance": {"total_time_ms": 45.2}
}
```

**field_equals 路由示例**：

```json
{
  "success": true,
  "query": "过去60天有多少篇 topic=work 的日志",
  "rewritten_query": "过去60天有多少篇 topic=work 的日志",
  "filtered_results": [],
  "summary": "",
  "citations": [],
  "agent_decisions": [],
  "agent_unavailable": true,
  "aggregate_result": {
    "success": true,
    "command": "aggregate",
    "predicate": {"type": "field_equals", "field": "topic", "value": "work"},
    "range": {"since": "2026-03-17", "until": "2026-05-15"},
    "result": {
      "count": 12,
      "denominator": 60,
      "exactness": "exact",
      "confidence": "high"
    },
    "limitations": []
  },
  "performance": {"total_time_ms": 38.1}
}
```

**Consumer Guidance**：

- 非聚合查询不包含 `aggregate_result` 字段
- `aggregate_result` 为附加字段（additive），不影响现有字段语义
- `aggregate_result.claim_envelope` 和 `aggregate_result.evidence_pack` 位于 `aggregate_result` 内，不新增 smart-search 顶层字段
- `agent_unavailable` 沿用既有含义：无可用 LLM 时为 `true`；aggregate 路由本身不调用 LLM

### Aggregate Evaluation Coverage (Internal Developer Tooling)

`life-index eval` uses `tools/eval/golden_queries.yaml` as the search quality
Gold Set authority. The same file may also contain companion sections for
deterministic aggregate/analyze checks:

- `aggregate_queries` exercises the aggregate primitive directly.
- `smart_aggregate_queries` exercises smart-search deterministic aggregate
  routing before normal retrieval.

`smart_aggregate_queries` is a route-family coverage matrix, not a product
scenario registry. Each case must prove that a natural-language query maps to a
generic deterministic primitive such as `journal_count`, `entry_time_after`,
`term_presence`, or `field_equals`. Representative samples are allowed, but the
expected contract must assert the generic route and predicate. For example,
"late sleep" may only appear as a sample for `entry_time_after=22:00`; it must
not create or require a dedicated `late_sleep` predicate in the CLI core.

These cases do not participate in search MRR/Recall/Precision calculations;
they are reported under `aggregate_eval` and `smart_aggregate_eval` so
aggregate regressions and smart-search route regressions are visible without
polluting retrieval metrics.

`aggregate_eval` result shape:

```json
{
  "total_queries": 3,
  "passed_queries": 3,
  "failed_queries": 0,
  "metrics": {"pass_rate": 1.0},
  "by_category": {
    "aggregate_analyze": {
      "query_count": 3,
      "passed_queries": 3,
      "failed_queries": 0,
      "pass_rate": 1.0
    }
  },
  "per_query": [
    {
      "id": "AGQ01",
      "eval_mode": "aggregate",
      "command": "aggregate",
      "count": 3,
      "exactness": "exact",
      "pass": true
    }
  ],
  "failures": []
}
```

`smart_aggregate_eval` uses the same high-level shape, with per-query entries
adding `eval_mode: "smart_aggregate"`, `route_present`, and predicate-detail
fields such as `predicate_term` or `predicate_threshold` when applicable. It
validates that a natural-language smart-search query produced a top-level
`aggregate_result` with the expected deterministic aggregate contract:

```json
{
  "total_queries": 1,
  "passed_queries": 1,
  "failed_queries": 0,
  "metrics": {"pass_rate": 1.0},
  "by_category": {
    "smart_aggregate_route": {
      "query_count": 1,
      "passed_queries": 1,
      "failed_queries": 0,
      "pass_rate": 1.0
    }
  },
  "per_query": [
    {
      "id": "SAGQ01",
      "eval_mode": "smart_aggregate",
      "route_present": true,
      "predicate_type": "field_equals",
      "predicate_field": "topic",
      "predicate_value": "work",
      "predicate_term": null,
      "predicate_threshold": null,
      "unit": "entry",
      "count": 4,
      "exactness": "exact",
      "pass": true
    }
  ],
  "failures": []
}
```

#### Diagnostic-Only Mode

When `run_evaluation()` is called without an explicit `data_dir` (default/live
eval against real user data), aggregate companion checks and smart aggregate
route companion checks run in **diagnostic-only** mode. In this mode:

- `diagnostic_only` is set to `true`.
- `failed_queries` is always `0` — count mismatches do not fail the gate.
- `failures` is an empty list.
- Mismatches are reported as `diagnostic_observations` with `id`, `query`,
  `reason`, `expected`, and `actual` fields.

When `data_dir` is explicitly provided (fixture/CI eval), aggregate and smart
aggregate route checks remain a **hard gate** with `failed_queries` incremented
on mismatch.

This is an eval-system extension, not a second Gold Set. Real-log diagnostic
queries should be promoted into `aggregate_queries` or `smart_aggregate_queries`
only after their expected counts, route criteria, and evidence criteria are
stable.

### Answer Evaluation Harness（Internal Developer Tooling，非 CLI Public API）

> **注意**: `tools/eval/answer_eval.py` 是**内部开发者/评估工具**，不属于 CLI 公共 API。以下文档仅供开发者和评估流水线参考。GUI 或 Agent 消费者不应导入或依赖此模块。

`tools/eval/answer_eval.py` 提供确定性 answer 级别评估工具。不依赖网络或 LLM 凭证，对 orchestrator 输出做离线质量分类。

#### 评估维度

| 维度 | 说明 | Verdict 值 |
|------|------|------------|
| 支撑度 | Answer 有有效引用且无不实声称 | `supported` |
| 过度声称 | 含 "all entries" 等全称断言但引用不足 | `overclaiming` |
| 无效引用 | 所有引用均为幻觉路径或绝对路径 | `invalid_citation` |
| 无引用 | Citations 列表为空 | `no_citations` |
| 空答案 | Answer text 为空 | `empty` |

#### 透明度质量

| 质量等级 | 说明 |
|----------|------|
| `complete` | `confidence_reason` + `limitations`(list) + `evidence_summary` 均存在 |
| `partial` | 部分字段缺失或 `limitations` 不是 list |
| `missing` | 三个透明度字段均缺失 |
| `not_applicable` | 答案为空，不适用透明度评估 |

#### API

**单条评估：**

```python
from tools.eval.answer_eval import evaluate_answer, evaluate_answer_from_orchestrator_output

# 直接评估 answer dict
result = evaluate_answer(answer_dict, known_paths={"Journals/..."})
print(result.verdict, result.valid_citation_count, result.transparency.verdict)

# 从完整 orchestrator 输出评估（自动提取 known_paths）
result = evaluate_answer_from_orchestrator_output(orchestrator_output_dict)
```

**批量评估：**

```python
from tools.eval.answer_eval import evaluate_answer_batch

batch = evaluate_answer_batch([
    {"answer": answer_dict_1, "known_paths": paths_1},
    {"answer": answer_dict_2, "known_paths": paths_2},
])
print(batch.by_verdict)  # {"supported": 1, "invalid_citation": 1}
```

#### 引用失败模式契约

| 失败模式 | 原因 | `reason` 字段 |
|----------|------|---------------|
| 绝对路径 | 引用包含完整文件系统路径 | `absolute_path` |
| 幻觉路径 | 引用路径不在 `known_paths` 中 | `unknown_path` |
| 类型错误 | 引用不是 string | `not_a_string` |
| 越界索引 | 数字引用超出 `filtered_results` 范围 | 被 `_parse_synthesis_response` 丢弃 |

---

## eval

> **Internal developer evaluation tooling.** `eval` runs search quality gates
> against the Gold Set in `tools/eval/golden_queries.yaml`. It is not a user
> search endpoint and must not be used to write or mutate journal data.
>
> **M04 注**：以下文档描述内部开发者 eval 测量子系统的实现行为，不是公开的
> CLI/API 扩展。没有新增公共 CLI flag（如 `--export-ir` 或 `--export-trec`）。

### 端点

```bash
life-index eval [options]
python -m tools eval [options]
```

### 参数

| 名称 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| data-dir | path | temp fixture data | 使用指定数据目录运行 eval |
| save-baseline | path | - | 保存当前 eval 结果为 baseline JSON |
| compare-baseline | path | - | 与既有 baseline JSON 对比 |
| json | flag | false | 输出完整 JSON |
| semantic | flag | false | 启用语义 pipeline 作为 top-level eval |
| no-semantic | flag | false | 显式禁用语义 pipeline |
| semantic-report | flag | false | 附加第二次语义诊断 pass；不改变 top-level keyword gate |
| judge | enum | keyword | `keyword` 或 `llm`；默认 `keyword` |
| live | flag | false | 使用真实 `~/Documents/Life-Index` 数据运行诊断 |
| no-overlay | flag | false | 禁用本地私有 eval overlay |
| overlay-path | path | - | 指定私有 eval overlay YAML |

### LLM 边界

- 默认 `judge=keyword`，不初始化 provider client，不读取 LLM key，不调用外部 LLM。
- `--judge llm` 是显式开发者 opt-in：该模式会通过 `tools/eval/llm_client.py`
  读取 `OPENAI_API_KEY` 或 `ANTHROPIC_API_KEY` 并调用 provider-backed judge。
- `--live --judge llm` 还会启用 LLM recall-gap 诊断；`--live` 本身不触发 LLM。
- `--semantic` / `--semantic-report` 属于检索 pipeline 诊断，不等同于 LLM judge。

### 返回值

```json
{
  "success": true,
  "schema_version": "v1.1.1",
  "provenance": {
    "source_hash": "sha256:...",
    "tool_version": "1.1.1",
    "generated_at": "2026-05-23T10:00:00+00:00",
    "generator": "eval",
    "params_hash": "sha256:...",
    "fixture_version": null
  },
  "data": {
    "summary_lines": ["Queries: 50", "Failures: 0"],
    "metrics": {"mrr_at_5": 1.0, "recall_at_5": 1.0},
    "judge_mode": "keyword",
    "semantic_enabled": false,
    "aggregate_eval": {},
    "smart_aggregate_eval": {}
  }
}
```

### 内部测量输出（M04 实现）

`run_evaluation()` 在 JSON 结果中附加以下内部开发者测量字段。这些字段由
`tools/eval/run_eval.py` 生成，供 baseline 保存、回归比较和 CI 门控使用。

#### `ir_eval` — IR 测量制品

`ir_eval` 是 Pack A 引入的纯增量内部测量节，基于现有的 `tools/eval/eval_qrels.py`、
`eval_run.py`、`eval_export.py` 等无依赖 helper 构建。

| 字段 | 类型 | 说明 |
|------|------|------|
| `ir_eval.qrel_coverage` | object | Qrel 覆盖分类报告，见下表 |
| `ir_eval.run_coverage` | object | Run 覆盖统计报告，见下表 |
| `ir_eval.artifacts.qrels` | dict | query ID → doc ID → int grade 的 qrels 字典 |
| `ir_eval.artifacts.run` | dict | query ID → doc ID → float score 的 run 字典 |

**隐私约束**：`artifacts.qrels` 和 `artifacts.run` 仅包含 query ID 和 doc ID；
不序列化原始 query 文本、日志标题或正文内容。该约束由
`tests/unit/test_eval_runner.py::test_eval_runner_includes_ir_eval_artifacts` 校验。

**`qrel_coverage` 字段**：

| 子字段 | 类型 | 说明 |
|--------|------|------|
| `total_queries` | int | 总查询数 |
| `resolved` | int | 已解析到至少一个 doc ID 的查询数 |
| `ambiguous` | int | 存在多个可能 doc 匹配的查询数 |
| `unresolved` | int | 无法解析到 doc ID 的查询数 |
| `negative` | int | 负例查询数（预期无匹配结果） |
| `min_results_only` | int | 仅含 `min_results` 期望、无 title 期望的查询数 |
| `broad_eval` | int | 使用 broad_eval 谓词评估的查询数 |
| `broad_eval_with_titles` | int | 同时使用 broad_eval 和 must_contain_title 的查询数 |
| `unresolved_ids` | list[str] | 未解析查询 ID 列表 |
| `ambiguous_ids` | list[str] | 歧义查询 ID 列表 |
| `procedural_only_ids` | list[str] | 纯过程性查询 ID 列表 |
| `warnings` | list[str] | 构建过程中的警告信息 |

**`run_coverage` 字段**：

| 子字段 | 类型 | 说明 |
|--------|------|------|
| `total_queries` | int | 总查询数 |
| `total_result_items` | int | 结果项总数 |
| `emitted_items` | int | 实际写入 run 的项数 |
| `skipped_empty_doc_ids` | int | 因 doc ID 为空而被跳过的项数 |
| `length_mismatch_query_ids` | list[str] | 结果长度与期望长度不匹配的查询 ID |
| `duplicate_doc_ids_query_ids` | list[str] | 存在重复 doc ID 的查询 ID |
| `queries_with_no_run_items` | list[str] | 没有任何 run 项的查询 ID |
| `warnings` | list[str] | 构建过程中的警告信息 |

#### Baseline 规范化策略（M04 Pack B）

Baseline 查找遵循确定性 canonical 路径偏好：

1. **Canonical 目录**：优先使用 `tools/eval/baselines/` 中的冻结 baseline。
2. **Fallback 目录**：若 canonical 目录无匹配，回退到 `tests/eval/baselines/`。
3. **确定性排序**：在同一目录内，按 embedded `frozen_at` 或 `anchor_date` 降序、
   文件名降序排序；mtime 仅作为最终 tie-breaker。

`save-baseline` 写入时开发者自行指定路径；`compare-baseline` 读取调用方显式传入的
baseline 路径。`_find_latest_baseline()` 使用上述策略为未设置
`LIFE_INDEX_TIME_ANCHOR` 的 eval run 推断稳定时间锚点。

#### `compare_against_baseline()` diff 增量（M04 Pack C）

当使用 `compare-baseline` 时，`diff` 对象在保留原有字段（`metric_deltas`、
`regressions`、`new_failures`、`new_passes`、`recall_gap_changes`）的基础上，
新增以下内部比较节：

| 字段 | 类型 | 说明 |
|------|------|------|
| `diff.eval_comparison` | object | 基于 `EvalRun` 的 typed pass/fail 比较结果 |
| `diff.ir_run_comparison` | object | 基于 qrels/run 的 IR 指标比较结果 |
| `diff.companion_eval_deltas` | list[object] | aggregate / smart-aggregate / timeline 的 companion 比较增量 |

**`eval_comparison` 字段**：

| 子字段 | 类型 | 说明 |
|--------|------|------|
| `baseline_commit` | str | baseline 的 git commit |
| `candidate_commit` | str | current 的 git commit |
| `baseline_anchor` | str | baseline 的锚定日期 |
| `candidate_anchor` | str | current 的锚定日期 |
| `total_shared_queries` | int | 两边共有的查询数 |
| `fixed_query_ids` | list[str] | 从失败变为修复的查询 ID |
| `regressed_query_ids` | list[str] | 从通过变为失败的查询 ID |
| `still_failing_ids` | list[str] | 两边均失败的查询 ID |
| `still_passing_ids` | list[str] | 两边均通过的查询 ID |
| `new_in_candidate` | list[str] | current 新增而 baseline 没有的查询 ID |
| `missing_from_candidate` | list[str] | baseline 有而 current 缺失的查询 ID |
| `failure_delta` | int | current 相对 baseline 的失败数变化（负值表示改善） |

**`ir_run_comparison` 字段**：

| 子字段 | 类型 | 说明 |
|--------|------|------|
| `metric_deltas` | list[object] | 每项含 `metric_name`、`baseline_value`、`candidate_value`、`delta`、`direction` |
| `per_query_deltas` | list[object] | 每项含 `query_id`、`status`，以及可选 `baseline_score`、`candidate_score`、`delta`、`metric_deltas` |
| `queries_compared` | int | 实际参与比较的查询数 |
| `queries_skipped_no_qrel` | int | 因缺少 qrel 而跳过的查询数 |

> **降级行为**：当 baseline 为 legacy 格式（不含 `ir_eval` 节）时，
> `ir_run_comparison` 不会崩溃，而是显式报告 `queries_skipped_no_qrel` 并继续。

**`companion_eval_deltas` 字段**：

`companion_eval_deltas` 是一个列表，每项对应一个 companion eval 节
（`aggregate_eval`、`smart_aggregate_eval`、`timeline_eval`），结构如下：

| 子字段 | 类型 | 说明 |
|--------|------|------|
| `section` | str | 节名称 |
| `baseline_mode` | str \| null | baseline 的评估模式：`hard_gate` / `diagnostic` / `null` |
| `current_mode` | str \| null | current 的评估模式 |
| `passed_delta` | int | current 通过数 − baseline 通过数 |
| `failed_delta` | int | current 失败数 − baseline 失败数 |
| `pass_rate_delta` | float | current 通过率 − baseline 通过率 |
| `comparable` | bool | 两节是否可比较 |
| `reason` | str | 不可比较时的原因说明 |

> **隔离原则**：companion eval deltas 始终与搜索 MRR/Recall/P 指标分离，
> 不会合并到 `metric_deltas` 中。诊断模式与硬 gate 模式之间的结构差异会降级为
> 显式警告，不会导致崩溃。

## entity-graph-eval

> **Graph ablation evaluation (gbrain Phase A).** Runs search across 8 pipeline
> combinations to measure the impact of Entity Graph expansion, semantic search,
> and hybrid policy on retrieval quality. Default path is fully deterministic —
> zero LLM calls. Output schema version: `gbrain-ablation.v1`.

### 端点

```bash
life-index entity-graph-eval --queries <fixture.json> [--output stdout|<path>] [--data-dir <dir>]
python -m tools.eval.ablation --queries <fixture.json> [--output stdout|<path>] [--data-dir <dir>]
```

### 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| queries | path | (required) | JSON fixture path with ablation queries |
| output | string | `stdout` | `stdout` or a file path for JSON output |
| data-dir | path | — | Override data directory (sets `LIFE_INDEX_DATA_DIR`) |

### 返回值

```json
{
  "success": true,
  "schema_version": "gbrain-ablation.v1",
  "query_count": 25,
  "combinations": [
    {
      "entity_graph": false,
      "semantic": false,
      "hybrid": false,
      "precision_at_5": 0.12,
      "recall_at_5": 0.08,
      "mrr_at_5": 0.15,
      "query_count": 25
    }
  ]
}
```

**Output contains 8 entries** — one for each combination of:

| Flag | Values | Effect |
|------|--------|--------|
| `entity_graph` | true/false | Entity Graph alias expansion on/off |
| `semantic` | true/false | Semantic vector search on/off |
| `hybrid` | true/false | Hybrid RRF policy vs. fallback (keyword-first) |

### LLM 边界

- Default path: **zero LLM calls**. All search uses FTS keyword + deterministic ranking.
- `semantic=true` combinations use local `sentence-transformers` embeddings (no API call).
- No `anthropic`, `openai`, or `llm_client` imports in the module.

### Fixture format

The queries fixture is a JSON array of objects:

```json
[
  {
    "id": "AQ01",
    "query": "search terms",
    "category": "entity_expansion",
    "expected_relevant_ids": ["life-index_2026-03-04_002.md"]
  }
]
```

---

## maintenance

> **Maintenance cycle (gbrain Phase D).** Dry-run/report-only maintenance command that
> aggregates six health checks without any production writes. All external CLI calls
> are delegated via subprocess. Default path is fully deterministic — zero LLM calls.
> Output schema version: `m16.maintenance.v0`.

### 端点

```bash
life-index maintenance --dry-run [--output text|json] [--data-dir <dir>]
python -m tools maintenance --dry-run [--output text|json] [--data-dir <dir>]
```

### 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| dry-run | flag | (default) | Run maintenance in dry-run/report-only mode |
| output | enum | `text` | Output format: `text` (human-readable) or `json` |
| data-dir | path | — | Override data directory (sets `LIFE_INDEX_DATA_DIR`) |

### 六项检查

| 检查 | 说明 | 调用的 CLI |
|------|------|-----------|
| `index_freshness` | FTS/vector index health and freshness | `index --check --json` |
| `entity_audit` | Entity graph quality audit (duplicates, orphans, incomplete relationships) | `entity --audit` |
| `orphan_related_entries` | Journal `related_entries` referencing unknown entities | Read-only file inspection |
| `search_eval_smoke` | Minimal ablation eval smoke test (3 queries) | `entity-graph-eval --queries <fixture>` |
| `backup_verification` | Backup destination accessibility check | `backup --list --dest <path>` |
| `candidate_edges` | Candidate relationship edges report | `entity --candidate-edges` |

### 状态枚举

每项检查返回以下状态之一：

| 状态 | 含义 |
|------|------|
| `pass` | 检查通过，无需操作 |
| `fail` | 检查失败，需要调查 |
| `needs-user-action` | 需要用户手动操作 |

### JSON 返回值

```json
{
  "success": true,
  "command": "maintenance",
  "schema_version": "v1.1.1",
  "provenance": {
    "source_hash": "sha256:...",
    "tool_version": "1.1.1",
    "generated_at": "2026-05-23T10:00:00+00:00",
    "generator": "maintenance",
    "params_hash": "sha256:...",
    "fixture_version": null
  },
  "checks": [
    {
      "category": "index_freshness",
      "status": "pass",
      "details": {
        "fts_count": 56,
        "vector_count": 56,
        "file_count": 56,
        "healthy": true
      },
      "timestamp": "2026-05-21T10:00:00.000000+00:00"
    }
  ],
  "summary": {
    "pass_count": 4,
    "fail_count": 0,
    "needs_user_action_count": 2,
    "overall_healthy": true
  },
  "timestamp": "2026-05-21T10:00:05.000000+00:00",
  "error": null
}
```

### LLM 边界

- Default path: **zero LLM calls**. All checks use subprocess delegation or read-only file inspection.
- No `anthropic`, `openai`, or `llm_client` imports in the module.
- Search eval smoke delegates to `entity-graph-eval` which is itself LLM-free.

### 设计约束

- **零生产写入**: maintenance 自身及其所有子进程调用均为只读操作
- **Subprocess 边界**: 所有外部 CLI 调用通过 subprocess，不直接 import 被调用模块内部
- **Report-only**: maintenance 只报告状态，不执行自动修复 (CHARTER §1.10)

---

## aggregate

<!-- M16-CONTRACT: aggregate -->

### M16 Public JSON Contract: aggregate

#### JSON Shape / Top-Level Fields

| Field | Type | Always Present | Description |
|-------|------|----------------|-------------|
| `success` | bool | yes | Command execution success (`not_measurable` is still success) |
| `schema_version` | string | yes | `"m16.aggregate.v0"` — top-level output schema version |
| `query` | string | yes | Caller-provided natural language query (may be empty string) |
| `command` | string | yes | Fixed `"aggregate"` |
| `metric` | string | yes | Computed metric name (e.g., `journal_count`, `entry_count`) |
| `unit` | string | yes | Aggregation unit: `day` / `week` / `month` / `entry` |
| `range` | object | yes | Parsed date range `{since, until}` |
| `predicate` | object | yes | Parsed predicate with `type`, `definition`, and type-specific fields |
| `result` | object | yes | `{count, denominator, exactness, confidence}` plus additive partial fields |
| `buckets` | array | yes | Per-unit group stats (empty for `entry` unit) |
| `matched_entries` | array | yes | Relative paths of entries matching the predicate |
| `excluded_entries` | array | yes | Relative paths of entries not matching |
| `unknown_entries` | array | yes | Entries that could not be evaluated (`{path, reason}`) |
| `evidence_paths` | array | yes | All participating relative paths (matched + excluded + unknown) |
| `limitations` | array | yes | Human-readable limitation notes |
| `performance` | object | yes | `{total_time_ms}` |
| `claim_envelope` | object | yes | M02/A+ evidence-based claim wrapper |
| `evidence_pack` | object | yes | M02/A+ aggregate-specific evidence pack |

#### Field Semantics

- `success`: execution success. `result.exactness = not_measurable` is still `success: true`.
- `command`: always `"aggregate"` even when invoked via the `analyze` alias.
- `result.exactness`: `exact` / `approximate` / `partial` / `not_measurable`.
- `result.confidence`: data quality signal (`high`/`medium`/`low`), not LLM opinion.
- `claim_envelope.schema_version`: `m02a.claim_envelope.v0`.
- `evidence_pack.schema_version`: `m02a.aggregate_evidence_pack.v0`.
- All output paths are relative; no absolute filesystem paths.

#### Error Behavior / Error Codes

Errors use the structured unified format with `command="aggregate"`:

| Code | Meaning | Recovery Strategy |
|------|---------|-------------------|
| E0001 | Invalid input (bad format, unknown predicate, illegal unit) | ask_user |

For both `aggregate` and its `analyze` alias, invalid range, unit, and predicate inputs return `success: false`, `command: "aggregate"`, `error.code: "E0001"`.

#### schema_version Policy

`aggregate` emits a top-level `schema_version` field set to `"m16.aggregate.v0"`. Versioning in additive sub-structures is unchanged:
- `claim_envelope.schema_version = "m02a.claim_envelope.v0"` — stable; changes require a new version string.
- `evidence_pack.schema_version = "m02a.aggregate_evidence_pack.v0"` — stable; changes require a new version string.
- Top-level field names and types are stable; new fields may be added without a version bump.
- A `schema_version` bump will accompany any backward-incompatible change.

<!-- /M16-CONTRACT -->

> **Additive primitive, not a replacement.** `aggregate` is a deterministic, read-only CLI tool for explicit counts and trends over structured journal fields. It does **not** replace `search` or `smart-search`; use those for retrieval and synthesis. Use `aggregate` only when the user question can be settled by a whitelisted predicate over a date range.

### 端点

```bash
life-index aggregate --range <since>..<until> --unit <unit> --predicate <predicate> [--query "..."] [--explain] [--json]
python -m tools aggregate --range <since>..<until> --unit <unit> --predicate <predicate> [--query "..."] [--explain] [--json]
life-index analyze --range <since>..<until> --unit <unit> --predicate <predicate> [--query "..."] [--explain] [--json]
python -m tools analyze --range <since>..<until> --unit <unit> --predicate <predicate> [--query "..."] [--explain] [--json]
```

`analyze` is an alias for `aggregate`. It does not add a separate reasoning
engine; JSON output still uses `"command": "aggregate"` and the same
claim/evidence contract.

<!-- M16-CONTRACT: analyze -->

### M16 Public JSON Contract: analyze

#### JSON Shape / Top-Level Fields

`analyze` produces the **identical** JSON output shape as `aggregate`. The `command` field is always `"aggregate"`. See the `aggregate` M16 contract block for the full field table.

#### Field Semantics

All field semantics are identical to `aggregate`. The alias exists for user convenience; no separate processing pipeline or additional fields are involved.

#### Error Behavior / Error Codes

Error behavior is identical to `aggregate`: invalid inputs return `success: false`, `command: "aggregate"`, `error.code: "E0001"`. Error payloads always use `command: "aggregate"` even when invoked via the `analyze` alias.

#### schema_version Policy

Identical to `aggregate`: emits top-level `schema_version = "m16.aggregate.v0"`. Additive sub-structures carry their own version stamps (`m02a.claim_envelope.v0`, `m02a.aggregate_evidence_pack.v0`).

<!-- /M16-CONTRACT -->

### 参数

| 名称 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--range` | string | ✅ | — | 日期范围，格式 `YYYY-MM-DD..YYYY-MM-DD`（两端均包含） |
| `--unit` | enum | ✅ | — | 聚合单位：`day`、`week`、`month`、`entry` |
| `--predicate` | string | ✅ | — | 白名单谓词表达式（见下方） |
| `--query` | string | ❌ | `""` | 原始自然语言查询（仅存入输出，不参与计算） |
| `--explain` | flag | ❌ | false | 在输出中包含人类可读的谓词解释与局限性说明 |
| `--json` | flag | ❌ | false | 输出完整 JSON 契约 |

### 支持的聚合单位

| 单位 | 行为 |
|------|------|
| `day` | 按日历日聚合；同一日多条日志去重 |
| `week` | 按 ISO 周聚合（`YYYY-WNN`） |
| `month` | 按月聚合（`YYYY-MM`） |
| `entry` | 按单条日志文件计数，不做去重 |

### 支持的谓词

| 谓词 | 语法 | 数据要求 | 精确度 | 说明 |
|------|------|----------|--------|------|
| `journal_count` | `journal_count` | 仅需日期范围和日志路径 | `exact` | 统计每个聚合单位内的日志数量 |
| `entry_time_after` | `entry_time_after=HH:MM` | Frontmatter `date` 含时间部分或独立 `time` 字段 | `exact`（全部有时间字段）或 `partial`（部分缺失） | 日志时间戳晚于指定时间 |
| `term_presence` | `term_presence=TERM` | 全文检索覆盖标题、正文、摘要 | `approximate` | 日志内容中出现指定词项 |
| `entity_presence` | `entity_presence=ENTITY_ID` | Entity Graph 别名扩展 + 文本匹配 | `approximate` | 日志中出现指定实体（主名 + 别名） |
| `field_equals` | `field_equals=FIELD:VALUE` | Frontmatter 标量或列表字段 | `exact` | Frontmatter 字段值等于指定值（大小写不敏感）；列表字段匹配任一元素 |

> **⚠️ 重要**：`entry_time_after=22:00` 表示**日志写入/记录时间晚于 22:00**，不是实际入睡时间的证明。系统优先读取 frontmatter `date` 中的 ISO 8601 时间部分；若不存在，则回退到独立的 `time` 字段。若两者均缺失，对应条目进入 `unknown_entries`，精确度降为 `partial`，`count` 为确认下限而非完整计数。

### 返回值

```json
{
  "success": true,
  "query": "过去2天我有多少次晚睡",
  "command": "aggregate",
  "metric": "entry_count",
  "unit": "day",
  "range": {"since": "2026-03-14", "until": "2026-03-15"},
  "predicate": {
    "type": "entry_time_after",
    "threshold": "22:00",
    "definition": "journal timestamp later than 22:00; not proof of actual sleep time"
  },
  "result": {
    "count": 1,
    "denominator": 2,
    "exactness": "partial",
    "confidence": "high",
    "min_count": 1,
    "max_count": 2,
    "unknown_count": 1,
    "unknown_bucket_count": 1,
    "count_semantics": "partial_lower_bound"
  },
  "buckets": [],
  "matched_entries": ["Journals/2026/03/life-index_2026-03-14_001.md"],
  "excluded_entries": [],
  "unknown_entries": [
    {"path": "Journals/2026/03/life-index_2026-03-15_001.md", "reason": "no_time_field_available"}
  ],
  "evidence_paths": [
    "Journals/2026/03/life-index_2026-03-14_001.md",
    "Journals/2026/03/life-index_2026-03-15_001.md"
  ],
  "limitations": [
    "No reliable time-of-day field was available for one or more journal entries."
  ],
  "performance": {"total_time_ms": 45.2}
}
```

### 输出字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `success` | bool | 命令执行是否成功（`not_measurable` 仍视为成功） |
| `query` | string | 调用方传入的原始自然语言查询 |
| `command` | string | 固定为 `"aggregate"` |
| `metric` | string | 计算出的指标名，如 `journal_count`、`entry_count`、`term_presence_count`、`entity_presence_count`、`field_equals_count` |
| `unit` | string | 聚合单位 |
| `range` | object | 解析后的日期范围 `{"since", "until"}` |
| `predicate` | object | 解析后的谓词，含 `type`、`threshold`/`term`/`entity_id`/`field`/`value`（如适用）及 `definition` |
| `result.count` | int | 计算结果计数 |
| `result.denominator` | int | 范围内总候选单位数（如总天数） |
| `result.exactness` | enum | `exact` / `approximate` / `partial` / `not_measurable` |
| `result.confidence` | enum | `high` / `medium` / `low`；反映数据质量，非 LLM 意见 |
| `result.min_count` | int | additive；`exactness=partial` 时确认的下限计数 |
| `result.max_count` | int | additive；`exactness=partial` 时可能的上限计数（含未知条目） |
| `result.unknown_count` | int | additive；`exactness=partial` 时缺失数据字段的条目总数 |
| `result.unknown_bucket_count` | int | additive；`exactness=partial` 时仅含未知条目（无确认匹配）的桶数 |
| `result.count_semantics` | string | additive；`exactness=partial` 时为 `"partial_lower_bound"` |
| `buckets` | array | 非 `entry` 单位时的分组统计；每项含 `key`、`count`、`total`、`evidence_paths` |
| `matched_entries` | array | 谓词判定为 true 的日志相对路径 |
| `excluded_entries` | array | 谓词判定为 false 的日志相对路径 |
| `unknown_entries` | array | 无法评估的日志，每项含 `path` 和 `reason` |
| `evidence_paths` | array | 参与结果的所有相对路径（`matched` + `excluded` + `unknown`） |
| `limitations` | array | 人类可读的局限性说明 |
| `performance.total_time_ms` | float | 执行耗时 |
| `claim_envelope` | object | M02/A+ 证据化结论外壳，见下方 Claim Envelope 子节 |
| `evidence_pack` | object | M02/A+ aggregate 专用证据包，见下方 Aggregate Evidence Pack 子节 |

### Claim Envelope（`claim_envelope`）

`claim_envelope` 是 aggregate 结果的 additive 机器可读结论外壳。它不改变 `result` 字段语义，只把已有计数、精确度、谓词和局限性组织成未来 L3/L4 模块可组合的 claim。

| 字段 | 类型 | 说明 |
|------|------|------|
| `schema_version` | string | 固定为 `m02a.claim_envelope.v0` |
| `claim_type` | enum | `measurable_exact` / `measurable_approximate` / `measurable_partial` / `not_measurable`，由 `result.exactness` 映射 |
| `source_command` | string | 固定为 `aggregate` |
| `query` | string | 原始自然语言查询（若调用方提供） |
| `metric` | string | aggregate 指标名 |
| `unit` | string | aggregate 单位 |
| `time_range` | object | 与 `range` 相同的日期范围 |
| `predicate` | object | 解析后的谓词 |
| `value` | int | 与 `result.count` 相同 |
| `denominator` | int | 与 `result.denominator` 相同 |
| `exactness` | enum | 与 `result.exactness` 相同 |
| `confidence` | enum | 与 `result.confidence` 相同 |
| `limitations` | array | 与 aggregate 局限性说明相同 |
| `evidence_pack_ref` | string | 固定为 `aggregate.evidence_pack` |
| `min_count` | int | additive；`exactness=partial` 时与 `result.min_count` 相同 |
| `max_count` | int | additive；`exactness=partial` 时与 `result.max_count` 相同 |
| `unknown_count` | int | additive；`exactness=partial` 时与 `result.unknown_count` 相同 |
| `unknown_bucket_count` | int | additive；`exactness=partial` 时与 `result.unknown_bucket_count` 相同 |
| `count_semantics` | string | additive；`exactness=partial` 时与 `result.count_semantics` 相同 |

### Aggregate Evidence Pack（`evidence_pack`）

aggregate 专用 `evidence_pack` 是 deterministic source map，不是 smart-search `--include-evidence` 的检索证据包。它列出本次 aggregate 判定涉及的日志路径、日期、角色和最小未来兼容钩子。

| 字段 | 类型 | 说明 |
|------|------|------|
| `schema_version` | string | 固定为 `m02a.aggregate_evidence_pack.v0` |
| `source_command` | string | 固定为 `aggregate` |
| `query` | string | 原始自然语言查询（若调用方提供） |
| `time_range` | object | 与 `range` 相同的日期范围 |
| `predicate` | object | 解析后的谓词 |
| `items` | array | 证据项列表 |
| `index_scope` | object | 月度 Index Tree 导航锚点范围，见下方 `index_scope` 子节 |
| `page_info` | object | 最小未来钩子，当前固定 `has_more=false`, `cursor=null`, `cursor_hint=null` |

`items[]` 字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `path` | string | 日志相对路径，使用 `/`，不得为绝对路径 |
| `date` | string | 日志日期 |
| `role` | enum | `matched` / `excluded` / `unknown` |
| `bucket` | string | aggregate bucket key |
| `reason` | string | `unknown` 等状态的原因（如适用） |
| `index_node_ref` | object | 可选未来钩子，当前为月度 Index Tree 引用；不是完整 Index Tree API |

`index_node_ref` 字段（additive，月度引用）：

| 字段 | 类型 | 说明 |
|------|------|------|
| `type` | string | 固定为 `"month"` |
| `node_id` | string | 逻辑节点标识，格式 `month:YYYY-MM`（如 `"month:2026-03"`） |
| `id` | string | 物理月路径，格式 `Journals/YYYY/MM`（如 `"Journals/2026/03"`） |
| `path` | string | 月度索引文件相对路径（如 `"Journals/2026/03/index_2026-03.md"`） |

> `node_id` 与 `id` 构成月度节点的**双身份**：`node_id` 是逻辑标识（用于导航/分组/比较），`id` 是既有物理路径引用（用于文件系统定位）。`node_id` 为 additive 字段，现有消费者可忽略。

`index_scope` 字段（additive，范围级月度锚点）：

| 字段 | 类型 | 说明 |
|------|------|------|
| `type` | string | 固定为 `"month_range"` |
| `refs` | array | `since..until` 范围内所有月份的 `index_node_ref` 列表，按时间顺序排列 |
| `note` | string | 固定为 `"navigation anchors only; evidence items remain authoritative"` |

> `index_scope` 是导航辅助信息，不替代 `items[]` 中的证据路径。`refs` 列表由 `since`/`until` 日期范围确定性生成，不读取或写入文件系统，不包含 cursor/page 行为，不过滤证据。

### 精确度标签语义

| 标签 | 含义 |
|------|------|
| `exact` | 所有单元均使用可靠结构化数据完成布尔判定，无推断或启发式 |
| `approximate` | 谓词依赖检索召回（词项/实体存在），可能存在假阳性或假阴性 |
| `partial` | 部分条目有所需数据字段，部分缺失；`count` 为确认下限，附加 `min_count`/`max_count`/`unknown_count`/`unknown_bucket_count`/`count_semantics` 字段提供完整范围 |
| `not_measurable` | 所需数据字段缺失或不可靠；`count` 按惯例为 `0`，不得当作统计意义上的零 |

### 行为约束

- **只读**：`aggregate` 不创建、修改或删除任何日志、索引、Entity Graph 文件。
- **本地执行**：所有计算在用户本地完成，无内容上传。
- **沙盒兼容**：正确响应 `LIFE_INDEX_DATA_DIR` 指向临时目录的场景。
- **路径隐私**：输出路径均为相对路径，不含绝对文件系统路径。

### 限制与已知问题

- `analyze` is an alias for `aggregate`; JSON output still uses `"command": "aggregate"`。
- 复合谓词（如 `AND` / `OR`）在 MVP 中**不支持**。
- `term_presence` 和 `entity_presence` 使用大小写不敏感的简单子串匹配（`casefold()`），不做分词或语义扩展；计数为召回支撑，非现实世界行为的证明。
- `field_equals` 的 `FIELD` 限制为 `[A-Za-z_][A-Za-z0-9_]*` 模式；值为大小写不敏感的精确字符串匹配。列表字段匹配任一元素。不含目标字段的条目归入 `excluded_entries`。
- 性能目标：典型范围（< 5 年数据）< 2 秒；未针对 > 10,000 条日志做过专项优化。

### 错误码

| 代码 | 说明 | 恢复策略 |
|------|------|----------|
| E0001 | 无效输入（格式错误、未知谓词、非法单位等） | ask_user |

For both `aggregate` and its `analyze` alias, invalid range, unit, and
predicate inputs are returned as JSON error payloads with `success=false`,
`command="aggregate"`, and `error.code="E0001"`.

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

<!-- M16-CONTRACT: generate-index -->

### M16 Public JSON Contract: generate-index

#### JSON Shape / Top-Level Fields

`generate-index --json` emits a JSON **array** of result objects (not a single top-level response wrapper). Each element's shape depends on the operation:

| Field | Type | Always Present | Description |
|-------|------|----------------|-------------|
| `type` | string | conditional | Operation type: `"monthly"` / `"yearly"` / `"root"` / `"rebuild"` |
| `success` | bool | yes | Whether this specific operation succeeded |
| `year` | int | conditional | Year (monthly/yearly results) |
| `month` | int | conditional | Month (monthly results) |
| `output_path` | string | conditional | Generated index file path |
| `journal_count` | int | conditional | Number of journals indexed |
| `message` | string | conditional | Human-readable status message |
| `updated` | bool | conditional | Whether the index was actually updated |
| `monthly_indexes_rebuilt` | int | conditional | Rebuild mode: count of monthly indexes rebuilt |
| `yearly_indexes_rebuilt` | int | conditional | Rebuild mode: count of yearly indexes rebuilt |
| `root_index_rebuilt` | bool | conditional | Rebuild mode: whether root was rebuilt |
| `errors` | array | conditional | Rebuild mode: failed result objects |

#### Field Semantics

- The output is a JSON array; each element represents one index operation result.
- `success: true` on an element means that specific index generation succeeded.
- Error objects from internal functions (`create_error_response`) are appended to the results array, not emitted as a separate top-level error envelope.
- `journal_count`: number of journals covered by the generated index.

#### Error Behavior / Error Codes

**Known deviation**: `generate-index` error handling is inconsistent with the unified error format.

- **Parse errors** (e.g., invalid `--month` format): the CLI raises `SystemExit` and outputs a plain text error message. No JSON error payload is emitted.
- **I/O errors** during index generation: `create_error_response` objects are appended as elements within the results array. These are not top-level CLI error envelopes.
- No structured `{success: false, error: {code, message, ...}}` envelope is emitted for CLI-level errors.
- Runtime alignment to the unified error format is deferred to a post-M16 milestone.

#### schema_version Policy

`generate-index` does **not** emit a `schema_version` field at any level. Top-level field names and types are stable; new fields may be added without a version bump. **BLOCKED**: `generate-index --json` emits a JSON **array**, not a dict; wrapping it with a top-level `schema_version` would be a breaking shape change for existing consumers. A future milestone may introduce versioning by migrating the output to a dict wrapper (`{schema_version, results}`), which requires a documented migration path.

<!-- /M16-CONTRACT -->

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
| json | flag | ❌ | false | 以 JSON 格式输出结果（含 `schema_version` + `provenance`） |
| explain | flag | ❌ | false | 输出构建诊断 JSON（含 `diagnostics`） |
| cache-dry-run | flag | ❌ | false | 评估 cache 失效状态，**零写入** |

### 返回值

**构建/重建模式**：

```json
{
  "success": true,
  "schema_version": "v1.1.1",
  "provenance": {
    "source_hash": "sha256:...",
    "tool_version": "1.1.1",
    "generated_at": "2026-05-23T10:00:00+00:00",
    "generator": "index",
    "params_hash": "sha256:...",
    "fixture_version": null
  },
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

**`--cache-dry-run` 模式**：

```json
{
  "success": true,
  "dry_run": true,
  "cache_version": {
    "exists": true,
    "stored_schema_version": "v1.1.1",
    "stored_source_hash": "sha256:...",
    "current_schema_version": "v1.1.1",
    "version_match": true,
    "hash_match": true,
    "would_rebuild": false,
    "reasons": []
  }
}
```

退出码：healthy → 0, unhealthy → 1（便于 CI 集成）

---

## health

<!-- M16-CONTRACT: health -->

### M16 Public JSON Contract: health

#### JSON Shape / Top-Level Fields

**Standard mode:**

| Field | Type | Always Present | Description |
|-------|------|----------------|-------------|
| `success` | bool | yes | Always `true` (even when degraded) |
| `schema_version` | string | yes | `"m16.health.v0"` — top-level output schema version |
| `data` | object | yes | `{status, checks[], issues[], issue_count}` |
| `data.status` | string | yes | `"healthy"` / `"degraded"` / `"unhealthy"` |
| `data.checks` | array | yes | Individual check results |
| `data.issues` | array | yes | Issue descriptions |
| `data.issue_count` | int | yes | Number of issues found |
| `events` | array | no | Piggyback event notifications |

**`--data-audit` mode:**

| Field | Type | Always Present | Description |
|-------|------|----------------|-------------|
| `success` | bool | yes | Always `true` |
| `schema_version` | string | yes | `"m16.health.v0"` — top-level output schema version |
| `data` | object | yes | `{file_count, anomalies[], distribution{}}` |
| `data.file_count` | int | yes | Total journal file count |
| `data.anomalies` | array | yes | Anomaly objects (`type`, `severity`, `description`, `path`) |
| `data.distribution` | object | yes | Month → count mapping |

#### Field Semantics

- `success`: always `true` for health checks. Degraded/unhealthy status is communicated via `data.status`, not via `success: false`.
- `data.status`: the primary health indicator. `degraded` means partial functionality; `unhealthy` means critical issues.
- `data.checks`: additive; new checks may be added (e.g., `index_tree` check).
- `data.anomalies[].type`: `revision_file`, `naming`, `distribution`.
- `events`: piggyback notifications; same format as other commands.

#### Error Behavior / Error Codes

**Known deviation**: `health` does not use the structured error format for error paths.

- Standard mode always returns `success: true`. Health status degradation is communicated through `data.status` and `data.issues`, not through structured error codes.
- No `{success: false, error: {code, message, ...}}` envelope is emitted in normal operation.
- Runtime alignment to the unified error format is deferred to a post-M16 milestone.

#### schema_version Policy

`health` emits a top-level `schema_version` field set to `"m16.health.v0"`. The output shape is stable; new `data.checks` entries and `data.anomalies` types may be added without a version bump. A `schema_version` bump will accompany any backward-incompatible change.

<!-- /M16-CONTRACT -->

### 端点

```bash
python -m tools health [options]
```

### 参数

| 名称 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| data-audit | flag | ❌ | false | 数据目录清洁度审计 |
| cache-audit | flag | ❌ | false | Cache 版本只读审计（JSON） |

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

**`--cache-audit` 模式**：

```json
{
  "success": true,
  "cache_audit": {
    "version_exists": true,
    "status": "valid|stale|incompatible|missing",
    "json": true
  }
}
```

Additive standard checks may include:

| check.name | status | meaning |
|------------|--------|---------|
| index_tree | ok / warning / info | Internal Index Tree freshness visibility. Warnings are non-critical; run `life-index generate-index` to refresh missing/stale tree nodes. |

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

## verify

### 端点

```bash
life-index verify [--json]
python -m tools verify [--json]
```

### 参数

| 名称 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--json` | flag | ❌ | false | 以 JSON 格式输出结果 |

### 返回值

```json
{
  "success": true,
  "total_journals": 42,
  "checks": [
    {
      "name": "frontmatter_valid",
      "status": "ok",
      "count": 42,
      "issues": []
    },
    {
      "name": "required_fields",
      "status": "ok",
      "count": 42,
      "issues": []
    },
    {
      "name": "fts_consistency",
      "status": "ok",
      "count": 42,
      "issues": []
    },
    {
      "name": "vector_consistency",
      "status": "ok",
      "count": 42,
      "issues": []
    },
    {
      "name": "attachment_refs",
      "status": "ok",
      "count": 3,
      "issues": []
    },
    {
      "name": "topic_consistency",
      "status": "ok",
      "count": 15,
      "issues": []
    }
  ],
  "issues_count": 0,
  "suggestion": ""
}
```

### 检查项说明

| 检查名 | 说明 |
|--------|------|
| `frontmatter_valid` | 每篇日志的 YAML frontmatter 是否可正常解析 |
| `required_fields` | 必填字段（如 `date`）是否完整 |
| `fts_consistency` | FTS 索引条目与实际日志文件的一致性（缺失 / 孤儿） |
| `vector_consistency` | 向量索引条目与实际日志文件的一致性（缺失 / 孤儿） |
| `attachment_refs` | 正文中引用的附件文件是否存在 |
| `topic_consistency` | `by-topic/` 索引中链接的日志路径是否有效 |

### 行为约束

- **只读**：不创建、修改或删除任何文件。
- `success` 为 `true` 当且仅当 `issues_count == 0`。
- 存在问题时，`suggestion` 包含修复建议（如 `life-index index --rebuild`）。

---

## timeline

<!-- M16-CONTRACT: timeline -->

### M16 Public JSON Contract: timeline

#### JSON Shape / Top-Level Fields

| Field | Type | Always Present | Description |
|-------|------|----------------|-------------|
| `success` | bool | yes | Whether the timeline was generated |
| `schema_version` | string | yes | `"m16.timeline.v0"` — top-level output schema version |
| `range` | array | yes | `[start_month, end_month]` as `"YYYY-MM"` strings |
| `entries` | array | yes | Timeline entry objects |
| `entries[].date` | string | yes | Entry date `"YYYY-MM-DD"` |
| `entries[].title` | string | yes | Entry title |
| `entries[].mood` | array | yes | Mood tags |
| `entries[].abstract` | string | yes | Entry abstract/summary |
| `entries[].path` | string | yes | Relative journal path |
| `total` | int | yes | Total number of entries |

#### Field Semantics

- `success`: whether the timeline was generated successfully.
- `range`: two-element array of the requested time range (YYYY-MM format, inclusive).
- `entries`: sorted by date ascending.
- `entries[].path`: relative path to the journal file.
- `total`: total count of entries in the response.

#### Error Behavior / Error Codes

**Known deviation**: `timeline` error handling is inconsistent with the unified error format.

- Invalid date format returns `{success: false, error: "Invalid date format..."}` where `error` is a **plain string**, not a structured `{code, message, details, recovery_strategy}` object.
- The `success` and `error` keys are present, but `error` does not conform to the unified error object format documented in the 通用规范.
- Runtime alignment to the structured error format is deferred to a post-M16 milestone.

#### schema_version Policy

`timeline` emits a top-level `schema_version` field set to `"m16.timeline.v0"`. Top-level field names and types are stable; new fields may be added without a version bump. A `schema_version` bump will accompany any backward-incompatible change.

<!-- /M16-CONTRACT -->

### 端点

```bash
life-index timeline --range <START> <END> [--topic <topic>]
python -m tools timeline --range <START> <END> [--topic <topic>]
```

### 参数

| 名称 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--range` | string×2 | ✅ | — | 时间范围，两个 `YYYY-MM` 参数（起止月份，均包含） |
| `--topic` | string | ❌ | — | 按主题过滤 |

### 返回值

```json
{
  "success": true,
  "range": ["2026-01", "2026-03"],
  "entries": [
    {
      "date": "2026-01-15",
      "title": "项目启动",
      "mood": ["focused"],
      "abstract": "开始了新项目的开发...",
      "path": "Journals/2026/01/life-index_2026-01-15_001.md"
    }
  ],
  "total": 25
}
```

### 行为约束

- **只读**：不创建、修改或删除任何文件。
- `entries` 按日期升序排列。
- `--topic` 过滤匹配 frontmatter `topic` 字段（列表中任一元素）。
- 日期格式错误时返回 `success: false`，`error` 字段含描述。

---

## on-this-day

<!-- M24-CONTRACT: on-this-day -->

### M24 Public JSON Contract: on-this-day

#### JSON Shape / Top-Level Fields

| Field | Type | Always Present | Description |
|-------|------|----------------|-------------|
| `success` | bool | yes | Whether the command succeeded |
| `command` | string | yes | Fixed `"on-this-day"` |
| `schema_version` | string | yes | `"m24.on_this_day.v0"` |
| `query` | object | yes | Echo of resolved query/date parameters |
| `query.date` | string | yes | Target date `"YYYY-MM-DD"` (defaults to today) |
| `query.month_day` | string | yes | Target month/day `"MM-DD"` used for matching |
| `query.years_back` | int | yes | Years lookback range used |
| `query.since_year` | int | yes | First prior year scanned |
| `query.until_year` | int | yes | Last prior year scanned; excludes target year |
| `matches` | array | yes | Array of match objects (may be empty) |
| `matches[].date` | string | yes | Entry date `"YYYY-MM-DD"` |
| `matches[].year` | int | yes | Entry year |
| `matches[].years_ago` | int | yes | How many years before target |
| `matches[].title` | string | yes | Entry title |
| `matches[].abstract` | string | yes | Entry abstract |
| `matches[].mood` | array | yes | Mood tags from the timeline entry |
| `matches[].path` | string | yes | Relative journal path (forward slashes only) |
| `matches[].source_command` | string | yes | Fixed `"timeline"` |
| `total` | int | yes | Count of returned matches |
| `evidence_paths` | array | yes | Array of relative paths |
| `source_contracts` | array | yes | `[{command: "timeline", contract: "M16 Public JSON Contract"}]` |
| `limitations` | array | yes | Human-readable limitation notes |
| `performance` | object | yes | `{timeline_calls, total_time_ms}` |
| `error` | object\|null | yes | Structured error on failure; `null` on success |

#### Field Semantics

- `success`: execution success. No matches is still `success: true` with `total: 0` and `matches: []`.
- `command`: always `"on-this-day"`.
- `schema_version`: `"m24.on_this_day.v0"`.
- `query.date`: the resolved target date in YYYY-MM-DD format (defaults to today).
- `query.month_day`: the same-month/day key used to filter timeline entries.
- `query.years_back`: the lookback range in years (`target_year - years_back` through `target_year - 1`).
- `query.since_year` / `query.until_year`: inclusive prior-year scan bounds.
- `matches`: sorted newest-first by date; excludes the target year.
- `matches[].path`: relative path with forward slashes only; no backslashes.
- `total`: count of matches actually returned (after `--limit` applied).
- `source_contracts`: identifies the upstream data source contract.
- `performance.timeline_calls`: number of timeline subprocess invocations.

#### Error Behavior / Error Codes

| Code | Meaning | Recovery Strategy |
|------|---------|-------------------|
| E2401 | Invalid `--date` format | ask_user |
| E2402 | Invalid numeric bounds (`--years-back` or `--limit`) | ask_user |
| E2403 | Timeline subprocess/contract failure | retry |

#### schema_version Policy

`on-this-day` emits `schema_version = "m24.on_this_day.v0"`. Top-level field names and types are stable; new fields may be added without a version bump. A version bump will accompany any backward-incompatible change.

<!-- /M24-CONTRACT -->

### 端点

```bash
life-index on-this-day [--date YYYY-MM-DD] [--years-back N] [--limit N] [--json]
python -m tools on-this-day [--date YYYY-MM-DD] [--years-back N] [--limit N] [--json]
```

### 参数

| 名称 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--date` | string | ❌ | today | 目标日期 (YYYY-MM-DD) |
| `--years-back` | int | ❌ | 10 | 向前回溯年数 |
| `--limit` | int | ❌ | 20 | 最大返回条数 |
| `--json` | flag | ❌ | true | 输出 JSON（唯一格式） |

### 返回值

```json
{
  "success": true,
  "command": "on-this-day",
  "schema_version": "m24.on_this_day.v0",
  "query": {
    "date": "2026-05-19",
    "month_day": "05-19",
    "years_back": 10,
    "since_year": 2016,
    "until_year": 2025
  },
  "matches": [
    {
      "date": "2025-05-19",
      "year": 2025,
      "years_ago": 1,
      "title": "Example title",
      "abstract": "Example abstract",
      "mood": ["calm"],
      "path": "Journals/2025/05/life-index_2025-05-19_001.md",
      "source_command": "timeline"
    }
  ],
  "total": 1,
  "evidence_paths": [
    "Journals/2025/05/life-index_2025-05-19_001.md"
  ],
  "source_contracts": [
    {"command": "timeline", "contract": "M16 Public JSON Contract"}
  ],
  "limitations": [
    "Deterministic same-month/day recall aid; not narrative synthesis.",
    "Relies on timeline CLI subprocess for journal discovery."
  ],
  "performance": {
    "timeline_calls": 10,
    "total_time_ms": 500
  },
  "error": null
}
```

### 行为约束

- **只读**：不创建、修改或删除任何文件。
- 通过 `timeline` CLI 子进程发现日志条目；不直接扫描 `Journals/**`。
- 排除目标年份的条目。
- `matches` 按日期降序排列（newest-first）。
- 所有路径为相对路径，仅使用正斜杠。

---

## recall

<!-- GBRAIN-E-CONTRACT: recall -->

### recall Public JSON Contract

#### JSON Shape / Top-Level Fields

| Field | Type | Always Present | Description |
|-------|------|----------------|-------------|
| `success` | bool | yes | Whether the recall search succeeded |
| `schema_version` | string | yes | `"gbrain.recall.v1"` |
| `mode` | string | yes | Requested mode: `default` / `recall` / `deep` |
| `effective_mode` | string | yes | Actual mode used (may differ from `mode` on degradation) |
| `query` | string | yes | Search query string |
| `results` | array | yes | Array of search result objects from L2 (may be empty) |
| `source_command` | string | yes | L2 command used: `search --no-semantic` / `search` / `smart-search --use-llm` |
| `performance` | object | yes | `{total_time_ms}` |
| `error` | object\|null | yes | Structured error on failure; `null` on success |

#### Field Semantics

- `success`: search execution success. Empty results is still `success: true` with `results: []`.
- `mode`: the mode requested by the caller.
- `effective_mode`: the mode actually executed. When `mode=deep` but `--use-llm` not provided, `effective_mode` will be `recall` (degradation).
- `source_command`: identifies which L2 command was used — confirms subprocess boundary.
- `results`: extracted from L2 output (`merged_results` from `search`, `filtered_results` from `smart-search`).

#### Mode Behavior

| Mode | L2 Command | LLM? | Notes |
|------|-----------|------|-------|
| `default` | `search --no-semantic` | No | Pure FTS keyword search. `--use-llm` ignored. |
| `recall` | `search` | No | Default hybrid search (FTS + semantic fallback). `--use-llm` ignored. |
| `deep` + `--use-llm` | `smart-search --use-llm` | Yes (opt-in) | LLM-enhanced search with explicit opt-in. |
| `deep` (no `--use-llm`) | `search` | No | Degrades to `recall` mode. Stderr warning emitted. `effective_mode=recall`. |

#### Error Behavior / Error Codes

| Code | Meaning | Recovery Strategy |
|------|---------|-------------------|
| E2501 | Invalid mode value | ask_user |
| E2502 | Empty query | ask_user |
| E2503 | L2 subprocess failure | retry |

#### schema_version Policy

`recall` emits `schema_version = "gbrain.recall.v1"`. Top-level field names and types are stable; new fields may be added without a version bump.

<!-- /GBRAIN-E-CONTRACT -->

### 端点

```bash
life-index recall --mode {default|recall|deep} --query "..." [--use-llm]
python -m tools recall --mode {default|recall|deep} --query "..." [--use-llm]
```

### 参数

| 名称 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--mode` | enum | ✅ | - | 搜索模式：`default`（纯 FTS）、`recall`（混合）、`deep`（LLM 需 opt-in） |
| `--query` | string | ✅ | - | 搜索查询字符串 |
| `--use-llm` | flag | ❌ | false | 显式启用 LLM 搜索（仅影响 `deep` 模式） |

### 返回值

```json
{
  "success": true,
  "schema_version": "gbrain.recall.v1",
  "mode": "default",
  "effective_mode": "default",
  "query": "python",
  "results": [
    {
      "path": "C:/Users/.../Journals/2026/03/life-index_2026-03-01_001.md",
      "rel_path": "Journals/2026/03/life-index_2026-03-01_001.md",
      "title": "Python Learning",
      "date": "2026-03-01",
      "rrf_score": 0.85
    }
  ],
  "source_command": "search --no-semantic",
  "performance": {
    "total_time_ms": 50
  },
  "error": null
}
```

### 行为约束

- **只读**：不创建、修改或删除任何文件。
- 通过 subprocess 调用 L2 `search` / `smart-search`；不直接 import L2 内部模块。
- `default` 和 `recall` 模式：零 LLM 调用。
- `deep` 模式不带 `--use-llm`：自动降级到 `recall`，stderr 输出警告。
- `--use-llm` 仅对 `deep` 模式有效；`default` 和 `recall` 模式忽略此标志。
- 保留 `LIFE_INDEX_DATA_DIR` 环境变量传递给子进程。

---

## entity

<!-- M16-CONTRACT: entity -->

### M16 Public JSON Contract: entity

#### JSON Shape / Top-Level Fields

`entity` has multiple subcommand shapes. All share a common envelope pattern but with known deviations:

**Standard envelope** (used by `--audit`, `--stats`, `--check`, `--review`, `--delete`, `--list`):

| Field | Type | Always Present | Description |
|-------|------|----------------|-------------|
| `success` | bool | yes | Whether the subcommand succeeded |
| `schema_version` | string | yes | `"v1.1.1"` — top-level output schema版本（取代 `m16.entity.v0`） |
| `provenance` | object | yes | Provenance envelope；详见 [v1.1.1 Observability Contract](#v111-observability-contract) |
| `data` | object\|array | yes | Subcommand-specific result payload |
| `error` | null\|string | yes | `null` on success; string on some error paths |

**`--merge` deviation** (flat envelope, no `data` wrapper):

| Field | Type | Description |
|-------|------|-------------|
| `success` | bool | Whether the merge succeeded |
| `action` | string | `"merge_as_alias"` |
| `source_id` | string | Source entity ID |
| `target_id` | string | Target entity ID |
| `transferred_names` | array | Names/aliases transferred from source to target |

**`--resolve` envelope:**

| Field | Type | Description |
|-------|------|-------------|
| `success` | bool | Whether resolution succeeded |
| `data` | object\|null | Resolved entity or null |
| `error` | null\|string | `null` on success; plain string (e.g., `"Entity not found"`) on failure |

#### Field Semantics

- `success`: subcommand execution success.
- `data`: subcommand-specific payload. Shape varies by subcommand (see per-subcommand examples below).
- `error`: on most subcommands, `null` for success. Known deviations:
  - `--resolve` returns a plain string error message on failure (not a structured error object).
  - `--merge` returns a flat object without `data` wrapper.
- `--audit` data contains: `audit_date`, `total_entities`, `issues[]`, `summary{}`.
- `--stats` data contains: `total_entities`, `by_type{}`, `total_aliases`, `total_relationships`, `top_referenced[]`, `top_cooccurrence[]`.
- `--check` data contains: `total_entities`, `issues[]`, `summary{}`.

#### Error Behavior / Error Codes

**Known deviations**: `entity` error handling is inconsistent across subcommands.

- Most read subcommands (`--audit`, `--stats`, `--check`, `--review`) use the standard `{success, data, error}` envelope with `error: null` on success.
- `--merge` returns a **flat shape** without a `data` wrapper — this is a documented deviation from the standard envelope.
- `--resolve` returns `error` as a **plain string** (e.g., `"Entity not found"`) instead of a structured error object with `code`/`message`/`recovery_strategy`.
- Parser errors (missing required flags) raise `SystemExit` with a plain text message, not a JSON error envelope.
- Runtime alignment to the unified error format is deferred to a post-M16 milestone.

#### schema_version Policy

`entity` emits a top-level `schema_version` field set to `"m16.entity.v0"`. Subcommand output shapes are stable; new fields in `data` objects may be added without a version bump. A `schema_version` bump will accompany any backward-incompatible change.

<!-- /M16-CONTRACT -->

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
| `--preview` | flag | ❌ | false | 仅预览影响，不修改图谱（配合 `--delete`） |
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
  "schema_version": "v1.1.1",
  "provenance": {
    "source_hash": "sha256:...",
    "tool_version": "1.1.1",
    "generated_at": "2026-05-23T10:00:00+00:00",
    "generator": "entity",
    "params_hash": "sha256:...",
    "fixture_version": null
  },
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
  "schema_version": "v1.1.1",
  "provenance": {
    "source_hash": "sha256:...",
    "tool_version": "1.1.1",
    "generated_at": "2026-05-23T10:00:00+00:00",
    "generator": "entity",
    "params_hash": "sha256:...",
    "fixture_version": null
  },
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
  "schema_version": "v1.1.1",
  "provenance": {
    "source_hash": "sha256:...",
    "tool_version": "1.1.1",
    "generated_at": "2026-05-23T10:00:00+00:00",
    "generator": "entity",
    "params_hash": "sha256:...",
    "fixture_version": null
  },
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
  "schema_version": "v1.1.1",
  "provenance": {
    "source_hash": "sha256:...",
    "tool_version": "1.1.1",
    "generated_at": "2026-05-23T10:00:00+00:00",
    "generator": "entity",
    "params_hash": "sha256:...",
    "fixture_version": null
  },
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
  "schema_version": "v1.1.1",
  "provenance": {
    "source_hash": "sha256:...",
    "tool_version": "1.1.1",
    "generated_at": "2026-05-23T10:00:00+00:00",
    "generator": "entity",
    "params_hash": "sha256:...",
    "fixture_version": null
  },
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

##### `--delete --preview --id ENTITY_ID`

预览删除影响，不修改实体图谱。返回与实际删除相同的 JSON 结构（`deleted_id`、`deleted_name`、`cleaned_refs`），但**不会移除实体或清理引用**：

```bash
life-index entity --delete --preview --id p003
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

> **注意**: `--preview` 仅配合 `--delete` 使用，对其他子命令无效。不带 `--preview` 的 `--delete` 行为不变（立即删除并落盘）。

#### `entity --seed`

从现有 journal frontmatter 中冷启动实体图谱：

```bash
life-index entity --seed
```

#### `entity --candidate-edges`

生成候选关系边报告（只读，零生产图谱写入）。扫描 journal 中的 `people` co-occurrence、`related_entries`、wikilinks `[[X]]` 与正文共现，输出去重后的候选边 JSON。

```bash
life-index entity --candidate-edges --output=json
```

返回：

```json
{
  "success": true,
  "schema_version": "v1.1.1",
  "provenance": {
    "source_hash": "sha256:...",
    "tool_version": "1.1.1",
    "generated_at": "2026-05-23T10:00:00+00:00",
    "generator": "entity",
    "params_hash": "sha256:...",
    "fixture_version": null
  },
  "candidates": [
    {
      "type": "people_cooccurrence",
      "source": "Alice",
      "target": "Bob",
      "evidence_paths": ["2026/05/life-index_2026-05-10_001.md"],
      "confidence": 0.2,
      "suggested_action": "review-required-low-confidence"
    }
  ],
  "total": 1,
  "error": null
}
```

**Candidate 字段说明**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `type` | string | 提取器类型：`people_cooccurrence` / `related_entry` / `wikilink` / `body_cooccurrence` |
| `source` | string | 源节点名称 |
| `target` | string | 目标节点名称 |
| `evidence_paths` | array | 支撑该候选的 journal 相对路径列表（至少 1 条） |
| `confidence` | float | 置信度 0.0–1.0，基于 evidence 数量线性计算 |
| `suggested_action` | string | 建议操作：`auto-confirm-recommended`（≥3 evidence）、`review-recommended`（2 evidence）、`review-required-low-confidence`（<2 evidence） |

**行为约束**：
- **只读**：不创建、修改或删除 `entity_graph.yaml` 或任何 journal 文件
- **确定性**：不调用 LLM，纯本地确定性扫描
- **路径隐私**：`evidence_paths` 均为相对路径，使用 `/` 分隔符

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
  "package_version": "1.1.0",
  "bootstrap_manifest": {
    "repo_version": "1.1.0",
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

> **E08xx 状态**: Reserved / 未实现。`tools/migrate/` 当前不发射结构化 E08xx 错误码；迁移失败以非结构化日志或异常形式报告。E0800–E0803 为预留编码，未来若迁移模块统一接入 `tools/lib/errors.py` 结构化错误体系时可启用。

### `life-index entity` — 实体图谱管理

Entity 管理工具在 Round 6 引入，现已成为独立一级命令。完整参数、操作模式、返回值结构和 Agent 约束见上文 `## entity` 章节。

---

## trajectory

### 端点

```bash
life-index trajectory --field {weight|sleep|mood|location|project} --range YYYY-MM..YYYY-MM
python -m tools trajectory --field weight --range 2025-01..2025-12
```

### 参数

| 名称 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| field | enum | ✅ | - | 提取字段: `weight`, `sleep`, `mood`, `location`, `project` |
| range | string | ✅ | - | 月份范围 `YYYY-MM..YYYY-MM` (含起止) |

### 返回值

```json
{
  "success": true,
  "command": "trajectory",
  "schema_version": "v1.1.1",
  "provenance": {
    "source_hash": "sha256:...",
    "tool_version": "1.1.1",
    "generated_at": "2026-05-23T10:00:00+00:00",
    "generator": "trajectory",
    "params_hash": "sha256:...",
    "fixture_version": null
  },
  "field": "weight",
  "range": ["2025-01", "2025-12"],
  "observations": [
    {
      "type": "weight",
      "value": 72.5,
      "time": "2025-01-15",
      "evidence_paths": ["Journals/2025/01/life-index_2025-01-15_001.md"]
    }
  ],
  "total": 1,
  "performance": {
    "files_scanned": 12,
    "total_time_ms": 15
  },
  "error": null
}
```

### 字段语义

- `observations`: 按时间升序排列的 typed observation 列表。
- `observations[].type`: 与 `--field` 一致。
- `observations[].value`: 提取值。`weight`/`sleep` 为数值; `mood`/`location`/`project` 为字符串。
- `observations[].time`: 来源日志的 `date` 字段 (YYYY-MM-DD)。
- `observations[].evidence_paths`: 指向来源日志文件的路径数组（相对 `LIFE_INDEX_DATA_DIR`）。
- `performance.files_scanned`: L2 `search` 返回并被 trajectory 处理的候选日志条目数；不是 trajectory 直接文件系统扫描计数。
- **只读语义**: 本命令不写入、不修改任何 L1 frontmatter 或 journal 文件。

### 错误码

| 代码 | 说明 | 恢复策略 |
|------|------|----------|
| E2601 | 无效 field | ask_user |
| E2602 | 无效 range 格式 | ask_user |

### 说明

- `trajectory` 是 L3 模块，通过 L2 `search` CLI 子进程读取候选日志内容并提取 typed observations；不直接扫描 `Journals/**`，不直接读写 L1 文件。
- 各 field 的提取策略：
  - `weight`: frontmatter `weight_kg` + 正文 `体重: XX.X kg` / `weight XX.X kg` 模式。
  - `sleep`: frontmatter `sleep_hours` + 正文 `睡了 X 小时` / `slept X hours` 模式。
  - `mood`: frontmatter `mood` 列表 + 正文 emoji 与描述词。
  - `location`: frontmatter `location` + 正文 `在 XX` / `in/at XX` 模式。
  - `project`: frontmatter `project` + tags + 正文项目名模式。
- 默认路径无 LLM 调用，全部确定性提取。
- 支持 `LIFE_INDEX_DATA_DIR` 环境变量覆盖数据目录。

---

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
