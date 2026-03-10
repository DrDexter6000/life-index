# Life Index 错误码参考

本文档定义所有错误码及其含义，便于 Agent 根据错误类型采取不同策略。

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