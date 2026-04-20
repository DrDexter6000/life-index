# Life Index 搜索系统 — 自然语义查询诊断报告

**时间**：2026-04-17  
**方法**：用 12 条模拟真实用户的自然语义中文提问，跑 `python -m tools.search_journals --query ... --explain`，分析 `l1/l2/l3/semantic/merged_results` 各层输出、RRF 分数、耗时与 Ground-Truth 命中情况。  
**数据集**：71 条 journal（2026-01 ～ 2026-04）。  
**测试脚本**：`tests/nl_query_smoke.py`（完整结果 `tests/nl_query_smoke_results.json`）。

---

## 一、高优先级缺陷（P0 — 影响可用性）

### P0-1 · Windows 下 stderr 编码会让请求直接崩溃

**现象**：查询 `最近有什么让我焦虑的事？` 在启用 semantic 时，CLI 子进程 stderr 线程抛 `UnicodeDecodeError: 'utf-8' codec can't decode byte 0xd7`，整个 JSON 输出被吞。

**根因**：sentence-transformers / torch 在 Windows 上往 stderr 写了本地码页（GBK）编码的进度/日志字节，但调用方若按 utf-8 读取就炸。从 [tools\search_journals\__main__.py](tools/search_journals/__main__.py) 看，CLI 本身未对 stderr 做编码统一；任何把它当子进程来用的 Agent（Claude Code、MCP 工具、脚本）都会踩到。

**修复方向**：
- 在 `__main__.py` 启动时 `sys.stdout.reconfigure(encoding='utf-8', errors='replace')` + `sys.stderr.reconfigure(...)`。
- 对 transformers 的 `logging.set_verbosity_error()`，或把所有 lib 的 stderr 统一重定向到文件/DevNull，不污染 CLI 契约。
- 测试：在 subprocess 模式下传入非 ASCII query，要求进程退出码为 0 且 stdout 是合法 JSON。

---

### P0-2 · 标题被"分词后"直接写回展示

**现象**：`merged_results[*].title` 全部形如 `"计划 回 重庆 给 小朋友 过生日 与 生活 反思"`，词与词之间有空格。真实原标题是 `"计划回重庆给小朋友过生日与生活反思"`。

**根因**：[tools\lib\fts_update.py:68](tools/lib/fts_update.py:68) 把 `segment_for_fts(metadata.get("title"), mode="index")` 的输出直接塞进 FTS `journals.title` 列。读取时又把这列当显示标题返回。

```python
segmented_title = segment_for_fts(metadata.get("title", ""), mode="index")
...
"title": segmented_title,   # 这里就回不去了
```

**影响**：所有 Agent/用户看到的 UI 都是分词脏数据。`--diagnose` 的 zero-result list、每条结果、--explain 输出……全部受影响。

**修复方向**：
- FTS 列拆两份：`title`（原文，用于展示）、`title_segmented`（用于全文索引）；或者干脆让 SQLite FTS5 用自定义 tokenizer 在查询侧完成分词，索引列存原文。
- 跑一次 rebuild。

---

### P0-3 · L2 元数据层对自然语义 100% 空召回

**现象**：12 条 NL query，L2 命中次数 = **0 / 12**。意思是"mood=焦虑"、"weather 含 雨"、"topic=work"、"location=Lagos"、"project=Life Index"、"tags 含 Claude Opus"这些极精确的结构化字段完全没被用到。

**具体翻车案例**：

| 查询 | 应匹配字段 | 实际 Top-1 |
|------|-----------|-----------|
| 3月份有哪几天下雨？ | `weather` 含 rain/雨 + `date_from=2026-03-01` | 2026-02-04 to-do-list（完全跑题） |
| 上个月在尼日利亚都干了什么工作？ | `location=Lagos` + `topic=work` + 3 月 | 2026-03-11 生日计划（topic=life/relation） |
| 最近有什么让我焦虑的事？ | `mood` 含 焦虑/忧虑 | 2026-03-24（对，但纯属巧合——正文里 hit 上） |
| 我跟 Claude Opus 互动的记录 | tag/title 含 Claude Opus | 2026-04-02（04-02 只提一笔，03-14_001 标题就是 Claude Opus 评审，被压到第 2） |

**根因**：CLI 把自然语义当成一个纯关键词串丢进 FTS + 向量。没有一个环节做"查询理解"：
- 没有 **NL → 过滤器映射**：没人把"3月"变成 `--month 03`；没人把"尼日利亚"变成 `--location Lagos`；没人把"焦虑"变成 `--mood 焦虑`。
- 没有 **时间短语归一**："最近"、"上次"、"上个月"、"过去两个月"、"3月份"全部丢失。
- 实体图 [core.py:279 `resolve_query_entities`](tools/search_journals/core.py:279) 只能精确匹配用户维护的 `entity_graph.yaml`，对"中东局势""家人"这种常识概念不生效。

**修复方向**（三档选一或组合）：
1. 轻量：加一个基于正则/关键词表的查询预处理器——月份词 / 地名 / 情绪词 → 结构化字段。代码量 < 200 行，对 90% 的常见问题生效。
2. 中等：调一次便宜 LLM（Haiku 4.5 即可）做 query rewriting，输出 `{date_from, date_to, topic, mood, location, people, rewritten_query}`；代价 ~200ms + 少量 token。
3. 彻底：给 L2 做语义检索——把每条 journal 的 frontmatter（mood/weather/location/tags 字符串化）也 embedding 进向量库，让 L2 用语义余弦命中。

---

## 二、中优先级缺陷（P1 — 影响质量/性能）

### P1-1 · Semantic 查询稳定 ~23 秒/次（性能黑洞）

**现象**：12 次请求 Semantic 耗时 19.9 ~ 25.6 s。L3 content ~1 s，L2 元数据 <25 ms。总延迟 100% 被 Semantic 吃。

**根因**：CLI 是**一次性子进程**——每次查询都要 `Loading embedding model: BAAI/bge-m3 via sentence-transformers...` 重新把 600MB+ 模型载入内存 + jieba prefix dict 重建。Agent 串行调 3 次搜索就等于 70 秒。

**修复方向**：
- 加一个常驻服务进程（`tools/search_journals/daemon` 或沿用项目的 MCP pipe），CLI 只作为客户端 socket/http 调用；模型载一次，后续查询 <200 ms。
- 或者提供 `--embed-cache` 把 bge-m3 的 query embedding 做磁盘缓存（命中率低，不如上面）。
- 先做短期止血：运行 `scripts/run_eval_gate.sh` 时实测下 warm 状态下单次 query 的 semantic 耗时，如果 warm 后 <100 ms，就 100% 只是冷启动问题。

---

### P1-2 · 没有置信度下限 —— 不存在的概念也能"找到 10 条"

**现象**：`我有没有提到过北京？` — 真实答案是"从未提过"。系统自信返回 10 条结果，Top-1 是 03-11「计划回**重庆**给小朋友过生日」（重/京混淆）、RRF 0.0323，视觉上和真实命中无差别。

**根因**：`merged_results` 按 RRF 从高到低排序后直接 slice `[:limit]`，没有 **最小得分阈值** 或 **归一化置信度** 字段给 Agent。所有查询的 RRF 都在 0.028 ~ 0.033 之间徘徊——没有分数分布可供 Agent 判断。

**修复方向**：
- 在 merged_results 每条加 `confidence: "high" | "medium" | "low"`（基于该查询 top-1 与 top-k 的分布方差 + 绝对 fts/sem 分数）。
- 新增 `no_confident_match: bool` 顶层字段。
- `--explain` 里显式列出"判定为低置信的原因"（ex: `fts_score < 50 && semantic_score < 45`）。

---

### P1-3 · 标题/标签命中没有强加权

**现象**：查 `我跟 Claude Opus 互动的记录` → Top-1 是 04-02《Agents Epiphany》（正文含 Claude），Top-2 才是 03-14_001《**Claude Opus 4.6** 对 Life Index 的 CTO 级别技术评审》。后者标题就是答案，应该压倒性第一。

**根因**：[ranking.py](tools/search_journals/ranking.py) 里 fts_score 已包含一部分 title_match 奖励（match_count +1），但权重不足以在 RRF 里翻盘。Round 8 "实体/语义对称集成"没把 title-exact-match 作为独立维度。

**修复方向**：
- RRF 之外再加一个 `title_hit_multiplier`（e.g. 1.5x）乘到最终分上。
- 或者保留一个"hard promotion"层：title 或 tags 精确命中（非分词匹配）的文档直接插到前 3。

---

## 三、低优先级缺陷（P2 — 体验/可观测性）

### P2-1 · `source` 字段始终报 `"fts_index"` —— 信息失真

即使某条 `semantic_score=70` 且 `fts_score=0`（纯语义命中），`source` 仍写 `fts_index`。Agent/用户根本看不出该条是哪条管线找回的。应为 `["fts","semantic"]` / `["semantic"]` / `["fts"]`。

### P2-2 · `merged_results[*].final_score = None`（但 explain.fusion.rrf_score 有值）

顶层 `final_score` 没赋值。Agent 只能 `explain.fusion.rrf_score` 里挖。让使用者误以为 hybrid fusion 没跑。

### P2-3 · `--diagnose` 报文里的中文也被 GBK 污染

```
"semantic_unavailable: ��������δ����"  ← 本来应该是"语义索引未启用"
```

后台跑 eval 时写的日志是 GBK，读回来再写 JSON 没转码。

### P2-4 · `--explain` 缺失"为什么这条进了 top-5"的自然语言理由

现有 explain 只有数值（`rrf_score`, `cosine_similarity`）。对调试很有用，但对用户来说不如一行 `"标题含查询词 'Claude Opus'（+20），body 匹配 3 次（+15），语义相似度 0.52（中）"`。

---

## 四、整体评估与建议路线图

### 现状：**"索引能扛，查询理解是 0"**

索引层（L1 index、FTS5 with jieba、bge-m3 向量、RRF 融合）扎实，测试覆盖、Round 9 的重建可靠性都到位。这部分可以给 8/10。

但自然语义查询落到这套索引上之前，**没有任何 query understanding 层**：
- 时间短语没人解析；
- 元数据字段没人映射；
- 实体只能匹配用户维护的 yaml；
- 置信度没有归一化。

所以 12 条自然提问里，强依赖字段过滤（#3 地点工作、#6 3月雨天、#9 家人互动）基本全挂；强依赖关键词重合（#7 生日、#10 搜索改进、#12 心情）表现良好；混合型（#1 睡眠、#4 架构决策、#5 Claude Opus）表现中等。

### 建议优先级

1. **最先修**（1 天内）：P0-1 stderr 编码 + P0-2 标题分词泄漏 + P2-1/2/3 显示层字段——不改算法，只改出口。
2. **第二阶段**（1 周）：P0-3 加一个轻量的 Query Understanding 层（正则 + 关键词字典 → `date_from/date_to/topic/location/mood`），直接把结构化参数灌进 L2。目标：使 #3/#6/#9 的 Top-1 命中正确。
3. **第三阶段**（2 周）：P1-1 语义模型常驻服务（daemon）把 23s → <200ms；P1-2 置信度归一化。
4. **第四阶段**（按需）：P0-3 的 LLM query rewriter 或 L2 元数据语义化——覆盖剩下的长尾。

### 金牌 vs 现实的 Gap

| 查询 | 理想 | 当前 | 差距 |
|------|-----|-----|-----|
| 3月份有哪几天下雨？ | 列出 3 月所有 weather 含 rain 的日期（可枚举） | 返回无关条目 10 条 | **严重** |
| 最近焦虑的事？ | 按 mood=焦虑/忧虑 召回，3-5 条 | 混合召回，语义 + 正文 | 中等（结果能用） |
| 生日相关计划 | 03-11 命中 | 03-11 命中 ✓ | 无 |
| 心情怎么样？ | mood 聚合 | 情绪相关条目 | 可用 |

---

## 五、附件

- `tests/nl_query_smoke.py` — 测试脚本（可复用，新 query 改 `QUERIES` 列表即可）
- `tests/nl_query_smoke_results.json` — 本轮 12 次运行的完整输出

---

*Generated by Claude Opus 4.7 during ad-hoc diagnosis, 2026-04-17.*
