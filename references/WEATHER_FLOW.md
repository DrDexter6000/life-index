# 天气处理流程

本文档详细说明 Life Index 的天气处理机制。

## 三层天气处理机制

`tools.write_journal` 内置完整天气处理逻辑，Agent 只需调用工具，无需额外处理。

### 第一层：用户提及为准

如果用户明确提供了 location 和 weather 字段，直接使用用户提供的值，不进行任何查询或修改。

**示例**：
```
用户：记录日志，地点是北京，天气晴天，今天完成了...
→ location = "北京" → 规范化为 "Beijing, China"
→ weather = "晴天" → 直接使用
```

### 第二层：自动填充（工具内部处理）

当用户未提供 location 或 weather 时，工具自动处理：

| 场景 | location 处理 | weather 处理 |
|------|--------------|--------------|
| 都未提供 | 使用默认 "Chongqing, China" | 调用天气 API 查询 |
| 仅提供 location | 规范化地点名 | 调用天气 API 查询 |
| 仅提供 weather | 使用默认地点 | 直接使用用户值 |

**地点规范化规则**：

| 用户输入 | 规范化结果 |
|---------|-----------|
| "重庆" | "Chongqing, China" |
| "重庆，中国" | "Chongqing, China" |
| "Tokyo, Japan" | "Tokyo, Japan" (不变) |
| 其他中文城市 | "{城市}, China" |

### 第三层：写入后确认（强制）

`tools.write_journal` 返回 JSON 后，Agent **必须执行**：

1. **检查 `needs_confirmation` 字段**
2. **如果为 `true`**：
   - **必须**展示 `confirmation_message` 给用户
   - **必须**询问："地点和天气是否正确？"
   - 等待用户回复
3. **如果用户需要修改**：
   - 调用 `python -m tools.edit_journal` 更新 location/weather

**禁止行为**：
- 看到 `success: true` 就直接结束
- 忽略 `needs_confirmation` 字段
- 不展示确认信息就结束对话

## 流程图

```
┌─────────────────────────────────────────────────────────────┐
│                    用户发起记录请求                           │
└─────────────────────────┬───────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  Agent 调用 write_journal.py                                 │
│  参数: title, content, date, [location?], [weather?]         │
└─────────────────────────┬───────────────────────────────────┘
                          ▼
            ┌─────────────┴─────────────┐
            │  用户提供 location?        │
            └─────────────┬─────────────┘
                   ┌──────┴──────┐
                   │             │
                  Yes           No
                   │             │
                   ▼             ▼
         ┌──────────────┐  ┌──────────────────────┐
         │ 使用用户值    │  │ 默认 "Chongqing,     │
         │              │  │ China"               │
         └──────┬───────┘  └──────────┬───────────┘
                │                     │
                └──────────┬──────────┘
                           ▼
            ┌─────────────┴─────────────┐
            │  用户提供 weather?         │
            └─────────────┬─────────────┘
                   ┌──────┴──────┐
                   │             │
                  Yes           No
                   │             │
                   ▼             ▼
         ┌──────────────┐  ┌──────────────────────┐
         │ 使用用户值    │  │ 调用 query_weather   │
         │              │  │ 自动查询天气          │
         └──────┬───────┘  └──────────┬───────────┘
                │                     │
                └──────────┬──────────┘
                           ▼
              ┌────────────────────────┐
              │  写入日志文件           │
              │  返回 needs_confirmation│
              └────────────┬───────────┘
                           ▼
              ┌────────────────────────┐
              │  Agent 展示确认信息     │
              │  "地点: X, 天气: Y      │
              │   是否正确？"           │
              └────────────┬───────────┘
                           ▼
            ┌─────────────┴─────────────┐
            │  用户确认                  │
            └─────────────┬─────────────┘
                   ┌──────┴──────┐
                   │             │
                正确          需修改
                   │             │
                   ▼             ▼
              ┌────────┐  ┌──────────────────────┐
              │ 完成   │  │ 调用 edit_journal.py │
              └────────┘  │ 更新 location/weather│
                          └─────────────────────┘
```

## 用户修改场景处理

**重要**：`tools.edit_journal` **不会自动查询天气**，Agent 需要手动调用 `tools.query_weather`。

| 用户反馈 | Agent 操作 |
|:---|:---|
| 用户补充了地点和天气 | 调用 `python -m tools.edit_journal --set-location "..." --set-weather "..."` |
| 用户只补充了地点 | 1. 调用 `python -m tools.query_weather --location "..."` 获取天气<br>2. 调用 `python -m tools.edit_journal --set-location "..." --set-weather "..."` |
| 用户只补充了城市（如"北京"） | 1. 推断为"北京，中国"<br>2. 调用 `python -m tools.query_weather --location "Beijing, China"`<br>3. 调用 `python -m tools.edit_journal --set-location "..." --set-weather "..."` |

**错误示例**（不要这样做）：
```bash
# 只传 location，期望工具自动查询天气
python -m tools.edit_journal --set-location "Lagos"
# ❌ 结果：weather 字段不会更新
```

**正确示例**：
```bash
# Step 1: 查询天气
python -m tools.query_weather --location "Lagos, Nigeria"

# Step 2: 同时更新地点和天气
python -m tools.edit_journal --journal "..." --set-location "Lagos, Nigeria" --set-weather "阵雨 33.3°C/28.5°C"
```

## 天气 API 故障处理

当 `query_weather` 工具的天气 API 不可用时，遵循以下 **Fallback 链**：

### 第一层：工具内置 API（自动）

`write_journal` 内部调用 `query_weather`，如果 API 返回错误：
- 工具返回 `weather_auto_filled: false`
- 日志正常写入，weather 字段为空
- 返回 `needs_confirmation: true`

### 第二层：Agent 网络搜索 Fallback（**Agent-First 原则**）

**当工具返回天气查询失败时**，Agent 应利用自身能力进行 Fallback：

1. **使用网络搜索工具**
   - 搜索查询：`"{location} weather {date}"` 或 `"{location} 天气 {日期}"`
   - 从搜索结果中提取天气信息

2. **Fallback 成功**
   - 将搜索到的天气信息通过 `edit_journal` 写入日志
   - 告知用户天气来源

3. **Fallback 失败**
   - 告知用户天气查询失败
   - 询问用户是否手动输入天气

### 流程图（故障处理）

```
天气 API 失败
      │
      ▼
┌─────────────────────────┐
│ Agent 使用网络搜索工具   │
│ 查询 {location} 天气     │
└───────────┬─────────────┘
            │
      ┌─────┴─────┐
      │           │
   成功         失败
      │           │
      ▼           ▼
┌──────────┐  ┌──────────────────┐
│ 调用      │  │ 告知用户失败      │
│ edit_    │  │ 询问是否手动输入  │
│ journal  │  └──────────────────┘
└──────────┘
```

### Agent 行为示例

```
工具返回：weather_auto_filled: false, needs_confirmation: true

Agent：
1. 检测到天气查询失败
2. 使用网络搜索："Beijing China weather March 10 2026"
3. 从搜索结果提取天气信息："Partly cloudy, 15°C"
4. 调用 python -m tools.edit_journal --set-weather "Partly cloudy, 15°C"
5. 告知用户：日志已保存。天气来源于网络搜索：Partly cloudy, 15°C。是否正确？
```

**这体现了 Agent-First 原则**：工具提供基础能力，Agent 利用自身能力增强体验。
