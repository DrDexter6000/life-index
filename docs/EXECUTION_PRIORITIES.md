# Life Index v1.x Execution Priorities

> **文档角色**: 定义 Life Index v1.x 的正式执行优先级与 roadmap guardrails
> **目标读者**: 项目 Owner、贡献者、评审者、后续执行的 Agent
> **Authority**: 主动开发与文档收敛的优先级备忘录；产品身份以上游 `docs/PRODUCT_BOUNDARY.md` 为准

---

## 1. 一句话执行方向

**v1.x 的主线不是继续扩功能，而是继续收敛 canonical workflows、固化 Agent / Tool 边界、补强验证闭环，并降低真实使用门槛。**

---

## 2. 为什么需要这份文档

产品边界已经明确，但边界本身并不会自动告诉后续执行者：

- 现在最该做什么
- 哪些事情可以做，但不该现在做
- 哪些方向默认不该进入 v1.x 主线

这份文档的作用，就是把 `docs/PRODUCT_BOUNDARY.md` 转成可执行的优先级顺序。

---

## 3. v1.x 当前最高优先级

## P0 — Canonical Workflow 收敛

这是当前最重要的主线。

优先完成：

- 固化 write / search / edit 三条黄金路径
- 把谁负责决策、谁负责执行、谁负责确认、谁负责兜底讲清楚
- 收敛 `needs_confirmation`、weather/edit coupling、write-through / rebuild 等关键语义
- 把现在主要依赖文档记忆的正确流程，尽可能变成更稳定、可验证的契约

### P0 的目标结果

- 新调用者不需要“知道内情”也能理解主流程
- Tool 不继续膨胀成超级入口
- Agent / Tool / host-platform 的职责边界更难被误用

---

## P1 — Validation / Eval / Contract Proof

当 workflow 已经被说清楚后，下一步不是立刻扩产品，而是证明这些判断能稳定成立。

优先完成：

- 把关键 workflow 约束转成更可复用的 eval / checklist / test evidence
- 优先验证容易被误用的边界：
  - `needs_confirmation`
  - location / weather coordination
  - write success vs side-effect success
  - retrieval execution vs user-facing interpretation
- 减少“文档这么写了，但运行时未被验证”的灰区

### P1 的目标结果

- 关键产品约束不仅能说清，还能被重复验证
- 后续调整时更容易知道有没有破坏产品契约

---

## P1 — Onboarding / Distribution / Upgrade Experience

这条线与上一条并列重要，但优先级略后于 workflow clarity 本身。

优先完成：

- 继续降低 fresh install 与 first-use friction
- 保持 repo-first、CLI-first 的升级与验证路径清晰
- 修复真实 operator 会遇到的使用阻塞点，而不是为了“技术先进感”扩层
- 维持 onboarding / upgrade / compatibility / version policy 的一致叙事

### P1 的目标结果

- 用户或 Agent 能稳定安装、验证、升级
- 分发体验改善不以引入额外协议层或服务层为代价

---

## P2 — Core Reliability / Retrieval Quality Improvements

只有当以下条件同时满足时，这类工作才应进入主线：

- 它直接改善 journaling core
- 它不会模糊产品身份
- 它不会引入明显更大的复杂度债务

适合放在这一层的工作包括：

- 搜索与索引可靠性增强
- 更清晰的 failure semantics
- 更稳健的跨平台行为
- 对已有核心命令的质量提升

### P2 的规则

- 优先做“小而硬”的可靠性改进
- 不借可靠性名义偷渡大范围产品扩张

---

## 4. 可以做，但不该现在做

以下方向可以保留在 parking lot，但不应进入当前主线：

- Future app shell / GUI / dashboard shell
- 更丰富的 timeline browsing experience
- repo-first 之外的分发扩展（如更重的 installer / package channel）
- MCP / protocol adapter
- 更强的 optional automation recipe 扩展

这些方向的问题不是“永远不能做”，而是：

- 它们依赖已经稳定的 workflow model
- 它们依赖已经清楚的 product contract
- 它们很容易分散当前最重要的收敛工作

---

## 5. 默认拒绝的方向

除非出现压倒性新证据，否则 v1.x 默认拒绝：

- 把 Life Index 做成通用生活管理平台
- 把 scheduler / reminder / delivery infrastructure 变成核心运行时
- 把 Agent memory optimization 变成主产品目标
- 把 resident service、后台进程、云中心能力变成默认架构中心
- 为了“像平台”而过早协议化、服务化、app 化

这些拒绝项不是独立新增规则，而是 `docs/PRODUCT_BOUNDARY.md` 的执行层翻译。

---

## 6. 新工作进入主线前的判断规则

在接受任何新的实现方向前，先问：

1. 它是否直接帮助收敛 canonical workflow？
2. 它是否直接降低真实安装、升级、使用摩擦？
3. 它是否直接补强产品契约的验证证据？
4. 它是否会把本应属于 orchestration 或 future shell 的逻辑推入核心？

### 进入主线的默认门槛

满足前 3 问之一，且第 4 问答案为“不会”，才应优先进入当前主线。

否则：

- 放入 parking lot
- 或明确拒绝

---

## 7. 当前最合理的后续执行顺序

按逻辑顺序，v1.x 后续最合理的执行顺序应当是：

1. 继续把 canonical workflows 变成更稳定的正式文档与契约
2. 对关键 workflow 补充更强的 eval / verification evidence
3. 收敛剩余 onboarding / operator friction
4. 只在前 3 项持续稳定后，才考虑 future shell 或 protocol adapter 类议题

---

## 8. 当前推荐的下一个具体主题

在本文件落地之后，最合逻辑的下一个执行主题是：

### Workflow Contract Consolidation

也就是继续把这些问题变成更稳定的正式契约：

- write flow 的主体成功 / 增强成功 / 修复路径语义
- edit + weather 的 caller-owned orchestration 规则
- search result 与 agent answer 的职责边界
- 哪些 workflow 仍然只存在于 review 文档，而尚未提升到更稳定的正式层级

---

## 9. 与其他文档的关系

- `docs/PRODUCT_BOUNDARY.md` 定义“产品是什么 / 不是什么”
- 本文档定义“既然边界已定，那么 v1.x 现在应优先做什么”
- `docs/review/PROJECT_DIAGNOSIS_AND_ROADMAP.md` 保留 review-scoped 诊断背景，不再单独承担正式优先级判断

---

## 10. Maintainer Rule of Thumb

如果一个想法听起来“很酷”，但不能明确证明它比 workflow clarity、contract proof、operator experience 更重要，那它大概率不该进入 v1.x 当前主线。
