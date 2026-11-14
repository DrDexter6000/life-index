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
5. **读回**：用返回的 `rel_path` 执行 `journal get --path <rel_path>`；返回的
   `id` 是这条碎片的持久身份，供以后 `reply_to` 引用。
6. `write` 保持不变：带标题与 topic 的整理性日志（legacy title-and-topic
   journal）仍走 `write`。分不清"存原话"还是"写日志"时，问用户一次。
