# 每日索引维护场景指南

> **场景**：检查索引一致性，修复问题（如需），更新向量索引
> **触发**：每天 23:50

---

## 背景说明

**重要**：`write_journal.py` 在写入日志时会**自动更新**以下索引：
- `by-topic/主题_xxx.md`（主题索引）
- `by-topic/项目_xxx.md`（项目索引）
- `by-topic/标签_xxx.md`（标签索引）
- `monthly_report_YYYY-MM.md`（月度摘要）

因此，每日任务的目的是**检查+修复**，而非更新。

**向量索引**（用于语义搜索）需要单独更新，不会自动触发。

---

## 触发条件

| 类型 | 条件 | 行为 |
|------|------|------|
| **Immediate** | 系统时间到达 23:50 | 自动执行 |

---

## 执行流程

### Step 1: 扫描昨日日志

**命令**：
```bash
python -m tools.search_journals --date-from {YESTERDAY} --date-to {YESTERDAY} --limit 100
```

**参数说明**：
- `{YESTERDAY}`: 昨日日期，格式 `YYYY-MM-DD`
- 示例: `python -m tools.search_journals --date-from 2026-03-10 --date-to 2026-03-10 --limit 100`

**输出解析**：
```json
{
  "success": true,
  "data": [
    {"title": "...", "path": "Journals/2026/03/life-index_2026-03-10_001.md", ...}
  ]
}
```

**记录结果**：
```
昨日日志数量：{COUNT}
日志路径列表：[...]
```

---

### Step 2: 检查索引一致性

**检查项**：

| 检查项 | 说明 | 通过条件 |
|--------|------|----------|
| **主题索引** | 每篇日志的 topic 是否都有对应的 `by-topic/主题_xxx.md` | 所有日志都被引用 |
| **项目索引** | 每篇日志的 project 是否都有对应的 `by-topic/项目_xxx.md` | 所有日志都被引用 |
| **标签索引** | 每篇日志的 tags 是否都有对应的 `by-topic/标签_xxx.md` | 所有日志都被引用 |
| **月度摘要** | 当月是否有 `monthly_report_YYYY-MM.md` | 文件存在 |

**执行方式**：
1. 读取昨日日志的 frontmatter
2. 检查对应的索引文件是否存在
3. 检查索引文件是否包含该日志的引用

**结果判断**：
```
IF 所有检查项通过:
  → 记录 "索引一致性检查通过"
  → Proceed to Step 4（向量增量更新）

IF 发现不一致:
  → 记录问题详情
  → Proceed to Step 3（自动修复）
```

---

### Step 3: 自动修复（如需）

**触发条件**：Step 2 发现不一致

**命令**：
```bash
python -m tools.build_index
```

**说明**：
- 增量模式会修复缺失的索引引用
- 不会影响已有索引

**修复后验证**：
```
IF 修复成功:
  → 记录修复详情
  → Proceed to Step 4

IF 修复失败:
  → 记录错误
  → 通知用户
  → 结束执行
```

---

### Step 4: 向量增量更新

**前提条件**：已安装 `sentence-transformers`

**命令**：
```bash
python -m tools.build_index
```

**说明**：
- 增量更新向量索引
- 仅处理新增/修改的日志

**跳过条件**：
```
IF sentence-transformers 未安装:
  → 记录 "向量索引跳过：未安装 sentence-transformers"
  → 继续执行 Step 5
```

---

### Step 5: 记录结果

**成功（无问题）**：
```
日志记录："[{NOW}] Daily index maintenance completed. Journals scanned: {COUNT}, Issues: 0"
```

**成功（发现并修复问题）**：
```
日志记录："[{NOW}] Daily index maintenance completed. Issues found: {N}, Fixed: {N}"
```

**失败**：
```
日志记录："[{NOW}] Daily index maintenance failed: {ERROR}"
通知用户
```

---

## 验证规则

### 索引一致性检查清单

```
验证项：
- [ ] 昨日日志已扫描 ✓
- [ ] 主题索引引用完整 ✓
- [ ] 项目索引引用完整 ✓
- [ ] 标签索引引用完整 ✓
- [ ] 月度摘要存在 ✓
- [ ] 向量索引已更新（如已安装依赖）✓
```

---

## 错误处理

| 场景 | 处理 | 重试 |
|------|------|------|
| 工具执行失败 | 记录错误，通知用户 | 下次执行 |
| 发现索引不一致 | 自动修复 | 是 |
| 修复失败 | 记录错误，通知用户 | 否 |
| 向量更新跳过 | 记录原因，继续执行 | N/A |

---

## 快速参考

```
执行时间：每天 23:50
任务性质：检查 + 修复 + 向量增量
关键发现：tools.write_journal 已自动更新 by-topic 索引
工具命令：python -m tools.build_index
输出形式：静默完成（问题/失败时通知）
```
