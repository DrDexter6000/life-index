# Entity Graph Operating Contract

> **本文档职责**: `entity_graph.yaml` 的操作规范与维护规则
> **目标读者**: Agent、开发者、用户
> **权威层级**: 本文档从属于 [`CHARTER.md`](../CHARTER.md)。Schema 定义、操作准入、别名规则、生产写入约束以本文档为准。
> **起草日期**: 2026-05-05
> **状态**: Active / 生效

---

## 1. 定位与存储

Entity Graph 是 Life Index 的**轻量级实体网络**，用于别名解析、查询扩展和搜索质量提升。

- **SSOT 格式**: YAML (`entity_graph.yaml`)
- **存储位置**: `~/Documents/Life-Index/entity_graph.yaml`（用户数据目录，**不是**代码仓库）
- **架构原则**: 人可读、工具可解析、50 年兼容。不引入 RDF/OWL/Neo4j/GEDCOM 等重型方案。
- **与搜索的关系**: Entity Graph 激活后，搜索端的 `alias expansion` / `entity_hints` / `ranking bonus` / `semantic query expansion` 自动生效。
- **与 GUI 的关系**: 未来 GUI 的人生关系网、项目关系网、地点记忆图可视化，均消费此 YAML。

> **术语**: 本系统称为 **Entity Graph**。Relationship 是 Graph 内的边，不是独立系统。

---

## 2. 核心概念边界

| 概念 | 定义 | 示例 |
|------|------|------|
| **Entity** | 有独立身份的真实存在（人、地点、项目、事件、概念） | `person-wang-lele`, `place-chongqing` |
| **Alias** | 指向同一实体的**稳定、无歧义**的替代名称 | `晴岚` → `person-wang-lele` |
| **Attribute** | 描述实体静态特征的键值对 | `role: child`, `subtype: family` |
| **Relationship** | 实体与实体之间的有向边 | `child_of`, `parent_of`, `spouse_of` |

**关键区分**:
- Alias 解决的是"这个词就是这个实体"
- Attribute 描述的是"这个实体具有什么特征"
- Relationship 描述的是"这个实体与那个实体有什么关系"

---

## 3. Alias 准入规则

### 3.1 允许作为 Alias

| 类别 | 示例 | 理由 |
|------|------|------|
| 中文名 ↔ 英文名 | `晴岚` ↔ `Toto` | 跨语言检索刚需 |
| 昵称/小名 | `小风筝`, `小队长` | 稳定、长期使用、日志中实际出现 |
| 常见缩写 | `life-index` → `Life Index` | 项目/产品的标准缩写 |
| 常见 typo | `life indx` -> `Life Index` | 频率高、无歧义、可预期重复出现 |
| 地名变体 | `渝`, `山城` -> `重庆` | 行政区划简称或文化别称 |

### 3.2 禁止作为 Alias

| 类别 | 示例 | 风险 |
|------|------|------|
| **通用角色词** | `女儿`, `老婆`, `妈妈`, `爸爸` | 固化为具体人后，通用查询被污染 |
| 一次性称呼 | 某次聚会临时起的外号 | 不可复现，无法预期搜索行为 |
| 上下文依赖词 | `老板`, `CEO`（无具体姓名时） | 指代对象随时间变化，alias 是静态的 |
| 情感/评价词 | `小天使`, `捣蛋鬼` | 非稳定标识符，主观性强 |
| AI 泛词/类别词 | `AI`, `模型`, `大模型`, `LLM`, `助手` | 泛词会污染所有 AI 相关查询；具体模型名按 §8 规则在用户明确批准后处理 |

### 3.3 为什么角色词不能进 Aliases

若 `女儿` 是 `person-wang-lele` 的 alias，搜索 `女儿` 会匹配所有含 `晴岚` 的文档。但用户搜索 `女儿` 的意图可能是泛指概念，而非特指晴岚。结果：通用查询被固化 alias 污染，precision 下降。

**正确做法**:
```yaml
# 错误
aliases: [晴岚, 小风筝, 小队长, Toto, 女儿]

# 正确
aliases: [晴岚, 小风筝, 小队长, Toto]
attributes:
  role: child        # 过渡表达
  subtype: family
```

**日志正文 `people` 字段不受此约束**，frontmatter 的自由文本字段可按自然语言使用角色词。

---

### 3.4 搜索匹配语义

Entity Graph 的 alias 准入仍以“稳定、无歧义”为前提；搜索端当前匹配语义如下：

- **大小写不敏感**：ASCII 实体名和 alias 在查询扩展、`entity_hints` 和 Evidence Pack `entity_matches` 中按大小写不敏感方式匹配。
- **ASCII 边界匹配**：ASCII 术语使用字母数字边界，短 alias 不匹配无关单词内部。例如 `LI` 不匹配 `life`，`Ali` 不匹配 `Alibaba` 或 `Align`。
- **下划线语义**：`_` 被视为 word character，因此 `Ali_note` 和 `my_LI_project` 不匹配 `Ali` / `LI`。
- **非 ASCII 子串匹配**：中文等非 ASCII 术语保留子串匹配；因此极短中文 alias 仍应谨慎准入，避免泛词或高频片段污染搜索。
- **准入规则优先**：边界匹配降低短 ASCII alias 的误报风险，但不能替代 §3.1-§3.3 的 alias 准入审查。

## 4. Relationship 与 Role 的过渡策略

### 4.1 最小 Relationship Vocabulary

当前支持的关系类型（按优先级排序）：

| Relation | 方向 | 示例 | 说明 |
|----------|------|------|------|
| `child_of` | A → B | 晴岚 `child_of` 我 | A 是 B 的孩子 |
| `parent_of` | A → B | 我 `parent_of` 晴岚 | A 是 B 的父母 |
| `spouse_of` | A ↔ B | 我 `spouse_of` 老婆 | 双向对称关系 |

**暂缓的关系类型**（等图谱稳定后再评估）：

| Relation | 暂缓理由 |
|----------|----------|
| `located_in` | 地点信息已由 frontmatter.location 承载 |
| `works_on` / `related_to_project` | 项目关系可通过 tag/project 字段表达，图关系收益不明确 |
| `sibling_of` | 当前 corpus 中无明确需求 |
| `colleague_of` / `friend_of` | 边界模糊，易产生 orphan |

关系边的必填字段是 `target` 与 `relation`。v1.2 起，边可带
`evidence`（支撑该关系的 journal rel_path 列表）、`source`
（`seed`/`review`/`user`/`agent`/`system`）、`created_at`、`status`
（`confirmed`/`candidate`）以及可选 `start`/`end`。旧裸边不强迁；加载时按
`source=system`、`status=confirmed`、`evidence=[]` 补默认值。可选字段
`weight` 与 `supporting_journal_ids` 继续兼容，仍仅记录已经确定的边强度和支撑日志路径。
这些元数据是给确定性导航工具消费的，不得由工具从自然语言推断或自动编造。

实体可选字段 `not_duplicate_of[]` 记录用户已判定“不是同一实体”的重复审订结果。
每条记录包含 `target`、`source` 和 `created_at`；`entity --review --action
keep_separate --id A --target-id B` 会在 A/B 两侧写入对称记录，audit 必须尊重
该用户判决，不再把该 pair 报为 `possible_duplicate`。`entity --review --action
undo_keep_separate --id A --target-id B` 会撤销该标记，让 audit 重新检测该 pair。

### 4.2 Role Attribute 是过渡表达

`attributes.role`（如 `child`, `spouse`, `parent`）用于**当前阶段**快速标注实体在家庭结构中的位置，但它:
- **不是**长期关系建模的终点
- **不能**替代 `relationships` 字段中的有向边
- 生产图已配置核心家庭 relationship 边（见 §4.3），`attributes.role` 与 `family_role_labels` 仍作为补充检索信号存在

### 4.3 关系短语搜索的当前状态

关系短语搜索（如 `"我女儿"` → 通过 `child_of` 反向查找）对已配置的 relationship 边**可用**：

- 当前生产图已建立核心家庭 person 实体（含 self / spouse / child / parent）
- 已配置 `child_of` / `parent_of` / `spouse_of` / `grandmother_of` / `grandfather_of` relationship
- 已配置 `family_role_labels`（如 `parent_perspective: 女儿`、`child_perspective: 爸爸`）
- 因此 `"王小橙的妈妈"` → `person-chen-xiaohong`、`"王小橙的外婆"` → `person-li-yulan` 等短语可解析（示例为虚构，不对应 production 具体实体）

**限制**：
- 裸词角色搜索（直接搜 `"妈妈"`、`"爸爸"`、`"婆婆"`、`"爷爷"`）仍不是通用关系解析能力；这些词作为 alias 被禁止（见 §3.2）
- 新关系类型（如 `sibling_of`、`colleague_of`）仍暂缓，需按 §6 审批和 §7 验证
- 新实体、新 relationship 边仍必须按 §6 生产写入规则和 §7 验证清单执行

---

## 5. 新实体准入条件

### 5.1 硬条件（满足任一即可准入）

| # | 条件 | 验证方式 |
|---|------|----------|
| 1 | **日志证据**: 在日志正文/frontmatter 中稳定出现，有具体上下文支撑 | 搜索日志确认出现并有明确语义 |
| 2 | **用户明确确认**: 用户主动提出或批准添加该实体 | 用户明确语句（批准添加...） |
| 3 | **可验证检索收益**: 关联某个已知失败的 query，添加后能改善 rank | 跑搜索验证，确认 expected doc rank 改善 |

### 5.2 额外硬约束（必须同时满足）

| # | 约束 | 验证方式 |
|---|------|----------|
| 4 | 有明确的 `primary_name`（稳定、长期、无歧义） | 人工判断 |
| 5 | 至少 1 个有效 alias 或明确的唯一标识 | 该 alias 在搜索中有实际改善预期 |
| 6 | `type` 在 `ENTITY_TYPES` 中（新：`actor`/`artifact`/`place`/`project`/`event`/`concept`；兼容旧：`person`） | `entity --check` 验证 |
| 7 | 无 alias 冲突（不与其他实体的 alias/primary_name 重叠） | `entity --check` 验证 |
| 8 | 有明确的添加理由（修复某个查询失败 / 提升 recall / 用户要求） | 文档化在激活报告中 |

### 5.3 批量准入必须两段式

- 不通过 `--seed` 自动落盘（见 §6.2）
- 不通过 LLM 静默写 confirmed graph
- 从既有日志冷启动时，先 `entity build --from-journals --preview --json` 生成候选计划，访谈确认后再走 batch/review/显式写入原语
- 批量新增必须先 `entity build --from-batch FILE --preview --json`，向用户复述新建数、关系数、冲突数和重复跳过数
- 用户逐条确认或批量授权后，才可 `entity build --from-batch FILE --apply --json`
- 重名冲突永不自动合并；冲突项进入 `status=candidate` review 队列

---

## 6. 生产写入规则

### 6.1 铁律：任何写入必须用户明确确认

在图谱稳定前（实体数 < 20 且运行稳定），任何对 production `entity_graph.yaml` 的写入操作，都必须经过用户明确确认。

这包括但不限于：
- 添加新实体
- 为已有实体添加 alias
- 添加/修改 relationship
- 删除实体
- 合并实体
- 复原已合并实体
- 标记或撤销“保持分离”重复审订结果
- 修改 `primary_name`

**什么算用户明确确认**:
- ✅ "批准添加老婆实体，aliases: [王某某, 晴岚妈]"
- ✅ "女儿不入 aliases，保持 role: child"
- ✅ "同意将 Toto 添加为晴岚 alias"

**不算确认**:
- ❌ "看着办"
- ❌ "你觉得呢"
- ❌ 沉默或默许

用户是 confirmed 图谱的权威来源。`source=user,status=confirmed,evidence=[]` 是健康态；
日志只是证据流之一，不能因为零日志引用而建议归档或删除用户确认的人物/关系。

### 6.2 直接 `--seed` 禁止在 Production 主路径运行

- `life-index entity --seed` **当前会真实写入 `entity_graph.yaml`**，不是 dry-run
- 因此 **禁止把 `--seed` 作为 production 主路径运行**
- 如需从既有日志冷启动，先运行 `life-index entity build --from-journals --preview --json`；该命令只读、零写入
- 只有在用户看过候选并明确授权后，才可经 `entity build --from-batch ... --apply`、review action，或其他显式写入原语落盘
- 旧 `--seed` 仅保留为高级兼容原语；默认只在显式配置的 sandbox / 临时 `LIFE_INDEX_DATA_DIR` 中使用

### 6.3 Agent 可自主执行的低风险操作

| 操作 | 说明 |
|------|------|
| `entity --check` / `--stats` / `--audit` | 只读，无风险 |
| `entity --list` / `--resolve` | 只读查询 |
| `entity --review` | 只读队列；包含 why/evidence/action_choices |
| `entity --propose` | 写入 `status=candidate` 假设，不进入 confirmed 检索语义 |
| `search --query` | 检索验证 |
| 提出 patch 草案 | 写成 YAML 片段供用户审阅，不直接落盘 |

---

### 6.4 Review Hub 与可逆合并

`entity --review` 只生成候选队列。高置信重复、疑似关系、重复未知名和 agent
假设都只能排队，不得自动合并或自动写入 confirmed 图谱。宿主 agent 负责读取
`evidence`、分桶、向用户访谈；用户确认后，agent 只能通过
`entity --review --action ...`、`entity --update/--add-alias`、`entity --merge`、
`entity --unmerge` 或 `entity --apply-batch` 等 CLI 原语修改 confirmed 图谱。

候选池持久化在 `entity_graph.yaml` 中，使用 `source=seed|agent|user` 与
`status=candidate` 标记。candidate 实体/边不参与 entity expansion 或 confirmed
检索语义；确认后才转为 `status=confirmed`。

`entity --merge` 会在目标实体下保存 `merged_entities[]` 墓碑，包含被吸收实体的完整
原始记录以及本次合并新增的 alias、转移关系和反向引用改写。`entity --unmerge --id
MERGED_ID --target-id TARGET_ID` 使用该墓碑完整复原，并移除合并产生的 alias / 转移关系。

`entity --review --action keep_separate --id A --target-id B` 持久化用户对疑似重复
pair 的“不是同一人/物”判决，写入 `source=user` 与 `created_at`。该记录是可逆的；
`entity --review --action undo_keep_separate --id A --target-id B` 删除标记后，下次
audit 会重新报告仍符合规则的 `possible_duplicate`。

## 7. 变更后验证清单

每次对 `entity_graph.yaml` 做任何修改后，必须执行：

### 7.1 结构验证（必须）

```bash
life-index entity --check      # 确认无 dangling/duplicate/schema issue
life-index entity --stats      # 确认 entity count / alias count 合理
```

### 7.2 搜索验证（必须）

对新增/修改实体的每个 alias 跑搜索：

```bash
life-index search --query "ALIAS_NAME" --level 3
```

检查项：
- `entity_graph_status` = `initialized`
- `entity_hints` 命中正确实体
- `expanded_query` 包含所有预期 aliases
- 预期文档在 top 5 内

### 7.3 Eval 验证（如适用）

如果该变更是为修复某个已知失败的 golden query：

```bash
life-index eval
```

确认该 query 从 fail → pass。

### 7.4 记录验证结果

验证结果应包含在相关任务报告中，至少记录：
- 变更的实体 YAML 片段
- `entity --check` 输出
- 搜索验证的 `merged_results` top 5
- 如适用：eval 前后对比

---

## 8. AI 模型实体规则

### 8.1 当前立场：允许入图，须用户明确批准

- AI 模型/助手**允许入图**，但**不默认自动添加**
- 旧图中的 `person` + `subtype=ai` + `role=ai_assistant` 仍兼容；归一化后表达为 `actor` + `attributes.kind=software_agent`
- 每个 AI 实体仍需**用户明确确认**后方可写入 production（见 §6.1）

### 8.2 AI 实体固定规则

| 规则 | 要求 | 说明 |
|------|------|------|
| `type` | `actor` | 旧 `person` 仍可加载，`maintain --normalize` 会迁移 |
| `attributes.kind` | `software_agent` | 表示可行动的宿主/助手实体；AI 模型文件、书、设备等用 `artifact` |
| `attributes.subtype` | 可保留 `ai` | 旧图兼容字段，归一化不要求删除 |
| `attributes.role` | 固定为 `ai_assistant` | 统一角色标识，便于检索过滤 |
| `attributes.provider` | 嵌套对象 `{name, aliases}` | 厂商信息暂放属性，**不单独建 entity** |
| aliases | 禁止泛词 | `AI`、`模型`、`大模型`、`LLM`、`助手` 等不得进入 aliases |
| 家族名绑定 | 需单独确认 | `Claude` 不应默认作为 `Claude Opus` alias；家族名与具体模型分开处理 |
| 批次大小 | 建议 ≤3 个 | 控制 blast radius，便于回滚与验证 |

### 8.3 什么时候可以入图

满足以下全部条件：
1. 用户明确批准添加该 AI 实体（如"把 Kimi 加入实体图"）
2. 指定具体、无歧义的 aliases（如 `Kimi`, `Kimi Chat`）
3. 确认 aliases 不含 §8.2 禁止的泛词
4. 按 §5 准入条件 + §7 验证清单执行激活

### 8.4 替代检索方案

即使 AI 实体已入图，以下方式仍可作为补充检索路径：
- frontmatter tags: `[Claude, AI, Agent]`
- 日志正文中的模型名称被 FTS 直接索引
- concept 实体（如 `concept-agent-native`）覆盖抽象概念层面

---

## 9. 候选实体池原则

以下实体可能已从日志中被识别为高价值候选，但**候选不等于激活**：

| 实体 | 候选理由 | 当前状态 |
|------|----------|----------|
| `Morgan` | 多篇日志中重复出现但未确认身份 | **candidate**，等用户确认 primary_name、aliases、是否建立 relationship |
| `Alice` / `A. Example` | 批量导入时与现有实体重名 | **candidate**，等用户裁决是否同一人 |
| `Project Atlas` | 宿主 agent 读 evidence 后提出的项目假设 | **candidate**，等用户确认 |
| AI 模型（Claude/Kimi 等） | 日志中多次出现 | **允许入图**，须用户明确批准并按 §8.2 固定规则执行（见 §8） |

**候选池管理原则**:
- 候选可持久化在 `entity_graph.yaml`，但必须标记 `status=candidate`
- candidate 实体/边不参与 confirmed 检索语义或 relationship expansion
- agent 可用 `entity --propose` 写候选；确定性写入路径可在重复未知名达到阈值时写候选
- 每次用户确认一个候选后，按 §5 准入条件 + §7 验证清单执行激活

---

## 10. 回滚策略

### 10.1 单实体回滚

```bash
life-index entity --delete --id ENTITY_ID
```

**当前实现行为**：`--delete` 会**立即删除**实体并清理引用，`cleaned_refs` 是删除完成后的返回信息，**不是 preview**。

**执行前必须**：
1. 手动备份 `entity_graph.yaml`
2. 先复制一份 sandbox 数据目录，并显式设置 `LIFE_INDEX_DATA_DIR` 指向该 sandbox，再执行 delete/check/search 验证删除影响

**production 删除仍必须经过用户明确确认**（见 §6.1）。

> 未来如需安全删除流程，应新增 `--dry-run` / `--preview` 参数，在真正落盘前展示影响范围。

### 10.2 全图回滚

`entity_graph.yaml` 是单一 YAML 文件。回滚方式：
1. 备份当前文件（手动复制）
2. 编辑 YAML 恢复旧状态
3. 重新运行 §7 验证清单

**注意**: Life Index 没有 entity graph 的版本控制。重要变更前建议手动备份。

---

## 11. 与现有文档的关系

| 文档 | 职责 | 本文档的补充 |
|------|------|-------------|
| [`docs/API.md`](./API.md) §entity | CLI 参数、返回值、错误码 | 本文档聚焦**何时调用、调用前检查什么、生产约束** |
| [`docs/ARCHITECTURE.md`](./ARCHITECTURE.md) | 技术实现 SSOT（架构、模块结构） | 本文档是 Entity Graph 的操作规范，被 ARCHITECTURE 引用 |
| [`docs/ENTITY_GRAPH_UX_SURFACE_SPEC.md`](./ENTITY_GRAPH_UX_SURFACE_SPEC.md) | 用户心智入口与未来收敛计划 | 本文档定义当前生产规则；UX spec 仅定义未来 build/audit/maintain 收敛方向 |
| [`CHARTER.md`](../CHARTER.md) | 最高治理文件 | 本文档从属于宪章；数据主权、纯文本永久、CLI SSOT 等不变量由宪章保证 |

---

## 12. 修订记录

| 版本 | 日期 | 变更 | 作者 |
|------|------|------|------|
| v1.2 | 2026-07-04 | 明确用户是 confirmed 图谱权威来源；candidate 可持久化在 `entity_graph.yaml` 但不参与 confirmed 检索；新增批量 apply、agent propose、review 节律说明；`keep_separate` 持久化为可撤销的 `not_duplicate_of` 用户判决 | Codex |
| v1.1 | 2026-05-06 | §8 AI 模型实体规则更新：从"暂缓入图"改为"允许入图，须用户明确批准"；固定 `person`+`subtype=ai`+`role=ai_assistant` 规则；明确 provider 属性表达、禁止泛词 alias、批次 ≤3 等约束；同步更新 §9 候选池状态 | Kimi |
| v1.0 | 2026-05-05 | 基于 D0.3 草案正式落盘为 `docs/ENTITY_GRAPH.md`，收紧生产写入规则，明确 relationship 过渡策略，定义验证清单 | Kimi |
