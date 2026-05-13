# CN-003: L1/L2 Future Compatibility Baseline 副审与 DeepSeek 审计记录

> **状态**: 原始审计意见归档
> **日期**: 2026-05-13
> **性质**: 全文记录；非执行路线图；非产品承诺
> **相关讨论记录**: `docs/concepts/CN-002-life-index-terminal-architecture-discussion-record.md`
> **相关决策**: `docs/adr/ADR-026-l1-l2-future-compatibility-baseline.md`
> **相关 RFC**: `docs/rfc/RFC-2026-05-13-l1-l2-future-compatibility-baseline.md`

本文归档副审_Opus 与 码农C_DeepSeek 对 L1/L2 Future Compatibility Baseline 文档群的 read-only 审计意见，用于未来战略回顾。稳定规则以 CHARTER / Architecture / API / ADR / RFC 为准。

---

## 1. 副审_Opus 审计意见全文

事实核查完成：CHARTER §1.5 确实写明"L2 内部不得调用 LLM"，§1.4/§2 已锁 L2 5-10 年生命周期；ARCHITECTURE §1.4 编号无冲突；ADR INDEX 16 个 ADR 文件实际存在（核对 `ls` 输出，math 通过）。

下面是副审_Opus 的 read-only 审计意见。

---

# 副审_Opus · L1/L2 Future Compatibility Baseline 第三轮固化审计

## A. 总体判断

**可以推进固化**。CN-002 / ADR-026 / RFC-2026-05-13 / ARCHITECTURE §1.4 四件套相互一致，方向上忠实于三轮讨论的最终对齐结果，关键红线没有走样。下列问题属于"建议在 commit 前一并清理"，不构成 block。

我此前两轮提出的硬约束都在最终产物中找到了对应条款：

| 我此前的硬约束 | 落点 | 状态 |
|---|---|---|
| L2 永不调 LLM（与 CHARTER §1.5 不冲突） | ADR-026 §7 / RFC §7 / ARCH §1.4 | ✓ |
| Anti-requirements 作为独立交付物 | ADR-026 §7、RFC §7 | ✓ |
| 幂等 + 可寻址中间制品 + 断点恢复 | ADR-026 §5（Addressable intermediate artifacts） | ✓ |
| Index Tree 节点禁存 LLM 派生结论；若引入须 provenance + 可关闭 + 不参与默认召回 | ADR-026 §3 / RFC §5 末段 | ✓ |
| 大版本门槛 = 契约门槛 + 评估门槛，非功能门槛 | ADR-026 Versioning / RFC §8 | ✓ |
| 评估契约扩张到证据覆盖、事实正确性、契约稳定性 | ADR-026 §6 | ✓ |
| 拒绝 GPT 的 "agent-native tool substrate" 措辞 | 未出现在任一固化文档 | ✓ |

CHARTER §1.5 的硬红线（L2 不得调 LLM）经 grep 核实存在于 `CHARTER.md:212`、`:126`、`:296`，因此 ADR-026 §7 不是新增约束，而是把已存在的红线进一步**展开为数据形态层面的禁存清单**（persona/emotion/relationship/narrative/digital letters）。这一展开必要且无矛盾。

---

## B. 需要在 commit 前清理的一致性瑕疵

### B.1 三份文档的 Anti-requirements 清单不完全对齐（**应统一**）

- **RFC §7**：persona / emotion / relationship / narrative / digital letters / **creative emulation** / cross-journal LLM reasoning / any LLM call
- **ADR-026 §7**：persona / emotion / relationship / narrative / digital letters / cross-journal LLM reasoning / any LLM call（**少了 creative emulation**）
- **ARCH §1.4**：persona / emotion / relationship judgment / narrative synthesis / digital letters（**少了 creative emulation、cross-journal、any LLM call**）

后续会有人 grep "L2 anti-requirements" 来引用。建议：ADR-026 §7 作为**单一权威列表**，RFC §7 和 ARCH §1.4 都改写为"参见 ADR-026 §7"，避免日后任何一份漂移。

### B.2 Claim Envelope 类型枚举的归属错位

RFC §6 列出 5 个 claim type（`measurable_exact / measurable_approximate / interpretive_evidence_backed / creative_emulation / not_measurable`），ADR-026 §2 只笼统说"declare type / confidence / evidence / counter-evidence / limitations"，不枚举。

由于 RFC 是 Draft，ADR 是 Accepted —— **真正具有"决策约束力"的枚举应当落在 ADR**，否则未来 RFC 被替换/废弃时枚举会一起消失。

建议：把 5 类枚举移入 ADR-026 §2，RFC §6 改为引用。

### B.3 RFC §10 Q4 是结构性 gate，不是普通 open question

> Q4: What is the first external/separable advanced module used to validate the major-version gate?

ADR-026 的大版本判据是"至少一个外部/可分离高级模块能在不修改 L1/L2 的前提下跑出 long-horizon analysis"。Q4 没回答之前，**这个 gate 本身是不可证伪的**（永远可以说"还没找到验证模块"）。

建议：把 Q4 从 "Open Questions" 提升为 RFC §8 / ADR Versioning 的明确遗留事项（"gate validation candidate to be selected in a separate RFC"），不要和真正可延后的 Q1/Q2/Q3 平铺。

---

## C. 一个结构性问题（建议明示，不必修改）

ADR-026 §7 把"L2 不得存储 persona / emotion / relationship / narrative 等派生结论"作为约束写下。

- 这条**不是** CHARTER §1.5（CHARTER §1.5 只禁 LLM call，不直接禁数据形态）。
- 它是 ADR-026 这一份 📋 Decision 文档创造的新架构约束。
- 这是合规的（📋 Decision 允许在不修宪的前提下创建实现层约束）。
- 但如果 5 年后回顾，**没有任何 grep 路径会从 CHARTER 找到这条规则**，违规者可能在不读 ADR-026 的情况下违反它。

建议在 ADR-026 §Consequences 末尾补一句明示：

> 在 Charter 修订完成前，本 ADR §7 的 anti-requirements 清单具有架构决策级（📋 Decision）约束力。任何引入相关数据形态/能力到 L2 的提议，必须先废除或修订本 ADR。

这样未来的 RFC 审阅者会清楚知道：要在 L2 加 persona 字段，**必须先动 ADR-026，不能绕过**。

---

## D. 治理流程合规性

用户原话明确："RFC + 冷静期 + 作者签字"，"最后产出的结论要固化到最高 SSOT 文档体系"。

- CHARTER 未被直接 edit ✓（正确遵守 §5 修订流程，等冷静期/签字）
- ARCHITECTURE / ADR / RFC / CN-002 全部就位 ✓
- **RFC 元数据未携带 author / sign-off 字段**。当前 frontmatter 是 Status/Created/Decision record/Discussion archive/Charter impact —— 没有 author / approver / cooldown end date。

建议在 RFC frontmatter 补：
```
Authors: Life Index Developer + 主审_GPT + 副审_Opus
Cooldown until: 2026-05-20   # 7 天最短冷静期，或按 CHARTER §5 实际值
Status transitions: Draft (2026-05-13) → ...
```

冷静期具体天数请按 CHARTER §5 实际规定填，我此处不擅自指定。

---

## E. 不需改的、写得好的几处

1. **ARCH §5.6 的反例澄清**——明确"ADR-026 的 checkpoint/resume 指 L3 中间制品，**不等于** L2 检索/索引基座引入 WAL/checkpoint"。这条防御性边注非常关键，避免日后有人引用 ADR-026 把 WAL 塞进 L2。
2. **CN-002 §8 的"读取来源声明"**——明确"后续稳定规则不应从本文件读取"。完美防止讨论记录被未来人当 SSOT 反向引用。
3. **大版本 gate 的反向判据**（"如果做不到，就算单个内置模块再光鲜也不算到位"）——这条保护了 Life Index 不会因为某个酷炫 demo 就匆忙升 2.0。

---

## F. 一句话结论

**忠实、自洽、可固化**。建议在 commit 前做 B.1 / B.2 / B.3 三项轻量对齐 + D 项 RFC 元数据补齐，C 项可选择以一条说明明示约束级别。Charter 修订请严格按 §5 走，**不要因为这次讨论达成共识就跳过冷静期或签字**——Life Index 自己的 50 年契约性，从这次怎么对待 Charter 修订就开始建立。

——副审_Opus（read-only audit, 2026-05-13）

---

## 2. 码农C_DeepSeek 审计意见全文

现在我已审阅所有文档及 diff。以下是审计报告。

---

## 审计报告：L1/L2 Future Compatibility Baseline 文档群

### 1. Verdict: **PASS_WITH_NOTES**

---

### 2. 必须修改项

**无。** 未发现 SSOT 断链、文档间实质性矛盾、或与 CHARTER 现有条款冲突。

---

### 3. 建议修改项

**A. ARCHITECTURE.md §2（分层搜索架构）缺少对 ADR-026 的交叉引用**

§2 中 S3 描述为"心理诊断、人格判断、数字人格、数字家书、家训提炼等领域编排 — 远景模块"。虽然"远景"二字已暗示非当前承诺，但在 §1.4 新增了未来兼容基线后，§2 应加一句简短引用以消除歧义——例如："S3 高级模块的具体范围详见 ADR-026 中的终局压力测试定位，非当前路线图承诺。"

**B. ARCHITECTURE.md §1.4 末句位置微调**

当前末句"L2 仍不得调用 LLM...此类能力属于 L3/L4 模块，并必须保留证据、限制与 provenance"中，后半句是对 L3/L4 的行为要求。这段在 §1（索引树架构）的语境下略感越界。建议改为两句独立：一句收束 L2 红线，另一句指向 L3/L4 证据契约，或将该句整体移至 §5.6 的补充注释区。

**C. RFC Open Questions 尚缺归属说明**

RFC §10 列了 4 个 Open Question（中间制品位置、Claim Envelope 公开契约 vs 内部 schema、可导航 API 命令形态、首个验证模块选择）。这些问题的回答时机未在 ADR-026 中提及。建议在 ADR-026 的 Consequences 段增加一句："RFC §10 Open Questions 将在各基线组件进入实现阶段时逐一决议。"避免未来误认为这些是"已忽略"而非"待决议"。

---

### 4. 逐项审计详析

#### 4.1 文档间一致性

| 检查项 | CN-002 | ADR-026 | RFC | ARCH (diff) | ADR INDEX (diff) |
|--------|--------|---------|-----|-------------|------------------|
| 终局压力测试 ≠ 当前路线图 | ✅ L191-196 | ✅ L11, L23 | ✅ L13 | ✅ §1.4 | N/A |
| L2 确定性/无 LLM | ✅ L232 | ✅ §Baseline 7 | ✅ §4, §7 | ✅ §1.4 | N/A |
| Index Tree 角色升级 | ✅ L217-226 | ✅ L59-68 | ✅ §5 | ✅ §1.4 | N/A |
| 七项基线组件枚举 | ✅ L240-247 | ✅ L25-57 | ✅ §3 | ✅ §1.4 | N/A |
| CHARTER 修订走正式流程 | ✅ L351-356 | ✅ L83-84 | ✅ L7, L135 | N/A | N/A |
| 大版本门槛 = 契约而非功能 | ✅ L235-236 | ✅ L72-78 | ✅ §8 | N/A | N/A |

**结论**：5 份文档在核心命题上完全对齐，无任何一处相互矛盾。

#### 4.2 ADR/RFC "终局压力测试" vs "当前路线图承诺" 区分

每条路径都做了明确声明：
- CN-002 L3: "性质：全文记录；非执行路线图；非产品承诺"
- CN-002 L194-196: 用户原话澄清"并非现在立即要求你们加入 Roadmap"
- ADR-026 L11, L23: 两次声明"不是当前路线图承诺"
- ADR-026 §Non-Goals L87-92: 四条不承诺清单
- RFC L13: "These examples are not immediate roadmap commitments"
- ARCH diff §1.4: "这些是终局压力测试，不是当前路线图承诺"

**结论**：区分足够明确，无歧义。

#### 4.3 L2 deterministic/no LLM 边界

一致且冗余加固：
- CHARTER §1.5 表格 + 核心规则（已有）
- CHARTER §4.1 反模式（已有）
- ADR-026 §Anti-requirements（本次）
- RFC §7 L2 Anti-Requirements（本次，8 项枚举）
- ARCH diff §1.4 末句（本次）
- ARCH diff §5.6 插注（本次，澄清 "checkpoint/resume ≠ L2 WAL"）

**结论**：L2 红线以三层（Charter → ADR → ARCH）反复锚定，足够硬。

#### 4.4 基线组件工程可落地性

七项基线组件的分阶段可行性：

| 组件 | 现有基础 | 工程增量 | 可行性 |
|------|----------|----------|--------|
| 稳定 CLI contract | JSON 输出已有雏形 | schema 版本字段、向后兼容承诺 | 低风险，可渐进 |
| Evidence Pack / Claim Envelope | aggregate_result 已有 exactness 字段 | schema 泛化到非确定性场景 | 中等，需设计迭代 |
| 可导航 Index Tree | Index Tree 已存在 | API 化、稳定节点 ID | RFC 已标记为 Open Question 3 |
| batch/cursor/pagination | search 已有 --limit/--offset | 扩展到其他 L2 原语 | 低风险，可渐进 |
| addressable intermediate artifacts | 无 | 全新，需约定目录和 run-id 协议 | RFC 已标记为 Open Question 1 |
| eval contract | eval 框架已存在 | 扩展指标到证据覆盖/事实正确性 | 中等，需定义新 metric |
| L2 anti-requirements | CHARTER 已有部分 | 整理成显式清单 | 零风险 |

**结论**：所有组件均可分阶段落地，未发现架构死锁或"必须先做 A 才能做 B"的阻碍。Open Questions 标记恰当。

#### 4.5 与 ARCHITECTURE.md §5.6 / CHARTER 边界冲突检查

- ARCH §5.6 "不做 WAL/checkpoint" → diff 插注澄清这是 L2 层面，与 ADR-026 的 L3 checkpoint 不矛盾。**无冲突。**
- CHARTER §2.3 L2 "禁止维护独立的长期进程、守护进程、服务" → ADR-026 的 checkpoint/resume 归属 L3，L2 只提供幂等写入中间制品的原语。**无冲突。**
- CHARTER §1.5 "L2 内部不得调用 LLM" → 所有新文档反复确认。**无冲突。**
- CHARTER §4.1 "不得在 retrieval/ranking 层硬切 top-K" → 新文档不涉及。**无冲突。**
- CHARTER §3.3 "高级模组的实现方式" → ADR-026 §Consequences 明确"不做内置高级模块、不建专用 L2 工具"。**对齐。**

---

### 5. 是否同意当前方案进入用户审阅与治理 commit 待 ack 阶段

**同意。**

理由：
1. 5 份文档在核心命题上完全一致，无实质性矛盾
2. "终局压力测试 ≠ 当前路线图"在每份文档中独立声明，冗余充分
3. L2 红线以三层加固（Charter 已有 + ADR + ARCH），边界硬度足够
4. CHARTER 修订流程被正确尊重——RFC 标记为 Draft，ADR 标记为 "Charter amendment pending"，ARCH diff 只做实现层补充，未越权改 Charter
5. 建议修改项均为文档润色级（交叉引用、措辞微调、Open Question 归属说明），不阻塞审阅
6. 按 AGENTS.md 推送政策，新增 `docs/adr/ADR-026` 属于治理文件，ARCHITECTURE.md 与 ADR INDEX.md 伴随修改构成混合 commit → 升级为治理类，**需用户显式 ack 后方可 push**——此路径合规

建议用户在审阅时重点关注建议项 A 和 C，其余可以签字通过。

---

## 3. 主审_GPT 采纳记录

本轮已采纳以下审计建议：

1. 统一 ADR / RFC / Architecture 的 L2 anti-requirements，补入 `creative_emulation`、`cross-journal LLM reasoning` 与 `any LLM call` 的边界说明，并明确 ADR-026 是 canonical list。
2. 将 Claim Envelope 初始类型枚举移入 ADR-026，并在 RFC 中声明该枚举由 ADR-026 持有。
3. 将 major-version gate 的首个验证模块从普通 Open Question 提升为 Gate Validation Follow-up，说明需要单独 RFC 或 roadmap 决策。
4. 在 ADR-026 Consequences 中补充 RFC open questions 的后续归属，以及 Charter 修订前 ADR anti-requirements 的架构决策约束力。
5. 在 RFC metadata 中补充 authors/reviewers、24 小时 cooldown 与状态流转说明。
6. 在 Architecture §2 为 S3 高级模块示例补充 ADR-026 指针，避免误读为当前 roadmap 承诺。
