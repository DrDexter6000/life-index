<!-- AGENTS.md - Life Index Agent 导航入口 -->

> 本文档为 AI 编码代理提供**快速导航入口**。详细规范已归源到 SSOT 文档，本文件仅保留指引与 Agent 行为约束。
> **最后更新**: 2026-05-20 | **AGENTS.md 文档版本**: v3.3 | **状态**: 活跃维护
>
> 本地专属配置（含部署路径与 Agent 并行治理规则）见 `.agents.local.md`（已 gitignored，仅本地可用）。
> 若 `.agents.local.md` 存在，所有 Agent 在执行任何**非只读**任务前必须先读取它，并遵守其中指向的本地治理层。

---

## 🏛️ 宪章优先（Charter First）

**[`CHARTER.md`](CHARTER.md) 是最高治理文件**，效力高于本文件及所有其他文档。动手写代码前，若触及 L2/L3 边界、搜索参数、架构变更，**必须先通读 CHARTER.md**。

---

> **战略文档协同规则**：任何 Agent 接手 CLI 开发时，必须先阅读 `.strategy/strategy.md` 与 `.strategy/ROADMAP.md`（本地 NTFS junction，仅本地可用），禁止跳过共享战略文档直接开始开发。
>
> **CLI / GUI 共享规则**：所有高层战略、路线图、阶段进展统一记录在共享 `.strategy/` 中；CLI 侧不得维护一份独立平行战略文档。

> **本地 Agent 治理规则**：`.agents.local.md` 可指向本地私有治理目录（如 `.agent-governance/`）。该目录用于并行 session 管理、文件所有权、dirty state 协议、mission 模板与 CI failure 分类。它已 gitignored，不得提交；但在本地存在时，其执行规则对所有 Agent 生效。

## 项目概述

**Life Index** 是一个 Agent-Native、local-first 的个人人生日志与检索系统。

- **CLI 原子工具**：write / confirm / search / smart-search / edit / abstract / weather / index / generate-index / backup / verify / timeline / migrate / eval / entity / health / health --data-audit / aggregate / analyze / version
- 用户通过自然语言 + Agent 调用 Python CLI 工具

**核心理念**:
- **Agent-Native**：CLI 是 Agent 的母语。发挥 Agent 自然语言理解能力，仅在需要原子性/准确性时开发专用工具
- **本地优先**：所有数据存储在 `~/Documents/Life-Index/`
- **纯文本格式**：Markdown + YAML Frontmatter，永不过时

---

## 📚 Agent 必读导航

| 场景 | 必读文档 | 说明 |
|------|----------|------|
| **首次接手项目** | `CHARTER.md` → `AGENT_ONBOARDING.md` → `SKILL.md` | 先理解治理规则，再执行安装，最后掌握技能接口 |
| **涉及架构/模块变更** | `CHARTER.md` §1-§2 + `docs/ARCHITECTURE.md` | 宪章分层边界 + 技术实现细节 |
| **修改搜索参数/阈值** | `CHARTER.md` §3 + `docs/ARCHITECTURE.md` §4-§5 | 搜索子系统不变量 + 架构参数 |
| **新增/修改 CLI 命令** | `docs/API.md` + `CHARTER.md` §1.3 | 接口契约 + CLI 为 SSOT 规则 |
| **修改数据格式/Schema** | `CHARTER.md` §1.1-§1.2 + `docs/ARCHITECTURE.md` §6.3 | 数据隔离不变量 + 日志格式规范 |
| **修改 Entity Graph / alias / relationship** | `docs/ENTITY_GRAPH.md` + `docs/ARCHITECTURE.md` §5.3 | 实体图谱操作契约 + 搜索集成边界 |
| **版本号 / release / tag 操作** | `docs/VERSIONING.md` + `CHANGELOG.md` | 保守 SemVer + release checklist + tag policy |
| **并行 session / mission / dirty state / CI 归属** | `.agents.local.md` → `.agent-governance/README.md` | 本地私有治理层；存在时必须遵守，不进入公开仓库 |
| **Maestro 编排 / Auto Run / worker dispatch** | `.agent-governance/maestro/MAESTRO-EXECUTION.md` + `.agent-governance/maestro/MAESTRO-REFERENCE.md` | 本地 Maestro 主审、worker 调度、Auto Run、worker evidence vs lead acceptance；常规 Maestro 执行入口 |
| **长程治理 / mission graph / TDD Program Plan** | `.agent-governance/maestro/LONG-HORIZON-ORCHESTRATION-DOCTRINE.md` + `.agent-governance/maestro/LIFE-INDEX-LONG-HORIZON-ADAPTER.md` | 长程任务循环、decision register、user-presence floor、milestone envelope |
| **代码风格疑问** | `docs/ARCHITECTURE.md` §6.1 | 命名、类型注解、路径处理等 |
| **模块结构疑问** | `docs/ARCHITECTURE.md` §6.2 | tools/ 目录树 |
| **本地部署到实机** | `.agents.local.md` | 本地 OpenClaw/WSL 部署路径（已 gitignored） |

> **重要**：`docs/archive/` 目录包含历史开发文档，仅供考古参考。除非用户明确要求，Agent 不应阅读该目录内的文件，以避免浪费上下文和 token。

---

## 文档层级（高→低）

| 层级 | 文档 | 内容 | SSOT 归属 |
|:---:|------|------|----------|
| 🏛️ **L0** | [`CHARTER.md`](CHARTER.md) | **项目宪章**：不变量、分层宪章、反模式、修订流程、工程纪律 | 最高权威 |
| 📐 **L1** | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | **技术实现 SSOT**：架构、参数、代码风格、模块结构、日志格式 | 从属于 CHARTER |
| 📡 **L1** | [`docs/API.md`](docs/API.md) | **接口契约 SSOT**：CLI 参数、错误码、返回值 | 从属于 CHARTER |
| 🧭 **L1** | [`docs/ENTITY_GRAPH.md`](docs/ENTITY_GRAPH.md) | **Entity Graph 操作契约 SSOT**：别名准入、生产写入、验证、回滚 | 从属于 CHARTER / ADR-024 |
| 🏷️ **L1** | [`docs/VERSIONING.md`](docs/VERSIONING.md) | **版本治理 SSOT**：保守 SemVer、release checklist、tag policy | 从属于 CHARTER |
| 🗺️ **L2** | `.strategy/strategy.md` | 双产品线战略枢纽（本地 junction） | 本地只读 |
| 🗺️ **L2** | `.strategy/ROADMAP.md` | CLI + GUI 综合路线图（本地 junction） | 本地只读 |
| 📖 **L3** | [`SKILL.md`](SKILL.md) | Agent 技能定义、触发词、工具接口 | Agent 调用入口 |
| 📖 **L3** | [`AGENT_ONBOARDING.md`](AGENT_ONBOARDING.md) | 安装与初始化指南 | 面向 Agent |
| 📖 **L3** | [`README.md`](README.md) | 用户入口、快速开始、常用命令 | 面向人类用户 |
| 🏠 **本地** | `.agents.local.md` | 本地部署路径、环境配置 | 已 gitignored |
| 🏠 **本地** | `.agent-governance/` | 本地 Agent 并行治理、mission 模板、dirty state 协议 | 已 gitignored |

---

## 核心工具命令速查

```bash
life-index write --data '{"title":"...","content":"...","date":"2026-03-07","topic":"work"}'
life-index confirm                          # 应用 write 确认更新
life-index search --query "关键词" --level 3
life-index smart-search --query "自然语言查询"
life-index edit --journal "Journals/2026/03/life-index_2026-03-07_001.md" --set-weather "晴天"
life-index abstract --month 2026-03         # 别名：generate-index
life-index weather --location "Lagos,Nigeria"
life-index index           # 增量更新
life-index index --rebuild # 全量重建
life-index generate-index  # 生成索引树（monthly/yearly/root）
life-index backup --dest "D:/Backups/Life-Index"
life-index verify --json   # 数据完整性校验
life-index timeline --range 2026-01 2026-03  # 输出时序摘要流
life-index migrate --dry-run
life-index migrate --apply
life-index entity --audit
life-index entity --stats
life-index entity --check
life-index entity --review
life-index eval            # 搜索评估门
life-index aggregate --range 2026-01-01..2026-03-31 --unit month --predicate journal_count
life-index analyze --range 2026-01-01..2026-03-31 --unit day --predicate entry_time_after=22:00
life-index health          # 安装健康检查
life-index version         # 显示版本信息
life-index health --data-audit    # 审计数据目录异常

# 开发者模式（无需安装）
python -m tools.write_journal --data '{...}'
```

完整命令列表与参数详情见 [`docs/API.md`](docs/API.md)。

---

## Agent 行为约束

### OpenCode TypeScript LSP 运行时保护

本地应保留项目级 OpenCode 配置：`.opencode/opencode.json`，禁用 `typescript` LSP。该文件属于本地运行时配置，必须保持 gitignored，不得提交或推送。

背景：FDE 项目在 OpenCode `1.15.3` 下复现过 TypeScript read-tool 失败，触发路径为"读取 `.ts` 文件 → OpenCode 启动 TypeScript LSP → 出现 `InstanceRef not provided` → Auto Run/continuation 失败"。该配置是预防性平移，用于避免 Life Index 未来在类似 TypeScript/JavaScript 项目结构或 worker 任务中命中同类 runtime 问题。

该配置不禁用 TypeScript、Python、测试、构建、文件读取或模型推理；只关闭 OpenCode 在本项目内的 IDE 式 TypeScript 语义辅助。

本地复现方式：如果新 clone 或新机器缺少该文件，按以下内容在本地创建 `.opencode/opencode.json`，不要把它加入 Git：

```json
{
  "$schema": "https://opencode.ai/config.json",
  "lsp": {
    "typescript": {
      "disabled": true
    }
  }
}
```

补偿规则：

- TypeScript/JavaScript 相关任务必须优先使用 `rg`、`rg --files`、定向文件读取、明确的文件/函数引用来建立代码上下文。
- 涉及代码变更时，用确定性 gate 补足语义确认：相关测试、typecheck、lint、契约测试或构建命令，按任务风险选择。
- 跨文件或行为变更必须提供具体文件/函数证据；中高风险变更应安排独立 review worker。
- 不得根据该 incident 推断某个 provider 或 worker 长期不可用；已验证的问题是 OpenCode TypeScript LSP 路径。
- OpenCode 升级后，可临时删除本地 `.opencode/opencode.json` 做一次受控复测；只有复测通过后才恢复 TypeScript LSP。

### 工具调用规则

```bash
# ✅ 正确
python -m tools.write_journal --data '{...}'

# ❌ 错误 - 直接调用脚本
python tools/write_journal.py --data '{...}'
```

### 内容保留原则

详见 [`SKILL.md`](SKILL.md) §Content Preservation。核心：用户原始输入的 `content` 必须 100% 原样传递。

### 数据隔离

详见 [`CHARTER.md`](CHARTER.md) §1.1。摘要：
- 用户数据: `~/Documents/Life-Index/`
- 项目代码: 仓库目录
- 两者物理隔离，不可混淆

### ⚠️ 本地目录 Junction 警告（ critical ）

`life-index/.strategy/` 是 **NTFS junction**，实际指向 `D:\Loster AI\Projects\.strategy\`（与 `life-index_gui/.strategy/` 共享同一目标）。

**后果**：在此目录下的任何删除、移动、覆盖操作会同时影响两个仓库可见的文件。历史上已发生误删 Round 19 研究文档的事故。

**操作规则**：
- 删除 `.strategy/` 下任何文件前，必须先用 `fsutil reparsepoint query` 或 `Get-Item .strategy` 确认是否为 reparse point
- 若需清理 CLI 专属文件，只操作 `.strategy/cli/` 子目录，绝不触碰 `.strategy/` 根目录下的 `strategy.md`、`ROADMAP.md`、`v1.x.zip`
- 优先使用 `git` 管理文档版本，避免手动删除

### ⚠️ Windows 终端 + 中文输出 = 不可信（ critical ）

PowerShell 默认代码页 **936 (GBK)**，会把 Python UTF-8 stdout 中的中文渲染为 `����` 乱码。
**永远不要根据 PowerShell 终端中看到的中文字符串做判断。**

**历史事故**：Round 19 Phase 1 inspect 中，终端乱码导致将 "想念小英雄" 误读为 "人生碎片"、将 "CTO 级别技术评审" 误读为 "投资决策"，进而做出了错误的 Gold Set 修正判定。

**正确做法**：
- 用 `ReadFile` / `Read` 工具读文件 / JSON / YAML —— 工具层做了 UTF-8 解码
- 写 Python 脚本时把结果 `json.dump(..., ensure_ascii=False)` 到文件，再用 `ReadFile` 读
- 必要时在脚本顶部 `sys.stdout.reconfigure(encoding='utf-8')` —— 但这只解决显示，不改变审计员看到的内容

**任何"我在终端看到 X，所以判定 Y"的论证，必须先回答"X 是怎么从字节读到我眼里的"。经过 PowerShell stdout 的中文，等于经过一道有损压缩。**

### 测试防污染规则（强制）

- **严禁**向真实用户数据目录写入测试数据
- 自动化测试必须使用临时目录（`tmp_path`、`LIFE_INDEX_DATA_DIR` override）
- 如因调试不得不在真实目录创建临时文件，任务结束前必须清理并 `life-index index --rebuild`
- 手工验收优先使用隔离沙盒：`python -m tools.dev.run_with_temp_data_dir`

### 仓库卫生规则（强制）

详见 [`CHARTER.md`](CHARTER.md) 附录 D。摘要：
- Push 前执行 `git ls-files | git check-ignore --stdin`，输出必须为空
- 禁止提交 `.handoff.md`、`.pytest_tmp/`、`.recovery/`、调试标记等过程性/临时文件
- 禁止提交个人环境配置（用户名、本地路径等）

### 审计-代码耦合规则（强制）

> **来源**: Round 19 Plan B+ Step 4 流程安全杠
> **根因**: Round 18 commit `f13ff93` 写了 audit.md 却未改 golden_queries.yaml，导致 18 条应删除 query 全部存活到 Round 19

**规则**: 任何声称修改代码 artifact（YAML/JSON/Python/config）的审计/ADR 文档，**必须在同一 commit 内包含该 artifact 的实际 diff**。只改 docs 不改 yaml/code 的 commit 应被 review 拒绝。

**执行方式**:
- PR review checklist 加一项："若 ADR/审计文档声称修改了数据/schema/config，请出示对应 artifact 的 diff"
- 临时例外：若文档先行、代码后续，必须在文档中明确标注 `PENDING_IMPLEMENTATION: 代码变更将在 commit X 中完成`
- 禁止状态：文档写"已删除"但代码未删 → 视为流程违规

### 推送政策（强制）

> **来源**: Round 19 Phase 1-C Track A F3
> **根因**: Commit 编排后 push 权限边界模糊，治理类 commit 与 artifact commit 混同 push

**规则**:
- **代码 / eval / baseline / artifact commits**: 通过审计 gate 后可直接 push 至 main，无需逐 commit 二次确认
- **治理 commits（CHARTER / AGENTS.md / ADR / SKILL.md / 操作契约）**: 必须用户显式 ack 后才能 push
- **`docs/API.md` 接口契约更新**: 若与对应代码 / 测试实现同 commit 且不改变未授权的公开契约，按 artifact commit 处理；若为纯文档契约变更、行为承诺变更、或与实现不一致，按治理 commit 处理并需用户 ack
- **混合 commits**（同 commit 含治理 + 代码）: 视同治理类，必须 ack
- **判定标准**: 若任何 governance 类文件出现在 commit diff 中，整个 commit 升级为治理类

**Governance 文件清单**:
- `CHARTER.md`
- `AGENTS.md`
- `docs/ENTITY_GRAPH.md`
- `docs/VERSIONING.md`
- `docs/adr/*.md`
- `SKILL.md`（若存在）
- `.strategy/*.md`

### 工作派发纪律（强制）

> **来源**: RFC-2026-05-19 Foundation Freeze v1 §1、§8
> **根因**: "把地基弄稳固"是不可证伪的目标。自主编排循环面对不可证伪目标无法返回 done，只能无限追加 —— v1.0.0（2026-05-06）后 13 天 130 commit、数亿 token、CHANGELOG `[Unreleased]` 为空。CHARTER §1.10 反模式清单已逐字禁止"在 CLI core 中提前实现尚无真实消费者的工作流原语"，但宪章的 ❌ 不会自我执行 —— 循环照犯了 13 天。**缺的不是原则，是派发前的闸门。**

**适用范围**: 里程碑、工作包、自主 / 多步循环的派发。单步小改不受此约束 —— 本节是闸门，不是流程税。

**边界**: 本纪律针对*派发的工作*（决策内容、代码改动、模块边界），不针对*主理人的状态*（情绪、节奏、表达方式、消息频率）。CTO agent 不基于主理人状态做 governance 决定。

**规则**: 上述派发前，必须同时满足以下三条 —— 缺一则该派发无效。

1. **可证伪退出**: 写明一条退出标准，且存在某个命令或测试能对它判 PASS / FAIL。"改进 X""把 Y 弄稳""强化 Z" 不是退出标准 —— 写不出那个会失败的测试，就不开工。
2. **真实消费者**: 构建任何共享原语 / substrate / "地基"能力前，指名一个**当前已存在**的模块或命令在消费它。"将来某模块可能用到" 不成立（CHARTER §1.10 反模式）。**这一条的答案属于用户** —— Agent 的职责是停下、把问题交还用户（RFC-2026-05-19 §8 不可委托闸门），不是替用户答"是"。
3. **有界自主**: 任何自主 / 多步循环，启动前声明终止判据、step / commit 预算、预算耗尽时的动作（停下并报告，而非继续）。无终止判据的循环不派发。

**红旗**: 出现以下任一念头，立即停。

| 念头 | 现实 |
|------|------|
| "先建好，将来造模块会用到" | 没有模块在拉它。停。（规则 2） |
| "地基还不够稳" | "够稳"不可证伪 —— 说出那个会失败的测试。（规则 1） |
| "循环在出 commit，让它跑" | commit ≠ 交付。查 CHANGELOG `[Unreleased]` 是否仍空。（规则 3） |
| "先建着，之后再接线" | 未接线的代码就是死代码。现在接，或现在别建。 |
| "编排器已批准这个工作包" | 批准工作包 ≠ 给了可证伪退出。退回规则 1。 |

**执行方式**:

- 三条由派发方（MAESTRO lead 或单 agent 自身）写进工作包 / mission 模板；缺任一条，派发无效。
- 规则 2 的"真实消费者"由用户口头答一句即可（RFC-2026-05-19 §8），不需要文档评审 —— 刻意保持到疲惫时 30 秒可答。
- closeout review 检查项: 工作包产出了 commit 但 CHANGELOG `[Unreleased]` 仍为空 —— 这是本节根因的复发信号，据此打回。

---

## 设计底线

详见 [`CHARTER.md`](CHARTER.md) 附录 D.1。

```
宁可功能简单，不可系统复杂
宁可人工维护，不可自动化陷阱
宁可牺牲性能，不可牺牲可靠性
```
