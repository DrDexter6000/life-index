---
type: implementation-rfc
status: accepted
charter-amendment: "携带 §1.9 增量解释条款（additive，不削弱不变量）；触发 CHARTER §5 substantive gate + owner 授权"
created: 2026-06-03
approved: 2026-06-03
approved-by: Life Index 主理人（CHARTER §5 substantive gate 授权 + ack #1）
title: L3/L4 智能交接契约（Intelligence Handoff Contract）
related:
  - CHARTER.md §1.5 §1.9 §1.10 §2.1 §2.2
  - docs/rfc/RFC-2026-05-15-advanced-module-developer-contract.md   # 本 RFC 填补其 §5「向 calling agent 交接」的未规约缺口
  - docs/rfc/RFC-2026-05-20-foundation-module-interface.md          # §4「永不进 L2」清单
  - docs/rfc/RFC-2026-05-25-mcp-discovery-only-layer.md             # P0 in-context 路径的传输基础
  - RFC-2026-05-19 Foundation Freeze v1（私有治理 RFC；§8 真实消费者闸门；Phase-2）
---

# RFC-2026-06-03: L3/L4 智能交接契约（Intelligence Handoff Contract）

## §1 Rationale

### 背景

CHARTER §1.9 规定：高级功能的**默认形态**是 Life Index 输出可审计的 evidence /
scaffold，由 **calling agent 用其自身 LLM** 负责语言合成；只有「为没有 calling
agent 的终端用户」才允许**显式 provider opt-in fallback**。模块默认输出
`evidence_pack` / `claim_envelope` / `scaffolded_prompt` / `agent_instructions`。

RFC-2026-05-15（Advanced Module Developer Contract）§5 进一步规定模块「evidence
before interpretation」，并写道：模块「**may later ask a calling agent to
synthesize prose**」。

**但全仓没有任何地方规约：一个 L3/L4 消费者究竟*如何抵达*那个 calling agent /
brain，并把 scaffold 交给它。** 这是 §1.9 与 RFC-05-15 之间一个明确的、未填的缺口。

### 问题

缺少一条共享的交接契约，会产生三个后果：

1. **pipeline 分裂**：每个高级模块（Memoir Engine、数字家书、虚拟家属对话、心潮
   地图、GUI…）各自重造「取得 brain + 发送 scaffold + 收回结果」的代码，workflow
   与 prompt 在 CLI 之外被复制，互相漂移。这正是主理人指出的「要维护两套体验/交付
   物」的坑。
2. **§1.9 渗漏风险**：模块在各自压力下有动机偷偷捆绑 provider client —— 恰是 §1.9
   「❌ 为每个高级模块维护隐藏的 per-module provider 配置」明令禁止的形态。
3. **GUI 割裂**：若 GUI 自带一个 BYOL 裸模型作为其「脑子」，它**不是**用户已经
   信任、已经调好的那个 agent（人格 / 记忆 / 技能）。对一个手里已有可信 agent 的
   用户，GUI 会像「另一个完全不同的软件」。

### 目标

定义**一条**确定性的、跨 L3/L4 共享的**智能交接契约**：任何需要智能的消费者，如何
**解析（resolve）并抵达一个 brain** 来执行 CLI 产出的 scaffold，同时严守：

- §1.9（默认 calling agent；无 agent 时显式 opt-in fallback；模块默认不持 LLM）
- §1.10（模块消费稳定 CLI 契约；不建第二真相源）
- §1.5 + RFC-05-20 §4（LLM 调用 / provider 代码**永不进 L2**，由 M16 层级 CI 门守卫）

GUI 是本契约的**首个 / 参考消费者**，而非唯一消费者。

## §2 Non-Goals

本 RFC **明确拒绝**：

| Non-goal | 拒绝理由 |
|---|---|
| 模块 / L2 默认路径调用 LLM | 违反 §1.9 与 RFC-05-20 §4。本契约的默认仍是 P0（交还 in-context calling agent）。 |
| 在 L2 新增承担语言/合成职责的原语（如 `synthesize`） | 违反 §1.5 / §1.9 / RFC-05-20 §4「永不进 L2」。bridge 是 **L3**。 |
| 在 GUI 内建完整 agent runtime | 会使 Life Index 漂移为「自带 LLM 的独立应用」（违 §1.9 身份），且与用户可信 agent 割裂。 |
| 第二数据真相源 | 一切改状态结果回经 CLI validate/apply；bridge 不直写 L1（§1.10）。 |
| plugin loader / 动态发现 / runtime registry | 违反 §1.10。bridge 是静态 import 的 L3 helper。 |
| 反转 RFC-2026-05-25 | P0 in-context 路径**构建于**其 MCP discovery/invoke 之上，不取代它。 |
| 生成式自修复桥（self-repair） | 因 P0/P1/P2 皆走标准传输（MCP / OpenAI-compatible / ACP），无 bespoke 桥可坏；列入 §8 实验性附录，不在本 RFC 范围。 |

## §3 Design

### §3.1 三个 brain 源 + 确定性解析顺序

一个需要智能的任务，其 brain 来源恰好取自以下之一（**永不两个脑子**）：

| 优先级 | brain 源 | 何时 | CHARTER 依据 |
|---|---|---|---|
| **P0** | **in-context calling agent** | 消费者已运行在某 agent 上下文内（如用户在 Hermes / OpenClaw 中、经 MCP/skill 驱动该模块） | §1.9 默认路径。等同现有 smart-search 模式：只返回 scaffold + `agent_instructions`，在场 agent 合成。**零端点调用。** |
| **P1** | **用户自有 host-agent 端点** *(本 RFC 新增)* | 无 in-context agent，但用户有一个暴露端点的可信 agent | §1.9「calling agent」的延伸：brain = 用户那个**已调好的 agent 本体**（人格/记忆/技能），经其对外端点抵达。**解 GUI 割裂。** |
| **P2** | **裸 provider / 本地模型（BYOL）** | 用户没有任何 agent，且显式 opt-in | §1.9「为没有 calling agent 的终端用户提供显式 provider opt-in fallback」原文。 |
| **降级** | **deterministic-only** | 以上皆不可用 | 仍返回 evidence / scaffold，不做合成。§1.9 判断法：「能输出确定性结果、证据包、候选集、骨架或可执行提示 → 合宪」。 |

**解析规则**：`P0 → P1 → P2 → deterministic-only`，确定性、有序、每任务单一来源。

> 设计要点：P1 把「BYOL」与「用我信任的 agent」统一成同一机制——区别只在 endpoint
> 指向谁。一个**有 agent** 的用户，其 GUI 的脑子被解析为他自己的 agent（P1），不再
> 是第二个脑子；一个**无 agent** 的用户走 P2，他本就没有「另一个脑子」可供割裂。

### §3.2 统一传输：OpenAI-compatible（+ ACP 适配）

P1 与 P2 是**同一传输层**（OpenAI-compatible HTTP），只差 endpoint 配置：

- Hermes Agent 可暴露为 **OpenAI-compatible HTTP 端点**（`/v1/chat/completions`），
  且以其**完整 toolset（终端/文件/web/memory/skills）**处理请求 —— 调它即调用户的
  可信 agent 本体。
- 裸 provider 与本地模型（ollama / llama.cpp / LM Studio 等）同为 OpenAI-compatible。
- OpenClaw 经 **ACP**（Agent Client Protocol，JSON-RPC 2.0）→ 一个薄 ACP 适配器。

一个 client 接口即覆盖 P1 + P2；新增宿主一般只是新增一个 endpoint 配置或薄适配器。

### §3.3 交接载荷 = CLI scaffold 原样

消费者调 CLI（如 `life-index smart-search --query "…" --include-evidence`）取得
`evidence_pack` / `scaffolded_prompt` / `answer_scaffold` / `agent_instructions`，
**原样**发给解析出的 brain。

**模块不重造 workflow / prompt —— CLI 是单一 pipeline。** 「写日志的元数据抽取」「搜索
的 info-flow / 交付物形状」等全部住在 CLI scaffold 里，维护一次；P0/P1/P2 消费的是
同一份 scaffold。（直接回应主理人「是否一套 pipeline 共同消费」的诉求。）

### §3.4 回程 = CLI validate/apply 闸门

brain 产出的任何**改变状态**的结果（拟写 / 拟改日志、拟更新 entity 等）都是
**proposal**，回经 CLI 既有命令做确定性校验后才落 L1。brain 无论多能动（哪怕是带
完整工具的 Hermes 本体），也只能产 proposal —— **桥的正确性 ≠ 数据安全；数据安全
由 CLI 闸门独立保证**。这使 P1/P2 与 brain 的能动性无关地安全。（§1.10 无第二真相源）

### §3.5 边界纪律（通过 M16 层级不变量 CI 门）

- brain-resolution + transport client = 一个 **L3 共享 helper**（建议
  `tools/agent_bridge/`，显式标注 L3）。
- **解析是确定性的**（选哪个 endpoint = 读配置 + 探测能力，无 LLM）；**真正的 LLM
  调用只发生在 L3**，永不 L2。
- **L4 GUI 经 L3 bridge 取得智能**（调用方向 L4→L3→L2，合 §1.4/§1.5）；GUI→L2 直通
  仅用于确定性操作（§1.5 第 128 行）。
- 该 helper **不得**升格进 L2（它含 LLM/provider 触点）—— RFC-05-20 §4「永不进 L2」。
  `tests/contract/test_layer_invariants.py` 守的是 **L2** 默认路径；§2.2 明确允许 **L3**
  调 LLM，故 L3 helper import OpenAI/ACP client 合规。

### §3.6 `brain` 配置 schema（确定性）

```json
{
  "brain": {
    "mode": "auto | in_context | host_agent | byol | deterministic_only",
    "endpoint": "http://localhost:8642/v1",
    "transport": "openai | acp",
    "auth_ref": "env:HERMES_API_KEY",
    "data_exposure_ack": true
  }
}
```

- `mode: auto` → 按 §3.1 解析顺序自动定级。
- `data_exposure_ack`：走 P1/P2 前**必须**为 true，且执行前清楚说明 provider 与数据
  暴露范围（§1.9 强制）。

### §3.7 Onboard 能力检测 SOP（确定性，无 LLM）

安装时一次性：检测是否有 in-context agent → 探测 Hermes(`:8642`) / OpenClaw(ACP) 是否
在场 → 写 `brain` 配置 → 发一个 trivial scaffold **探针**验证端到端 round-trip → 落定
tier。宿主升级后可重跑探针：失败即**优雅降级**到 deterministic-only / 通用 Skill floor，
并响亮报告，而非静默劣化。

## §4 Architectural Placement

`tools/agent_bridge/`（L3 共享 helper）；首个消费者 = GUI（L4）。

| 问题 | 答 |
|---|---|
| 哪层？ | L3 接口 helper。解析确定性，LLM 调用在 L3。 |
| 改 L2 吗？ | 否，纯增量。无既有 CLI 工具 / 契约变更。 |
| 平行数据路？ | 否。改状态结果回经 CLI validate/apply。 |
| 违反层隔离（§1.4）？ | 否。L4→L3→L2 合法；L3 调 LLM 合 §2.2。 |
| 违反 §1.10（plugin loader）？ | 否。静态 import 的 L3 helper，无动态发现 / registry。 |
| 生命周期 | L3/L4，1-3 年，可随生态替换，不影响 L2/L1。 |

## §5 与既有决策的关系

- **RFC-2026-05-15 §5**：本 RFC 填补其「ask a calling agent to synthesize」的 *how*。
- **RFC-2026-05-25**：P0 in-context 经其 MCP discovery / `invoke_tool` 路径达成；本 RFC
  **不反转、构建其上**。Hermes / OpenClaw 皆 MCP host，故宿主驱动路已被该 RFC 背书。
- **RFC-2026-05-20 §4**：本 RFC 遵守「永不进 L2」；bridge 留在 L3。
- **Foundation Freeze（RFC-2026-05-19）§8**：真实消费者 = GUI（主理人日常 Hermes 用法
  驱动）。**「哪个真实消费者现在需要它」是主理人不可委托的职能**；本 RFC 把「接受契约」
  与「派发实现」分离——契约可现在 accept，**实现由首个消费者（GUI）拉动**，派发时机由
  主理人按 §8 拍板。（若 `RFC-2026-05-21-phase-2-governance` 已 land，则实现并入其
  4-Milestone workflow。）
- **§1.9**：本 RFC 是其**实现**，并携带一条**增量解释条款**（additive，不削弱不变量；见 §6），经 CHARTER §5 substantive gate。

## §6 CHARTER Amendment（§1.9 增量解释条款）

本 RFC **携带一条 §1.9 增量解释**，**触发 CHARTER §5 substantive gate**（需 owner 授权），
closeout 时归档 `docs/charter-history/`。该增量解释**不修改 §1.9 任何核心规则 / 禁止项 /
默认路径，不削弱不变量**；它仅锁定「P1/P2 是被许可的实现、不得倒置为默认」这一解释，杜绝
未来对「fallback」一词的漂移性误读（长治久安 / 不留歧义）。

> **决策依据**：评审中考虑过直接**改写 §1.9 不变量**以「一等化」P1/P2，但该路径会触动
> §1.9 的防漂移护栏、反成长期隐患，故否决；改采**增量解释**（additive，不削弱不变量）。
> 主理人于 2026-06-03 拍板走增量解释方案。

### 拟新增条款（追加至 §1.9，不改原文）

> **§1.9 解释补充（RFC-2026-06-03）— 智能交接的 sanctioned 实现**
> §1.9 所称「calling agent 负责语言合成」与「无 calling agent 用户的 provider opt-in
> fallback」，其 sanctioned 实现由 RFC-2026-06-03 定义为确定性解析顺序
> **P0→P1→P2→deterministic-only**：
> - **P0** = in-context calling agent（默认，本条不变）；
> - **P1** = 经用户自有 agent 端点抵达**同一** calling agent（仍属「calling agent」，非新增 LLM 持有）；
> - **P2** = §1.9 既有 provider opt-in fallback。
>
> 本补充**不改变** §1.9 任何核心规则 / 禁止项 / 默认路径：默认仍 P0；模块默认仍不持
> LLM；L2 仍零 LLM；无 provider 仍以确定性输出满足合宪判断。它仅锁定「**P1/P2 是被
> 允许的实现、不得倒置为默认路径**」这一解释。

### 其余条款合规（不变）

| 条款 | 合规 |
|---|---|
| §1.1 数据主权 | ✅ 无云上传；bridge 不新增持久化点 |
| §1.5 确定性/智能分层 | ✅ L2 零 LLM；解析确定性，LLM 调用在 L3 |
| §1.9 Agent-Native 模块原则 | ✅ 默认 P0；P2 = §1.9 fallback 原文；无 provider → 确定性降级仍合宪；本 RFC 增量解释**强化而非削弱**本条 |
| §1.10 模块-基础层契约 | ✅ 经 CLI 契约消费；无第二真相源；无 plugin loader |
| §1.11 召回优先 | ✅ 不改 retrieval；scaffold 来自既有 CLI 输出 |

## §7 Guards / Falsifiability

**Guards（须恒为真）**：

1. `agent_bridge` 的**解析逻辑**不调用任何 LLM（解析纯确定性）。
2. **L2 默认路径不得 import `agent_bridge` 或任何 LLM client**（layer invariant）。
3. P1/P2 执行前 `data_exposure_ack` 必须为 true。
4. brain 产出的改状态结果必须回经 CLI validate/apply；bridge 不得直写
   `~/Documents/Life-Index/`。
5. `mode = deterministic_only` 时，消费者仍输出 evidence / scaffold（§1.9 合宪判断）。

**Falsifiability**：

| 测试 | 方法 | 合规期望 | 违反信号 |
|---|---|---|---|
| L2 无 LLM/bridge | `rg "agent_bridge\|openai\|anthropic" tools/<L2 默认路径>` + `test_layer_invariants.py` | 无匹配 / 通过 | L2 引入 bridge 或 LLM client |
| 解析确定性 | 同输入 + 同配置多次解析 brain 源 | 结果一致、无网络 LLM 调用 | 解析期出现 LLM 调用 |
| 数据闸门 | bridge 产出 proposal 后审计写路径 | 仅经 CLI 命令落 L1 | bridge 直写用户数据目录 |
| 数据暴露同意 | `data_exposure_ack=false` 走 P1/P2 | 被拒绝 | 未确认即外发 |
| 降级合宪 | 清空 brain 配置后调消费者 | 仍返回 evidence/scaffold | 无 brain 即报「不可用」 |

## §8 Alternatives Considered

| 方案 | 结论 |
|---|---|
| **A. 每模块各自实现 brain 接入** | 否。违 §1.9「per-module provider 配置」禁令；workflow 漂移（主理人第 2 点）。 |
| **B. 在 L2 加 `synthesize` 原语** | 否。§1.5 / §1.9 / RFC-05-20 §4「永不进 L2」。 |
| **C. GUI 内建完整 agent runtime** | 否。漂移为独立 LLM 应用（违 §1.9 身份）；且与用户可信 agent 割裂。 |
| **D. 只做 P0（纯 in-context），不做 P1/P2** | 否。无 agent 的用户拿不到智能；有 agent 用户的 GUI 仍割裂——**P1 才是 coherence 解**。 |
| **E. 把 AG-UI 标准推给宿主** | 否。AG-UI 在 harness 层尚未采纳；P0 经 MCP（已采纳）+ P1 经 OpenAI-compatible（已广泛）成本更低、更可靠。 |
| **F. 生成式自修复桥** | 推迟为实验性附录。P0/P1/P2 皆标准传输，无 bespoke 桥可坏；待真出现 bespoke 适配器再以「黄金契约 + 一致性探针 oracle + sandbox + 仅 CLI 信任锚」单独立 RFC。 |

## §9 Substantive Gate（CHARTER §5 + RFC_WORKFLOW 四件套）

- **rationale** ✅（§1）
- **≥2 反对意见 addressed** ✅（§8 列 A–F，其中 A/C/D 为对抗性反对并逐一回应）
- **影响清单** ✅（§5/§6 + §10）
- **范围** ✅（§10）

**Gate 问答**：

1. 引入 CHARTER 违反？ —— 无。§1.9 以**增量解释**方式显式记录（§6），不削弱不变量。
2. 需修宪？ —— **是**：一条 §1.9 **增量解释条款**（§6）。additive、不削弱不变量，但**触发 §5 substantive gate + owner 授权 + charter-history 归档**。
3. 真实消费者？ —— 有：GUI（主理人日常 Hermes 用法驱动）；多模块将复用（§1）。
4. 退出标准可证伪？ —— 是（§7）。
5. 制造技术债 / 锁定未来？ —— 否。bridge 是 L3，可随生态替换，不触 L2/L1。

**Gate 结论**：2026-06-03，主理人经 CHARTER §5 substantive gate 授权并 ack #1（「应该做」+ 同意 §6 拟入宪条款文字）。RFC `proposed → accepted`。CHARTER.md 写入 + `charter-history` 归档 + 代码实现，留待 worktree 实施/closeout；派发时机按 Foundation Freeze §8 主理人拍板。

## §10 Acceptance Criteria

**契约接受（本 RFC，含 CHARTER §5 gate）**：

- [x] CHARTER §5 substantive gate 通过 + owner 授权（2026-06-03，主理人）
- [x] 主理人 ack #1（「应该做」+ 同意 §1.9 增量解释条款文字）
- [x] §1.9 增量解释条款写入 `CHARTER.md`；closeout 归档 `docs/charter-history/`（commit `ba7e3c4`）
- [x] RFC status `proposed` → `accepted`

**P1 Spike 实现状态（2026-06-03，branch `agent-bridge-p1`）**：

> 以下记录 P1 spike 在该分支上实际交付的范围。spike 目的是验证核心
> 解析/传输/边界/降级路径可工作，而非完整 GUI 端到端或全 onboard SOP。

- [x] `tools/agent_bridge/`（L3）：确定性 P0→P1→P2→deterministic-only 解析顺序（`resolve.py`）
- [x] OpenAI-compatible 传输 client（`client.py`；lazy import OpenAI SDK）
      — ACP 薄适配尚未实现，留待 GUI 拉动时随需添加
- [x] `brain` 配置 schema（§3.6）落地：`BrainConfig` dataclass 含 `mode` / `endpoint` /
      `transport` / `api_key` / `model` / `data_exposure_ack`；`require_ack()` 强制门
- [x] `handoff.py`：完整交接流（subprocess L2 smart-search → resolve → maybe synthesize）
- [x] `test_layer_invariants.py` 扩展：agent_bridge 不 import L2 internals、不引用用户数据目录
- [x] **降级探针**：`test_degrade_path_no_endpoint`（always-on）—— 清空 brain 配置后
      handoff 返回 `source=deterministic_only`、`synthesis=None`、scaffold 仍在
- [x] **Hermes 探针 harness**：`test_p1_round_trip_via_real_hermes`（env-gated，需
      `LIFE_INDEX_BRAIN_ENDPOINT` 指向可达端点 + `LIFE_INDEX_BRAIN_ACK=1`）——
      已在本机 Hermes OpenAI-compatible endpoint 上完成验证
- [ ] **P2 探针**：未实现（spike 范围不含 P2）
- [x] **最小 operator surface**：`agent-bridge probe --json` 可做无 journal evidence 的
      endpoint / model / ack / token-presence preflight；完整 onboard 自动配置 SOP 仍不在本 slice
      范围内

**实现验收（由首个消费者 GUI 拉动，post-ack；派发时机按 Freeze §8 主理人拍板）**：

- [x] `tools/agent_bridge/`（L3）：确定性解析 + OpenAI-compatible 传输（ACP 薄适配留待 GUI 拉动）
- [x] `brain` 配置 schema（§3.6）落地，含 `data_exposure_ack` 强制
- [x] 最小 operator surface：host-agent bridge runbook + `agent-bridge probe --json`
- [x] `test_layer_invariants.py` 通过（L2 无 `agent_bridge` / LLM client import）
- [x] **P1 真机探针**：本机 Hermes `:8642` → 消费 smart-search scaffold → 合成通过
      — GUI 与状态变更 proposal 的 CLI validate/apply UX 仍作为未来消费者路径，不在本 slice 实现
- [ ] **P2 探针**：对一个 OpenAI-compatible provider 通过
- [x] **降级探针**：清空 brain 配置，deterministic-only 仍输出 evidence/scaffold

**范围（在做 / 不做）**：

- **在做**：交接契约（解析顺序 / 传输 / 载荷=CLI scaffold / 回程=validate-apply 闸门）、
  `brain` 配置 schema、onboard 检测 SOP、GUI 作参考消费者、L3 `agent_bridge` helper。
- **不做**：GUI 本身的实现、各具体高级模块（Memoir 等）、生成式自修复（§8-F 附录）、
  任何 L2 改动、多 agent 编排。
