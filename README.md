<h1 align="center">Life Index | 人生索引</h1>

<p align="center"><em>"Your life, indexed."</em></p>

<p align="center"><strong>Agent-Native 的个人人生档案系统 ——</strong></p>

<p align="center"><strong>不是个人知识库，不是 Agent 记忆，是你留给未来的数字遗产。</strong></p>

<div align="center">

<p align="center"><a href="./README.en.md">English</a> | <strong>简体中文</strong></p>

</div>

<p align="center">
  <a href="https://github.com/DrDexter6000/life-index/actions/workflows/tests.yml"><img src="https://img.shields.io/github/actions/workflow/status/DrDexter6000/life-index/tests.yml?branch=main&label=CI" alt="CI"></a>
  <img src="https://img.shields.io/badge/检索-Keyword_+_Index_Tree_+_Entity_Graph-78206E" alt="检索：Keyword + Index Tree + Entity Graph，无 Vector RAG">
  <img src="https://img.shields.io/badge/python-≥3.11-3776AB?logo=python&logoColor=white" alt="Python ≥3.11">
  <a href="./LICENSE"><img src="https://img.shields.io/badge/license-AGPL--3.0-blue" alt="License"></a>
</p>

<p align="center">
  <img src="./assets/life_index_readme.png" alt="Your Digital Legacy" width="600">
</p>

<p align="center">
  <a href="#为什么需要-life-index">核心能力</a>  •
  <a href="#四个承诺">我们的 USP</a>  •
  <a href="https://github.com/DrDexter6000/life-index-gui">可视化 GUI</a>  •
  <a href="#快速开始">快速开始</a>  •
  <a href="#愿景与架构">愿景与架构</a>  •
  <a href="#设计决策--design-decisions">设计决策</a>
</p>

---

## TL;DR

Life Index 是一个 **agent-native、本地优先**的人生档案系统 —— 把你的每一个人生碎片存成永远可读的 Markdown，并让它们永远可被检索、可被追溯、永不被覆盖。

- **写入**：人生碎片 → Markdown + YAML，任何文本编辑器可读，50 年不过期
- **检索**：关键词 + **Index Tree**（人生目录导航）+ Entity Graph，**离线 · 零 token · 可审计 · 可重建**
- **原子**：20+ 种精心打磨的 CLI 原子工具，完全基于 Agent-Native 理念打造
- **智能编排（剧本在 LI，思考在 Agent）**：Life Index 自带一套确定性的 agent 操作剧本（SKILL.md + smart-search scaffold）—— 主动提示宿主 Agent 怎么排序：先给查询归类，再按类型建议走哪条 workflow、调哪些工具与 facet。真正的语义理解与 LLM 推理，交给你的宿主 Agent（**Hermes** / OpenClaw / Claude / Codex 等）；LI 给"怎么做"的剧本，不替它"想"
- **取舍**：**本地优先，不做云端存储**；默认**不带 LLM / embedding 模型、不做工具内 vector RAG** —— [为什么？](#设计决策--design-decisions)
- **定位**：不是知识库，不是 Agent 记忆，是你留给未来的数字遗产

```bash
# 写入人生（零 LLM、零网络）
life-index write --data '{"title":"想念尿片侠","content":"...","date":"2026-03-04T19:43:02"}'

# 检索人生（关键词 + Index Tree + Entity Graph，离线、可复现）
life-index search --query "团团"
# → 命中你写过的每一篇相关日志，附 trace_id 与可审计的排序
```

<details>
<summary>🎨 可视化 GUI（独立公开仓）</summary>

<br>

CLI Core 是地基，GUI 是建在这个地基上的人类体验层。GUI 的当前公开说明、真实界面截图、移动访问与快速开始见独立公开仓 [`life-index-gui`](https://github.com/DrDexter6000/life-index-gui)。

GUI 不替代 CLI，也不新增自己的智能层；AI+ 只做 handoff 与证据呈现，智能仍归宿主 Agent。

<p align="center">
  <a href="https://github.com/DrDexter6000/life-index-gui">
    <img src="https://raw.githubusercontent.com/DrDexter6000/life%2Dindex%2Dgui/main/public/launch/life%2Dindex%2Dgui%2Dhero%2Dscreen.webp" alt="Life Index GUI hero screen 动态演示" width="760">
  </a>
  <br>
  <em>GUI hero screen（脱敏演示语料）。更多截图与快速开始见 GUI 公开仓。</em>
</p>

</details>

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

### 一个父亲的初心

这是我在 GitHub 上创建的第一个仓库。

我只是一个零编程基础的平凡父亲，甚至连这篇 README 也是在 AI 的帮助下完成的 —— 我创建它不是为了展示编程技术，而是因为我迫切需要一个**专门存放人生碎片的地方**。

对我来说，Life Index 真正的用法发生在深夜：偶然翻到女儿两岁时的照片，那种**幸福中带怅然若失的复杂情绪**可以被准确地固定下来——不仅是她的笑脸，更是我当时作为父亲的心跳、阳台上的光线、以及那个知道"这一刻正在消逝"的清醒。这些记录最终会成为一本**数字化家书**：也许有一天我不在人世，她打开这些文件，读到的不仅是爸爸的爱，还有爸爸这一生跌撞出来的经验、犯过的错误与得来的智慧。

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

---

## 四个承诺

Life Index CLI Core 只做两件事：**写入人生（`write`）+ 检索人生（`search`）**。围绕这两件事，我们做出四条**写进《[宪章](./CHARTER.md)》、可被外部审计、只能变严不能变松**的承诺。如果未来 Life Index 违反了其中任何一条，请你引用本节质询。

|        | 承诺                        | 一句话                                                      |
|:------:|:------------------------- |:-------------------------------------------------------- |
| **P1** | **心智年轮**                  | 每篇日志写下后都留存，编辑是追溯式修订，不是悄悄覆盖。                              |
| **P2** | **无 LLM 即可 · 有 Agent 更强** | CLI Core 不调用任何 LLM 就能完成 write + search；Agent 的智能编排只让它更强。 |
| **P3** | **纯 Markdown 永远**         | 即使明天 Life Index 消失，你的数据依然能用任何文本编辑器打开。                    |
| **P4** | **五十年契约**                 | 始于一位父亲写给女儿的信，被工程化设计为能在作者之后继续存活。                          |

> 四条承诺都有对应的**否证条件**（怎样算违约）锁在《宪章》里。想看每条的工程形态与可运行的测试锚点，展开下面一栏。

<details>
<summary>展开 · 四个承诺的约束载体与否证条件</summary>

<br>

**P1 · 心智年轮**

> Agent 记忆随评分淘汰，知识库随认知迭代覆盖。Life Index 选择第三条路：**追加而不替代**。你五年前的判断，即使后来被证明是错的，也是你的一圈心智成长年轮。
> · **约束**：[CHARTER](./CHARTER.md) §1.2 纯文本永久性
> · **否证**：任一次 `edit_journal` 操作丢失 prior content，即视为违约。

**P2 · 无 LLM 即可 · 有 Agent 更强**

> 行业惯例是先公布**端到端 + LLM 合成**的"漂亮分数"，让人误以为是检索系统本身的能力。Life Index 反向操作 —— **CLI Core 自证原子搜索能力地板，LLM 增强是显式 opt-in**：search 结果由确定性代码产出（可审计、可复现、零 token、完全离线）；切换 Claude / GPT / DeepSeek / 本地 Llama，CLI Core 这一侧无需任何配置变更。**LLM 是上层 frosting，不是地基；地基本身已经能扛住。**
> · **约束**：[CHARTER](./CHARTER.md) §1.5 + §1.9 + §1.10 + §1.11（§1.11 入 §5.3 不可弱化清单）
> · **当前可验证面**：20+ CLI 命令 · 4,200+ pytest-collected tests · 公开 synthetic token-match blocker · 私有质量 eval 仅作 advisory evidence
> · **否证**：(a) L2 默认 retrieval 路径加入 precision threshold 截断 token-match 候选；(b) 任一默认路径模块隐含 bundled LLM / provider client 初始化 / 读取 API key；(c) 默认路径引入 embedding 模型或向量索引构建 —— 任一即视为违约。

**P3 · 纯 Markdown 永远**

> `.index/` 下的 SQLite 检索索引与派生缓存都可删除重建。你的日志、附件、frontmatter，任何文本编辑器都能直接读，不需要 Life Index 在场。**软件可以消亡，数据不会。**
> · **约束**：[CHARTER](./CHARTER.md) §1.1 + §1.2 + §1.6（均入 §5.3 不可弱化清单）
> · **否证**：用户原始内容以非 Markdown 格式存储为唯一副本，或 `.index/` 无法从 `Journals/` 完整重建。

**P4 · 五十年契约**

> CHARTER §5.3 不可弱化清单约束所有未来的 maintainer —— 他们只能让承诺**变得更严**，不能变得更松。
> · **约束**：[CHARTER](./CHARTER.md) §5.3 不可修订的章节
> · **否证**：§5.3 自身、§1.1、§1.2、§1.6、§1.11 中任一条被弱化。

</details>

> *即使 Life Index 最终成为只有一个开发者、一个用户、一直 0🌟 的孤独仓库 —— 我也会持续迭代，因为那个用户就是我自己，而它保存的是我留给女儿的东西。*
> 
> *Tuan Tuan, this one is for you.*

### 我们刻意不做的事

为了守住上面四条承诺，Life Index 主动放弃了一批"行业默认项"：

**✕ 云端存储 · ✕ 富文本编辑 · ✕ 实时协作 · ✕ 默认携带 LLM / embedding 模型 · ✕ 工具内 Vector RAG · ✕ AI 替你思考**

这些取舍的详细说明见 → [设计决策](#设计决策--design-decisions)。

---

## 快速开始

<details>
<summary>🗣️ 普通用户：把项目交给你的 Agent 安装（点击展开）</summary>

<br>

把下面这段话直接发给你的 Agent（**Hermes**、OpenClaw、Claude Desktop、Codex 等均可）：

```text
请阅读并严格按照这个仓库里的 `AGENT_ONBOARDING.md` 完成 Life Index 的安装、初始化与验证：
https://github.com/DrDexter6000/life-index/blob/main/AGENT_ONBOARDING.md

要求：
1. 先阅读 `AGENT_ONBOARDING.md`；如果本地还没有 Life Index 命令或 checkout，按文档的最小安装片段取得一个可运行的 `bootstrap`
2. 运行 `life-index bootstrap --json` 或 checkout 内 `python -m tools bootstrap --json`
3. 在重建 `.venv`、运行 `health`、采纳 checkout、删除任何目录、或判断 fresh install / upgrade / repair 之前，先看 bootstrap JSON
4. 如果发现本地 checkout，必须通过 bootstrap 的 `--checkout-path` / `--checkout-origin` 规则评估；只有 `safe_to_adopt: true` 才能采纳
5. 先处理 `needs_human`，再按 `execution_policy` 与 `safe_next_steps` 顺序执行；不要把 "clean slate" / "fresh install" / "start from scratch" 理解为可以删除已有日志数据
6. 所有 Python/CLI 命令都必须使用文档指定的虚拟环境路径
7. 如果某一步失败，立即停止并报告精确错误
8. 最终请使用中文按文档要求向我汇报结果
```

</details>

<details>
<summary>🖥️ 开发者：clone + venv 安装（点击展开）</summary>

<br>

```bash
git clone https://github.com/DrDexter6000/life-index.git
cd life-index

# 创建虚拟环境 + 可编辑安装（默认无 LLM、无 embedding 模型）
python3 -m venv .venv
.venv/bin/pip install -e .    # Windows: .venv\Scripts\pip install -e .
```

</details>

<details>
<summary>⌨️ 开发者常用命令（点击展开）</summary>

<br>

| 操作                       | 命令                                                                      |
|:------------------------ |:----------------------------------------------------------------------- |
| 激活虚拟环境                   | `source .venv/bin/activate` (Windows: `.venv\Scripts\activate`)         |
| 统一 CLI（推荐）               | `life-index --help`                                                     |
| 查看版本                     | `life-index --version`                                                  |
| 健康检查                     | `life-index health`                                                     |
| 记录日志                     | `life-index write --data '{...}'`                                       |
| 搜索日志（关键词 + Entity Graph） | `life-index search --query "关键词"`                                       |
| 宿主导航（index-tree）         | `life-index index-tree discover` / `navigate`                           |
| 搜索 + 时间/主题预过滤            | `life-index search --query "关键词" --year 2026 --topic work`              |
| 兼容旧语义开关（no-op）           | `life-index search --query "关键词" --semantic --semantic-policy fallback` |
| 生成索引树（月/年/根）             | `life-index generate-index --month 2026-03`                             |
| 全量重建索引树                  | `life-index generate-index --rebuild`                                   |
| 备份数据                     | `life-index backup --dest <backup-dir>`                                 |
| Schema 迁移（预览 / 执行）       | `life-index migrate --dry-run` / `--apply`                              |
| Entity 质量审计              | `life-index entity --audit`                                             |
| 历史同日回顾                   | `life-index on-this-day --date 2026-05-19 --years-back 3 --json`        |
| 运行单元测试                   | `python -m pytest tests/unit/ -v`                                       |

> **提示**：先 `source .venv/bin/activate`，之后所有命令无需 `.venv/bin/` 前缀。
> **安全调试**：手工调试 / 验收时，显式设置临时 `LIFE_INDEX_DATA_DIR` 用沙盒数据，不要直接操作真实用户目录。

</details>

<details>
<summary>🔍 故障排除（点击展开）</summary>

<br>

**技能触发不稳定** → 用 `"/life-index" + 意图词`（例如 `/life-index 记日志：...`）

**工具报错（ModuleNotFoundError）** → 确认使用 `.venv/bin/python`（而非系统 python），且在技能根目录下

**fresh install 时 health 显示 degraded** → 全新 / 空数据安装的 pre-init `degraded` 属预期，不当作失败；若 `safe_next_steps` 含索引或 skill artifact 命令，按原顺序执行后重跑 health

**旧集成仍传 `--semantic*`** → 这是兼容 no-op，不会安装模型、构建向量索引或改变搜索结果。核心检索是关键词 + Index Tree + Entity Graph；要"按意思搜"请让你的宿主 Agent 做 query 改写 + 多轮检索。

**venv 损坏（Python 升级后 / 迁移系统后）** → 先确认 `bootstrap --json` 已判定当前目录是目标安装目录，再重建代码环境，且绝不触碰用户数据

**升级到新版本** → 先运行 onboarding bootstrap gate，按返回的 `execution_policy` 与 `safe_next_steps` 执行

</details>

---

## 愿景与架构

### 远景：从人生碎片到数字人格

Life Index 的起点是一个父亲的日志，但它的终点远不止于此。当你持续记录 —— 一年、五年、二十年 —— 这些碎片会自然生长为**心智年轮**：

```
今天的一篇日志 → 一年的情感轨迹 → 十年的人生叙事 · 完整的心智年轮 → 独一无二的数字人格
```

数十年后，当数据积累到足够密度，这些记录能够回答一个问题：

> **"如果爸爸还在，他会怎么看这件事？"**

这不是科幻，是 Life Index 的终极目标。而通往它的第一步 —— 一个可靠的、属于你自己的人生档案系统 —— **已经建好了。**

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
> 当你收集了足够多的碎片，也许有一天 ——
> 这颗刻录着你一生回忆的梦核，就会孵化出一个硅基灵魂，
> 替你走向时间的尽头。

</details>

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
           │    │ 🧠 回忆编排·实体消解  │   ← 需要"思考"时才启动（你的宿主 Agent）
           │    │ LLM 推理·回忆录生成   │
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

**一句话原则：能确定的事不问 Agent，需要思考的事才找 Agent。** 确定性操作（写日志、按标签/关键词/实体搜索、浏览时间线）由 GUI 直连 CLI Core；需要"思考"的操作（开放式回忆编排、回忆录生成、数字人格）才经由 Intelligence Layer —— 而那一层是**你的宿主 Agent**，不是 Life Index 自己内建的智能。

### 两件事 × 两层

Life Index 的整体形态可以装进一张 2×2 矩阵 —— 纵轴是它做的**两件事**（write + search），横轴是它做这两件事的**两层**（确定性 CLI Core + 你的 Agent 介入的增强层）：

|                       | **L2 · CLI Core**<br>确定性 · 离线 · 零 LLM · 零 token                               | **L3 · Agentic Enhancement**<br>你的 Agent · 你的 LLM · 你的 API key |
|:--------------------- |:----------------------------------------------------------------------------- |:-------------------------------------------------------------- |
| **✍️ write**<br>记录人生  | Markdown + YAML 写入<br>附件管理 / 索引增量更新<br>Entity Graph 维护                        | frontmatter 草拟<br>情感 / 实体 / 标签建议<br>天气 / 位置丰富化<br>内容编辑建议       |
| **🔍 search**<br>检索人生 | FTS5 关键词检索<br>Index Tree 宿主导航<br>Entity Graph 确定性扩展<br>`--semantic*` 兼容 no-op | Query 改写 / 意图识别<br>多轮检索编排<br>证据筛选 / 摘要 / 解释<br>引用整理 / 报告生成     |

**矩阵读法**：左列 = Life Index 提供的确定性能力（[CHARTER](./CHARTER.md) §1.5 + §1.11）；右列 = 你的 Agent 用它自己的 LLM 做的语言与推理工作。Life Index 不内置 embedding 模型，也不在工具内维护 vector RAG；"按意思检索"发生在右列。

> *The intelligence is yours; the memory is yours; Life Index is the protocol layer that lets the two meet.*

### 开发路线

**CLI Core 当前稳定线** 已稳定运行 —— 不是原型，不是 demo，是经过 4,200+ pytest-collected tests、CI 全绿、真实日常使用的系统；当前包版本以 `life-index --version` 和 [CHANGELOG.md](./CHANGELOG.md) 为准。**地基已成；GUI 体验层已在独立公开仓维护，CLI 仓保留确定性工具层与 CLI/GUI 关系入口。**

<details>
<summary>🧱 已经建好的地基（CLI Core，点击展开）</summary>

<br>

| 核心能力                   | 状态  | 说明                                                                              |
|:---------------------- |:---:|:------------------------------------------------------------------------------- |
| 日志写入 / 编辑              | ✅   | 结构化 Markdown + YAML，自动天气/情感/实体标注                                                |
| 分层人生检索                 | ✅   | 关键词精确匹配 + Entity Graph 实体扩展；Agent 可选负责搜索前编排和搜索后表达                               |
| Index Tree 宿主导航        | ✅   | `ensure → discover → navigate` 三步导航；按时间 / 主题 / 标签 facet 浏览人生目录                  |
| 智能搜索编排器 (smart-search) | ✅   | 输出 agent-ready 确定性检索 scaffold；query 改写与精筛由宿主 agent 完成，工具内不启用 LLM                |
| 搜索质量评估 (eval)          | ✅   | 公开合成 Core 契约与哨兵阻断确定性回归；本地 / 私有、noise 与 quality 指标评估仅作咨询证据             |
| 实体图谱 + 质量审计 + 维护       | ✅   | 别名消解、关系推理、重复/孤立检测 + Agent 访谈修复                                                  |
| 一页式安装 / 升级 (bootstrap) | ✅   | `bootstrap --json` 输出确定性 execution_policy + freshness 检查；可靠交付 SKILL 到宿主 skill 库 |
| 数据体检 (data doctor)     | ✅   | `maintenance audit` 统一数据完整性检测；`verify` 只读校验                                     |
| Schema 迁移              | ✅   | 链式迁移框架，确定性字段补齐 + Agent 语义回填协作                                                   |
| 操作级可观测性                | ✅   | 每次操作附带 trace_id + 分步耗时 + 状态诊断                                                   |
| 数据备份 / 完整性验证           | ✅   | 加密备份 + 数据一致性校验                                                                  |
| 跨平台                    | ✅   | Windows / macOS / Linux，Python 3.11+                                            |

</details>

<details>
<summary>🔭 远景模组（点击展开）</summary>

<br>

在稳固的 CLI Core + GUI 之上，更多模组将陆续生长 —— 每个都是**稳定记录格式 + 确定性检索 + Entity Graph 增强 + 宿主 Agent 编排**的组合：

| 模组         | 代号       | 说明                                        |
|:---------- |:-------- |:----------------------------------------- |
| EXIF 照片时间线 | **光影年轮** | 从相册自动提取时间/地点/场景，为新用户在 1 天内生成 5 年视觉年轮      |
| 社媒历史归档     | **回溯导入** | 解析各平台官方导出 zip，把过去 20 年的博文/推文纳入 Life Index |
| 童年记忆手动录入   | **穿越时空** | 那些珍贵的童年碎片，现在就可以录入                         |
| 回忆录自动生成    | **自传引擎** | 把碎片日志编织成完整叙事；你的人生，成书                      |
| 数字人格       | **数字灵魂** | 数十年数据积累后的终极能力——"如果爸爸还在……"                 |

</details>

<details>
<summary>🕰️ 五十年存活愿景（点击展开）</summary>

<br>

50 年跨越至少 3 次硬件淘汰、5 次操作系统大版本，可能还要跨过我自己这一生的剩余时长。让一个一个人开发的项目活过 50 年，工程上近乎傲慢。但 Life Index 的承诺正建立在"承认这种傲慢"之上：

- **数据这一层**用 Markdown + YAML 兑现 —— 即使"Life Index"这个名字消失，你的日志依然能被任何文本编辑器打开。
- **承诺这一层**用外部约束兑现 —— [CHARTER §5.3](./CHARTER.md) 把数据主权、纯文本永久性、向下兼容、召回优先锁进"不可弱化清单"。
- **作者这一层**是最薄弱的一环 —— 我不假装能活 50 年，但只要我还在写代码，宪章第零条就锁定了：宪章高于代码、高于本人。

**50 年的真正含义不是"我保证活到那时"，而是"今天的我，把未来的我也约束住了"。**

</details>

---

## 设计决策 · Design Decisions

> Life Index 的几个关键取舍 —— 都不是技术债，是**有证据、有架构一致性的主动选择**。主线给结论，这里给"为什么"。

<details>
<summary>🧭 为什么不做 in-tool vector RAG（点击展开）</summary>

<br>

很多人第一次看 Life Index 会问：一个 2026 年的个人检索系统，为什么默认搜索还是关键词，而不是向量语义？

这是一个刻意的选择，有四层理由，从架构到实测：

**① 架构上 —— 智能归宿主 Agent，工具只做确定性原语。**
Life Index 是 agent-native 架构：它给宿主 Agent 提供可审计、可复现、零 token、完全离线的确定性原语；而"按意思理解"本就该由越来越强的宿主 Agent 来做。把语义塞进工具内部，等于在 Agent 和数据之间插进一个会静默出错的概率层 —— 而 Agent 自己就擅长这件事。

**② 检索上 —— 默认 keyword-only honest floor，向量不进默认路径。**
检索层对用户的承诺是"不遗漏你每一个人生碎片"（[CHARTER §1.11](./CHARTER.md)），这要求默认行为是 **recall-first**：忠实返回所有 token-match 的候选，不在源头做相关度阈值截断。向量检索天然带噪声，与 recall-first 有结构性张力。

**③ 验证上 —— 公开 blocker 保护 recall-first，不发布私有语料指纹。**
仓库内的 synthetic token-match assertion 负责阻断真实匹配被删除；本地 / 私有质量 eval 保留为 advisory evidence，用于观察 ranking、noise 与 nDCG，不覆盖 Core truth，也不把私有 query 数、精确指标或失败事实写入公开说明。

**④ 工程上 —— 默认安装更轻、更快、更离线。**
启用语义检索需要一个约 **1.3 GB** 的 ML 栈（torch + CUDA），把首次安装拖到约 **16 分钟**。我们把它拆成了 opt-in extra，默认安装秒装、秒跑、完全离线。

> **这不是反 RAG。** 我们做的三件精确的事是：把重模型栈从默认安装拆走、把工具内的 LLM/RAG 编排路径退役、把默认搜索形态锁成 keyword-only（并写进 [CHARTER §1.11 / §3.2 amendment](./CHARTER.md)，入 §5.3 不可弱化清单）。`--semantic*` 旗标保留为兼容 no-op —— 老调用不报错，但不下载模型、不建向量索引、不改变结果。
> 
> *近年来检索工程的一个清晰转向是：把"按意思扩展查询"交给 LLM（由宿主 Agent 完成），把"结构化扩展"交给知识图谱。Life Index 的 Entity Graph + Agent 编排，恰好落在这条路径上。把语义交给 Agent，把关系交给图谱 —— 更快、更简洁，也更准确。*

</details>

<details>
<summary>🤖 Agent-Native，不是 Agent-First（点击展开）</summary>

<br>

> Agent-First 是"先考虑 Agent 的需求"。Agent-Native 是"这个系统天生就是为 Agent 而写的"。

Life Index 的 CLI 不是一个人类命令行工具"加了 AI 支持" —— 它的结构化信号系统、确认工作流、枚举式错误码，从第一行代码就是 Agent 的母语。Agent 不需要解析自然语言错误信息，它拿到的是枚举值和确定性的恢复路径。

但 Agent-Native 不意味着"只有 Agent 能用"：我们为 Agent 提供它最需要的——**精确的机器接口**；同时为人类提供人类最需要的——**自然语言对话和视觉体验**。

</details>

<details>
<summary>📐 三条设计底线（点击展开）</summary>

<br>

```
宁可功能简单，不可系统复杂
宁可人工维护，不可自动化陷阱
宁可牺牲性能，不可牺牲可靠性
```

向量阈值调参、模型安装、索引缓存、噪音过滤，很容易变成第二条说的"自动化陷阱"。keyword + Index Tree + Entity Graph 简单、可审计，且比 hybrid 更快、更 deterministic。

</details>

<details>
<summary>🔒 数据主权：你的灵魂不进 Mikoshi（点击展开）</summary>

<br>

Life Index 采用「本地优先」和「程序与数据彻底分离」策略，用户日志存储在系统用户目录下：

```
~/Documents/Life-Index/
├── INDEX.md                     # 根索引——你的人生地图
├── Journals/                    # 日志（按年月组织）
│   └── 2026/03/...
├── attachments/                 # 附件（照片、视频、语音）
├── by-topic/                    # 主题维度索引（与时间索引树正交互补）
└── .index/                      # 机器检索层（FTS5 + 元数据缓存，人不可读，可删除重建）
```

`Journals/` 是数据真相源；任何时候删除 `.index/`、运行 `life-index index --rebuild`，所有检索能力即可重建。**数据不依赖 Life Index 的任何运行时** —— 程序与数据彻底解耦，这正是"不做云端存储"的底气。

> **Life Index 强烈建议本地备份** —— 保护好你的**数字遗产 (Relic)**，不要把你的**灵魂印记 (Engram)** 主动送入大公司的**神舆 (Mikoshi)**。

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

## 参与贡献

Life Index 处于个人驱动的早期阶段，但理念早已超出"一个父亲写给女儿的日志"的边界。如果你是创作者、心理咨询师、家庭文化研究者、agent-native 工程师，或量化自我（QS）实践者，你可能会发现 Life Index 的[四个承诺](#四个承诺)正好契合你需要的工具属性。

- **模组开发** —— 最有影响力的贡献。每个[远景模组](#开发路线)都是独立功能单元，遵循 [CHARTER §1.9](./CHARTER.md) agent-native 原则，默认不持 LLM。
- **提 Issue** —— 分享使用场景、报告 Bug、提出你想要的模组方向。
- **文档翻译 / 分享故事** —— 让更多人用母语了解这个项目；如果你用它记录下了重要瞬间，我们很想听到。

## 许可证

[GNU Affero General Public License v3.0](./LICENSE) (`AGPL-3.0-only`) —— 你的人生数据属于你。

白话说：本地使用、个人记录、在自己电脑上运行 Life Index 不受任何影响。若你把修改版作为托管或网络衍生服务提供给他人，就需要按 AGPL 公开相应服务代码和修改。

---

> *"我既希望我们一家人永恒停留在团团2岁的时光 —— 也盼望她长大可以去感受更美好的世界。*
> *总而言之，小疙瘩，爸爸想你了。Tuan Tuan, this one is for you."*
> 
> *—— 摘自 Life Index 第一篇日志，2026年3月4日*
> *这不是关于她的成长记录，而是关于我爱她的记录。*
