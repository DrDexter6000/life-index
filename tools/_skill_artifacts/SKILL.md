---
name: life-index
description: "Personal life journaling system with deterministic keyword/entity retrieval. Use when user says 'record journal', 'log this', 'search logs', 'generate summary', '记日志', '写日记', '搜索记录', '生成摘要'. Features: auto weather, Entity Graph search, attachment handling."
user-invocable: true
disable-model-invocation: false
metadata: {"clawdbot":{"emoji":"📖","requires":{"bins":["python"]}}}
triggers:
  - "/life-index"
  - "记日志"
  - "写日记"
  - "记录一下"
  - "write journal"
  - "daily log"
  - "log this"
  - "record this"
---

# Life Index Agent Skill

> **Authority Chain**: `bootstrap-manifest.json` 是 freshness / authority anchor。涉及安装、升级、repair、环境判断时，必须先刷新 `bootstrap-manifest.json`，再按其 `required_authority_docs` 刷新对应文档，然后才允许 sync checkout 或 route 判断。
> **工具参数与错误码**: 详见 [API.md](docs/API.md)
> **平台边界**: `CHARTER.md §1.10` 独占 C1–C7 闭合 Core 准入域；`docs/ARCHITECTURE.md` 的 `PLATFORM-SSOT:PUBLIC-COMMAND-CLASSIFICATION` 命名块独占 31 条 public route 的精确分类。Distribution/Host Operations 即使与 Core 同包分发也属于 non-Core；`weather` 是 #166 跟踪的 Legacy External Adapter。本 Skill 不复制域目录或命令分类表。

<!-- PLATFORM-SSOT:HOST-AGENT-ROUTING:START -->
## Host Agent / Core / Gateway routing boundary

- Host Agent + Skill own planning, multi-hop reasoning, interpretation, and synthesis. They also own orchestration.
- Core calls remain deterministic; Core does not plan, reason, orchestrate, interpret, or synthesize.
- Gateway is an optional future typed 1:1 projection under #164; it is not yet implemented, is not a second semantic API, and owns no intelligence. If introduced, it is only a contract-equivalent transport. Gateway is never required for the core route.
<!-- PLATFORM-SSOT:HOST-AGENT-ROUTING:END -->

---

## Triggers & When to Use

| 意图 | 触发词 | 工具 |
|:---:|:---|:---|
| 记录日志 | "记日志"、"记录一下"、"写日记"、"记下来"、"log this"、"record this"、"write journal" | `write_journal` |
| 搜索日志 | "查找日志"、"搜索记录"、"找一下关于...的日记"、"search journal"、"find log" | `search_journals` |
| 智能搜索 | "帮我回忆..."、"我和女儿之间有哪些珍贵的回忆？"、"smart search" | `smart_search`（确定性 scaffold；合成与判断由宿主 agent 完成） |
| 历史同日 | "去年今天在做什么"、"历史上的今天"、"on-this-day"、"历史同日" | `on_this_day` |
| 编辑日志 | "修改日志"、"补充日记"、"更新记录"、"edit journal"、"update log" | `edit_journal` |
| 实体图谱 | "列出实体"、"解析人物关系"、"entity graph"、"谁是谁的..." | `entity` |
| 生成摘要 | "生成摘要"、"月度总结"、"年度总结"、"generate summary" | `life-index abstract` / `tools.generate_index` |
| 修订历史 | "查看修订历史"、"编辑记录" | `edit_journal` |
| 定时报告 | 日报/周报/月报/年报 | Life Index 无内置 scheduler；由宿主平台定时能力编排 CLI |

---

## Quick CLI Reference

**⚠️ 所有命令须在技能根目录（本文件所在目录）下执行。所有 Python/CLI 命令必须通过虚拟环境调用。**

**跨平台 venv 路径规则**：
- **Linux/macOS/WSL**: `.venv/bin/life-index` 或 `.venv/bin/python`
- **Windows**: `.venv\Scripts\life-index` 或 `.venv\Scripts\python`（首次排障/验证时优先显式使用此路径）

```bash
# 统一 CLI（推荐）
.venv/bin/life-index write --data '{"title":"...","content":"...","date":"2026-03-14","topic":["work"],"abstract":"...","mood":[],"people":[],"project":"","tags":[],"links":[]}'
.venv/bin/life-index search --query "关键词" --topic work --level 3
.venv/bin/life-index search --query "学习"  # 关键词 + Entity Graph；--semantic* 是兼容 no-op
.venv/bin/life-index smart-search --query "我和女儿之间有哪些珍贵的回忆？"  # 确定性检索 scaffold（默认不调用 LLM）
.venv/bin/life-index smart-search --query "..." --explain  # 展示确定性执行详情
.venv/bin/life-index smart-search --query "..." --include-evidence  # 含 evidence pack + 检索诊断
.venv/bin/life-index on-this-day --date 2026-05-19 --years-back 3       # 历史同日回顾
.venv/bin/life-index edit --journal "Journals/2026/03/life-index_2026-03-14_001.md" --set-location "Beijing"
.venv/bin/life-index entity audit --json
.venv/bin/life-index entity build --from-journals --preview --json
.venv/bin/life-index entity maintain --normalize --preview --json
.venv/bin/life-index abstract --month 2026-03
.venv/bin/life-index weather --location "Lagos,Nigeria"
.venv/bin/life-index index           # 增量更新
.venv/bin/life-index index --rebuild # 全量重建
.venv/bin/life-index sync-skill      # 刷新 host agent 的 SKILL.md + references/
.venv/bin/life-index health          # 安装健康检查

# Windows 用户主动写入时可用文件参数；onboarding 不应创建首写验证日志
.venv\Scripts\life-index write --data @journal-entry.json

# 开发者模式
.venv/bin/python -m tools.write_journal --data '{...}'
.venv/bin/python -m tools.search_journals --query "关键词"
.venv/bin/python -m tools.edit_journal --journal "..."
.venv/bin/python -m tools.generate_index --month 2026-03
.venv/bin/python -m tools.query_weather --location "Lagos,Nigeria"
.venv/bin/python -m tools.build_index
```
**安装 / 首次验证 / 故障恢复指针**：
- 首次安装、upgrade、repair、fresh install 判断 → 读 `AGENT_ONBOARDING.md`，运行 `bootstrap --json`，按 `execution_policy` / `needs_human` / `safe_next_steps` 执行
- `ModuleNotFoundError`、venv 损坏、`health` 异常、Windows 首次写入转义问题 → 先回到 `bootstrap --json` 输出，不自行扩写 repair 决策树
- 写入成功后的状态字段解释（`needs_confirmation` / `index_status` / `side_effects_status` / 附件处理计数）→ 读 `docs/API.md` 中 `write_journal` 返回语义
**会话 freshness / 运维纪律（升级摩擦 UF-1 + Ops）**：
- 升级 Life Index CLI 时，优先运行 `life-index upgrade --plan --json`，读取 `actions[]` 和 `recommended_next_step`。package install 走 PyPI 非 yanked 版本升级；editable/source install 走安全 git fast-forward 后 `python -m pip install -e <repo>`，再校验版本、同步 SKILL、跑 health。只有当计划中的动作 `safe_to_run=true` 且 `requires_human=false` 时，才可运行 `life-index upgrade --apply --json`；dirty checkout、ahead/diverged commits、remote probe 不可达、未知安装方式、yanked 目标版本等情况必须停下来转述给用户。`upgrade` 不替代开发者发布流程，也不操作 GUI 仓。
- 每次新会话首次使用 Life Index 前，运行 `life-index health --json` 并读取 `data.upgrade_freshness`；若 `freshness == "update_available"` 或 `git_freshness == "behind"`，先执行 `suggested_refresh_step`，再运行 `life-index sync-skill --install`；执行 health 建议命令前先看同一对象的 `side_effect` / `side_effect_note`，`write` 需用户确认或确认只是派生物刷新
- 你是 Life Index 的使用者/运维者，不是开发者：不要向产品仓库克隆 commit/push；仓库克隆保持零改动，升级前 `git status --porcelain` 必须为空，脏了先 `git checkout -- .` 恢复；friction/笔记写到 `<data>/frictions/`，永不写进仓库克隆
- `sync-skill --install` 的目标槽位始终是 `<host-home>/skills/life-index/`；若传入 `<host-home>/skills` parent，会自动归一化到 canonical slot，并可清理已知 1.4.2 parent-slot 坏状态；它也会自动收敛本管理树的 `skills/life-index/life-index` 嵌套重复；若返回 `HOST_SKILL_DIR_AMBIGUOUS`，说明存在多个无关或不安全候选，需让用户指定 `--host-skill-dir`
- 这是会话面提示，不替代 `bootstrap --json` 的安装/repair authority；旧版本无法自带新检测码时，以 `bootstrap-manifest.json` + `CHANGELOG.md` 为人工校验锚点；GUI 栈升级/运维见 GUI 仓 `docs/AGENT_UPDATE_PLAYBOOK.md`

<!-- GROUNDED_QUERY_SKILL_START -->
## Grounded Query Skill Playbook

Use the compact routing rules here for ordinary search. Load the Full grounded query playbook from `references/GROUNDED_QUERY_PLAYBOOK.md` only when the user asks for magazine-style analysis, time-scoped evidence, facet/count/enumeration answers, cross-facet questions, or explicit `GROUNDED` / `PARTIAL` / `UNGROUNDED` status.

Minimal deterministic path:

1. For count, enumerate, facet, cross-facet, and bounded time-range questions,
   use `index-tree ensure`, then the agent-facing `ensure` -> `discover` -> `navigate`
   path before journal reads.
2. Use `journal batch-get` for two or more returned paths; use `journal get`
   only for one path.
3. Use `aggregate` for counts/buckets and `trajectory` for typed observation
   series.
4. Use `search` or `smart-search --include-evidence` only for open recall or
   keyword/entity-weighted discovery, then read bounded returned paths.
5. Do not use `index-tree nodes`, `index-tree lens`, or `index-tree shadow`
   for normal host-agent retrieval/navigation. They are debug-only legacy
   diagnostics retained for compatibility.
6. Do not use `recall`, broad grep, or full-directory reads for new playbooks.

<!-- GROUNDED_QUERY_SKILL_END -->

## Project Structure

```
life-index/                         # 技能根目录
├── SKILL.md                       # [本文件] 技能定义
├── tools/                         # 可执行工具目录
│   ├── write_journal/             # 写入日志（天气查询、附件处理、索引更新）
│   ├── search_journals/           # 搜索日志（L1/L2/L3 + Entity Graph）
│   ├── smart_search/              # 确定性智能检索 scaffold；宿主 agent 负责合成
│   ├── edit_journal/              # 编辑日志（修改元数据、追加内容）
│   ├── entity/                    # 实体图谱（build/audit/maintain + review）
│   ├── generate_index/            # 生成索引树（monthly/yearly/root）
│   ├── build_index/               # 构建索引（FTS5 + metadata cache）
│   ├── query_weather/             # 查询天气
│   ├── backup/                    # 备份日志数据
│   ├── verify/                    # 数据完整性校验
│   ├── timeline/                  # 时序摘要流
│   ├── on_this_day/               # 历史同日回顾
│   ├── migrate/                   # Schema 链式迁移
│   ├── eval/                      # 搜索质量评估
│   ├── dev/                       # 开发/验收辅助工具
│   └── lib/                       # 共享库（SSOT）
├── docs/                          # API.md, ARCHITECTURE.md
└── references/                    # WEATHER_FLOW.md, SCHEDULE.md
```

**关键约定**：
- **虚拟环境**: 所有命令通过 `.venv/bin/`（Windows: `.venv\Scripts\`）前缀调用
- **用户数据目录**: `~/Documents/Life-Index/`（日志、附件、索引，与代码物理隔离）
- **跨平台路径**: 自动处理（Agent 传原始路径即可，工具自动转换 Windows↔WSL）
- **健康检查**: 遇到异常时先运行 `.venv/bin/life-index health` 诊断

---

## Core Constraints

### Content Preservation (MUST)

**100% 保留用户原始输入**：
- 不修改段落结构
- 不改变标题层级
- 不转换列表格式
- 不添加序号标记
- **⚠️ 不修改文件名（不在中英文间添加空格）**

```markdown
# ❌ 错误
用户输入："1、完成A 2、完成B"
Agent 改成："1. 完成A\n2. 完成B"

# ❌ 错误（文件名被修改）
用户附件："C:\Users\test\Opus审计报告.txt"
Agent 改成："C:\Users\test\Opus 审计报告.txt"  ← 添加了空格

# ✅ 正确
用户输入什么，content 和附件路径就原封不动传递什么
```

### Guardrails

- **永不删除文件**：编辑只修改内容
- **数据隔离**：数据在 `~/Documents/Life-Index/`，与代码分离
- **天气处理**：详见 [WEATHER_FLOW.md](references/WEATHER_FLOW.md)

```markdown
❌ 不要：假设用户知道内部概念（如"by-topic索引"）
✅ 必须：用人话说明（如"已归类到工作相关"）

❌ 不要：一次问多个问题
✅ 必须："地点和天气是否正确？"（单次确认）
```

### 天气与地点确认（强制）

**⚠️ 最常见错误点：看到 `success: true` 就直接结束对话**

调用 `write_journal` 后，检查返回的 `needs_confirmation` 字段：
```json
{
  "success": true,
  "journal_path": "...",
  "needs_confirmation": true,
  "confirmation_message": "地点：Lagos, Nigeria；天气：晴天 33°C"
}
```

```
❌ 错误：工具返回 success: true → Agent 直接结束："日志已保存"

✅ 正确：工具返回 needs_confirmation: true
→ Agent：日志已保存。地点：Lagos, Nigeria；天气：晴天 33°C。是否正确？
→ 等待用户回复
```

**⚠️ 用户纠正地点时的完整流程（Correction Flow）**：

当用户说"地点不对，应该是 XXX"时，**必须修改已保存的日志，不能重新调用 write_journal 创建新日志**。

```
❌ 错误：用户纠正地点 → Agent 重新调用 write_journal → 创建了第二篇日志

✅ 正确：用户纠正地点
→ Agent 查询新地点天气（query_weather --location "XXX"）
→ Agent 调用 write_journal confirm --journal "<journal_path>" --location "XXX" --weather "新天气"
  或调用 edit_journal --journal "<journal_path>" --set-location "XXX" --set-weather "新天气"
→ 日志原地更新，不产生新文件
```

---

## Required Metadata Fields

写入日志时，必须包含所有元数据字段（即使为空值）：

| 字段 | 类型 | 必填 | 说明 |
|------|------|:----:|------|
| title | string | ✅ | 日志标题 |
| content | string | ✅ | 日志正文（100%原样保留） |
| date | string | ✅ | ISO 8601 日期时间 |
| abstract | string | ✅ | ≤100字摘要（Agent生成） |
| topic | array | ✅ | 主题分类（见下方 Topic 表） |
| mood | array | ✅ | 心情标签，Agent语义提取1~3个（如["开心","专注"]） |
| tags | array | ✅ | 标签，Agent语义提取关键词（可多个） |
| location | string | ❌ | 地点；用户未指定时默认 "Chongqing, China"，写入后必须走地点/天气确认 |
| weather | string | ❌ | 天气，根据确认的地点自动查询 |
| people | array | ❌ | 相关人物，Agent语义提取，没有则留空 |
| project | string | ❌ | 关联项目，Agent语义提取，没有则留空 |
| links | array | ❌ | 相关链接 |
| attachments | array | ❌ | 附件（自动检测 content 中的本地文件路径；也可显式传递 `{"source_path":"...","description":"..."}` 对象） |
| entities | array | ❌ | 已匹配的 entity graph ID 列表 |

### 写入增强（已实现）

- 写入结果现在可包含：`entities`
- 编辑日志时会自动写入 co-located `.revisions/`

### Tool Schema（已实现）

- 每个 CLI 工具目录下均已提供 `schema.json`
- Agent Runtime 可读取 schema 发现参数/返回值契约
- 高频意图："列出工具"、"工具参数"、"schema"

### Attachment Media（已实现）

- Use `life-index attachment --info <path>` or `--export <path>` for the legacy
  JSON/base64 contract.
- Use `life-index attachment media <path> --variant thumbnail|preview|original`
  for raw bytes/file-export media delivery. `thumbnail` and `preview` are
  deterministic cached image derivatives; `original` streams source bytes and
  supports byte ranges.
- GUI/backend consumers must call this CLI contract and forward the returned
  media headers/bytes. They must not read the Life Index data directory
  directly.

### Entity Graph（已实现）

- 主入口：`life-index entity build ...` / `life-index entity profile --id ENTITY_ID --json` / `life-index entity audit --json` / `life-index entity maintain --normalize --preview --json` / `life-index entity maintain --add-relationship --id SOURCE_ID --target-id TARGET_ID --relation RELATION --preview --json` / `life-index entity maintain --delete --id ENTITY_ID --preview --json`
- Deterministic relationship traversal: `life-index index-tree navigate --entity-neighbors "Entity Name" --json`.
- 存储：`~/Documents/Life-Index/entity_graph.yaml`
- 操作规范：见 `docs/ENTITY_GRAPH.md`
- 作用：
  - 搜索时做 alias / relationship query expansion；回答“关于某实体”优先读 `Entities/<entity_id>.md`；缺失时运行 `life-index abstract --entities --json`，再按 `mentions` 下钻
  - 写入时标记 `new_entities_detected`
- 当前最小支持类型：`actor` / `place` / `project` / `event` / `artifact` / `concept`；人物、组织、宿主 agent 用 `actor` + `attributes.kind`；实体 ID 不透明且长期稳定，前缀没有语义

### Topic 分类（必填）

> **SSOT**：`tools/lib/topics.py` `VALID_TOPICS`（含验证逻辑，无效值静默丢弃）。下表为 Agent 便捷参考，若与代码不一致以代码为准。

| Topic | 含义 | 示例场景 |
|-------|------|----------|
| `work` | 工作/职业 | 项目进展、会议、职业发展 |
| `learn` | 学习/成长 | 读书笔记、课程学习、技能提升 |
| `health` | 健康/身体 | 运动、饮食、体检、医疗 |
| `relation` | 关系/社交 | 家人、朋友、社交活动 |
| `think` | 思考/反思 | 人生感悟、决策思考、复盘 |
| `create` | 创作/产出 | 文章、代码、设计作品 |
| `life` | 生活/日常 | 日常琐事、娱乐、购物 |

### Agent 职责

1. **必填字段**：title, content, date, abstract, topic, mood, tags — 必须有值
2. **语义提取**：从用户内容中主动提取 mood（1~3个）、tags（关键词）、people、project
3. **工具边界**：`write_journal enrich` 默认只做规则补全、规范化和地点/天气处理；不会替 Agent 从正文语义推断 mood/tags/people/project
4. **地点规则**：正文里明确写出的地点优先；只有正文和入参都未提供地点时，工具才使用默认地点；但无论地点来源为何，只要写入成功，Agent 都必须展示确认信息并等待用户确认或修正
5. **空值处理**：people, project, links 未提取到时传空值（如 `"people": []`）
6. **摘要生成**：从 content 提取关键信息，生成 ≤100 字的 abstract
7. **必须确认**：工具返回后检查 `needs_confirmation`；对所有成功写入结果，这都应视为必须执行的 follow-up

---

## Workflows

### 意图澄清（强制）

当用户请求可能被解读为多种操作时，**必须先澄清再调用工具**：

| 歧义类型 | 示例 | 正确处理 |
|:---|:---|:---|
| 写入 vs 编辑 | "把今天晚饭记进去，或者如果有了就补进去" | 先询问：是新建日志还是修改已有日志？ |
| 编辑目标不明确 | "把那篇写深圳的日志改一下" | 先搜索确认目标，再执行编辑 |
| 修改范围不清 | "更新一下昨天的日志" | 先确认要修改哪些字段 |

❌ 错误：猜测用户意图，直接调用工具
✅ 正确：明确意图后再调用工具

### 工作流1: 记录日志

| 步骤 | 动作 | 关键检查点 | 常见错误 |
|:---:|:---|:---|:---|
| 1 | **解析意图** | 提取 title, content, date, topic | 遗漏 topic |
| 2 | **提取元数据** | 识别 mood(1-3个)、tags、people、project | mood 为空数组 |
| 3 | **生成摘要** | abstract ≤100字 | 摘要过长 |
| 4 | **调用工具** | `write_journal` 包含所有字段；正文里明确地点/天气时优先采用正文信息；location 缺失时才允许工具使用默认地点 | 让默认值覆盖正文里已写明的信息 |
| 5 | **检查确认** | `needs_confirmation` 为 true？（成功写入后必须 follow-up） | ⚠️ **最常见错误：直接跳过** |
| 6 | **展示确认** | 展示 `confirmation_message` | 不展示直接结束 |
| 7 | **等待回复** | 询问用户"是否正确？" | 不询问 |

**澄清规则（强制）**：
- 如果无法判断用户是在“新写一篇”还是“修改已有日志”，必须先澄清
- 如果无法负责任地构造最小可写 payload，必须先澄清再调用 `write_journal`
- 不得把缺失的用户意图留给工具在运行时“猜出来”

**失败与后续规则（强制）**：
- pre-tool 阶段若意图或关键字段不清楚，先澄清，不得直接调用工具
- tool failure 时，不得假装 journal 已保存
- write succeeded 但用户拒绝自动补全值时，应进入 correction flow，不得把已成功写入重新表述为“写入失败”
- 必须区分：未保存 / 已保存但待确认 / 已保存但存在降级 side effects
- 检查 `side_effects`：`journal_commit.status == "complete"` 时 journal 已持久化；即使后续步骤失败，也绝不能再次调用 write 创建同一篇日志
- 对 `success_degraded`，逐项读取失败记录的 `recovery_strategy` 并只修复对应派生物；`mark_pending: queued` 表示 freshness queue 已可靠落盘，后续 search preflight 会消费它
- `attachments_processed` 可含失败诊断，但 journal frontmatter 只引用已成功发布的附件；`auto_index`（如启用）也必须作为 post-commit side-effect record 消费
- `journal_commit` 未完成且 pre-commit 记录为 `failed/compensated` 时，确认无 durable `journal_path`，解决错误后才可重试写入

**安装后可选个性化与写入状态指针**：
- 安装完成后的专用触发词 / 默认地址偏好配置 → 仅在用户明确要求时处理；安装本身只按 `bootstrap --json` 输出执行
- 场景：想调整 trigger、设置默认地址、区分“已保存”与“已验证生效” → 先读相关 API / config 契约，别把它并入 onboarding 成败
- 场景：需要解释 `write_journal` 的 `needs_confirmation` / `index_status` / `side_effects_status` / 附件处理结果 → 先读 `docs/API.md` 的 `write_journal` 返回语义
- `SKILL.md` 保留 workflow 与职责边界；安装细节和返回字段契约不在此重复展开

### 工作流2: 检索日志

**检索架构**:

> 检索管道与编排器架构的完整细节见 [ARCHITECTURE.md §5](docs/ARCHITECTURE.md)。
> 以下为简化概览：

```
             用户查询
          ┌────┴────┐
   ┌──────▼──────┐
   │ 关键词/实体管道 │
   │ FTS5 + metadata│
   │ Entity Graph   │
   └──────┬──────┘
       确定性排序
             │
         最终结果
```

对于复杂自然语言查询，`smart-search` 返回确定性检索 scaffold；它会复用 SearchPlan
已抽取的关键词作为 bounded 子查询。判断、过滤、query rewrite、多跳调用与总结仍由宿主
agent 按本 Skill 的 playbook 完成，详见
[ARCHITECTURE.md §5.8](docs/ARCHITECTURE.md)。

**检索路径选择（不要使用 `recall` 作为新入口）**:

| 需求 | 使用 |
|:---|:---|
| 严格关键词 / FTS-only，要求可复现精确匹配 | `life-index search --query "关键词" --no-semantic`（兼容 no-op） |
| 普通关键词、实体加权、结构化过滤检索 | `life-index search --query "关键词"` |
| 开放回忆、关键词 / 实体加权发现，或需要 scaffold / evidence pack | `life-index smart-search --query "..." --include-evidence` |
| 旧 GUI / Agent 仍传语义旗标 | `life-index search --query "..." --semantic --semantic-policy fallback`（接受但废弃的 no-op） |

`life-index recall` 仅为旧集成保留的兼容壳；新宿主 agent 流程直接选择上表中的 `search` / `smart-search`。

<!-- PLATFORM-SSOT:SYNTHESIZE-TRANSITION:START -->
**`--synthesize` transition**

Current runtime: the product CLI accepts `--synthesize` for at least two major versions and constructs `SmartSearchOrchestrator()` with no injection surface. It emits no `answer` and preserves the ordinary deterministic domain payload.

Current warning: exactly one stderr line is emitted: `DEPRECATED: --synthesize is a compatibility no-op; synthesis belongs to the Host Agent + Life Index Skill.`

A3/A4 implementation: search/smart-search production packages contain no dormant/injectable LLM rewrite, filter, provider, prompt, trust-gate, or synthesis implementation. The Tier 1 no-LLM hard check enforces the documented static structural policy over these production roots. A5 extends the deterministic-only boundary and structural scan to product eval; #163 remains open pending review, so D1-A is not complete.

Intelligence owner: Host Agent + Skill remain responsible for planning, multi-hop reasoning, orchestration, interpretation, and synthesis.
<!-- PLATFORM-SSOT:SYNTHESIZE-TRANSITION:END -->

<!-- PLATFORM-SSOT:EVAL-LANGUAGE-JUDGE:START -->
**`eval --judge llm` compatibility boundary**

`life-index eval` is deterministic C7 verification. `--judge llm` remains recognizable in this version but immediately returns non-success code `EVAL_LLM_JUDGE_HOST_AGENT_REQUIRED` before evaluation or provider/configuration import. It never silently falls back to keyword and never claims language-assisted evaluation ran.

Language-assisted evaluation belongs to Host Agent + Life Index Skill. The A5 candidate removes product eval provider/prompt/client ownership; #163 remains open pending review, and D1-A is not complete.
<!-- PLATFORM-SSOT:EVAL-LANGUAGE-JUDGE:END -->

**计数 vs 观测序列选择**:

| 需求 | 使用 |
|:---|:---|
| 明确计数、分桶、频率、下限/上限、可核 claim envelope | `life-index aggregate --range ... --unit ... --predicate ... --json` |
| 同一字段随时间变化的 typed observation series | `life-index trajectory --field ... --range YYYY-MM..YYYY-MM` |
| 需要解释趋势含义、异常点、原因或叙述总结 | 先用 `trajectory` 或 `aggregate` 取确定性数据，再由宿主 agent 解释并引用来源 |

`aggregate` owns counts, buckets, and claim envelopes. `trajectory` owns typed
observation series. Do not use `trajectory` as a hidden counter, and do not use
`aggregate` to extract field-value time series.

**Agent consumption rule（按问题形态选工具）**:
1. 先判定问题形态，不把 `smart-search` 当作所有查询的强制首调。
2. 结构化问题（计数、枚举、facet、跨 facet、趋势）优先按上方 Grounded Query Skill Playbook 走确定性路径：`index-tree ensure` -> `discover` -> `navigate`，或直接用 `aggregate` / `trajectory` 取得可核数据。
3. 只有开放回忆、关键词 / 实体加权发现、或 facet 菜单无法提供有效候选时，才调用 `life-index smart-search --query "..." --include-evidence` 或 `life-index search`。
4. 使用 `smart-search` 时，检查 `query_plan.sub_queries`、`query_plan.strategy` 与检索诊断，消费返回的 `agent_instructions`、`answer_scaffold`、`filtered_results` 与 `evidence_pack`；只引用返回或已读取的来源，不得自行补造证据。
5. 如需深度分析，由宿主 agent 迭代调用 deterministic tools，不在工具内启用 LLM。
6. 不要为获得工具侧合成而叠加 `--synthesize`：该兼容旗标至少保留两个主版本，但只向 stderr 发出一次稳定弃用警告；它不注入 LLM、不添加 `answer`，也不改变普通 deterministic domain payload。完整过渡契约见上方命名块。

**查询意图 → 参数映射**:

| 用户意图 | 推荐参数 |
|:---|:---|
| "关于工作的日志" | `--topic work` |
| "去年的记录" | `--date-from 2025-01-01 --date-to 2025-12-31` |
| "跟示例人物有关的" | `--people 示例人物` |
| "关于重构的" | `--query "重构"` |
| "开心的回忆" | `--mood 开心` |
| "LifeIndex项目" | `--project LifeIndex` |
| 精确关键词匹配 | `--query "关键词" --no-semantic` |

**步骤**:
1. **解析查询意图**：从用户表述中识别过滤条件
2. **执行搜索**：`search_journals`（关键词 + Entity Graph；`--semantic*` 仅兼容 no-op）
3. **呈现结果**：展示日志列表（按确定性分数排序）

**职责边界（强制）**：
- `search_journals` 负责 retrieval execution，不负责替用户下结论
- Agent 必须区分“搜索结果为空”与“搜索执行失败”
- Agent 负责解释结果、回答用户真正的问题，并在需要时建议 refinement / follow-up；可读取 `entity_expansion` 解释别名/关系扩展来源，但不得把它当作过滤或裁决依据

**Evidence Pack 检索诊断消费（`--include-evidence`）**：

当使用 `smart-search --include-evidence` 时，返回值包含 `evidence_pack.diagnostics`，提供确定性检索质量信号。Agent 应据此调整行为：

| `retrieval_outcome` | Agent 行为 |
|---------------------|-----------|
| `ok` | 正常消费结果 |
| `weak_results` | 向用户说明置信度低，参考 `suggestions` 建议调整查询 |
| `no_confident_match` | 告知未找到高置信匹配，建议换词或加过滤 |
| `zero_results` | 如实报告无结果，参考 `suggestions` 建议放宽条件 |

> `diagnostics` 是纯确定性推导，不依赖 LLM。详见 [API.md §Evidence Pack Diagnostics](docs/API.md)。
- 不得把工具返回的原始结果列表直接等同于最终用户答案

**澄清与失败规则（强制）**：
- 当用户请求过于模糊、无法形成有意义的 query / filter 时，应先澄清，再调用 `search_journals`
- 如果工具执行失败，不得把 failure 伪装成“没搜到”
- 如果工具成功但无结果，应如实说明为空结果，并可建议用户缩小/放宽条件
- 如果用户在搜索后其实想继续执行 edit / summarize / compare，Agent 必须显式切换到下一工作流，而不是默认混做

### 工作流2.5: 聚合型自然语言查询

**适用场景**：
- “过去30天我有多少次晚于10点睡觉”
- “上个月我写了多少篇关于工作的日志”
- “最近两周我情绪低落的次数多吗”
- “去年这个时候我主要在做什么”

**核心原则**：
- 聚合型问题不是单次 retrieval 的直接结果，而是 **检索 → 阅读证据 → 条件判定 → 聚合回答**
- 不得把 `search_journals.total_found` 直接当作最终答案，除非用户问的就是“搜到了几条”
- 优先使用确定性证据；启发式证据只能辅助判断，不能伪装成硬事实

**步骤**：
1. **识别问题类型**：判断用户要的是 count / compare / trend / summarize
2. **提取时间窗与过滤条件**：优先形成 `date-from/date-to/topic/project/people/...`
3. **优先找硬证据**：
   - frontmatter 明确字段
   - 正文明确陈述
   - index / timeline / metadata 可直接回答的信息
4. **必要时做候选检索**：调用 `search_journals`，必要时围绕同一用户问题做多轮 query expansion
5. **逐条判定证据**：
   - `MATCH`：明确满足
   - `NO_MATCH`：明确不满足
   - `UNCERTAIN`：存在相关线索，但证据不足
6. **聚合输出**：count / compare / trend / summary，并明确区分确定结论与启发式推断

**证据分层（强制）**：
- **硬证据**：结构化字段或正文明确陈述
- **软证据**：只能间接支持结论的 proxy signal（如日志写作时间很晚、正文出现“熬夜/很困/准备睡”）
- **不确定证据**：不足以单独支撑结论，只能作为补充说明

**启发式规则（强制）**：
- Agent 可以使用软证据做推断，但必须降级表达为“高概率 / 可能 / 无法确认”
- 不得把启发式结论写成 CLI 硬规则
- 不得为某个具体问题发明专门 workflow 分支；应复用本工作流的证据分层与聚合步骤

**职责边界（强制）**：
- CLI 负责提供原始证据与检索结果
- Agent 负责条件判定、聚合、解释不确定性
- 如果结论高度依赖启发式，必须在最终回答中说明依据与局限

### 工作流3: 编辑日志

1. **定位日志**：根据日期或标题找到目标文件
2. **确认修改**：展示当前内容，明确修改范围
3. **执行编辑**：`edit_journal`
4. **如修改地点**：必须同时更新 location 和 weather；先调用 `query_weather` 获取新天气，若失败可由 Agent 手动联网查询天气后再一起更新

**澄清规则（强制）**：
- 如果目标日志不明确，必须先定位并确认，不能猜测编辑目标
- 如果不清楚用户要 append、replace 还是 metadata update，必须先澄清
- 如果请求听起来更像“新增一段人生记录”而不是“修改已有日志”，必须切回 write vs edit 澄清

**确认与失败规则（强制）**：
- edit flow 默认不要求像 write flow 那样的 post-write confirmation loop，但对高风险 replace / destructive edit，Agent 可先做额外确认
- 如果 coupled-field prerequisite（如新地点对应天气）尚未解决，不得直接把 edit 当作可安全执行
- 如果 edit tool 执行失败，不得宣称修改已成功
- 如果 journal mutation 已完成但 weather alignment 未完成，必须诚实区分“编辑状态”和“字段语义对齐状态”

### 工作流4: 生成摘要

1. **确定类型**：月度摘要（`--month YYYY-MM`）或年度摘要（`--year YYYY`）
2. **执行生成**：`life-index abstract`（或开发者模式 `python -m tools.generate_index`）
3. **返回结果**：告知文件路径和统计信息

### 工作流5: 索引维护

| 场景 | 操作 |
|:---|:---|
| 日常写入 | 无需手动维护（Write-Through 自动更新） |
| 搜索结果异常/缺失 | `.venv/bin/life-index index --rebuild` 全量重建 |
| 首次安装 | `.venv/bin/life-index index` 初始化索引 |
| 升级后刷新 Agent playbook | `.venv/bin/life-index sync-skill` 同步 `SKILL.md` + `references/` |
| 手动编辑过日志文件 | `.venv/bin/life-index index` 增量更新 |

### 工作流6: Schema 迁移

1. **扫描**：`life-index migrate --dry-run` 查看版本分布和缺失字段
2. **执行**：`life-index migrate --apply` 自动迁移 + 获取 `needs_agent` 列表
3. **语义回填**：Agent 逐条处理 `needs_agent`（读取正文 → LLM 提取 abstract/mood → `life-index edit` 更新）

### 工作流7: 实体图谱访谈

**原则**：三权分立。CLI 只做确定性 JSON 原语；agent 可读证据、分桶、提出带理由建议；用户是确认态图谱的权威来源。建议自由，写入必须有人判（逐条确认或批量授权均可）。
**实体维护速查**：任何“检查/维护/整理实体图谱”任务，第一步先运行 `life-index health --json`。若 `data.upgrade_freshness.suggested_refresh_step` 存在，先按该步骤刷新代码与 playbook，再继续；然后看 `data.entity_maintenance.traffic_light`、`pending_count` 和 `next_step.command`。绿灯且无待决即可结束；黄/红灯再运行 `life-index entity audit --json`，按返回的 `next_step` 进入 `entity --review` 或 `entity maintain ... --preview`。详细步骤见 `references/ENTITY_MAINTENANCE_PLAYBOOK.md`；契约见 `docs/API.md` 与 `docs/ENTITY_GRAPH.md`。
**实体档案回报**：回答“关于某人/项目/实体”时，先定位实体 ID，优先读取 `<data>/Entities/<entity_id>.md`；若档案不存在，运行 `life-index abstract --entities --id ENTITY_ID --json`（或全量 `life-index abstract --entities --json`）生成；顺 `mentions` 指针下钻，不足再 `search`，用 `entity_expansion` 归因块解释命中来源；档案不回写 `entity_graph.yaml`。
**触发**：用户说“整理人物/谁是谁/检查实体”；写日志时出现新候选；`life-index entity audit --json` 或 `health` 的实体维护灯为 yellow/red；月度整理。
**查 → 筛 → 荐 → 问 → 写**：先 `life-index entity audit --json` 看 `traffic_light`、`pending_count`、`structural_issue_count` 和 `next_step.command`；需要访谈时再 `life-index entity --review`，按 `evidence` 指针读原文，把候选按人物分桶为很确定 same / 很确定 different / 拿不准 / 低价值可缓；再给带理由建议，而不是复述队列；每轮 ≤5 组，问用户 Same / Different / Not-sure，也接受批量授权（如“你确定的那批照办”）。
确认后才写：从 `entity --review` 的 `action_choices[]` 取 `action/source_id/target_id/relation/evidence` payload。合并前 `life-index entity --review --action preview --review-action merge_as_alias --id REVIEW_ITEM_ID --source-id SOURCE_ID --target-id TARGET_ID --json`，再 `life-index entity --review --action merge_as_alias --id REVIEW_ITEM_ID --source-id SOURCE_ID --target-id TARGET_ID --json`；明确不同人/物时先 preview `keep_separate`，再 `life-index entity --review --action keep_separate --id REVIEW_ITEM_ID --source-id SOURCE_ID --target-id TARGET_ID --json` 持久化人判，误标后用 `life-index entity --review --action undo_keep_separate --id REVIEW_ITEM_ID --source-id SOURCE_ID --target-id TARGET_ID --json` 撤销；用户直接确认的自由关系事实先 `life-index entity maintain --add-relationship --id SOURCE_ID --target-id TARGET_ID --relation RELATION --preview --json`，复述 preview 后再 `life-index entity maintain --add-relationship --id SOURCE_ID --target-id TARGET_ID --relation RELATION --apply --json`；review 队列中的关系候选才用 `life-index entity --review --action preview --review-action add_relationship --id REVIEW_ITEM_ID --source-id SOURCE_ID --target-id TARGET_ID --relation RELATION --json` 和 `life-index entity --review --action add_relationship --id REVIEW_ITEM_ID --source-id SOURCE_ID --target-id TARGET_ID --relation RELATION --json`；候选确认用 `life-index entity --review --action confirm_candidate --id REVIEW_ITEM_ID --source-id ENTITY_ID --json` 或带 `--target-id TARGET_ID --relation RELATION`；加别名用 `life-index entity --add-alias ALIAS --id ENTITY_ID`；撤销合并用 `life-index entity --unmerge --id MERGED_ID --target-id TARGET_ID`。

**冷启动录入**：已有日志先 `life-index entity build --from-journals --preview --json` 看候选，读 evidence 后访谈确认；用户口述家人/关系时，先问清身份和方向，并询问“哪个实体是你本人”；逐条复述确认后用 `life-index entity --add '<json>'` 创建 `source=user,status=confirmed` 实体，用 `entity maintain --add-relationship ... --preview/--apply --json` 写用户确认的关系边，再运行 `life-index entity --set-self --id ENTITY_ID --json` 设置“我”的锚点；写完 `life-index entity --check`。`evidence=[]` 对用户确认事实是健康态。

**批量录入**：不要要求固定模板。用户可给 Excel/CSV/Markdown 表、一段话或照片转写；agent 复述结构并拿到批量授权后生成 JSON/YAML 批文件，先 `life-index entity build --from-batch FILE --preview --json`，再 `--apply --json`，最后 `life-index entity --check`。重名冲突会进入 `entity --review`。

**表格/直编通道**：偏好表格时，`life-index entity --review --export csv --output review.csv` 或 `--export xlsx`，用户填 decision 列后 `life-index entity --review --import review.csv`；高级用户可直接编辑 `entity_graph.yaml`，随后必须 `life-index entity --check`，必要时再 `life-index smart-search --query "..."` 验证。

**队列外观察义务**：写日志或读 evidence 时，如果注意到新人名/新关系线索，轻提一句或用 `life-index entity --propose '<json>'` 静默放入候选池；候选不会影响 confirmed 检索，等下一轮访谈再裁决。用户口述/纠正人物关系事实时，agent 应主动复述并提议写入图谱；建议自由，写入仍必须有人判。

**维护节律**：事件触发（新候选）轻提 1 句；周检 1 分钟跑 `life-index entity audit --json` 看灯号；类型旧时先 `life-index entity maintain --normalize --preview --json`，用户批准后 `--apply --backup`；删除实体先 `life-index entity maintain --delete --id ENTITY_ID --preview --json`，用户确认后 `--apply --backup`；月理 10 分钟过 ≤5 组访谈。

**红线**：仅经 CLI 原语写图；工具内无 LLM、无 TUI、无零人判自动合并。高置信候选也只排队或等待用户批量授权。

### 工作流8: 备份与灾难恢复

1. **创建可恢复备份**：使用 `life-index backup --dest DEST --full`；仅当
   `success=true` 且 `recovery_manifest_path` 指向 timestamped backup 内的
   `.life-index-recovery-manifest.json` 时，才把本次 full backup 视为 complete。
   不得用 exclude pattern 移除 journals、attachments 或 `entity_graph.yaml`。
2. **守住真相边界**：manifest 中 journals、attachments、`entity_graph.yaml` 是
   `canonical_source`；`.index/` 是 `rebuildable_derived` 且不恢复为权威数据。
3. **空目标恢复**：先证明目标 sandbox 不存在或完全为空，再设置该目录为
   `LIFE_INDEX_DATA_DIR` 执行 `life-index backup --restore BACKUP_PATH`。非空目标必须
   停止处理，不能要求 overlay 或手工绕过保护。读取 `restore_mode`、
   `recovery_manifest_verified` 和 `warnings[]`；只有 `manifest_verified` +
   `recovery_manifest_verified=true` 才是 manifest-verified recovery。
4. **重建与验证**：恢复成功后运行 `life-index index --rebuild` 与
   `life-index generate-index --rebuild`，用已知关键词执行 `life-index search`，最后
   `life-index verify --json`。重建失败只修复派生索引；不得改写或重复恢复 canonical
   source 来掩盖失败。
5. **失败判断**：copy/hash/manifest 校验失败时，该备份或恢复不 complete；向用户
   报告 `errors[]` 中的具体 artifact，保留现状并停止，不宣称灾备成功。中途
   copy 失败后只有在目标已补偿回空状态时才能重试。`legacy_unverified`
   的 warning 必须原样呈现，不得升格为 verified。

### 响应中的 events 和 _trace

- **events**：CLI 响应中的 `events` 字段包含搭便车事件通知（如"连续7天未记日志"）。Agent 自主决定是否向用户提及。
- **_trace**：CLI 响应中的 `_trace` 字段包含操作级诊断数据（trace_id、耗时、步骤状态）。用于调试性能问题。

---

## Related Documentation

| 文档 | 用途 |
|------|------|
| [bootstrap-manifest.json](bootstrap-manifest.json) | authority / freshness 锚点；先刷新它，再按 `required_authority_docs` 获取当前权威文档 |
| [AGENT_ONBOARDING.md](AGENT_ONBOARDING.md) | 一页 bootstrap 执行入口；按 `execution_policy` / `needs_human` / `safe_next_steps` 操作 |
| [API.md](docs/API.md) | 工具 API 接口、参数详情、错误码与恢复策略 |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | 架构设计、核心原则、关键决策；**§1.5 定义人-Agent-CLI 三层信息流交互范式** |
| [WEATHER_FLOW.md](references/WEATHER_FLOW.md) | 天气处理详细流程与故障 Fallback |

---

## Examples

**记录工作日志**：
```
用户：记录一下今天完成了搜索功能优化

Agent：
1. 解析：title="搜索功能优化", topic=["work"], abstract="完成搜索功能优化工作"
2. 提取：mood=["专注"], tags=["搜索", "优化"], people=[], project=""
3. 调用 write_journal（自动填充地点="Chongqing, China"、查询天气）
4. 检查 needs_confirmation=true
5. 展示：日志已保存。地点：Chongqing, China；天气：Sunny。是否正确？
```

**搜索历史**：
```
用户：查找去年关于重构的日志

Agent：
调用：search_journals --query "重构" --date-from 2025-01-01 --date-to 2025-12-31
返回：找到 5 篇相关日志
```
