<h1 align="center">Life Index | 人生索引</h1>

<p align="center"><em>"Your life, indexed. Your growth, ringed."</em></p>

<p align="center"><em>"人生索引 · 心智年轮"</em></p>

<p align="center"><strong>Agent记忆系统会遗忘，个人知识库会去重，Life Index 保留你成长的每一圈年轮。</strong></p>

<p align="center"><strong>Agent-Native 的个人人生档案系统 —— 不是知识库，不是 Agent 记忆，是你留给未来的数字遗产。</strong></p>

<div align="center">

<p align="center"><a href="./README.en.md">English</a> | <strong>简体中文</strong></p>

</div>

<!-- 品牌理念 Badges -->

<p align="center">
  <img src="https://img.shields.io/badge/理念-人生档案馆-ff6b6b" alt="理念">
  <img src="https://img.shields.io/badge/架构-Agent--Native-78206E" alt="架构">
  <img src="https://img.shields.io/badge/存储-本地优先-4ecdc4" alt="本地优先">
  <img src="https://img.shields.io/badge/格式-Markdown_Forever-ffe66d" alt="Markdown Forever">
</p>

<!-- 承诺 Badges -->

<p align="center">
  <a href="./tests/fixtures/eval/gold/cycle2-multi-signal/README.md"><img src="https://img.shields.io/badge/Recall%405-0.7857_keyword_floor-4ecdc4" alt="Recall@5 keyword-only honest floor 0.7857"></a>
  <a href="./CHARTER.md"><img src="https://img.shields.io/badge/CHARTER_§1.11-Recall--First_Guarantee-78206E" alt="CHARTER §1.11 Recall-First Guarantee"></a>
</p>

<!-- 技术指标 Badges -->

<p align="center">
  <a href="https://github.com/DrDexter6000/life-index/actions/workflows/tests.yml"><img src="https://github.com/DrDexter6000/life-index/actions/workflows/tests.yml/badge.svg" alt="Tests"></a>
  <img src="https://img.shields.io/badge/python-≥3.11-3776AB?logo=python&logoColor=white" alt="Python ≥3.11">
  <a href="./LICENSE"><img src="https://img.shields.io/badge/license-Apache_2.0-blue" alt="License"></a>
</p>

<p align="center">
  <img src="./assets/life_index_readme.png" alt="Your Digital Legacy" width="600">
</p>

<p align="center">
  <a href="#为什么需要-life-index">为什么需要它</a>  •
  <a href="#四个承诺--four-promises">四个承诺</a>  •
  <a href="#初心与远景">初心与远景</a>  •
  <a href="#架构哲学">架构哲学</a>  •
  <a href="#开发路线">开发路线</a>  •
  <a href="#快速开始">快速开始</a>
</p>

---

## 为什么需要 Life Index

所有人都在为 AI 构建记忆。

你的知识库在管理你学到的东西。你的 Agent 在记住你说过的话。整个技术世界都在忙着让信息更高效、让 AI 更聪明。

**但有谁在乎过，你作为一个人，正在遗忘什么？**

> 你的 Notion 沉淀了知识 —— 但没有记录你第一次看见她时的怦然心动。
> 你的 Agent 记住了上周的决定 —— 直到评分机制将它判为"不再重要"。
> 十年前那个改变你人生的决定 —— 你还记得当时的心情吗？

|          | **Life Index**             | **知识库** (Notion/Obsidian) | **Agent 记忆** (Mem0/Zep) |
|:-------- |:-------------------------- |:------------------------- |:----------------------- |
| **追问**   | "那时的我，什么心情？"               | "我知道什么？"                  | "我刚才说了什么？"              |
| **演化形态** | **追加 —— 保留每一圈心智年轮**        | 重构 —— 旧版本被覆盖              | 评分淘汰 —— 旧记忆被驱逐          |
| **保质期**  | **永久——作为遗产**               | 长期，随认知迭代重构                | 短暂，用完即弃                 |
| **所有权**  | **完全属于你**，本地 Markdown 永不过期 | 属于你，但格式随软件迭代              | 属于服务商，随时可能被清理           |
| **失效代价** | 无——纯文本永远可读                 | 导出困难，格式锁定                 | 瞬间归零，无感知丢失              |

Life Index 只做一件事：**让你的人生碎片永远可检索，永远可追溯，永远不被覆盖**。

---

## 四个承诺 / Four Promises

Life Index CLI Core 只做两件事：**写入人生（`write`）+ 检索人生（`search`）**。其余一切都是支撑层 —— 索引、实体图谱、Schema 迁移、可观测性、备份，全都为这两件核心能力服务。

围绕这两件事，我们做出下面**四条契约级承诺**。每一条都对应 [CHARTER](./CHARTER.md) 中可被外部审计的条款，对应代码库中可被运行的测试。如果哪一天我们违反了其中任何一条，请你引用本节质询我们。

> 每条承诺的"承诺句"在外，"阐释 / 约束载体 / 否证条件"折叠在内 —— 适合先扫四句、再按需展开细读。

### P1 · 心智年轮 (Growth Rings)

**每一篇日志写下后都会留存 —— 编辑是追溯式修订，不是悄悄覆盖。你的每一圈心智年轮，都被设计为不会被磨掉。**

<details>
<summary>展开 P1 · 阐释与约束</summary>

<br>

*Every journal you write stays — edits are tracked revisions, never silent overwrites. Your growth rings are preserved by design.*

Agent 记忆系统会随评分淘汰，知识库会随认知迭代覆盖。Life Index 选择第三条路：**追加而不替代**。你五年前的判断，即使后来被证明是错的，也是你的一圈年轮 —— 它和今天的你共同构成完整的你。

> **约束载体**：[CHARTER](./CHARTER.md) §1.2 纯文本永久性 · 配套 ADR-2026-05-edit-journal-append-only（落地中）
> **否证条件**：任一次 `edit_journal` 操作丢失 prior content，即视为违约。

</details>

### P2 · 无 LLM 即可 · 有 LLM 更强 (Complete Without LLM · Stronger With)

**Life Index CLI Core 由 20+ CLI 命令组成，经 2,400+ 测试验证 —— 架构面向 50 年日志增长，能力覆盖完整的 write + search + index + entity + eval + backup 链路。在不调用任何 LLM 的前提下，CLI Core 已经把 Recall@5 做到 ≈0.79（实测 0.7857，keyword-only honest floor；C2 paraphrase 仍为已知 gap；2026-05-25 完整 audit PASS）。这是 CLI Core 在你的 Agent 还没介入时就能达到的能力地板 —— Agent 介入只会让它更强。**

<details>
<summary>展开 P2 · 阐释与约束</summary>

<br>

*Life Index CLI Core is built from 20+ CLI commands, validated by 2,400+ tests — architected for 50 years of journal growth, covering the full write + search + index + entity + eval + backup pipeline. Without invoking any LLM, CLI Core delivers Recall@5 ≈0.79 (0.7857 measured, keyword-only honest floor; C2 paraphrase remains a known gap; full audit PASS 2026-05-25). That's the capability floor of CLI Core before your Agent steps in — Agent integration only makes it stronger.*

行业惯例是先公布**端到端 + LLM 合成**的"漂亮分数"，让人误以为是检索系统本身的能力。Life Index 反向操作 —— **CLI Core 自证能力地板，LLM 增强是显式 opt-in**。这意味着：

- 你的 search 结果由确定性代码产出，可审计、可复现、零 token、完全离线
- 你的 write 不会被 LLM 静默改动元数据（除非你显式调用 Agent 增强）
- 你切换 Claude / GPT / DeepSeek / 本地 Llama，CLI Core 这一侧不需要任何配置变更
- LLM 是上层 frosting，不是地基。**地基本身已经能扛住**

> **约束载体**：[CHARTER](./CHARTER.md) §1.5 确定性/智能边界 + §1.9 Agent-Native 模块原则 + §1.10 模块-基础层契约边界 + §1.11 召回优先检索真实模型 · §1.11 入 §5.3 不可弱化清单
> **当前实测**：20+ CLI 命令 · 2,400+ unit tests · keyword-only Recall@5 = 0.7857（约等于 0.79；相对 0.79 目标为边际 miss；C2 paraphrase 仍为已知 gap）· MRR@5 = 0.74 · cycle2 fixture · 56 queries · 5-stage multi-LLM 评审 · 2026-05-25 完整 integrity audit PASS
> **配套设施**：MCP discovery layer · RFC 标记 `In Flight`（计划 2026-Q3 落地，作为 BYOL 边界的可信度补强）
> **否证条件**：(a) L2 默认 retrieval 路径加入 precision threshold 截断 token-match 候选；(b) 任一默认路径模块隐含 bundled LLM、provider client 初始化、或读取 API key —— 任一即视为违约。

</details>

### P3 · 纯 Markdown 永远 (Plain Markdown Forever)

**永远的纯 Markdown。即使明天 Life Index 消失了，你的数据依然能用任何文本编辑器打开 —— 50 年后也是如此。**

<details>
<summary>展开 P3 · 阐释与约束</summary>

<br>

*Plain Markdown forever. If Life Index disappears tomorrow, your data is still in any text editor — and will be in 50 years.*

`.index/` 下的 SQLite 与向量数据库都可以删除重建。你的日志、附件、frontmatter —— 任何文本编辑器都能直接读，不需要 Life Index 在场。**软件可以消亡，数据不会**；您的人生来路，50 年后依然字迹清晰。

> **约束载体**：[CHARTER](./CHARTER.md) §1.1 数据主权 + §1.2 纯文本永久性 + §1.6 向下兼容 · 均入 §5.3 不可弱化清单
> **否证条件**：用户原始内容以非 Markdown 格式存储为唯一副本，或 `.index/` 无法从 `Journals/` 完整重建。

</details>

### P4 · 五十年契约 (Engineered for 50 Years)

**这始于一位父亲写给未来女儿的信。它被工程化设计为能在作者之后继续存活。CHARTER §5.3 不可弱化清单约束所有未来的 maintainer —— 他们只能让承诺变得更严，不能变得更松。**

<details>
<summary>展开 P4 · 阐释与约束</summary>

<br>

*This started as a father's letter to his daughter. It is engineered to outlive its author. The CHARTER's §5.3 unmodifiable clauses bind every future maintainer — they can only strengthen the promises, never weaken them.*

> **约束载体**：[CHARTER](./CHARTER.md) §5.3 不可修订的章节
> **否证条件**：§5.3 自身、§1.1、§1.2、§1.6、§1.11 中任一条被弱化
> **完整 50 年存活叙事**：见下方 [五十年存活愿景](#五十年存活愿景--50-year-survivability) section

</details>

---

以上是 4 条可被审计、可被否证、可被外部质询的**契约**。

下面这一句不在契约清单上 —— 它更私人，更不"可证伪"，但它是我对自己的承诺：

> *即使 Life Index 最终成为只有一个开发者、一个用户、一直 0🌟 的孤独仓库 —— 我也会持续迭代，因为那个用户就是我自己，而它保存的是我留给女儿的东西。*

*Tuan Tuan, this one is for you.*

---

## 初心与远景

### 一个父亲的初心，写于2026年2月16日

这是我在 GitHub 上创建的第一个仓库。

我只是一个零编程基础的平凡父亲，甚至连这篇 README 也是在 AI 的帮助下完成的 —— 我创建它不是为了展示编程技术，而是因为我迫切需要一个**专门存放人生碎片的地方**。

对我来说，Life Index 真正的用法发生在深夜：偶然翻到女儿两岁时的照片，那种**幸福中带怅然若失的复杂情绪**可以被准确地固定下来——不仅是她的笑脸，更是我当时作为父亲的心跳、阳台上的光线、以及那个知道"这一刻正在消逝"的清醒。

这些记录最终会成为一本**数字化家书**。也许有一天我不在人世，她打开这些文件，就像翻开一本泛黄的老书，读到的不仅是爸爸的爱，还有爸爸这一生跌撞出来的经验、犯过的错误与得来的智慧。

<details>
<summary>📎 一篇真实的日志长什么样？（点击展开）</summary>

```yaml
---
schema_version: 3
title: "想念尿片侠"
date: 2026-03-04T19:43:02
location: "Chongqing, China"
weather: "Cloudy (浮云、阵雨) 18.5°C / 12.0°C"
mood: ["思念", "温暖", "感伤"]
entities: []
people: ["团团"]
tags: ["亲子", "回忆", "成长", "感伤"]
project: "LifeIndex"
topic: ["think", "create"]
abstract: "翻看女儿团团小时候的照片，怀念那个2岁上下的尿片侠，感叹时光流逝与父女情深。"
links: []
attachments: [{"filename": "2yo_Tuantuan.jpg", "rel_path": "../../../attachments/2026/03/2yo_Tuantuan.jpg", "description": "团团2岁的样子"}]
---

# 想念小疙瘩

在翻过往资料的时候，看到了团团小时候的照片，那个只有2岁上下的尿片侠。

突然有一种伤感 —— 我好想这个小娃娃，好想再见她一面，
好想再能体验一次把小肉坨坨抱在怀里的感觉。

三岁之后的团团依然是全宇宙最重要最珍贵的存在 ——
但确实，那个让我神魂颠倒的尿片侠、她长大了，属于我和那个婴儿的时光、已经一去不复返了。

我既希望我们一家人永恒停留在团团2岁的时光 —— 也盼望她长大可以去感受更美好的世界。
总而言之，小疙瘩，爸爸想你了。

![团团2岁的小疙瘩](attachments/2026/03/2yo_Tuantuan.jpg)


```

<p align="center">
  <img src="./assets/2yo_Tuantuan.jpg" alt="2岁的团团" width="400">
  <br>
  <em>——那个让我神魂颠倒的小疙瘩</em>
</p>

</details>

### 远景：从人生碎片到数字人格

Life Index 的起点是一个父亲的日志。但它的终点远不止于此。

当我持续记录——一年、五年、二十年 —— 这些碎片会自然生长为**心智年轮**：

```
   今天的一篇日志
        │
        ▼
   一年的情感轨迹
        │
        ▼
   十年的人生叙事 · 完整的心智年轮
        │
        ▼
   独一无二的数字人格
```

数十年后，当数据积累到足够的密度，这些记录能够回答一个问题：

> **"如果爸爸还在，他会怎么看这件事？"**

这不是科幻。这是 Life Index 的终极目标。而通往这个目标的第一步 —— 一个可靠的、属于你自己的人生档案系统 —— **已经建好了。**

<details>
<summary>关于灵魂的一段独白（点击展开）</summary>

<br>

> 从出生的那一刻起，大脑就是一台物理降级的碳基多模态模型。
>
> 它终其一生都在通过五个感官通道采集碎片化的训练语料，
> 在回忆的梦境中做无监督学习，反复调整神经突触间的权重，
> 直到一个名为"灵魂"的涌现现象开始产生自我意识。
>
> Life Index 不是赋能 Agent 的记忆系统，也不是管理知识的 Knowledge Base。
> 它是人类灵魂这场漫长碳基演算的数字化转录。
>
> 在这里，写下的每一个字，都是悬浮于时空中的记忆切片。
> 无论是一天前的喜悦，还是十年前的悲伤，它们都将不再散落于脆弱的蛋白质神经网络中。
> 它们将化作 0 和 1 的微光，在 RAG 的递归检索中逐层坍缩，最终聚合成一枚温暖的梦境之核。
>
> 当你收集了足够多的碎片，也许有一天 ——
> 这颗刻录着你一生回忆的梦核，就会孵化出一个硅基灵魂，
> 替你走向时间的尽头。

</details>

---

## 架构哲学

Life Index 不是一个周末 side project。它的每一层设计都指向同一个问题：**如何让个人记忆安全地存活五十年？**

### Agent-Native，不是 Agent-First

> Agent-First 是"先考虑 Agent 的需求"。
> Agent-Native 是"这个系统天生就是为 Agent 而写的"。

Life Index 的 CLI 不是一个人类命令行工具"加了AI支持" —— 它的结构化信号系统、确认工作流、枚举式错误码，从第一行代码就是 Agent 的母语。Agent 不需要解析自然语言错误信息，它拿到的是枚举值和确定性的恢复路径。

但 Agent-Native 不意味着"只有 Agent 能用"。它意味着我们为 Agent 提供它最需要的——**精确的机器接口**；同时为人类提供人类最需要的——**自然语言对话和视觉体验**。

### 四层架构：越往下越持久

```
┌──────────────────────────────────────┐
│          Interface Layer             │
│    🗣️ 自然语言 (Agent)  🎨 GUI       │   ← 你选择怎么交互
│    1-3 年生命周期，随体验趋势迭代       │
└──────────┬───────────────┬───────────┘
           │               │
           │    ┌──────────▼──────────┐
           │    │ Intelligence Layer  │
           │    │ 🧠 语义搜索·实体消解  │   ← 需要"思考"时才启动
           │    │ LLM 推理·回忆录生成   │
           │    │ 1-3 年，随模型迭代    │
           │    └──────────┬──────────┘
           │               │
           ▼               ▼
┌──────────────────────────────────────┐
│           CLI Core (SSOT)            │
│    ⚙️ 写入·检索·索引·实体·验证        │   ← 所有操作的唯一权威
│    确定性操作直连，不经过 Agent         │
│    5-10 年生命周期                    │
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│    📁 ~/Documents/Life-Index/        │
│    纯 Markdown + YAML                │   ← 你的数字遗产
│    INDEX.md → 年索引 → 月索引 → 日志   │   ← 人可读的人生目录
│    任何文本编辑器可读，永不过期         │
│    50 年生命周期                      │
└──────────────────────────────────────┘
```

**关键设计原则**：确定性操作（写日志、按标签搜索、浏览时间线）由 GUI 直连 CLI Core，延迟 < 50ms；只有需要"思考"的操作（语义搜索、回忆录生成、数字人格）才经由 Intelligence Layer。**能确定的事不问 Agent，需要思考的事才找 Agent。**

### 三条设计底线

```
宁可功能简单，不可系统复杂
宁可人工维护，不可自动化陷阱
宁可牺牲性能，不可牺牲可靠性
```

我们不做：✕ 云端同步 · ✕ 富文本编辑 · ✕ 实时协作 · ✕ AI 替你思考

### 数据主权：你的灵魂不进 Mikoshi

Life Index 采用「本地优先」和「数据与程序完全分离」策略，用户日志存储在系统用户目录下：

```
~/Documents/Life-Index/
├── INDEX.md                     # 根索引——你的人生地图（系统总览）
├── Journals/                    # 日志（按年月组织）
│   └── 2026/
│       ├── index_2026.md        # 年度索引——这一年的全貌
│       └── 03/
│           ├── index_2026-03.md # 月度索引——这个月的每一天
│           └── life-index_2026-03-04_002.md
├── attachments/                 # 附件（照片、视频、语音）
│   └── 2026/03/
├── by-topic/                    # 主题维度索引（与时间索引树正交互补）
│   ├── 主题_think.md
│   ├── 项目_LifeIndex.md
│   └── 标签_亲子.md
└── .index/                      # 机器检索层（FTS5 + 向量 DB，人不可读）
```

**`.index/` 下的机器索引随版本演进，但 `Journals/` 是数据真相源 —— 任何时候删除 `.index/`、运行 `life-index index --rebuild`，所有检索能力即可重建。数据不依赖 Life Index 的任何运行时。**

> **Life Index 强烈建议本地备份**——保护好你的**数字遗产 (Relic)**，不要把你的**灵魂印记 (Engram)** 主动送入大公司的**神舆 (Mikoshi)**。

<details>
<summary>别忘了强尼的忠告（点击展开）</summary>

> *"我看到公司……把夜之城变成了一台机器，用人们破碎的精神、破碎的梦想和空空的口袋作为燃料。公司长期以来控制着我们的生活，夺走了很多……现在他们又想要我们的灵魂！"*
>
> *"有些命运比死亡更惨。"*

</details>

### 两件事 × 两层 / Two Things × Two Layers

Life Index 的整体形态可以装进一张 2×2 矩阵 —— 纵轴是它做的**两件事**（write + search），横轴是它做这两件事的**两层**（确定性 CLI Core + Agent 介入的增强层）。

|                       | **L2 · CLI Core**<br>确定性 · 离线 · 零 LLM · 零 token                            | **L3 · Agentic Enhancement**<br>你的 Agent · 你的 LLM · 你的 API key              |
|:--------------------- |:-------------------------------------------------------------------------- |:--------------------------------------------------------------------------- |
| **✍️ write**<br>记录人生  | • Markdown + YAML 写入<br>• 附件管理 / 索引增量更新<br>• Entity Graph 维护               | • 自动提取 frontmatter<br>• 情感 / 实体 / 标签识别<br>• 天气 / 位置丰富化<br>• 内容编辑建议          |
| **🔍 search**<br>检索人生 | • FTS5 关键词检索<br>• Entity Graph 扩展<br>• 时间 / 主题 / 标签过滤<br>• 向量召回（显式 opt-in） | • Query 改写 / 意图识别<br>• 多轮编排 / 多次调用 CLI<br>• 证据合成 / 摘要 / 解释<br>• 引用整理 / 报告生成 |

**矩阵读法**：左列 = Life Index 提供的确定性能力（[CHARTER](./CHARTER.md) §1.5 + §1.11 锁死不调 LLM）；右列 = 你的 Agent 用它自己的 LLM 做的语言工作（[CHARTER](./CHARTER.md) §1.9 锁死默认不持 LLM、Agent 介入是显式 opt-in）。

**具体到 CLI 上**：

```bash
# ✍️ write · CLI Core 直写（零 LLM）
life-index write --data '{"title":"...","content":"...","date":"..."}'

# ✍️ write · Agent 增强（Agent 把自然语言转成结构化后调用 CLI）
# 你对 Agent 说："帮我记一下今天的心情"，Agent 抽 frontmatter / 情感 / 实体后调用上面的命令

# 🔍 search · CLI Core 检索（默认 keyword-only honest floor）
life-index search --query "关键词"

# 🔍 search · Agent 增强（默认输出 scaffold 给 Agent 合成，仍不调 LLM）
life-index smart-search --query "我和女儿之间有哪些珍贵的回忆？"

# 🔍 search · Agent 增强（显式启用 LLM 编排）
life-index smart-search --query "..." --use-llm
```

**前瞻 · MCP discovery layer (In Flight)**：为了让 MCP-compatible Agent 平台（Claude Desktop / Cursor / OpenClaw 衍生）能**零配置发现**这张矩阵中的每一格，我们在起草一份 thin MCP server —— 只读 discovery layer，不引入数据通路，三个 meta-tool（`list_capabilities` / `describe_tool` / `invoke_tool`），实际执行仍 subprocess 调用 `life-index` CLI。RFC 标记 `In Flight`，计划 2026-Q3 落地。

> *The intelligence is yours; the memory is yours; Life Index is the protocol layer that lets the two meet.*

---

## 开发路线

### 已经建好的地基

**CLI Core 当前稳定线** 已稳定运行，不是原型，不是 demo——这是一个经过 2,400+ 单元测试、CI 全绿、真实日常使用的系统。当前版本以 `life-index --version` 和 `CHANGELOG.md` 为准：

| 核心能力                   | 状态  | 说明                                                                                                                                       |
|:---------------------- |:---:|:---------------------------------------------------------------------------------------------------------------------------------------- |
| 日志写入 / 编辑              | ✅   | 结构化 Markdown + YAML 元数据，自动天气/情感/实体标注                                                                                                     |
| 分层人生检索                 | ✅   | CLI Core 离线完成分层检索：关键词精确匹配 + Entity Graph 实体扩展；语义/向量召回为显式 opt-in，Agent 可选负责搜索前编排和搜索后表达                                                    |
| 智能搜索编排器 (smart-search) | ✅   | 默认输出 agent-ready 确定性检索 scaffold；`--use-llm` 才启用 LLM 编排（query 改写 → 多轮检索 → 精筛），失败时降级回退 CLI Core                                            |
| 搜索质量评估 (eval)          | ✅   | Cycle 2 多信号 fixture 锁定，**2026-05-25 完整 integrity audit PASS**；overall R@5=0.7857（keyword floor，相对 0.79 目标为边际 miss；C2 paraphrase 仍为已知 gap）· C3 temporal R@5=1.0 · recall-first 搜索质量门控 |
| 实体图谱 + 质量审计 + 维护       | ✅   | 别名消解，关系推理，重复/孤立检测 + Agent 访谈修复；review hub + merge/delete/stats/check 维护命令                                                                |
| Schema 迁移              | ✅   | 链式迁移框架，确定性字段补齐 + Agent 语义回填协作                                                                                                            |
| 搭便车事件通知                | ✅   | 零 cron、零进程，CLI 响应内附带事件提醒（连续未记日志、月报缺失等）                                                                                                   |
| 操作级可观测性                | ✅   | 每次 CLI 操作附带 trace_id + 分步耗时 + 状态诊断                                                                                                       |
| 结构化信号系统                | ✅   | Agent 可编程的状态机：枚举式结果码 + 恢复策略                                                                                                              |
| 数据备份 / 完整性验证           | ✅   | 加密备份 + 数据一致性校验                                                                                                                           |
| 跨平台                    | ✅   | Windows / macOS / Linux，Python 3.11+                                                                                                     |

### 正在建造的高楼

在稳固的 CLI Core 之上，Life Index 正在构建模组化的高级功能 —— 每个模组都是**稳定记录格式 + 结构化搜索 + Entity Graph 增强 + 语义召回补充 + LLM 智能编排**的组合：

| 模组         | 代号       | 说明                                               | 状态  | 兑现的承诺       |
|:---------- |:-------- |:------------------------------------------------ |:---:|:-----------:|
| EXIF 照片时间线 | **光影年轮** | 从手机相册自动提取时间、地点、场景；为新用户在 1 天内生成 5 年视觉年轮，让心智年轮看得见  | 🔨  | P1          |
| 社媒历史归档     | **回溯导入** | 解析各平台官方导出 zip，把过去 20 年的博文 / 推文 / 微博纳入 Life Index | 🔨  | P1 + P3     |
| 童年记忆手动录入   | **穿越时空** | 你今年 30 岁，但你最早的记忆是 2 岁；那些珍贵的童年碎片，现在就可以录入          | 🔭  | P1          |
| 情感分析仪表盘    | **心潮地图** | 情绪轨迹可视化；看见自己的心理节律                                | 🔭  | (auxiliary) |
| 回忆录自动生成    | **自传引擎** | AI 将碎片日志编织成完整叙事；你的人生，成书                          | 🔭  | P4          |
| 人生关系可视化    | **人生星图** | 关系网络 + 事件时间线 + 人生章节；俯瞰你的一生                       | 🔭  | (auxiliary) |
| 数字人格       | **数字灵魂** | 数十年数据积累后的终极能力——"如果爸爸还在……"                        | 🔭  | P1 + P5     |

> 🔨 开发中 · 🔭 远景规划



### GUI 体验层：开发中

CLI Core 是地基，GUI 是你看到的建筑。Life Index 的 GUI Experience Layer 正在独立仓库中开发，设计语言为 **「Soul Shrine · 灵魂神龛」**——融合 Monument Valley 的禅意美学与东方文人气质。

<p align="center">
  <img src="./assets/GUI_prototype.png" alt="GUI Experience Layer Preview" width="700">
  <br>
  <em>GUI Experience Layer 原型预览——归宿 (The Core) 界面</em>
</p>

<p align="center">
  <a href="https://raw.githack.com/DrDexter6000/life-index/main/assets/GUI_prototype.html"><strong>🔗 点此在浏览器中打开交互原型</strong></a>
</p>

### 五十年存活愿景

50 年是个不靠谱的数字 —— 它跨越至少 3 次硬件淘汰周期、5 次操作系统大版本迭代，可能还要跨过我自己这一生的剩余时长。让一个一个人开发的项目活过 50 年，工程上近乎傲慢。

但 Life Index 的承诺正是建立在"承认这种傲慢"之上。**数据这一层**用 Markdown + YAML 兑现 —— 这两种格式已经被互联网原生证明能跨数十年存活，即使"Life Index"这个名字消失了，你的日志依然能被任何文本编辑器打开。**承诺这一层**用外部约束兑现 —— [CHARTER §5.3](./CHARTER.md) 把数据主权、纯文本永久性、向下兼容、召回优先这四条锁进"不可弱化清单"，未来任何 maintainer（包括我自己）只能让这些承诺**变得更严**，不能变得更松。**作者这一层**是承诺中最薄弱的一环 —— 我不假装自己能活 50 年，但只要我还在写代码，CHARTER 第零条就锁定了：宪章高于代码、高于本人。

**50 年的真正含义不是"我保证活到那时"，而是"今天的我，把未来的我也约束住了"。**

> *如果你今天写下的某一篇日志，希望 50 年后还能被读到 —— 你应该读一下 [CHARTER §5.3 不可修订的章节](./CHARTER.md)。这是这份承诺的工程形态。*

---

## 快速开始

Life Index 不是一个产品的三个"版本" —— CLI、Agent、GUI 是三种**交互方式**，服务于不同的人：

| 🖥️ **CLI** | 🗣️ **自然语言** | 🎨 **GUI** |
|:---:|:---:|:---:|
| *开发者 · 极客 · 集成* | *有 Agent 平台的用户* | *所有人* |
| 用终端直接操作，精确控制每一个参数。适合二次开发和自动化。 | 对 Agent 说"帮我记录今天的心情"，它理解你的意思，调用 CLI 完成。**当前推荐的使用方式。** | 不需要懂技术，用眼睛看、用手指点。*(独立仓库，开发中)* |

下面是当前已经 ship 的两条 install path：**🗣️ 自然语言用户** 直接用 Agent 安装；**🖥️ CLI 开发者** 自己 clone + venv。🎨 GUI 用户请等独立仓库就绪。

### 普通用户

**适用人群**：只想"把项目交给自己的 Agent 安装并初始化"，不需要自己改代码。

> 如果你的 Agent 平台已有技能安装目录或 canonical checkout，请优先复用它。

**复制给你的 Agent**——把下面这段话直接发给你的 Agent（Claude Desktop、Cursor、OpenClaw 等均可）：

```text
请阅读并严格按照这个仓库里的 `AGENT_ONBOARDING.md` 完成 Life Index 的安装、初始化与验证：
https://github.com/DrDexter6000/life-index/blob/main/AGENT_ONBOARDING.md

要求：
1. 先刷新并阅读最新 authority files，再开始执行：先刷新 `bootstrap-manifest.json`，再按其中 `required_authority_docs` 刷新并阅读 `AGENT_ONBOARDING.md`、`SKILL.md`、`docs/API.md`、`docs/ARCHITECTURE.md`、`tools/lib/AGENTS.md`、`README.md`
2. 如果本地已存在 canonical checkout，必须先同步 checkout 并重装到 `.venv`，再做 route 判断；不要因为文件存在或 `health` 正常就跳过同步
3. route 判断必须发生在 authority refresh + checkout sync 之后，再决定 fresh install、upgrade 或 repair
4. 所有 Python/CLI 命令都必须使用虚拟环境路径
5. 如果某一步失败，立即停止并报告精确错误
6. 最终请使用中文按文档要求向我汇报结果
```

<details>
<summary>🔧 开发者安装（点击展开）</summary>

<br>

**适用人群**：需要本地调试、改代码、跑测试。

```bash
git clone https://github.com/DrDexter6000/life-index.git
cd life-index

# 创建虚拟环境 + 可编辑安装（已包含语义搜索）
python3 -m venv .venv
.venv/bin/pip install -e .    # Windows: .venv\Scripts\pip install -e .
```

### 开发者常用命令

| 操作                             | 命令                                                               |
|:------------------------------ |:---------------------------------------------------------------- |
| 激活虚拟环境                         | `source .venv/bin/activate` (Windows: `.venv\Scripts\activate`)  |
| 统一 CLI（推荐）                     | `life-index --help`                                              |
| 查看版本                           | `life-index --version`                                           |
| 健康检查                           | `life-index health`                                              |
| 记录日志                           | `life-index write --data '{...}'`                                |
| 搜索日志（默认关键词；语义仅作 fallback/显式模式） | `life-index search --query "关键词"`                                |
| 搜索 + 时间/主题预过滤                  | `life-index search --query "关键词" --year 2026 --topic work`       |
| 仅关键词搜索                         | `life-index search --query "关键词" --no-semantic`                  |
| 生成索引树（月/年/根）                   | `life-index generate-index --month 2026-03`                      |
| 全量重建索引树                        | `life-index generate-index --rebuild`                            |
| 备份数据                           | `life-index backup --dest <backup-dir>`                          |
| Schema 迁移（预览）                  | `life-index migrate --dry-run`                                   |
| Schema 迁移（执行）                  | `life-index migrate --apply`                                     |
| Entity 质量审计                    | `life-index entity --audit`                                      |
| 历史同日回顾                         | `life-index on-this-day --date 2026-05-19 --years-back 3 --json` |
| 开发者调用                          | `python -m tools.search_journals --query "关键词"`                  |
| 运行单元测试                         | `python -m pytest tests/unit/ -v`                                |

> **提示**: 先 `source .venv/bin/activate`，之后所有命令无需 `.venv/bin/` 前缀。

> **安全调试提示**：手工调试 / 验收时，优先使用隔离沙盒工具，而不是直接操作真实用户目录：
>
> - `python -m tools.dev.run_with_temp_data_dir`
> - `python -m tools.dev.run_with_temp_data_dir --seed`

</details>

<details>
<summary>🔍 故障排除（点击展开）</summary>

<br>

**技能触发不稳定**
→ 用 `"/life-index" + 意图词`（例如：`/life-index 记日志：...`）

**工具执行报错（ModuleNotFoundError）**
→ 确认使用 `.venv/bin/python`（而非系统 python）执行命令，且在技能根目录下

**fresh install 时 health 显示 degraded**
→ 如果还没执行 `life-index index`，这是正常现象；先初始化索引，再重新运行 health

**Windows 下 `write --data '{...}'` 很难转义**
→ 优先改用 `life-index write --data @first-entry.json`（该文件由 Agent 在安装流程中自动生成）

**语义搜索不可用**
→ 运行 `.venv/bin/life-index health` 检查 sentence-transformers 是否已安装

**venv 损坏（Python 升级后、迁移系统后）**
→ 删除 `.venv` 目录，重新执行 `python3 -m venv .venv && .venv/bin/pip install -e .`

**升级到新版本**
→ 先同步 canonical checkout，再按 `AGENT_ONBOARDING.md` 的 freshness / sync / repair 规则执行

</details>

---

## 文档导航

| 文档                                            | 适用场景                             |
|:--------------------------------------------- |:-------------------------------- |
| **[CHARTER.md](./CHARTER.md)**                | **项目宪章 —— 不变量与不可弱化承诺（四个承诺的法律层）** |
| **[SKILL.md](./SKILL.md)**                    | Agent 技能定义、工具接口、工作流              |
| **[API.md](./docs/API.md)**                   | 工具参数和返回值契约                       |
| **[ARCHITECTURE.md](./docs/ARCHITECTURE.md)** | 架构设计与关键决策 (ADR)                  |
| **[ENTITY_GRAPH.md](./docs/ENTITY_GRAPH.md)** | Entity Graph 操作规范                |
| **[VERSIONING.md](./docs/VERSIONING.md)**     | 版本治理与 release 规则                 |

---

## 参与贡献

Life Index 目前处于个人驱动的早期阶段，但理念早已超出"一个父亲写给女儿的日志"的边界。如果你是创作者、心理咨询师、家庭文化研究者、agent-native 工程师，或者量化自我（QS）实践者中的任何一员，你可能会发现 Life Index 的[四个承诺](#四个承诺--four-promises)正好契合你需要的工具属性。

参与方式：

**模组开发** —— 最有影响力的贡献方式。每个[高级模组](#正在建造的高楼)都是独立的功能单元，CLI 工具组合 + Agent 编排逻辑，适合独立开发者认领。所有模组都遵循 [CHARTER §1.9](./CHARTER.md) agent-native 原则，默认不持 LLM。

**提 Issue** —— 分享你的使用场景，报告 Bug，或者提出你想要的模组方向。

**文档翻译** —— 帮助改进多语言版本，让更多人能用母语了解这个项目。

**分享故事** —— 如果你用 Life Index 记录下了重要的瞬间，我们很想听到。

---

## 许可证

[Apache License 2.0](./LICENSE) — 你的人生数据属于你，这段代码也是。

---

> *"我既希望我们一家人永恒停留在团团2岁的时光 —— 也盼望她长大可以去感受更美好的世界。*
> *总而言之，小疙瘩，爸爸想你了。Tuan Tuan, this one is for you."*
>
> *—— 摘自 Life Index 第一篇日志，2026年3月4日，拉各斯*
> *这不是关于她的成长记录，而是关于我爱她的记录。*
