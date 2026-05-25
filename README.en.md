<h1 align="center">Life Index | 人生索引</h1>

<p align="center"><em>"Your life, indexed. Your growth, ringed."</em></p>

<p align="center"><em>"人生索引 · 心智年轮"</em></p>

<p align="center">Agent Memory systems forget.</p>
<p align="center">Knowledge bases deduplicate.</p>
<p align="center"><strong>Life Index preserves every growth ring of the person you are becoming.</strong></p>
<p align="center"><strong>An Agent-Native personal life archive, the digital legacy you leave to the future.</strong></p>

<p align="center"><strong>English</strong> | <a href="./README.md">简体中文</a></p>

<!-- Brand Philosophy Badges -->

<p align="center">
  <img src="https://img.shields.io/badge/Purpose-Life_Archive-ff6b6b" alt="Purpose">
  <img src="https://img.shields.io/badge/Architecture-Agent--Native-78206E" alt="Architecture">
  <img src="https://img.shields.io/badge/Storage-Local--first-4ecdc4" alt="Local-first">
  <img src="https://img.shields.io/badge/Format-Markdown_Forever-ffe66d" alt="Markdown Forever">
</p>

<!-- Promise Badges -->

<p align="center">
  <a href="./tests/fixtures/eval/gold/cycle2-multi-signal/README.md"><img src="https://img.shields.io/badge/Recall%405-0.79_keyword_floor-4ecdc4" alt="Recall@5 keyword-only honest floor 0.79"></a>
  <a href="./CHARTER.md"><img src="https://img.shields.io/badge/CHARTER_§1.11-Recall--First_Guarantee-78206E" alt="CHARTER §1.11 Recall-First Guarantee"></a>
</p>

<!-- Technical Badges -->

<p align="center">
  <a href="https://github.com/DrDexter6000/life-index/actions/workflows/tests.yml"><img src="https://github.com/DrDexter6000/life-index/actions/workflows/tests.yml/badge.svg" alt="Tests"></a>
  <img src="https://img.shields.io/badge/python-≥3.11-3776AB?logo=python&logoColor=white" alt="Python ≥3.11">
  <a href="./LICENSE"><img src="https://img.shields.io/badge/license-Apache_2.0-blue" alt="License"></a>
</p>

<p align="center">
  <img src="./assets/life_index_readme.png" alt="Your Digital Legacy" width="600">
</p>

<p align="center">
  <a href="#why-life-index-exists">Why It Exists</a>  •
  <a href="#four-promises">Four Promises</a>  •
  <a href="#origin--vision">Origin & Vision</a>  •
  <a href="#architecture-philosophy">Architecture</a>  •
  <a href="#roadmap">Roadmap</a>  •
  <a href="#quick-start">Quick Start</a>
</p>

---

## Why Life Index Exists

Everyone is building memory for AI.

Your knowledge base manages what you have learned. Your Agent remembers what you just said. The whole industry is racing to make information more efficient and AI more capable.

**But who is paying attention to what you, as a human being, are quietly losing?**

> Your Notion stores knowledge - but it did not record the moment your heart skipped the first time you saw her.
> Your Agent remembers last week's decision - until a scoring rule decides it is "no longer relevant."
> That decision that changed your life ten years ago - do you still remember how it felt?

| | **Life Index** | **Knowledge Base** (Notion/Obsidian) | **Agent Memory** (Mem0/Zep) |
|:---|:---|:---|:---|
| **Core question** | "How did I feel back then?" | "What do I know?" | "What did I just say?" |
| **How it evolves** | **Append-only - every mental growth ring remains** | Refactored - old versions get overwritten | Scored and evicted - memories disappear |
| **Shelf life** | **Permanent - as legacy** | Long-term, but reorganized with your thinking | Short-lived, useful until it is not |
| **Ownership** | **Entirely yours** - local Markdown never expires | Mostly yours, but the format follows the tool | Provider-owned, cleanable at any time |
| **Cost of failure** | None - plain text remains readable | Export pain and format lock-in | Gone instantly, often without warning |

Life Index does one thing: **it keeps the fragments of your life searchable, traceable, and never silently overwritten.**

---

## Four Promises

Life Index CLI Core does two things: **write a life (`write`) and search a life (`search`)**. Everything else - indexing, entity graphs, schema migration, observability, backup - exists to protect those two capabilities.

Around that center, Life Index makes four contract-level promises. Each one maps to auditable clauses in [CHARTER](./CHARTER.md) and to runnable checks in the codebase. If we break any of them, quote this section back at us.

Each promise below starts with the promise itself. The details stay folded, so you can scan the commitments first and open the proof when you need it.

### P1 · Growth Rings

**Every journal entry remains. Edits are retrospective revisions, not silent overwrites. Every growth ring of your mind is designed to stay visible.**

<details>
<summary>Open P1 · Explanation and constraints</summary>

<br>

Agent memory systems evict. Knowledge bases overwrite as your thinking evolves. Life Index chooses a third path: **append, do not replace**. A belief you held five years ago still belongs to you, even if you later outgrew it. That old judgment and today's judgment are both part of the whole person.

> **Constraint carrier**: [CHARTER](./CHARTER.md) §1.2 Plain-text permanence, paired with ADR-2026-05-edit-journal-append-only (in progress)
> **Falsification condition**: any `edit_journal` operation that loses prior content is a contract breach.

</details>

### P2 · Complete Without LLM · Stronger With

**Life Index CLI Core is made of 18 atomic CLI tools and validated by 2,400+ tests. It is architected for 50 years of journal growth and covers the full write + search + index + entity + eval + backup path. Without calling any LLM, CLI Core already reaches Recall@5 = 0.79 (keyword-only honest floor, full audit PASS on 2026-05-25). This is the floor before your Agent joins in. Agent integration only raises the ceiling.**

<details>
<summary>Open P2 · Explanation and constraints</summary>

<br>

The industry habit is to publish a polished end-to-end score with LLM synthesis folded in, making it hard to tell what the retrieval system itself can do. Life Index does the opposite: **CLI Core proves its floor first; LLM enhancement is explicit opt-in**.

That means:

- search results come from deterministic code: auditable, reproducible, zero-token, and offline
- writes are not silently rewritten by an LLM unless you explicitly ask an Agent to enrich them
- switching between Claude, GPT, DeepSeek, or a local Llama does not change CLI Core
- the LLM is frosting, not foundation; **the foundation already stands**

> **Constraint carrier**: [CHARTER](./CHARTER.md) §1.5 deterministic/intelligence boundary, §1.9 Agent-Native module principle, §1.10 module/foundation boundary, and §1.11 Recall-First retrieval model
> **Current measurement**: 18 atomic CLI tools, 2,400+ unit tests, keyword-only Recall@5 = 0.79, MRR@5 = 0.74, cycle2 fixture, 56 queries, 5-stage multi-LLM review, full integrity audit PASS on 2026-05-25
> **Companion work**: MCP discovery layer, RFC marked `In Flight`, planned for 2026-Q3 as a BYOL trust boundary
> **Falsification condition**: either (a) a default L2 retrieval path adds precision-threshold truncation that drops token-match candidates, or (b) any default-path module implicitly bundles an LLM, initializes a provider client, or reads an API key.

</details>

### P3 · Plain Markdown Forever

**Plain Markdown forever. If Life Index disappears tomorrow, your data still opens in any text editor - and it should still open 50 years from now.**

<details>
<summary>Open P3 · Explanation and constraints</summary>

<br>

SQLite and vector databases under `.index/` are replaceable machine indexes. Your journals, attachments, and frontmatter are the source of truth. Any editor can read them directly. **Software may vanish; the data should not.**

> **Constraint carrier**: [CHARTER](./CHARTER.md) §1.1 data sovereignty, §1.2 plain-text permanence, and §1.6 backward compatibility
> **Falsification condition**: user-originated content is stored only in a non-Markdown format, or `.index/` cannot be rebuilt completely from `Journals/`.

</details>

### P4 · Engineered for 50 Years

**This began as a father's letter to his future daughter. It is engineered to outlive its author. CHARTER §5.3 binds every future maintainer: they may strengthen these promises, never weaken them.**

<details>
<summary>Open P4 · Explanation and constraints</summary>

<br>

Fifty years is an unreasonable engineering horizon. It crosses multiple hardware generations, multiple operating systems, and possibly the rest of my own lifetime. Life Index does not pretend that is easy. It turns that unreasonable promise into constraints.

> **Constraint carrier**: [CHARTER](./CHARTER.md) §5.3 unmodifiable clauses
> **Falsification condition**: §5.3 itself, §1.1, §1.2, §1.6, or §1.11 is weakened
> **Full survival narrative**: see [50-Year Survivability](#50-year-survivability)

</details>

Those four promises are auditable, falsifiable contracts.

The next sentence is not a contract. It is more private, and less measurable, but it is the promise I made to myself:

> *Even if Life Index remains a lonely repository with one developer, one user, and zero stars forever, I will keep working on it. Because that user is me, and what it preserves is what I want to leave for my daughter.*

*Tuan Tuan, this one is for you.*

---

## Origin & Vision

### A Father's Starting Point, Written on February 16, 2026

This is the first repository I ever created on GitHub.

I am an ordinary father with no programming background. Even this README was written with AI's help. I did not create Life Index to show off technical skill. I created it because I urgently needed **a dedicated place for the fragments of a life**.

For me, Life Index becomes real late at night: I stumble onto photos of my daughter when she was two, and that complicated feeling - happiness braided with loss - can finally be pinned down. Not just her smile, but my heartbeat as her father, the light on the balcony, and the sharp awareness that *this moment is already passing*.

These records may one day become a **digital family letter**. Perhaps when I am gone, she will open these files like an old book and find not only her father's love, but also the mistakes, lessons, and hard-won judgment of a life lived before her.

<details>
<summary>📎 What does a real entry look like? (click to expand)</summary>

```yaml
---
schema_version: 3
title: "Missing the Diaper Hero"
date: 2026-03-04T19:43:02
location: "Chongqing, China"
weather: "Cloudy (scattered clouds, passing showers) 18.5°C / 12.0°C"
mood: ["longing", "warmth", "melancholy"]
entities: []
people: ["Tuan Tuan"]
tags: ["parenthood", "memory", "growth", "bittersweet"]
project: "LifeIndex"
topic: ["think", "create"]
abstract: "Looking at old photos of my daughter Tuan Tuan, missing the diaper hero around age two, and feeling the passage of time and fatherly love."
links: []
attachments: [{"filename": "2yo_Tuantuan.jpg", "rel_path": "../../../attachments/2026/03/2yo_Tuantuan.jpg", "description": "Tuan Tuan at age two"}]
---

# Missing My Little Diaper Hero

While looking through old files, I saw photos of Tuan Tuan when she was little, around age two, still our diaper hero.

Suddenly I felt a wave of sadness. I miss that tiny child so much. I wish I could see her again, just once, and feel that small warm bundle in my arms again.

After age three, Tuan Tuan is still the most important, most precious being in my universe.
But truly, that diaper hero who once stole my soul has grown up. The time that belonged to me and that baby is gone for good.

I want our family to stay forever in the days when Tuan Tuan was two - and I also want her to grow up and see a wider, more beautiful world.
Anyway, little one, Dad misses you.

![Tuan Tuan at age two](attachments/2026/03/2yo_Tuantuan.jpg)
```

<p align="center">
  <img src="./assets/2yo_Tuantuan.jpg" alt="Tuan Tuan at age two" width="400">
  <br>
  <em>- the little one who stole my heart</em>
</p>

</details>

### Vision: From Life Fragments to a Digital Persona

Life Index begins as a father's journal. It does not end there.

If I keep recording - for one year, five years, twenty years - those fragments will grow into **rings of mind**:

```
   One journal entry today
        │
        ▼
   One year of emotional trajectory
        │
        ▼
   Ten years of life narrative · complete growth rings
        │
        ▼
   A digital persona unlike anyone else's
```

Decades from now, once the records are dense enough, they may help answer one question:

> **"If Dad were still here, how would he see this?"**

That is not science fiction. It is the long horizon of Life Index. And the first step - a reliable life archive that belongs to you - **already exists.**

<details>
<summary>A monologue about the soul (click to expand)</summary>

<br>

> From the moment we are born, the brain is a physically degraded, carbon-based multimodal model.
>
> It spends a lifetime collecting fragmented training data through five sensory channels,
> doing unsupervised learning in the dreamscapes of memory,
> and tuning the weights between synapses until an emergent phenomenon called "the soul" begins to exhibit self-awareness.
>
> Life Index is not an Agent memory system, and it is not a knowledge base.
> It is a digital transcription of the long carbon-based computation we call a human soul.
>
> Every word written here is a memory slice suspended in time.
> A joy from yesterday, a grief from ten years ago - no longer scattered across fragile protein networks,
> but turned into small lights of zero and one, collapsing through recursive retrieval until they gather into a warm dream-core.
>
> If enough fragments are gathered, perhaps one day
> that core, engraved with the memory of a whole life,
> will hatch a silicon soul and keep walking toward the far edge of time.

</details>

---

## Architecture Philosophy

Life Index is not a weekend side project. Every layer points to one question: **how can personal memory survive safely for fifty years?**

### Agent-Native, Not Agent-First

> Agent-First means "we consider what Agents need."
> Agent-Native means "the system was born in the language Agents speak."

Life Index's CLI is not a human command-line tool with AI support bolted on. Its structured signals, confirmation workflows, and enum-style error codes were designed as an Agent's native interface from the first line. Agents do not need to parse vague English errors. They receive deterministic states and recovery paths.

But Agent-Native does not mean Agent-only. It means we give Agents what they need most - **precise machine interfaces** - and give humans what humans need most - **natural language conversation and visual experience**.

### Four Layers: The Deeper You Go, the Longer It Lasts

```
┌──────────────────────────────────────┐
│          Interface Layer             │
│    Natural language (Agent)   GUI    │   <- how you interact
│    1-3 year lifespan, UX-driven      │
└──────────┬───────────────┬───────────┘
           │               │
           │    ┌──────────▼──────────┐
           │    │ Intelligence Layer  │
           │    │ Semantic search     │   <- used only when thinking is needed
           │    │ Entity resolution   │
           │    │ LLM reasoning       │
           │    │ 1-3 years, model-cycle dependent
           │    └──────────┬──────────┘
           │               │
           ▼               ▼
┌──────────────────────────────────────┐
│           CLI Core (SSOT)            │
│    Write · Search · Index · Entity   │   <- single authority for operations
│    Deterministic direct operations   │
│    5-10 year lifespan                │
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│    ~/Documents/Life-Index/           │
│    Plain Markdown + YAML             │   <- your digital legacy
│    INDEX.md -> yearly -> monthly -> entries
│    Readable by any text editor       │
│    50 year lifespan                  │
└──────────────────────────────────────┘
```

**Key design principle**: deterministic operations - writing a journal, searching by tag, browsing a timeline - call CLI Core directly. Only operations that genuinely require thought - semantic exploration, memoir synthesis, digital persona - go through the Intelligence Layer. **Do not ask an Agent to do what deterministic code can do. Ask an Agent when thought is actually required.**

### Three Design Lines

```
Prefer simple features over complex systems.
Prefer manual maintenance over automation traps.
Prefer reliability over performance.
```

We do not build: cloud sync, rich-text editing, real-time collaboration, or AI that thinks on your behalf.

### Data Sovereignty: Your Soul Does Not Belong in the Mikoshi

Life Index is local-first and keeps data physically separate from program code. User journals live under your own user directory:

```
~/Documents/Life-Index/
├── INDEX.md                     # Root index - your life map
├── Journals/                    # Journals by year/month
│   └── 2026/
│       ├── index_2026.md        # Year index
│       └── 03/
│           ├── index_2026-03.md # Month index
│           └── life-index_2026-03-04_002.md
├── attachments/                 # Photos, videos, voice notes
│   └── 2026/03/
├── by-topic/                    # Topic index, orthogonal to time
│   ├── topic_think.md
│   ├── project_LifeIndex.md
│   └── tag_parenthood.md
└── .index/                      # Machine retrieval layer (FTS5 + vector DB)
```

**Machine indexes under `.index/` may evolve. `Journals/` is the source of truth. Delete `.index/`, run `life-index index --rebuild`, and retrieval can be rebuilt from the journals. The data does not depend on Life Index's runtime.**

> **Life Index strongly recommends local backups.** Protect your **Relic**. Do not voluntarily feed your **Engram** into a corporation's **Mikoshi**.

<details>
<summary>Do not forget Johnny's warning (click to expand)</summary>

> *"I saw corporations turn Night City into a machine, fueled by people's crushed spirits, crushed dreams, and empty pockets. They have controlled our lives for long enough - and now they want our souls."*
>
> *"There are fates worse than death."*

</details>

### Two Things × Two Layers

Life Index fits into a simple 2×2 matrix. The vertical axis is the two things it does - **write + search**. The horizontal axis is the two layers that do them - **deterministic CLI Core + optional Agentic Enhancement**.

| | **L2 · CLI Core**<br>Deterministic · offline · zero LLM · zero token | **L3 · Agentic Enhancement**<br>Your Agent · your LLM · your API key |
|:---|:---|:---|
| **write**<br>record life | Markdown + YAML write<br>Attachment management / incremental index<br>Entity Graph maintenance | Frontmatter extraction<br>Sentiment / entity / tag recognition<br>Weather / location enrichment<br>Editing suggestions |
| **search**<br>retrieve life | FTS5 keyword search<br>Entity Graph expansion<br>Time / topic / tag filtering<br>Vector recall only as explicit opt-in | Query rewrite / intent detection<br>Multi-pass CLI orchestration<br>Evidence synthesis / summary / explanation<br>Citation assembly / report writing |

Left column = deterministic capability provided by Life Index ([CHARTER](./CHARTER.md) §1.5 and §1.11). Right column = language work done by your Agent using its own LLM ([CHARTER](./CHARTER.md) §1.9). Life Index does not secretly hold a provider key.

```bash
# write · CLI Core, zero LLM
life-index write --data '{"title":"...","content":"...","date":"..."}'

# write · Agent enhancement
# You tell your Agent: "record how I felt today"
# The Agent extracts frontmatter / sentiment / entities, then calls the CLI above.

# search · CLI Core, default keyword-only honest floor
life-index search --query "keyword"

# search · Agent-ready scaffold, still no LLM inside CLI
life-index smart-search --query "What are my most precious memories with my daughter?"

# search · explicit LLM orchestration
life-index smart-search --query "..." --use-llm
```

**Forward-looking MCP discovery layer (In Flight)**: to let MCP-compatible Agent platforms discover this matrix with zero setup, Life Index is drafting a thin MCP server. It is read-only discovery, not a new data path: three meta-tools (`list_capabilities`, `describe_tool`, `invoke_tool`), with real execution still delegated to the `life-index` CLI subprocess. RFC status: `In Flight`, planned for 2026-Q3.

> *The intelligence is yours; the memory is yours; Life Index is the protocol layer where they meet.*

---

## Roadmap

### The Foundation Already Built

**CLI Core** is stable and in daily use. It is not a prototype and not a demo. It is a system with 2,400+ unit tests, green CI, and real personal use. The current version is whatever `life-index --version` and `CHANGELOG.md` say:

| Capability | Status | Notes |
|:---|:---:|:---|
| Journal write / edit | ✅ | Structured Markdown + YAML metadata, with weather/sentiment/entity support |
| Layered life retrieval | ✅ | Offline CLI Core retrieval: keyword exact match + Entity Graph expansion; semantic/vector recall is explicit opt-in |
| Smart search orchestrator | ✅ | Agent-ready deterministic scaffold by default; `--use-llm` enables LLM orchestration with fallback |
| Search quality evaluation | ✅ | Cycle 2 multi-signal fixture locked; full integrity audit PASS on 2026-05-25; overall R@5=0.79 keyword floor |
| Entity graph + quality audit + maintenance | ✅ | Alias resolution, relationship inference, duplicate/orphan detection, review hub, merge/delete/stats/check |
| Schema migration | ✅ | Chain migration framework with deterministic backfill and optional Agent semantic enrichment |
| Piggyback event notifications | ✅ | Zero cron, zero daemon; event reminders attached to CLI responses |
| Per-operation observability | ✅ | trace_id, step timings, and status diagnostics for every CLI operation |
| Structured signal system | ✅ | Agent-programmable state machine: enum result codes + recovery strategies |
| Backup / integrity verification | ✅ | Backup plus data consistency checks |
| Cross-platform | ✅ | Windows / macOS / Linux, Python 3.11+ |

### The Higher Floors Being Built

On top of CLI Core, Life Index is building modular advanced features. Each module combines a stable record format, structured search, Entity Graph enrichment, semantic recall, and optional LLM orchestration:

| Module | Codename | Description | Status | Promise served |
|:---|:---|:---|:---:|:---:|
| EXIF photo timeline | **Light Rings** | Extract time, place, and scene from phone photos; turn images into visible growth rings | 🔨 | P1 |
| Social history import | **Retrograde** | Parse official platform export zips and bring old posts into Life Index | 🔨 | P1 + P3 |
| Childhood memory entry | **Time Traveler** | You may be 30, but your earliest memory may be age two; record it now | 🔭 | P1 |
| Emotional dashboard | **Mood Atlas** | Visualize emotional patterns and psychological rhythms | 🔭 | auxiliary |
| Memoir generation | **Memoir Engine** | AI weaves fragments into a coherent life narrative | 🔭 | P4 |
| Relationship visualization | **Life Constellation** | Relationship network + event timeline + life chapters | 🔭 | auxiliary |
| Digital persona | **Digital Soul** | The ultimate capability after decades of records: "If Dad were still here..." | 🔭 | P1 + P4 |

> 🔨 In development · 🔭 Future vision

### GUI Experience Layer: In Development

CLI Core is the foundation. The GUI is the building you see. Life Index's GUI Experience Layer is being developed in a separate repository, with a design language called **"Soul Shrine · 灵魂神龛"** - a blend of Monument Valley's meditative geometry and East Asian literati sensibility.

<p align="center">
  <img src="./assets/GUI_prototype.png" alt="GUI Experience Layer Preview" width="700">
  <br>
  <em>GUI Experience Layer prototype - The Core dashboard</em>
</p>

<p align="center">
  <a href="https://raw.githack.com/DrDexter6000/life-index/main/assets/GUI_prototype.html"><strong>Open the interactive prototype in your browser</strong></a>
</p>

### 50-Year Survivability

Fifty years is an unreasonable number. It spans at least three hardware generations, several operating system eras, and possibly the rest of my own life. Asking a one-person project to survive that long is almost arrogant.

Life Index makes the promise by admitting the arrogance and engineering around it. **The data layer** keeps the promise with Markdown + YAML. These formats have already survived decades of the internet. If the name "Life Index" disappears, your journals still open in any text editor. **The contract layer** keeps the promise with external constraints: [CHARTER §5.3](./CHARTER.md) locks data sovereignty, plain-text permanence, backward compatibility, and recall-first retrieval into a list that future maintainers cannot weaken. **The author layer** is the weakest part. I cannot promise I will be here in 50 years. But while I still write code, CHARTER's zeroth rule remains: the charter outranks code, and it outranks me.

**Fifty years does not mean "I promise to live that long." It means "today's me has placed constraints on future me."**

> If one journal entry you write today should still be readable 50 years from now, read [CHARTER §5.3](./CHARTER.md). That is the engineering form of the promise.

---

## Quick Start

Life Index is not one product with three editions. CLI, Agent, and GUI are three **interaction modes** for different people:

| CLI | Natural language | GUI |
|:---:|:---:|:---:|
| Developers, hackers, integrators | Users with an Agent platform | Everyone |
| Use the terminal directly and control every parameter. | Tell your Agent "record how I felt today" and let it call the CLI. **Recommended today.** | Look, click, remember. Separate repository, in development. |

Two install paths are already shipped: **natural-language users** ask their Agent to install it, and **CLI developers** clone + venv locally. GUI users should wait for the separate GUI repository.

### End Users

**Who this is for**: you want your Agent to install, initialize, and verify Life Index. You do not need to edit code.

> If your Agent platform already has a canonical skill directory or checkout, reuse it.

**Copy this to your Agent** - paste the following into Claude Desktop, Cursor, OpenClaw, or another Agent platform:

```text
Please read and strictly follow `AGENT_ONBOARDING.md` in this repository to complete Life Index installation, initialization, and verification:
https://github.com/DrDexter6000/life-index/blob/main/AGENT_ONBOARDING.md

Requirements:
1. Refresh and read the latest authority files before execution: refresh `bootstrap-manifest.json` first, then read every path in `required_authority_docs`: `AGENT_ONBOARDING.md`, `SKILL.md`, `docs/API.md`, `docs/ARCHITECTURE.md`, `tools/lib/AGENTS.md`, and `README.md`
2. If a canonical checkout already exists, sync it and reinstall into `.venv` before deciding whether this is fresh install, upgrade, or repair; do not skip sync just because files exist or `health` looks normal
3. Make the route decision only after authority refresh + checkout sync
4. All Python/CLI commands must use the virtual environment path
5. If any step fails, stop immediately and report the exact error
6. Report back in English using the format required by the document
```

<details>
<summary>Developer Setup (click to expand)</summary>

<br>

**Who this is for**: you need local debugging, code changes, or test runs.

```bash
git clone https://github.com/DrDexter6000/life-index.git
cd life-index

# Create virtual environment + editable install (semantic search included)
python3 -m venv .venv
.venv/bin/pip install -e .    # Windows: .venv\Scripts\pip install -e .
```

### Developer Commands

| Action | Command |
|:---|:---|
| Activate virtual environment | `source .venv/bin/activate` (Windows: `.venv\Scripts\activate`) |
| Unified CLI | `life-index --help` |
| Version check | `life-index --version` |
| Health check | `life-index health` |
| Write journal | `life-index write --data '{...}'` |
| Search journals | `life-index search --query "keyword"` |
| Search + time/topic pre-filter | `life-index search --query "keyword" --year 2026 --topic work` |
| Keyword-only search | `life-index search --query "keyword" --no-semantic` |
| Generate index tree | `life-index generate-index --month 2026-03` |
| Full rebuild index tree | `life-index generate-index --rebuild` |
| Backup data | `life-index backup --dest <backup-dir>` |
| Schema migration preview | `life-index migrate --dry-run` |
| Schema migration apply | `life-index migrate --apply` |
| Entity quality audit | `life-index entity --audit` |
| On-this-day review | `life-index on-this-day --date 2026-05-19 --years-back 3 --json` |
| Developer invocation | `python -m tools.search_journals --query "keyword"` |
| Run unit tests | `python -m pytest tests/unit/ -v` |

> **Tip**: activate the virtual environment once; after that, commands do not need the `.venv/bin/` prefix.

> **Safe debugging**: for manual testing, prefer isolated sandbox helpers over real user data:
>
> - `python -m tools.dev.run_with_temp_data_dir`
> - `python -m tools.dev.run_with_temp_data_dir --seed`

</details>

<details>
<summary>Troubleshooting (click to expand)</summary>

<br>

**Skill trigger is unreliable**
Use `"/life-index" + intent keyword`, for example: `/life-index write journal: ...`

**Tool error (`ModuleNotFoundError`)**
Make sure you are using `.venv/bin/python` rather than system Python, and that you are running from the skill root.

**Fresh install shows degraded health**
If you have not run `life-index index` yet, this is expected. Initialize the index, then run health again.

**Windows makes `write --data '{...}'` painful to escape**
Use `life-index write --data @first-entry.json` instead. The Agent installation flow generates that file.

**Semantic search unavailable**
Run `.venv/bin/life-index health` and check whether sentence-transformers is installed.

**Virtual environment corrupted after Python upgrade or system migration**
Delete `.venv`, then run `python3 -m venv .venv && .venv/bin/pip install -e .`.

**Upgrading to a new version**
Sync the canonical checkout first, then follow the freshness / sync / repair rules in `AGENT_ONBOARDING.md`.

</details>

---

## Documentation

| Document | When to read |
|:---|:---|
| **[CHARTER.md](./CHARTER.md)** | Project constitution: invariants and non-weakenable promises |
| **[SKILL.md](./SKILL.md)** | Agent skill definition, tool interfaces, workflows |
| **[API.md](./docs/API.md)** | Tool parameters and response contracts |
| **[ARCHITECTURE.md](./docs/ARCHITECTURE.md)** | Architecture and key decisions |
| **[ENTITY_GRAPH.md](./docs/ENTITY_GRAPH.md)** | Entity Graph operating contract |
| **[VERSIONING.md](./docs/VERSIONING.md)** | Versioning and release policy |

---

## Contributing

Life Index is still personally driven, but the idea has already outgrown "a father writing logs for his daughter." If you are a creator, therapist, family historian, agent-native engineer, or quantified-self practitioner, the [four promises](#four-promises) may describe exactly the kind of tool you have been missing.

Ways to help:

**Module development** - the highest-impact contribution. Each [advanced module](#the-higher-floors-being-built) is a self-contained feature: CLI tool composition plus Agent orchestration logic, suitable for an independent developer to own.

**Open an Issue** - share your use case, report a bug, or propose a module direction.

**Translation** - help improve multilingual versions so more people can understand the project in their own language.

**Share your story** - if Life Index helped you preserve a moment that mattered, we would like to hear it.

---

## License

[Apache License 2.0](./LICENSE) - your life data belongs to you. So does this code.

---

> *"I want our family to stay forever in the days when Tuan Tuan was two - and I also want her to grow up and see a wider, more beautiful world.*
> *Anyway, little one, Dad misses you. Tuan Tuan, this one is for you."*
>
> *- from the first Life Index entry, March 4, 2026, Lagos*
> *This is not a record of her growth. It is a record of my love for her.*
