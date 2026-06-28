<h1 align="center">Life Index | 人生索引</h1>

<p align="center"><em>"Your life, indexed."</em></p>

<p align="center"><strong>An Agent-Native personal life archive ——</strong></p>

<p align="center"><strong>Not a knowledge base, not Agent memory. The digital legacy you leave to the future.</strong></p>

<div align="center">

<p align="center"><strong>English</strong> | <a href="./README.md">简体中文</a></p>

</div>

<p align="center">
  <a href="https://github.com/DrDexter6000/life-index/actions/workflows/tests.yml"><img src="https://img.shields.io/github/actions/workflow/status/DrDexter6000/life-index/tests.yml?branch=main&label=CI" alt="CI"></a>
  <img src="https://img.shields.io/badge/Retrieval-Keyword_+_Index_Tree_+_Entity_Graph-78206E" alt="Retrieval: Keyword + Index Tree + Entity Graph, no Vector RAG">
  <img src="https://img.shields.io/badge/python-≥3.11-3776AB?logo=python&logoColor=white" alt="Python ≥3.11">
  <a href="./LICENSE"><img src="https://img.shields.io/badge/license-Apache_2.0-blue" alt="License"></a>
</p>

<p align="center">
  <img src="./assets/life_index_readme.png" alt="Your Digital Legacy" width="600">
</p>

<p align="center">
  <a href="#why-life-index-exists">Core Capabilities</a>  •
  <a href="#four-promises">Our USP</a>  •
  <a href="#quick-start">Quick Start</a>  •
  <a href="#vision--architecture">Vision & Architecture</a>  •
  <a href="#design-decisions">Design Decisions</a>
</p>

---

## TL;DR

Life Index is an **agent-native, local-first** life archive — it stores every fragment of your life as plain Markdown and keeps it searchable, traceable, and never silently overwritten.

- **Write**: life fragments → Markdown + YAML, readable in any text editor, good for 50 years
- **Search**: Keyword + **Index Tree** (your life-directory navigation) + Entity Graph — **offline · zero-token · auditable · rebuildable**
- **Atoms**: 20+ carefully crafted CLI atomic tools, built ground-up on agent-native principles
- **Orchestration (the script lives in LI, the thinking lives in the Agent)**: Life Index ships a deterministic agent playbook (`SKILL.md` + smart-search scaffold) that tells your host Agent how to sequence — classify the query first, then suggest which workflow and which tools/facets to use. The actual semantic understanding and LLM reasoning belong to your host Agent (**Hermes** / OpenClaw / Claude / Codex). LI hands over the *how-to*; it does not do the thinking.
- **Trade-offs**: **local-first, no cloud storage**; **no bundled LLM, no embedding model, no in-tool vector RAG** by default — [why?](#design-decisions)
- **Position**: not a knowledge base, not Agent memory — the digital legacy you leave to the future

```bash
# Write a life (zero LLM, zero network)
life-index write --data '{"title":"Missing the Diaper Hero","content":"...","date":"2026-03-04T19:43:02"}'

# Search a life (Keyword + Index Tree + Entity Graph, offline, reproducible)
life-index search --query "Tuan Tuan"
# -> hits every relevant entry you ever wrote, with a trace_id and an auditable ranking
```

---

## Why Life Index Exists

Everyone is building memory for AI.

Your knowledge base manages what you have learned. Your Agent remembers what you just said. The whole industry is racing to make information more efficient and AI more capable.

**But who is paying attention to what you, as a human being, are quietly losing?**

> Your Notion stores knowledge — but it did not record the moment your heart skipped the first time you saw her.
> Your Agent remembers last week's decision — until a scoring rule decides it is "no longer relevant."
> That decision that changed your life ten years ago — do you still remember how it felt?

| | **Life Index** | **Knowledge Base** (Notion/Obsidian) | **Agent Memory** (Mem0/Zep) |
|:---|:---|:---|:---|
| **Core question** | "How did I feel back then?" | "What do I know?" | "What did I just say?" |
| **How it evolves** | **Append-only — every mental growth ring remains** | Refactored — old versions get overwritten | Scored and evicted — memories disappear |
| **Shelf life** | **Permanent — as legacy** | Long-term, but reorganized with your thinking | Short-lived, useful until it is not |
| **Ownership** | **Entirely yours** — local Markdown never expires | Mostly yours, but the format follows the tool | Provider-owned, cleanable at any time |
| **Cost of failure** | None — plain text remains readable | Export pain and format lock-in | Gone instantly, often without warning |

Life Index does one thing: **it keeps the fragments of your life searchable, traceable, and never silently overwritten.**

### A Father's Starting Point

This is the first repository I ever created on GitHub.

I am an ordinary father with no programming background — even this README was written with AI's help. I did not create Life Index to show off technical skill. I created it because I urgently needed **a dedicated place for the fragments of a life**.

For me, Life Index becomes real late at night: I stumble onto photos of my daughter when she was two, and that complicated feeling — happiness braided with loss — can finally be pinned down. Not just her smile, but my heartbeat as her father, the light on the balcony, and the sharp awareness that *this moment is already passing*. These records may one day become a **digital family letter**: perhaps when I am gone, she will open these files like an old book and find not only her father's love, but also the mistakes, lessons, and hard-won judgment of a life lived before her.

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

I want our family to stay forever in the days when Tuan Tuan was two — and I also want her to grow up and see a wider, more beautiful world.
Anyway, little one, Dad misses you.

![Tuan Tuan at age two](attachments/2026/03/2yo_Tuantuan.jpg)
```

<p align="center">
  <img src="./assets/2yo_Tuantuan.jpg" alt="Tuan Tuan at age two" width="400">
  <br>
  <em>— the little one who stole my heart</em>
</p>

</details>

---

## Four Promises

Life Index CLI Core does two things: **write a life (`write`) and search a life (`search`)**. Around that center, we make four promises — **written into the [CHARTER](./CHARTER.md), externally auditable, and only ever strengthened, never weakened**. If Life Index ever breaks one of them, quote this section back at us.

| | Promise | In one line |
|:---:|:---|:---|
| **P1** | **Growth Rings** | Every entry stays. Edits are retrospective revisions, never silent overwrites. |
| **P2** | **Complete Without LLM · Stronger With** | CLI Core does write + search without calling any LLM; an Agent's orchestration only makes it stronger. |
| **P3** | **Plain Markdown Forever** | If Life Index disappears tomorrow, your data still opens in any text editor. |
| **P4** | **Engineered for 50 Years** | It began as a father's letter to his daughter, engineered to outlive its author. |

> Each promise has a matching **falsification condition** (what counts as a breach) locked in the CHARTER. Open the panel below for the engineering form and the runnable test anchor of each.

<details>
<summary>Open · Constraint carriers and falsification conditions</summary>

<br>

**P1 · Growth Rings**

> Agent memory evicts by score; knowledge bases overwrite as thinking evolves. Life Index chooses a third path: **append, do not replace**. A belief you held five years ago — even one you later outgrew — is still a ring of yours.
> · **Constraint**: [CHARTER](./CHARTER.md) §1.2 plain-text permanence
> · **Falsification**: any `edit_journal` operation that loses prior content is a breach.

**P2 · Complete Without LLM · Stronger With**

> The industry habit is to publish a polished **end-to-end + LLM-synthesized** score, making it look like the retrieval system's own ability. Life Index does the opposite — **CLI Core proves its own floor; LLM enhancement is explicit opt-in**: search results come from deterministic code (auditable, reproducible, zero-token, fully offline); switching between Claude / GPT / DeepSeek / a local Llama changes nothing on the CLI Core side. **The LLM is frosting, not foundation; the foundation already stands.**
> · **Constraint**: [CHARTER](./CHARTER.md) §1.5 + §1.9 + §1.10 + §1.11 (§1.11 is in the §5.3 non-weakenable list)
> · **Current measurement**: 20+ CLI commands · 2,400+ unit tests · keyword-only Recall@5 = **0.7857** (cycle2 fixture · 56 queries; ≈0.79, a marginal miss vs the 0.79 target; C2 paraphrase remains a known gap) · full integrity audit PASS on 2026-05-25
> · **Falsification**: (a) a default L2 retrieval path adds precision-threshold truncation that drops token-match candidates; (b) any default-path module implicitly bundles an LLM / initializes a provider client / reads an API key; (c) the default path introduces an embedding model or vector-index build — any one is a breach.

**P3 · Plain Markdown Forever**

> The SQLite indexes and derived caches under `.index/` are all rebuildable. Your journals, attachments, and frontmatter are readable in any text editor, with no Life Index present. **Software may vanish; the data does not.**
> · **Constraint**: [CHARTER](./CHARTER.md) §1.1 + §1.2 + §1.6 (all in the §5.3 non-weakenable list)
> · **Falsification**: user-originated content is stored only in a non-Markdown format, or `.index/` cannot be fully rebuilt from `Journals/`.

**P4 · Engineered for 50 Years**

> CHARTER §5.3's non-weakenable list binds every future maintainer — they may only make the promises **stricter**, never looser.
> · **Constraint**: [CHARTER](./CHARTER.md) §5.3 unmodifiable clauses
> · **Falsification**: §5.3 itself, or any of §1.1, §1.2, §1.6, §1.11, is weakened.

</details>

> *Even if Life Index remains a lonely repository with one developer, one user, and zero stars forever, I will keep working on it. Because that user is me, and what it preserves is what I want to leave for my daughter.*
>
> *Tuan Tuan, this one is for you.*

### What We Deliberately Don't Do

To keep the four promises above, Life Index deliberately gives up a batch of "industry defaults":

**✕ Cloud sync · ✕ Rich-text editing · ✕ Real-time collaboration · ✕ Bundled LLM / embedding model by default · ✕ In-tool Vector RAG · ✕ AI that thinks for you**

Two of these matter most to the core philosophy:

**No cloud storage — because program and data are fully separated.** Your life data is a plain-Markdown asset that lives **independently of the software**, in your own local directory, on no one's servers. The Life Index program can be upgraded or vanish someday; your data stays put and stays readable. In other words: **the program is rented; the data is yours.** This is the engineering form of data sovereignty (see [Design Decisions · Data Sovereignty](#design-decisions)).

**No in-tool Vector RAG — because it measured as zero gain.** In 2026 nearly every retrieval system reaches for vectors by default. We built it, then deliberately removed it — for the personal-journal use case it is negative-ROI over-engineering.

| 108-query golden set (2026-06-28) | MRR@5 | Recall@5 | Precision@5 | nDCG@5 |
| --- | --- | --- | --- | --- |
| Keyword + Entity Graph | 0.6259 | 0.9231 | 0.5351 | 0.6602 |
| Keyword + `--semantic` | 0.6259 | 0.9231 | 0.5351 | 0.6602 |

**Identical to four decimals; not one of the 5 failing queries was recovered by semantics.** The full four-layer argument (architecture / retrieval / measurement / engineering) is in → [Design Decisions · Why no in-tool vector RAG](#design-decisions).

---

## Quick Start

CLI, natural language, and GUI are not three "editions" — they are three **interaction modes** for different people:

| 🖥️ **CLI** | 🗣️ **Natural language** | 🎨 **GUI** |
|:---:|:---:|:---:|
| *Developers · hackers · integrators* | *Users with an Agent platform* | *Everyone* |
| Drive the terminal directly, control every parameter. | Tell your Agent "record how I felt today" and let it call the CLI. **Recommended today.** | Look, click, remember. *(Separate repo, in development.)* |

**No API key, no embedding model, no cloud service** — CLI Core runs offline by default.

<details>
<summary>🗣️ End users: hand the project to your Agent to install (click to expand)</summary>

<br>

Paste the following to your Agent (**Hermes**, OpenClaw, Claude Desktop, Codex, etc.):

```text
Please read and strictly follow `AGENT_ONBOARDING.md` in this repository to complete Life Index installation, initialization, and verification:
https://github.com/DrDexter6000/life-index/blob/main/AGENT_ONBOARDING.md

Requirements:
1. Read `AGENT_ONBOARDING.md` first; if there is no Life Index command or checkout locally yet, obtain a runnable `bootstrap` via the document's minimal install snippet
2. Run `life-index bootstrap --json` or, inside a checkout, `python -m tools bootstrap --json`
3. Before recreating `.venv`, running `health`, adopting a checkout, deleting any directory, or classifying fresh install / upgrade / repair, read the bootstrap JSON first
4. If a local checkout is discovered, assess it with bootstrap's `--checkout-path` / `--checkout-origin` rules; adopt it only when `safe_to_adopt: true`
5. Handle `needs_human` first, then follow `execution_policy` and `safe_next_steps` in order; do not treat "clean slate" / "fresh install" / "start from scratch" as permission to delete existing journal data
6. All Python/CLI commands must use the virtual environment path specified by the document
7. If any step fails, stop immediately and report the exact error
8. Report back using the format required by the document
```

</details>

<details>
<summary>🖥️ Developers: clone + venv install (click to expand)</summary>

<br>

```bash
git clone https://github.com/DrDexter6000/life-index.git
cd life-index

# Create virtual environment + editable install (no LLM, no embedding model by default)
python3 -m venv .venv
.venv/bin/pip install -e .    # Windows: .venv\Scripts\pip install -e .
```

</details>

<details>
<summary>⌨️ Developer commands (click to expand)</summary>

<br>

| Action | Command |
|:---|:---|
| Activate virtual environment | `source .venv/bin/activate` (Windows: `.venv\Scripts\activate`) |
| Unified CLI | `life-index --help` |
| Version check | `life-index --version` |
| Health check | `life-index health` |
| Write journal | `life-index write --data '{...}'` |
| Search journals (Keyword + Entity Graph) | `life-index search --query "keyword"` |
| Host navigation (index-tree) | `life-index index-tree discover` / `navigate` |
| Search + time/topic pre-filter | `life-index search --query "keyword" --year 2026 --topic work` |
| Legacy semantic switch (no-op) | `life-index search --query "keyword" --semantic --semantic-policy fallback` |
| Generate index tree (month/year/root) | `life-index generate-index --month 2026-03` |
| Full rebuild index tree | `life-index generate-index --rebuild` |
| Backup data | `life-index backup --dest <backup-dir>` |
| Schema migration (preview / apply) | `life-index migrate --dry-run` / `--apply` |
| Entity quality audit | `life-index entity --audit` |
| On-this-day review | `life-index on-this-day --date 2026-05-19 --years-back 3 --json` |
| Run unit tests | `python -m pytest tests/unit/ -v` |

> **Tip**: activate the virtual environment once; after that, commands do not need the `.venv/bin/` prefix.
> **Safe debugging**: for manual testing/acceptance, set a temporary `LIFE_INDEX_DATA_DIR` and use copied sandbox data instead of operating on the real user directory.

</details>

<details>
<summary>🔍 Troubleshooting (click to expand)</summary>

<br>

**Skill trigger is unreliable** → use `"/life-index" + intent keyword` (e.g. `/life-index write journal: ...`)

**Tool error (`ModuleNotFoundError`)** → make sure you use `.venv/bin/python` (not system Python), from the skill root.

**Fresh install shows degraded health** → for a brand-new / empty-data install, a pre-init `degraded` is expected, not a failure; if `safe_next_steps` includes index or skill-artifact commands, run them in order and re-run health.

**A legacy integration still passes `--semantic*`** → it is a compatibility no-op; it will not install a model, build a vector index, or change results. Core retrieval is Keyword + Index Tree + Entity Graph; for "search by meaning," let your host Agent rewrite the query and run multi-pass retrieval.

**Virtual environment corrupted (after a Python upgrade / system migration)** → first confirm `bootstrap --json` has identified the current directory as the intended install target, then recreate the code environment without touching user data.

**Upgrading to a new version** → run the onboarding bootstrap gate first, then follow the returned `execution_policy` and `safe_next_steps`.

</details>

---

## Vision & Architecture

### Vision: From Life Fragments to a Digital Persona

Life Index begins as a father's journal, but it does not end there. As you keep recording — one year, five years, twenty years — those fragments grow into **rings of mind**:

```
One entry today → one year of emotional trajectory → ten years of life narrative · complete growth rings → a digital persona unlike anyone else's
```

Decades from now, once the records are dense enough, they may help answer one question:

> **"If Dad were still here, how would he see this?"**

That is not science fiction — it is the long horizon of Life Index. And the first step, a reliable life archive that belongs to you, **already exists.**

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
> If enough fragments are gathered, perhaps one day
> that core, engraved with the memory of a whole life,
> will hatch a silicon soul and keep walking toward the far edge of time.

</details>

### Four Layers: The Deeper You Go, the Longer It Lasts

```
┌──────────────────────────────────────┐
│          Interface Layer             │
│    Natural language (Agent)   GUI    │   <- how you interact
│    1-3 year lifespan, UX-driven      │
└──────────┬───────────────┬───────────┘
           │               │
           │    ┌──────────▼──────────┐
           │    │ Intelligence Layer  │   <- only when "thinking" is needed (your host Agent)
           │    │ Recall orchestration│
           │    │ LLM reasoning       │
           │    └──────────┬──────────┘
           │               │
           ▼               ▼
┌──────────────────────────────────────┐
│           CLI Core (SSOT)            │
│    Write · Search · Index · Entity   │   <- single authority for operations
│    Deterministic, direct, no Agent   │
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

**One rule: don't ask an Agent what deterministic code can settle; ask an Agent only when thought is required.** Deterministic operations (writing, searching by tag/keyword/entity, browsing the timeline) call CLI Core directly; operations that need "thinking" (open-ended recall orchestration, memoir synthesis, digital persona) go through the Intelligence Layer — and that layer is **your host Agent**, not intelligence built into Life Index.

### Two Things × Two Layers

Life Index fits into a 2×2 matrix — the vertical axis is the **two things** it does (write + search), the horizontal axis is the **two layers** that do them (deterministic CLI Core + your Agent's enhancement):

| | **L2 · CLI Core**<br>Deterministic · offline · zero LLM · zero token | **L3 · Agentic Enhancement**<br>Your Agent · your LLM · your API key |
|:---|:---|:---|
| **✍️ write**<br>record life | Markdown + YAML write<br>Attachment management / incremental index<br>Entity Graph maintenance | Frontmatter drafting<br>Sentiment / entity / tag suggestions<br>Weather / location enrichment<br>Editing suggestions |
| **🔍 search**<br>retrieve life | FTS5 keyword search<br>Index Tree host navigation<br>Entity Graph deterministic expansion<br>`--semantic*` compatibility no-op | Query rewrite / intent detection<br>Multi-pass retrieval orchestration<br>Evidence filtering / summary / explanation<br>Citation assembly / report writing |

**How to read it**: the left column is the deterministic capability Life Index provides ([CHARTER](./CHARTER.md) §1.5 + §1.11); the right column is the language and reasoning work your Agent does with its own LLM. Life Index does not bundle an embedding model or maintain an in-tool vector RAG; "search by meaning" happens in the right column.

> *The intelligence is yours; the memory is yours; Life Index is the protocol layer where they meet.*

### Roadmap

**CLI Core's current stable line (1.3.4)** is in daily use — not a prototype, not a demo, but a system with 2,400+ unit tests, green CI, and real personal use. **The foundation is laid; the current main line is standing up the experience layer (GUI v1).**

<details>
<summary>🧱 The foundation already built (CLI Core 1.3.4, click to expand)</summary>

<br>

| Capability | Status | Notes |
|:---|:---:|:---|
| Journal write / edit | ✅ | Structured Markdown + YAML, with auto weather/sentiment/entity tagging |
| Layered life retrieval | ✅ | Keyword exact match + Entity Graph expansion; Agent optionally handles pre-search orchestration and post-search expression |
| Index Tree host navigation | ✅ | `ensure → discover → navigate` three-step navigation; browse your life directory by time / topic / tag facet |
| Smart-search orchestrator | ✅ | Emits an agent-ready deterministic scaffold; query rewrite and refinement done by the host agent, no LLM in the tool |
| Search quality evaluation (eval) | ✅ | Cycle 2 multi-signal fixture; full integrity audit PASS on 2026-05-25; recall-first quality gate |
| Entity Graph + quality audit + maintenance | ✅ | Alias resolution, relationship inference, duplicate/orphan detection + Agent-interview repair |
| One-page install / upgrade (bootstrap) | ✅ | `bootstrap --json` emits a deterministic execution_policy + freshness check; reliably delivers SKILL into the host skill library |
| Data doctor | ✅ | `maintenance audit` is the single source for data-integrity detection; `verify` is the read-only check |
| Schema migration | ✅ | Chain migration framework, deterministic backfill + Agent semantic enrichment |
| Per-operation observability | ✅ | trace_id + step timings + status diagnostics on every operation |
| Backup / integrity verification | ✅ | Encrypted backup + data consistency checks |
| Cross-platform | ✅ | Windows / macOS / Linux, Python 3.11+ |

</details>

#### 🎨 In Construction: GUI v1 Experience Layer

CLI Core is the foundation; the GUI is the building you see. Life Index's GUI experience layer is developed in a separate public repository, [`life-index-gui`](https://github.com/DrDexter6000/life-index-gui) — turning **write (+ smart metadata)** and **search (+ smart-search)** into a graphical interface anyone can use without technical knowledge. Its design language is "**Soul Shrine · 灵魂神龛**," blending Monument Valley's meditative geometry with East Asian literati sensibility.

<p align="center">
  <img src="./assets/GUI_prototype.png" alt="GUI experience layer prototype" width="700">
  <br>
  <em>GUI experience layer prototype — The Core view</em>
</p>

<p align="center">
  <a href="https://raw.githack.com/DrDexter6000/life-index/main/assets/GUI_prototype.html"><strong>🔗 Open the interactive prototype in your browser</strong></a>
</p>

<details>
<summary>🔭 Future modules (click to expand)</summary>

<br>

On top of a solid CLI Core + GUI, more modules will grow — each a combination of **stable record format + deterministic retrieval + Entity Graph enrichment + host-Agent orchestration**:

| Module | Codename | Description |
|:---|:---|:---|
| EXIF photo timeline | **Light Rings** | Extract time/place/scene from photos; build a new user a 5-year visual ring of growth in a day |
| Social history import | **Retrograde** | Parse official platform export zips and bring 20 years of posts into Life Index |
| Childhood memory entry | **Time Traveler** | Those precious childhood fragments can be recorded now |
| Memoir generation | **Memoir Engine** | Weave fragmented journals into a coherent narrative; your life, as a book |
| Digital persona | **Digital Soul** | The ultimate capability after decades of records — "If Dad were still here..." |

</details>

<details>
<summary>🕰️ 50-year survivability (click to expand)</summary>

<br>

Fifty years spans at least three hardware generations, several operating-system eras, and possibly the rest of my own life. Asking a one-person project to survive that long is almost arrogant. But Life Index makes the promise precisely by admitting the arrogance:

- **The data layer** keeps the promise with Markdown + YAML — if the name "Life Index" disappears, your journals still open in any text editor.
- **The contract layer** keeps the promise with external constraints — [CHARTER §5.3](./CHARTER.md) locks data sovereignty, plain-text permanence, backward compatibility, and recall-first retrieval into a non-weakenable list.
- **The author layer** is the weakest part — I cannot pretend I will live 50 years, but as long as I write code, the charter's zeroth rule holds: the charter outranks the code, and outranks me.

**Fifty years does not mean "I promise to live that long." It means "today's me has placed constraints on future me."**

</details>

---

## Design Decisions

> A few of Life Index's key trade-offs — none of them technical debt, all **evidence-backed, architecturally consistent, deliberate choices**. The main line gives the conclusion; here is the "why."

<details>
<summary>🧭 Why no in-tool vector RAG (click to expand)</summary>

<br>

Many people's first question about Life Index: it's a personal retrieval system in 2026 — why is the default search still keyword, not vector semantics?

It is a deliberate choice, with four layers of reasoning, from architecture to measurement:

**① Architecture — intelligence belongs to the host Agent; the tool does deterministic primitives only.**
Life Index is agent-native: it gives the host Agent auditable, reproducible, zero-token, fully-offline deterministic primitives; "understanding meaning" should be done by an ever-stronger host Agent. Stuffing semantics inside the tool inserts a silently-fallible probabilistic layer between the Agent and the data — and the Agent is already good at this.

**② Retrieval — default keyword-only honest floor; vectors stay out of the default path.**
The retrieval layer's promise to you is "don't miss any fragment of your life" ([CHARTER §1.11](./CHARTER.md)), which requires the default to be **recall-first**: faithfully return every token-match candidate, without relevance-threshold truncation at the source. Vector retrieval is inherently noisy and structurally tensions with recall-first.

**③ Measurement — on our own golden set, vector recall is zero gain.**
On 2026-06-28, comparing semantics on vs off across a 108-query golden set:

| 108-query golden set (2026-06-28) | MRR@5 | Recall@5 | Precision@5 | nDCG@5 |
| --- | --- | --- | --- | --- |
| Keyword + Entity Graph | 0.6259 | 0.9231 | 0.5351 | 0.6602 |
| Keyword + `--semantic` | 0.6259 | 0.9231 | 0.5351 | 0.6602 |

**Identical to four decimals; not one of the 5 failing queries was recovered by semantics** — it added no extra hits, only low-relevance noise.

**④ Engineering — the default install is lighter, faster, more offline.**
Enabling semantic retrieval needs a ~**1.3 GB** ML stack (torch + CUDA) and drags first-time install to ~**16 minutes**. We split it into an opt-in extra; the default install is instant and fully offline.

> **This is not anti-RAG.** What we precisely did: pulled the heavy model stack out of the default install, retired the in-tool LLM/RAG orchestration path, and locked the default search shape to keyword-only (written into [CHARTER §1.11 / §3.2 amendment](./CHARTER.md), in the §5.3 non-weakenable list). The `--semantic*` flags remain as compatibility no-ops — old calls don't error, but nothing is downloaded, indexed, or changed.
>
> *A clear shift in retrieval engineering in recent years: hand "expand the query by meaning" to the LLM (done by the host Agent), and "structured expansion" to the knowledge graph. Life Index's Entity Graph + Agent orchestration land exactly on that path. Give meaning to the Agent, relations to the graph — faster, leaner, and more accurate.*

</details>

<details>
<summary>🤖 Agent-Native, not Agent-First (click to expand)</summary>

<br>

> Agent-First means "we consider what Agents need." Agent-Native means "the system was born in the language Agents speak."

Life Index's CLI is not a human command-line tool with AI bolted on — its structured signal system, confirmation workflows, and enum-style error codes are an Agent's native tongue from the first line. An Agent does not parse vague natural-language errors; it receives enum values and deterministic recovery paths.

But Agent-Native does not mean Agent-only: we give Agents what they need most — **precise machine interfaces** — and humans what they need most — **natural-language conversation and a visual experience**.

</details>

<details>
<summary>📐 Three design lines (click to expand)</summary>

<br>

```
Prefer simple features over complex systems.
Prefer manual maintenance over automation traps.
Prefer reliability over performance.
```

Vector-threshold tuning, model installs, index caches, noise gating — all easily become the "automation trap" of the second line. Keyword + Index Tree + Entity Graph is simple, auditable, and faster and more deterministic than hybrid.

</details>

<details>
<summary>🔒 Data Sovereignty: Your Soul Does Not Belong in the Mikoshi (click to expand)</summary>

<br>

Life Index is local-first and keeps program and data fully separated. User journals live under your own user directory:

```
~/Documents/Life-Index/
├── INDEX.md                     # Root index — your life map
├── Journals/                    # Journals by year/month
│   └── 2026/03/...
├── attachments/                 # Photos, videos, voice notes
├── by-topic/                    # Topic index, orthogonal to the time tree
└── .index/                      # Machine retrieval layer (FTS5 + metadata cache, not human-readable, rebuildable)
```

`Journals/` is the source of truth; delete `.index/`, run `life-index index --rebuild`, and all retrieval rebuilds. **The data does not depend on any Life Index runtime** — program and data are fully decoupled, which is exactly what makes "no cloud storage" possible.

> **Life Index strongly recommends local backups** — protect your **Relic**, and do not voluntarily feed your **Engram** into a corporation's **Mikoshi**.

</details>

---

## Documentation

| Document | When to read |
|:---|:---|
| **[CHARTER.md](./CHARTER.md)** | **Project constitution — invariants and non-weakenable promises (the legal layer of the four promises)** |
| **[SKILL.md](./SKILL.md)** | Agent skill definition, tool interfaces, workflows |
| **[API.md](./docs/API.md)** | Tool parameters and response contracts |
| **[ARCHITECTURE.md](./docs/ARCHITECTURE.md)** | Architecture and key decisions (ADR) |
| **[ENTITY_GRAPH.md](./docs/ENTITY_GRAPH.md)** | Entity Graph operating contract |
| **[VERSIONING.md](./docs/VERSIONING.md)** | Versioning and release policy |

## Contributing

Life Index is still personally driven, but the idea has already outgrown "a father writing logs for his daughter." If you are a creator, therapist, family historian, agent-native engineer, or quantified-self practitioner, the [four promises](#four-promises) may describe exactly the tool you have been missing.

- **Module development** — the highest-impact contribution. Each [future module](#roadmap) is a self-contained unit, following [CHARTER §1.9](./CHARTER.md) agent-native principles with no LLM held by default.
- **Open an Issue** — share your use case, report a bug, or propose a module direction.
- **Translation / share your story** — help more people understand the project in their own language; if Life Index helped you preserve a moment that mattered, we would like to hear it.

## License

[Apache License 2.0](./LICENSE) — your life data belongs to you, and so does this code.

---

> *"I want our family to stay forever in the days when Tuan Tuan was two — and I also want her to grow up and see a wider, more beautiful world.*
> *Anyway, little one, Dad misses you. Tuan Tuan, this one is for you."*
>
> *— from the first Life Index entry, March 4, 2026*
> *This is not a record of her growth. It is a record of my love for her.*
