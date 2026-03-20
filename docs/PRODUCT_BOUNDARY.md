# Life Index Product Boundary

> **文档角色**: 定义 Life Index v1.x 的正式产品边界
> **目标读者**: 项目 Owner、贡献者、评审者、后续执行的 Agent
> **Authority**: 产品边界决策备忘录；运行时接口与参数真相仍以上游 SSOT 文档和代码为准

---

## 1. 一句话产品定义

**Life Index 是一个 local-first、agent-first 的个人人生日志与检索系统，不是通用生活管理平台，也不是 Agent 记忆基础设施。**

---

## 2. 为什么需要这份文档

仓库已经明确了很多边界信号，但它们分散在 README、架构文档、工作流文档、scheduler 指南与 review 文档中。

这份文档的目的不是扩张能力，而是把已经成立的产品边界压缩成一个稳定、可引用的判断：

- 什么属于 Life Index 核心产品
- 什么属于 Agent / 宿主平台 orchestration
- 什么未来可以作为应用层壳存在，但不能反过来改写产品身份

---

## 3. 三层模型

## 3.1 Layer A — Core Product

Life Index 核心产品包含：

- 用户拥有的数据模型：`~/Documents/Life-Index/` 下的 journals、attachments、indexes、config
- 原子且可靠的 journaling tools 与统一 CLI
- 写入、检索、编辑、摘要、索引维护等显式能力
- 本地优先、可读可迁移的 Markdown + YAML 数据约定

### Layer A 的判断标准

如果一个能力满足以下特征，它更可能属于核心产品：

- 直接服务于“记录人生碎片”和“检索过去人生”
- 必须依赖明确、可验证、可恢复的 deterministic tool contract
- 不需要隐藏常驻进程或平台级后台运行时
- 与 durable user data 有直接关系

---

## 3.2 Layer B — Agent / Host-Platform Orchestration

这一层负责把核心能力组织成用户体验，但它不应被误写成核心运行时。

当前应归入这一层的内容包括：

- 从自然语言中理解用户意图
- 抽取或整理结构化 metadata 候选
- 处理确认循环（如 `needs_confirmation`）
- 串联多工具工作流（例如先查天气再编辑）
- 安装后的可选 customization
- 依赖宿主平台能力的可选 automation / scheduling
- 面向用户的回答组织、解释与体验包装

### Layer B 的关键规则

- orchestration 可以很强，但不等于核心工具应变成超级入口
- orchestration 失败不应自动等同于核心产品失败
- 宿主平台能力属于外层增强，不是产品安装完成的前置条件

---

## 3.3 Layer C — Future Application Layer

未来如果出现 GUI、timeline browser、dashboard shell、packaging shell 或其他更易用的访问层，它们只能被视为 Layer A + Layer B 之上的可选壳层。

### Layer C 可接受的前提

- 仍以同一份本地用户数据为中心
- 不破坏现有 durable data / compatibility 承诺
- 不把隐藏服务层变成新的产品中心
- 不宣称自己取代了核心 CLI / tool contract 的权威性
- 主要提供 convenience，而不是改写产品本体

### Layer C 不应跨越的边界

- 不能把 Life Index 改写成通用 digital life manager
- 不能把产品重定义为 Agent memory substrate
- 不能让云同步、协作、多租户后台服务成为默认中心
- 不能让 dashboard / app chrome 的重要性高于 journaling core

---

## 4. 产品原生 vs orchestration 组合

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

## 5. 当前接受的产品方向

v1.x 当前接受并鼓励的方向是：

- 继续收敛 canonical workflows
- 继续澄清 Agent vs Tool 边界
- 优先保护本地数据、兼容性与升级清晰度
- 在不改变产品身份的前提下，改善 onboarding、distribution、operator experience
- 允许未来出现更友好的应用层壳，但必须从属而非改写核心产品

---

## 6. 当前默认拒绝的方向

除非后续有压倒性新证据，否则以下方向默认拒绝：

- 把 Life Index 做成通用生活管理平台
- 把 scheduling / reminder / delivery infrastructure 做成核心运行时
- 把 Agent 记忆优化作为主产品目标
- 为了“先进感”过早协议化或平台化
- 让 cloud-centric、collaboration-centric、resident-service-centric 形态成为默认产品身份

---

## 7. 相关边界判断

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

## 8. Maintainer Rule of Thumb

遇到新的想法时，按这个顺序问：

1. 它是否直接服务于“人生日志与检索系统”这一核心定义？
2. 它是否更适合由 Agent / 宿主平台 orchestration 完成，而不是推入核心工具？
3. 如果它是未来壳层，它是否只是 convenience layer，而不是新产品中心？
4. 如果它会引入隐藏运行时、服务层或新的默认产品身份，是否应该先拒绝？

如果不能明确通过这四问，就不要把它写成核心产品承诺。

---

## 9. SSOT / Related Documents

- `README.md` / `README.en.md` — 产品定位与对外叙事
- `docs/ARCHITECTURE.md` — 架构原则与系统边界
- `docs/EXECUTION_PRIORITIES.md` — v1.x 执行优先级与 roadmap guardrails
- `SKILL.md` — skill-facing workflow truth
- `docs/API.md` — 工具接口与返回契约
- `references/WEATHER_FLOW.md` — 天气相关 caller/tool 边界与 correction flow
- `references/schedule/SCHEDULE.md` — 可选自动化边界
- `docs/review/PROJECT_DIAGNOSIS_AND_ROADMAP.md` — review-scoped 诊断与路线背景
- `docs/review/execution/TOOL_RESPONSIBILITY_MATRIX.md` — Agent / Tool 职责边界细化
