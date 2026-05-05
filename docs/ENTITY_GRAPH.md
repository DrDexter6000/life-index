# Entity Graph Operating Contract

> **本文档职责**: `entity_graph.yaml` 的操作规范与维护规则
> **目标读者**: Agent、开发者、用户
> **权威层级**: 本文档从属于 [`CHARTER.md`](../CHARTER.md) 与 [`ADR-024`](./adr/ADR-024-entity-schema-v0.md)。Schema 定义以 ADR-024 为准；操作准入、别名规则、生产写入约束以本文档为准。
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
| **Alias** | 指向同一实体的**稳定、无歧义**的替代名称 | `乐乐` → `person-wang-lele` |
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
| 中文名 ↔ 英文名 | `乐乐` ↔ `Toto` | 跨语言检索刚需 |
| 昵称/小名 | `小豆丁`, `小英雄` | 稳定、长期使用、日志中实际出现 |
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
| AI 模型名 | `Claude`, `Kimi`, `GPT-4` | 当前暂缓入图（见 §8），故无对应实体 |

### 3.3 为什么角色词不能进 Aliases

若 `女儿` 是 `person-wang-lele` 的 alias，搜索 `女儿` 会匹配所有含 `乐乐` 的文档。但用户搜索 `女儿` 的意图可能是泛指概念，而非特指乐乐。结果：通用查询被固化 alias 污染，precision 下降。

**正确做法**:
```yaml
# 错误
aliases: [乐乐, 小豆丁, 小英雄, Toto, 女儿]

# 正确
aliases: [乐乐, 小豆丁, 小英雄, Toto]
attributes:
  role: child        # 过渡表达
  subtype: family
```

**日志正文 `people` 字段不受此约束**，frontmatter 的自由文本字段可按自然语言使用角色词。

---

## 4. Relationship 与 Role 的过渡策略

### 4.1 最小 Relationship Vocabulary

当前支持的关系类型（按优先级排序）：

| Relation | 方向 | 示例 | 说明 |
|----------|------|------|------|
| `child_of` | A → B | 乐乐 `child_of` 我 | A 是 B 的孩子 |
| `parent_of` | A → B | 我 `parent_of` 乐乐 | A 是 B 的父母 |
| `spouse_of` | A ↔ B | 我 `spouse_of` 老婆 | 双向对称关系 |

**暂缓的关系类型**（等图谱稳定后再评估）：

| Relation | 暂缓理由 |
|----------|----------|
| `located_in` | 地点信息已由 frontmatter.location 承载 |
| `works_on` / `related_to_project` | 项目关系可通过 tag/project 字段表达，图关系收益不明确 |
| `sibling_of` | 当前 corpus 中无明确需求 |
| `colleague_of` / `friend_of` | 边界模糊，易产生 orphan |

### 4.2 Role Attribute 是过渡表达

`attributes.role`（如 `child`, `spouse`, `parent`）用于**当前阶段**快速标注实体在家庭结构中的位置，但它:
- **不是**长期关系建模的终点
- **不能**替代 `relationships` 字段中的有向边
- 在建立正式的 `person-wang-daming` / `user` 实体和 relationship 边之后，应逐步迁移到 relationship 表达

### 4.3 关系短语搜索的当前状态

关系短语搜索（如 `"我女儿"` → 通过 `child_of` 反向查找）是**设计目标**，但:
- 当前生产图尚未建立 `person-wang-daming` / `user` 实体
- 也未配置 `child_of`/`parent_of`/`spouse_of` relationship
- **因此该能力当前不可被描述为已可靠可用**

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
| 6 | `type` 在 `ENTITY_TYPES` 中（`person`/`place`/`project`/`event`/`concept`） | `entity --check` 验证 |
| 7 | 无 alias 冲突（不与其他实体的 alias/primary_name 重叠） | `entity --check` 验证 |
| 8 | 有明确的添加理由（修复某个查询失败 / 提升 recall / 用户要求） | 文档化在激活报告中 |

### 5.3 禁止批量准入

- 不通过 `--seed` 自动落盘（见 §6.2）
- 不通过 LLM 静默写 graph
- 不一次性添加 >3 个实体（控制变更范围，便于回滚）

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
- 修改 `primary_name`

**什么算用户明确确认**:
- ✅ "批准添加老婆实体，aliases: [王某某, 乐乐妈]"
- ✅ "女儿不入 aliases，保持 role: child"
- ✅ "同意将 Toto 添加为乐乐 alias"

**不算确认**:
- ❌ "看着办"
- ❌ "你觉得呢"
- ❌ 沉默或默许

### 6.2 `--seed` 禁止在 Production 运行

- `life-index entity --seed` **当前会真实写入 `entity_graph.yaml`**，不是 dry-run
- 因此 **禁止在 production 用户数据目录运行 `--seed`**
- 如需 seed，只能在 sandbox / 临时目录中运行（如 `python -m tools.dev.run_with_temp_data_dir`）
- 未来若要放开此限制，必须先实现真正的 `--dry-run` 参数并通过测试

### 6.3 Agent 可自主执行的只读操作

| 操作 | 说明 |
|------|------|
| `entity --check` / `--stats` / `--audit` | 只读，无风险 |
| `entity --list` / `--resolve` | 只读查询 |
| `search --query` | 检索验证 |
| 提出 patch 草案 | 写成 YAML 片段供用户审阅，不直接落盘 |

---

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

### 8.1 当前立场：暂缓入图

- AI 模型（Claude, Kimi, GPT-4 等）**不默认作为 person 实体入图**
- ADR-024 v1 在 schema 层面允许 `person` + `subtype=ai` + `role=ai_assistant`，但这是**schema 能力**，不是**默认策略**
- 当前 schema 没有专门的 `model` / `ai` 类型，直接塞进 `person` 会污染"人"的语义边界

### 8.2 什么时候可以入图

只有用户**明确要求**时，才考虑添加 AI 模型实体，且必须：
- 用户明确说"把 Claude 加入实体图"
- 指定具体的 aliases（如 `Claude Opus 4.6`, `Opus 4.6`）
- 确认不入通用角色词（如 `AI`、`模型` 不入 aliases）

### 8.3 替代检索方案

在 AI 模型入图前，相关日志可通过以下方式被检索到：
- frontmatter tags: `[Claude, AI, Agent]`
- 日志正文中的模型名称被 FTS 直接索引
- concept 实体（如 `concept-agent-native`）可覆盖抽象概念层面

---

## 9. 候选实体池原则

以下实体可能已从日志中被识别为高价值候选，但**候选不等于激活**：

| 实体 | 候选理由 | 当前状态 |
|------|----------|----------|
| `老婆` / `妻子` | 高频人物，乐乐妈是常见称呼 | **候选池**，等用户确认 primary_name、aliases、是否建立 relationship |
| `妈妈` / `母亲` | 高频人物，多篇日志提及 | **候选池**，等用户确认 |
| `Jordan` | GQ28 关联 | **阻塞**，需用户输入身份确认 |
| AI 模型（Claude/Kimi 等） | 日志中多次出现 | **暂缓**，除非用户明确要求（见 §8） |

**候选池管理原则**:
- 候选信息可记录在 `.kimi-learnings/` 或任务报告中，**不写入 `entity_graph.yaml`**
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
2. 先用 `python -m tools.dev.run_with_temp_data_dir --seed` 创建 sandbox，再在 sandbox 对应的 `LIFE_INDEX_DATA_DIR` 下执行 delete/check/search 验证删除影响

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
| [`ADR-024`](./adr/ADR-024-entity-schema-v0.md) | Schema v1 frozen（5 类型、字段定义、ID 规则） | 本文档聚焦**操作流程与写入约束**，不修改 schema |
| [`docs/API.md`](./API.md) §entity | CLI 参数、返回值、错误码 | 本文档聚焦**何时调用、调用前检查什么、生产约束** |
| [`docs/ARCHITECTURE.md`](./ARCHITECTURE.md) | 技术实现 SSOT（架构、模块结构） | 本文档是 Entity Graph 的操作规范，被 ARCHITECTURE 引用 |
| [`AGENTS.md`](../AGENTS.md) | Agent 开发指南与行为约束 | 本文档是 Agent 操作 entity graph 的具体执行规则 |
| [`CHARTER.md`](../CHARTER.md) | 最高治理文件 | 本文档从属于宪章；数据主权、纯文本永久、CLI SSOT 等不变量由宪章保证 |

---

## 12. 修订记录

| 版本 | 日期 | 变更 | 作者 |
|------|------|------|------|
| v1.0 | 2026-05-05 | 基于 D0.3 草案正式落盘为 `docs/ENTITY_GRAPH.md`，收紧生产写入规则，明确 relationship 过渡策略，定义验证清单 | Kimi |
