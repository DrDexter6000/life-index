# Fragment Playbook

When the user has just said something, a short thought, or dictation and the task is to keep the words themselves, the host agent loads this playbook before the first `fragment add`; do not use `write`.

```
.venv/bin/life-index fragment add --data '{"text":"用户的话，一字不改"}'
.venv/bin/life-index fragment add --data-file fragment.json   # Windows 大 payload 用文件
```

规则（机械执行）：

1. **原话原样传入 `text`**：不改写、不提炼、不加标题；工具只统一换行符并去
   首尾空白。碎片没有 title/topic/mood/tags/abstract——这些键会被拒绝并提
   示"碎片只存用户本人的原话与事实"。
2. **只在确实知道时才传时间与来源**：`expressed_at`（必须带时区 offset）、
   `source`（如 `{"channel":"whatsapp","message_id":"..."}`）、`location`、
   `place`、`weather`、`occurred`、`reply_to`、`attachments`（本地文件）。
   不知道就省略——**绝不编造地点**，工具也永不施加默认地点、永不查天气、
   永不联网。
3. **没有确认步骤**：返回 `success: true` 即已落盘、立即可被 `search` 检索。
   没有 `needs_confirmation`；不要追问用户"地点对不对"（这是 `write` 的流程）。
4. **重试安全**：带 `source.channel` + `source.message_id` 重发同一句话会返回
   `deduplicated: true`（什么都不写）；同键不同正文返回 `E0206` 键冲突——
   此时不要重试，按 `details.existing` 处理。识别窗口是一个日历月（含相邻月）。
5. **读回**：用返回的 `rel_path` 执行 `journal get --path <rel_path>`（或用
   `journal get --id <id>`）；返回的 `id` 是这条碎片的持久身份，文件移动或改名
   后仍可取回，供以后 `reply_to` 引用。带更正 note 的碎片：
   `content` 始终是原话，`notes` 数组单独给出每条更正。
6. `write` 保持不变：带标题与 topic 的整理性日志（legacy title-and-topic
   journal）仍走 `write`。分不清"存原话"还是"写日志"时，问用户一次。

## 更正（fragment note）

用户确认某条碎片里的话**说错了**（"是周二，不是周一"）时，不改原话——用
`fragment note` 把更正记在原话旁边。存储语法归 `docs/ARCHITECTURE.md`
（*碎片更正 note 存储形态*）；操作规则在这里：

```
.venv/bin/life-index fragment note --data '{"path":"<目标 rel_path>","expect_id":"<目标 id>","text":"<用户确认的更正>","based_on":[{"path":"<依据 rel_path>","id":"<依据 id 或省略>","quote":"<依据原文中逐字出现的一句>"}],"by":"<署名，如 host-agent>"}'
```

规则（机械执行）：

1. **只有用户确认过的更正才记 note**："它说错了、正确的是 X" 由用户说出，不由
   agent 推断。润色、补写、解释不是更正——没有 note 可记。
2. **`text` 就是更正本身**（用户的话，如"是周二，不是周一"），不是对原话的改写。
3. **`based_on` 指向用户确认更正的那条碎片**（可以是目标自己）：`quote` 必须逐字
   出现在那条碎片的**原文**里（先 `journal get` 抄原文，不要凭记忆写）；note 里
   的文字不算原文。`id` 给出时必须是那条碎片的 `id`。
4. **`expect_id` 与 `based_on[].id` 用碎片自身的 id**：即 `fragment add` 返回的
   `id`，也就是 `journal get` 输出顶层的 `id`（同一个值；`null` 表示该文件没有
   id，此时两个都省略）。目标带 `id` 时必须给 `expect_id`；传 `rel_path` 等其他
   值只会得到 `E0208`。
5. **重试安全**：同样的 text + `by` + 依据列表重发返回 `deduplicated: true`，什么
   都不写；`by`、text 或依据有任何不同就是另一条 note。
6. **读回**：`journal get --path <rel_path>` 的 `notes` 数组按存入顺序给出每条
   更正（`id` / `noted_at` / `by` / `text` / `based_on`）；`notes_malformed: true`
   出现时说明 note 区损坏——原话仍完整可读，把文件与该标志告诉用户，不要自行
   修复或重试 `fragment note`（它会拒绝）。
7. `edit` 永远改不了 `notes_boundary`，也不改原话；更正只有 `fragment note` 一条路。
