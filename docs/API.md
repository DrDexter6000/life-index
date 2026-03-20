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

### 通用返回格式

```json
{
  "success": true|false,
  "data": { ... },
  "error": {
    "code": "E0000",
    "message": "错误信息",
    "details": { ... },
    "recovery_strategy": "ask_user|skip_optional|continue_empty|fail"
  }
}
```

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
| title | string | ✅ | - | 日志标题（≤20字） |
| content | string | ✅ | - | 日志正文（原样保留） |
| date | string | ✅ | - | 日期（ISO 8601: YYYY-MM-DD） |
| location | string | ❌ | 默认地点兜底 | 地点；若正文中已明确写出地点，优先采用正文信息；仅在正文和入参都未提供时才使用默认地点 |
| weather | string | ❌ | 自动查询/手动兜底 | 天气描述；若正文中已明确写出天气，优先采用正文信息 |
| mood | array | ❌ | [] | 心情标签 |
| people | array | ❌ | [] | 相关人物 |
| topic | array | ✅ | - | 主题分类（7类之一） |
| project | string | ❌ | "" | 关联项目 |
| tags | array | ❌ | [] | 标签 |
| abstract | string | ✅ | - | 摘要（≤100字，**Agent生成**） |
| links | array | ❌ | [] | 相关链接 |
| attachments | array | ❌ | [] | 附件列表 |

### 附件对象格式

```json
{
  "source_path": "C:/Users/xxx/file.png",
  "description": "附件说明"
}
```

### 返回值

```json
{
  "success": true,
  "data": {
    "journal_path": "Journals/2026/03/life-index_2026-03-10_001.md",
    "updated_indices": ["主题_work.md", "项目_Life-Index.md"],
    "attachments_processed": [...],
    "location_used": "Beijing, China",
    "location_auto_filled": false,
    "weather_used": "Sunny 25°C",
    "weather_auto_filled": true,
    "needs_confirmation": true,
    "confirmation_message": "日志已保存。地点：Beijing, China；天气：Sunny 25°C。请确认以上信息是否正确？"
  }
}
```

### 写入与确认语义

- `needs_confirmation` 应视为当前写入协议中的正常后续步骤，而不是可忽略的偶发分支
- 正文中明确写出的地点/天气优先级最高，Agent 不得再用默认地点或自动查询结果覆盖
- 只有在正文和入参都未提供地点、工具使用了默认地点时，Agent 才必须展示 `confirmation_message` 并等待用户确认或修正
- 如果用户要求修正地点/天气，后续应进入 correction flow，而不是把原写入描述为失败

### 写入成功 / 降级 / 修复语义

- `journal_path` 可被成功返回时，应优先理解为**核心 journal 已 durably saved**
- `needs_confirmation: true` 表示“写入成功但仍需确认/修正”，**不等于写入失败**
- 索引、附件、补充信息等 side effects 若处于降级状态，应报告为“已保存，但仍有后续修复或可见性问题”，不应抹掉核心写入成功这一事实
- Agent 必须保留这三种区别：
  1. 写入失败
  2. 写入成功，但仍需 confirmation / correction
  3. 写入成功，但 side effects / index visibility 不完整

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

### 返回值

```json
{
  "success": true,
  "data": {
    "query": "重构",
    "total": 5,
    "results": [
      {
        "path": "Journals/2026/03/life-index_2026-03-06_001.md",
        "title": "搜索功能重构",
        "date": "2026-03-06",
        "location": "Chongqing, China",
        "abstract": "完成了搜索架构的重构...",
        "score": 0.85
      }
    ],
    "search_level": 3,
    "search_time_ms": 45
  }
}
```

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
  "data": {
    "journal_path": "Journals/2026/03/life-index_2026-03-10_001.md",
    "changes": {
      "location": {"old": "Chongqing, China", "new": "Beijing, China"},
      "weather": {"old": "Sunny", "new": "Cloudy"}
    }
  }
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
  "data": {
    "location": "Beijing, China",
    "date": "2026-03-10",
    "weather": "Partly cloudy",
    "temperature": {
      "max": 18.5,
      "min": 8.2,
      "unit": "celsius"
    },
    "description": "Partly cloudy 18.5°C/8.2°C"
  }
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

## generate_abstract

### 端点

```bash
python -m tools.generate_abstract [options]
```

### 参数

| 名称 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| month | string | ❌ | - | 生成月度摘要 (YYYY-MM) |
| year | int | ❌ | - | 生成年度摘要 (YYYY) |
| all-months | flag | ❌ | false | 与 year 一起使用，批量生成全年 |
| dry-run | flag | ❌ | false | 预览模式 |

### 返回值

```json
{
  "success": true,
  "data": {
    "type": "monthly",
    "period": "2026-03",
    "output_path": "Journals/2026/03/monthly_abstract.md",
    "stats": {
      "total_journals": 15,
      "by_topic": {"work": 8, "life": 5, "learn": 2}
    }
  }
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

### 返回值

```json
{
  "success": true,
  "data": {
    "journals_indexed": 45,
    "index_path": ".vector_index/journals_fts.db",
    "build_time_ms": 1200,
    "validation": {
      "status": "passed",
      "issues": []
    }
  }
}
```

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
