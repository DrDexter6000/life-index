# Life Index Product Boundary

> **文档角色**: 定义 Life Index v1.x 的正式产品边界与执行优先级
> **目标读者**: 项目 Owner、贡献者、评审者、后续执行的 Agent
> **Authority**: 产品边界决策备忘录与 v1.x roadmap guardrails；运行时接口与参数真相仍以上游 SSOT 文档和代码为准

---

## 1. 一句话产品定义

**Life Index 是一个 local-first、agent-first 的个人人生日志与检索系统，不是通用生活管理平台，也不是 Agent 记忆基础设施。**

---

## 2. 三层模型

### 2.1 Layer A — Core Product

Life Index 核心产品包含：

- 用户拥有的数据模型：`~/Documents/Life-Index/` 下的 journals、attachments、indexes、config
- 原子且可靠的 journaling tools 与统一 CLI
- 写入、检索、编辑、摘要、索引维护等显式能力
- 本地优先、可读可迁移的 Markdown + YAML 数据约定

如果一个能力满足以下特征，它更可能属于核心产品：

- 直接服务于"记录人生碎片"和"检索过去人生"
- 必须依赖明确、可验证、可恢复的 deterministic tool contract
- 不需要隐藏常驻进程或平台级后台运行时
- 与 durable user data 有直接关系

---

### 2.2 Layer B — Agent / Host-Platform Orchestration

这一层负责把核心能力组织成用户体验，但它不应被误写成核心运行时。

当前应归入这一层的内容包括：

- 从自然语言中理解用户意图
- 抽取或整理结构化 metadata 候选
- 处理确认循环（如 `needs_confirmation`）
- 串联多工具工作流（例如先查天气再编辑）
- 安装后的可选 customization
- 依赖宿主平台能力的可选 automation / scheduling
- 面向用户的回答组织、解释与体验包装

关键规则：

- orchestration 可以很强，但不等于核心工具应变成超级入口
- orchestration 失败不应自动等同于核心产品失败
- 宿主平台能力属于外层增强，不是产品安装完成的前置条件

---

### 2.3 Layer C — Future Application Layer

未来如果出现 GUI、timeline browser、dashboard shell、packaging shell 或其他更易用的访问层，它们只能被视为 Layer A + Layer B 之上的可选壳层。

可接受的前提：

- 仍以同一份本地用户数据为中心
- 不破坏现有 durable data / compatibility 承诺
- 不把隐藏服务层变成新的产品中心
- 不宣称自己取代了核心 CLI / tool contract 的权威性
- 主要提供 convenience，而不是改写产品本体

不应跨越的边界：

- 不能把 Life Index 改写成通用 digital life manager
- 不能把产品重定义为 Agent memory substrate
- 不能让云同步、协作、多租户后台服务成为默认中心
- 不能让 dashboard / app chrome 的重要性高于 journaling core

---

## 3. 产品原生 vs orchestration 组合

### 产品原生（应由项目直接声明为核心能力）

- 自然语言日志记录
- 结构化 frontmatter / metadata 支持
- 多维索引与检索
- journal 编辑
- 月报 / 年报生成工具本身
- 本地数据隔离与长期可读性

### orchestration 组合（可以支持，但不应被写成核心运行时）

- 基于用户偏好的确认与澄清对话
- 复杂 multi-step operator flow
- post-onboarding customization
- 可选 recurring reports 的宿主平台调度
- 平台相关的交互、推送、提醒或自动化体验

---

## 4. 相关边界判断

### 关于 Scheduler

- scheduler setup 属于 Layer B
- `references/schedule/SCHEDULE.md` 描述的是可选 host-platform automation guide
- 不代表 Life Index 核心内建 scheduler runtime

### 关于 MCP / Protocol Layer

- MCP 仍然是 deferred decision
- 当前产品重心是稳定 capability model 和 workflow model
- 协议适配层如果未来出现，也只能是外层适配，不应先于产品边界收敛

### 关于 Future App Shell

- future shell 可以被探索
- 但只有在不破坏本地数据中心、工具契约中心、产品身份中心的前提下才成立

---

## 5. v1.x 执行优先级

**v1.x 的主线不是继续扩功能，而是继续收敛 canonical workflows、固化 Agent / Tool 边界、补强验证闭环，并降低真实使用门槛。**

### P0 — Canonical Workflow 收敛

这是当前最重要的主线。

优先完成：

- 固化 write / search / edit 三条黄金路径
- 把谁负责决策、谁负责执行、谁负责确认、谁负责兜底讲清楚
- 收敛 `needs_confirmation`、weather/edit coupling、write-through / rebuild 等关键语义
- 把现在主要依赖文档记忆的正确流程，尽可能变成更稳定、可验证的契约

目标结果：

- 新调用者不需要"知道内情"也能理解主流程
- Tool 不继续膨胀成超级入口
- Agent / Tool / host-platform 的职责边界更难被误用

### P1 — Validation / Eval / Contract Proof

当 workflow 已经被说清楚后，下一步不是立刻扩产品，而是证明这些判断能稳定成立。

优先完成：

- 把关键 workflow 约束转成更可复用的 eval / checklist / test evidence
- 优先验证容易被误用的边界（`needs_confirmation`、location/weather coordination、write success vs side-effect success、retrieval vs interpretation）
- 减少"文档这么写了，但运行时未被验证"的灰区

### P1 — Onboarding / Distribution / Upgrade Experience

与上一条并列重要，但优先级略后于 workflow clarity 本身。

优先完成：

- 继续降低 fresh install 与 first-use friction
- 保持 repo-first、CLI-first 的升级与验证路径清晰
- 修复真实 operator 会遇到的使用阻塞点

### P2 — Core Reliability / Retrieval Quality

只有当以下条件同时满足时才应进入主线：直接改善 journaling core、不模糊产品身份、不引入明显更大的复杂度债务。

适合放在这一层的工作：搜索与索引可靠性增强、更清晰的 failure semantics、更稳健的跨平台行为、已有核心命令的质量提升。

> **状态更新**: 第一轮高优先级 workflow contract 已分别上提到 `docs/API.md`、`SKILL.md`、`references/WEATHER_FLOW.md`；下一轮应处理剩余仍停留在 review 层的 workflow rules。

---

## 6. 当前默认拒绝的方向

除非后续有压倒性新证据，否则以下方向默认拒绝：

- 把 Life Index 做成通用生活管理平台
- 把 scheduling / reminder / delivery infrastructure 做成核心运行时
- 把 Agent 记忆优化作为主产品目标
- 为了"先进感"过早协议化或平台化
- 让 cloud-centric、collaboration-centric、resident-service-centric 形态成为默认产品身份

---

## 7. Parking Lot（可以做，但不该现在做）

以下方向可以保留，但不应进入当前主线：

- Future app shell / GUI / dashboard shell
- 更丰富的 timeline browsing experience
- repo-first 之外的分发扩展（如更重的 installer / package channel）
- MCP / protocol adapter
- 更强的 optional automation recipe 扩展

它们依赖已经稳定的 workflow model 和 product contract，且很容易分散当前最重要的收敛工作。

---

## 8. 新工作进入主线前的判断规则

在接受任何新的实现方向前，先问：

1. 它是否直接帮助收敛 canonical workflow？
2. 它是否直接降低真实安装、升级、使用摩擦？
3. 它是否直接补强产品契约的验证证据？
4. 它是否会把本应属于 orchestration 或 future shell 的逻辑推入核心？

满足前 3 问之一，且第 4 问答案为"不会"，才应优先进入当前主线。否则放入 parking lot 或明确拒绝。

---

## 9. Maintainer Rule of Thumb

遇到新的想法时，按这个顺序问：

1. 它是否直接服务于"人生日志与检索系统"这一核心定义？
2. 它是否更适合由 Agent / 宿主平台 orchestration 完成，而不是推入核心工具？
3. 如果它是未来壳层，它是否只是 convenience layer，而不是新产品中心？
4. 如果它会引入隐藏运行时、服务层或新的默认产品身份，是否应该先拒绝？

如果不能明确通过这四问，就不要把它写成核心产品承诺。

如果一个想法听起来"很酷"，但不能明确证明它比 workflow clarity、contract proof、operator experience 更重要，那它大概率不该进入 v1.x 当前主线。

---

## 10. 相关文档

- `README.md` / `README.en.md` — 产品定位与对外叙事
- `docs/ARCHITECTURE.md` — 架构原则与系统边界
- `SKILL.md` — skill-facing workflow truth
- `docs/API.md` — 工具接口与返回契约
- `docs/UPGRADE.md` — 版本语义、兼容性承诺与升级指南
- `references/WEATHER_FLOW.md` — 天气相关 caller/tool 边界与 correction flow
- `references/schedule/SCHEDULE.md` — 可选自动化边界
- `docs/archive/review-2026-03/PROJECT_DIAGNOSIS_AND_ROADMAP.md` — review-scoped 诊断与路线背景（已归档）
- `docs/archive/review-2026-03/TOOL_RESPONSIBILITY_MATRIX.md` — Agent / Tool 职责边界细化
