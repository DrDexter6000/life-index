---
type: implementation-rfc
status: accepted
charter-amendment: "新增 §1.12 运行时/平台可移植性不变量 + §4.1 镜像反模式（additive，不修改或削弱任何 §5.3 保护条款）"
created: 2026-06-14
approved: 2026-06-14
approved-by: Life Index Developer
title: 运行时与平台可移植性宪章修正案（Runtime & Platform Portability Charter Amendment）
related:
  - CHARTER.md §1.9 §1.10 §1.12 §4.1 §5.2 §5.3
  - docs/ARCHITECTURE.md
---

# RFC-2026-06-14: 运行时与平台可移植性宪章修正案

## §1 Rationale

### 背景

Life Index 定位为 agent 生态的 CLI 基元层（CHARTER §1.9）。其集成对象——agent
runtime 与宿主平台——是多样且持续演进的：用户可能使用 Hermes、Claude Code、Codex
或其它 runtime；宿主平台可能是 Linux、macOS 或 Windows+WSL。

### 问题

当前 CHARTER 对「如何在不同 runtime / 平台间保持可移植性」缺少明确的不变量约束。
这导致以下风险：

1. **Runtime 锁定**：代码中可能出现针对特定 runtime 的排他分支（如
   `if runtime == "Hermes"`），使其它合规 runtime 功能断裂。
2. **端点假设泄漏**：代码可能将某 runtime 的私有 API 形状（特定 `/v1` 路径、特定
   JSON 字段）当作通用假设硬编码，破坏跨 runtime 互操作性。
3. **平台路径硬编码**：代码可能直接写入 WSL 路径（`/home`、`/mnt`）或 Windows
   盘符，导致跨平台部署时不可移植。

### 目标

新增 CHARTER §1.12 不变量，确立「换 runtime 或换 OS，只应改配置、不应改代码」的
宪章级承诺。同步在第四章反模式黑名单中加入对应镜像条目。

## §2 Non-Goals

本 RFC **明确拒绝**：

| Non-goal | 拒绝理由 |
|---|---|
| 要求代码在每种 runtime/平台上通过 CI | 这是实现层验证策略，非宪章级不变量；配置+runbook 覆盖即可 |
| 禁止为不同平台提供不同默认配置 | §1.12 明确允许（✅）不同平台的默认配置/runbook |
| 将 §1.12 加入 §5.3 不可弱化清单 | §1.12 是重要不变量，但不触及 §5.3 所保护的「数据主权/纯文本/向下兼容/召回优先」四条对用户的终极承诺；定位为第一章不变量但非 §5.3 级别 |
| 修改或削弱任何既有 §5.3 保护条款 | 本 RFC 是纯 additive 的，不触 §§5.3 中的 §1.1、§1.2、§1.6、§1.11 |

## §3 Design

### §3.1 新增 CHARTER §1.12（运行时/平台可移植性）

插入位置：CHARTER 第一章末尾，§1.11（召回优先检索真实模型）之后、第二章之前。

完整内容见 `CHARTER.md` 第 302–329 行。核心条款：

- **核心规则**：Agent 集成走标准协议（ACP），经配置选择 runtime；runtime/平台特异性
  进配置+runbook；backing LLM 由 runtime 自持。
- **明确禁止**：`if runtime == "X"` 排他分支、私有端点/字段形状通用化、平台路径硬编码。
- **明确允许**：capability 探测后的专门适应、不同平台默认配置/runbook。
- **判断方法**：「换 runtime 或换 OS，是只改配置还是必须改代码？」

### §3.2 新增 §4.1 镜像反模式

在 CHARTER §4.1（架构违宪）末尾追加三条 runtime/portability 反模式：

1. 以 runtime 名称做排他分支，使其它合规 runtime 功能断裂
2. 把某 runtime 私有端点/字段形状当通用假设硬编码
3. 将平台特异路径写进代码而非配置

### §3.3 ARCHITECTURE.md 指针

在 `docs/ARCHITECTURE.md` §0 原则镜像表中新增一行，指向 `CHARTER §1.12`。

## §4 与既有条款的关系

### §4.1 §5.3 非冲突声明

本修正案 **不修改、不削弱** 以下 §5.3 保护条款：

| §5.3 保护条款 | 状态 |
|---|---|
| §1.1 数据主权 | ✅ 不变 — §1.12 不涉及用户数据存储或云端上传 |
| §1.2 纯文本永久性 | ✅ 不变 — §1.12 不涉及数据格式 |
| §1.6 向下兼容 | ✅ 不变 — §1.12 不涉及数据读取兼容性 |
| §1.11 召回优先检索真实模型 | ✅ 不变 — §1.12 不涉及检索行为 |
| §5.3 自身 | ✅ 不变 — §1.12 未加入 §5.3 清单 |

### §4.2 与其它不变量关系

| 条款 | 关系 |
|---|---|
| §1.9 Agent-Native 模块原则 | 正交 — §1.9 防 LLM 捆绑，§1.12 保 runtime/平台可移植 |
| §1.10 模块-基础层契约边界 | 正交 — §1.10 定契约边界，§1.12 保集成面可移植 |

## §5 影响清单

| 受影响的文件/区域 | 变更类型 |
|---|---|
| `CHARTER.md` 第一章（新增 §1.12） | 新增 28 行 |
| `CHARTER.md` 第四章 §4.1（追加 3 条） | 新增 3 行 |
| `docs/ARCHITECTURE.md` §0 表格 | 新增 1 行 |
| `docs/rfc/RFC-2026-06-14-runtime-platform-portability.md` | 新增文件 |

**不破坏**任何既有 RFC、ADR 或测试用例。

## §6 Acceptance Criteria

- [x] §1.12 已写入 `CHARTER.md`，文本匹配本 RFC §3.1 设计
- [x] §4.1 三条 mirror 反模式已追加
- [x] `docs/ARCHITECTURE.md` §0 表格已新增 §1.12 指针行
- [x] `docs/rfc/RFC-2026-06-14-runtime-platform-portability.md` 存在且格式正确
- [x] `git diff --check` 无空白错误
- [x] 所有修改仅涉及允许路径（CHARTER.md、docs/ARCHITECTURE.md、docs/rfc/、.agent-reports/）
- [x] 公开文件中无内部或私有名称、无本地分支/提交/路径/私人引用

## §7 Substantive Gate（CHARTER §5）

- **rationale** ✅（§1 — 背景、问题、目标）
- **≥2 反对意见 addressed** ✅（§2 Non-Goals 表格：4 条明确拒绝及理由）
- **影响清单** ✅（§5）
- **主理人 ack 签字**：✅ Life Index Developer, 2026-06-14

**Gate 问答**：

1. 引入 CHARTER 违反？ — **无**。纯 additive 修正案，不修改任何既有条款。
2. 需修宪？ — **是**：新增 §1.12 不变量，需通过 §5 substantive gate。
3. §5.3 条款受影响？ — **否**。见 §4.1 非冲突声明。
4. 真实需求？ — **是**。以 Hermes、Claude Code、Codex 为公开示例的多 runtime
   生态需要此不变量；跨 Linux/macOS/Windows+WSL 的可移植性是 §1.12 的直接动机。

## §8 Alternatives Considered

| 方案 | 结论 |
|---|---|
| **A. 只在实现层添加配置抽象，不修宪** | 否。缺少宪章级约束会导致未来 runtime/平台分支在代码中扩散，§1.7「宁可功能简单」不支持为每个 runtime 维护代码分支。 |
| **B. 将 §1.12 加入 §5.3 不可弱化清单** | 否。§5.3 保护的是「对用户的终极数据承诺」；runtime/portability 是重要的架构不变量但不属于同一保护层级。 |
| **C. 仅为 Windows 提供适配，不要求 Linux/macOS** | 否。§1.12 明确要求保持跨平台可移植性；平台特异配置是允许的，但平台锁定代码分支被禁止。 |

## §9 Approval

| 角色 | 状态 |
|---|---|
| CHARTER §5 substantive gate | ✅ passed (2026-06-14, per written maintainer approval on 2026-06-14) |
| 主理人 ack 签字 | ✅ Life Index Developer |

---

> 本 RFC 遵循 CHARTER §5.2 修订流程：起草 RFC → substantive gate（4 项齐备方可 land）→ 版本递增 → 联动更新。
