# 月报场景指南

> **场景**：生成本月日志的智能月报，保存文件并推送给用户
> **触发**：每月最后一天 18:30 / 用户说"生成月报"
> **模板**：[monthly-template.md](../templates/monthly-template.md)

---

## 触发条件

| 类型 | 条件 | 行为 |
|------|------|------|
| **Immediate** | 系统时间到达月末 18:30 + 本月有日志 | 自动执行 |
| **Manual** | 用户说"生成月报"、"monthly report" | 执行，可选确认 |

---

## 执行流程

### Step 1: 获取本月日志

**命令**：
```bash
python tools/search_journals.py --month {YEAR}-{MONTH} --limit 2000
```

**参数说明**：
- `{YEAR}-{MONTH}`: 年月，格式 `YYYY-MM`
- 示例: `python tools/search_journals.py --month 2026-03 --limit 2000`

**条件判断**：
```
IF data.length == 0:
  → Skip, log "No journals this month"
  → 结束执行

IF data.length > 0:
  → Proceed to Step 2
```

---

### Step 2: 生成报告内容

**阅读模板**：[monthly-template.md](../templates/monthly-template.md)

**Token 预算**：~1000 tokens

**内容结构**：

| Section | Token | 内容要求 | 格式 |
|---------|-------|---------|------|
| 标题 | ~10 | # Life Index 月度报告 | Markdown H1 |
| 元数据 | ~20 | 报告周期、生成时间 | 引用块 |
| 概要 | 100-150 | 本月核心内容 | 纯文本 |
| 要点回顾 | 150-200 | 7-10 条 | 编号列表 |
| AI 甄选 | 150-200 | Top 5 日志 | 表格 |
| 要事提醒 | 0-50 | 待办 | 编号列表 |
| 本月热点 | 200-300 | Top 10 | 编号列表 |

**AI 甄选规则**：
1. 从本月日志中筛选最重要的 5 篇
2. 推荐理由：项目里程碑、情感价值、学习收获等
3. 格式：表格（排名、标题、日期、推荐理由）

---

### Step 3: 获取国际热点

**执行方式**：
1. 使用 Agent 网络搜索能力
2. 搜索关键词：`this month world news`、`本月国际热点`
3. 筛选 Top 10，每条 1 句话描述

**超时设置**：60 秒

**失败处理**：
```
IF 热点获取失败:
  → 省略热点部分
  → 在报告中备注
```

---

### Step 4: 保存文件

**保存位置**：
```
~/Documents/Life-Index/Journals/{YEAR}/{MONTH}/monthly_report_{YEAR}-{MONTH}.md
```

**示例**：
```
~/Documents/Life-Index/Journals/2026/03/monthly_report_2026-03.md
```

**⛔ STOP. 保存前验证**：
```
验证清单：
- [ ] 文件路径正确：{YEAR}/{MONTH}/ ✓
- [ ] 文件名格式：monthly_report_{YEAR}-{MONTH}.md ✓
- [ ] 内容格式：Markdown，包含所有必填部分 ✓
```

**失败处理**：
```
IF 文件写入失败:
  → 先推送内容到主会话
  → 提示用户："月报已生成，但文件保存失败。请检查存储空间。"
```

---

### Step 5: 推送前验证

**⛔ STOP. 推送前验证**：

```
验证清单：
- [ ] 标题格式正确 ✓
- [ ] 元数据完整 ✓
- [ ] 概要：100-150 tokens ✓
- [ ] 要点回顾：7-10 条 ✓
- [ ] AI 甄选：Top 5 日志 ✓
- [ ] 文件已保存 ✓
```

---

### Step 6: 推送消息

**推送渠道**：主会话 + 已配置渠道

**消息内容**：
- 报告概要
- 文件路径

---

## 错误处理

| 场景 | 处理 |
|------|------|
| 无日志 | 跳过执行 |
| 热点获取失败 | 省略热点部分 |
| 文件保存失败 | 先推送内容，提示用户 |

---

## 快速参考

```
执行时间：每月最后一天 18:30
Token 预算：~1000
输出形式：文件 + 推送
保存位置：~/Documents/Life-Index/Journals/{YEAR}/{MONTH}/
模板文档：../templates/monthly-template.md
```