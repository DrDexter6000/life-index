# 日报场景指南

> **场景**：生成今日日志的智能日报并推送给用户
> **触发**：每天 22:00 / 用户说"生成日报"
> **模板**：[daily-template.md](../templates/daily-template.md)

---

## 触发条件

| 类型 | 条件 | 行为 |
|------|------|------|
| **Immediate** | 系统时间到达 22:00 ± 15 分钟 + 当日有日志 | 自动执行 |
| **Manual** | 用户说"生成日报"、"daily report"、"今日总结" | 执行，可选确认 |
| **Soft** | 用户说"快10点了"、"准备睡觉" | 询问是否生成 |

---

## 执行流程

### Step 1: 获取今日日志

**命令**：
```bash
python tools/search_journals.py --date {TODAY} --limit 100
```

**参数说明**：
- `{TODAY}`: 当天日期，格式 `YYYY-MM-DD`
- 示例: `python tools/search_journals.py --date 2026-03-11 --limit 100`

**输出解析**：
```json
{
  "success": true,
  "data": [
    {"title": "...", "content": "...", "date": "..."}
  ]
}
```

**条件判断**：
```
IF data.length == 0:
  → Skip, log "No journals today"
  → 结束执行

IF data.length > 0:
  → Proceed to Step 2
```

---

### Step 2: 生成报告内容

**阅读模板**：[daily-template.md](../templates/daily-template.md)

**Token 预算**：~200 tokens

**内容结构**：

| Section | Token | 内容要求 | 格式 |
|---------|-------|---------|------|
| 标题 | ~10 | 【Life Index 日报】{日期} | 固定 |
| 今日概要 | 30-50 | 2-3 句话 | 纯文本 |
| 要点速览 | 60-100 | 3-5 条 | `• ` 开头 |
| AI 建议 | 30-50 | 1-3 条 | `→ ` 开头 |
| 要事提醒 | 0-30 | 待办（可为空） | `🔔 ` 开头 |

**生成要求**：
1. 使用 Agent 自然语言生成能力
2. 从日志中提取核心内容
3. 控制总 Token 在预算内

---

### Step 3: 推送前验证

**⛔ STOP. 推送前验证**：

```
验证清单：
- [ ] 今日概要：2-3 句话 ✓
- [ ] 要点速览：3-5 条 ✓
- [ ] AI 建议：1-3 条 ✓
- [ ] 要事提醒：如有待办则列出，否则"无待跟进事项" ✓

检查敏感信息：
- [ ] 无密码、密钥、隐私内容 ✓
- [ ] 如有敏感信息，已脱敏 ✓
```

**验证失败**：
- 补充缺失内容后重新验证
- 最多重试 2 次

---

### Step 4: 推送消息

**推送渠道**：
1. **主会话**（Main Session）- 始终推送
2. **IM 通讯软件渠道**（如 Slack、Telegram、微信）- 已配置则推送

**推送格式**：
```
【Life Index 日报】2026-03-11

📝 今日概要
{内容}

⚡ 要点速览
• {要点1}
• {要点2}
...

💡 AI 建议
→ {建议1}
...

🔔 要事提醒
{内容或"无待跟进事项"}
```

---

### Step 5: 记录执行

**成功**：
```
日志记录："[{NOW}] Daily report sent. Journals: {COUNT}, Tokens: ~{ESTIMATED}"
```

**失败**：
```
日志记录："[{NOW}] Daily report failed: {ERROR}"
保存报告到：~/Documents/Life-Index/memory/pending-reports/daily_{DATE}.md
```

---

## 错误处理

| 场景 | 处理 |
|------|------|
| 无日志 | 跳过执行，不发送空报告 |
| 工具失败 | 记录错误，下次执行重试 |
| 推送失败 | 保存报告到文件，下次会话展示 |

---

## 快速参考

```
执行时间：每天 22:00
Token 预算：~200
输出形式：推送（不保存文件）
模板文档：../templates/daily-template.md
```