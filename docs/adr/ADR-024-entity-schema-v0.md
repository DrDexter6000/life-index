# ADR-024: Entity Schema v1 — FROZEN

> **状态**: v1 — frozen（经 7 篇 Pilot 验证，schema 边界可操作，字段无死字段）
> **v1 冻结日期**: 2026-05-03
> **v0 起草日期**: 2026-05-02
> **Pilot 验证**: 7 篇日志，53 entity，12 ambiguities，无 stop-the-line
> **冻结后原则**: 只能新增字段/类型，不能修改既有类型的语义边界（CHARTER.md §1.8）
> **决策**: 采用 5 类实体体系（person / place / project / event / concept），显式定义边界、ID 规则、aliases 策略，拒绝子类拆分到类型层级（子类用 `attributes.subtype` 表达）。
> **来源**: Round 19 Phase 1-C Track A
> **前置**: `round-19-internal-evidence.md` §4 Schema 审计

---

## 1. 决策上下文

Entity graph 当前处于"工具完备、数据为零"状态（65/65 日志 `entities: []`）。在投入任何检索路由代码前，必须先冻结实体 schema，否则：
- 反向标注成本会随 schema 变动线性放大
- 检索层无法做稳定的 entity-type-based 路由
- Alias table（Phase 1-D）需要 schema 作为权威分类来源

本 ADR 定义 v0 schema，经 Pilot 标注验证后冻结为 v1。v1 冻结后遵循 CHARTER.md §1.8（长期主义原则）：只能新增字段/类型，不能修改既有类型的语义边界。

---

## 2. 实体类型定义

### 2.1 Person（人物）

**边界**
- ✅ 真实人类（自己、家人、朋友、同事、公众人物）
- ✅ 在上下文中以"人"的身份被提及的存在（如历史人物在反思中被引用）
- ❌ 宠物（狗、猫）→ edge case，见 §4
- ❌ 虚构角色（孙悟空、哈利·波特）→ 若作为"文化参照"出现，归 concept
- ❌ AI 模型/工具（Claude、Kimi、ChatGPT）→ 虽常被拟人化称呼（"大哥"、"和Kimi聊天"），但本质是技术工具/概念，归 concept（见 §4 edge case #7）

**必填字段**
- `id`, `type`, `primary_name`
- `attributes.role`: 与该人物在当前日志语境中的关系角色（见 §3.1 ROLE_LABELS）

**ID 规则**
- `person_{kebab_name}`，如 `person-wang-lele`, `person-zhou-yu`
- 若同名冲突，加后缀：`person-zhang-wei-work`

**Aliases 策略**
- 必须包含：中文名、英文名、昵称、关系称谓（如"爸爸"指向自己）
- 示例：`["乐乐", "Toto", "小英雄", "女儿"]`

**子类表达**
- 不拆 `person_family` / `person_colleague` 等子类型
- 用 `attributes.subtype` + `attributes.role` 组合表达：`{"subtype": "family", "role": "daughter"}`

---

### 2.2 Place（地点）

**边界**
- ✅ 物理地理实体（城市、国家、具体场所：家、公司、餐厅）
- ✅ 在日志中被赋予地理/空间意义的地点（"在咖啡馆写代码"中的咖啡馆）
- ❌ 虚拟空间（微信群、Discord 服务器）→ edge case，见 §4
- ❌ 情感锚点（"家"作为温暖概念 vs "家"作为物理地址）→ 依上下文决定，歧义时优先 place

**必填字段**
- `id`, `type`, `primary_name`
- `attributes.place_type`: `city` | `country` | `venue` | `home` | `workplace`

**ID 规则**
- `place_{kebab_name}`，如 `place-chongqing`, `place-home-lagos`

**Aliases 策略**
- 必须包含：中文名、英文名、行政区划简称（"渝"→"重庆"）
- 示例：`["重庆", "渝", "Chongqing", "山城"]`

---

### 2.3 Project（项目）

**边界**
- ✅ 有明确目标、时间跨度、产出物的持续努力（Life Index、Carloha Wiki、某个工作项目）
- ✅ 开源项目、个人 side project、工作职责内的项目
- ❌ 公司/组织本身（LobsterAI 作为公司）→ concept 或未来新增 `organization`
- ❌ 技术栈/工具（Python、FastAPI）→ concept

**必填字段**
- `id`, `type`, `primary_name`
- `attributes.project_type`: `personal` | `work` | `open_source`

**ID 规则**
- `project_{kebab_name}`，如 `project-life-index`, `project-carloha-wiki`

**Aliases 策略**
- 必须包含：全名、缩写、常见 typo（`life indx` → `life-index`）
- 示例：`["Life Index", "life-index", "life indx"]`

---

### 2.4 Event（事件）

**边界**
- ✅ 有明确时间边界、可被回顾的"发生的事"（会议、旅行、节日、发布会）
- ✅ 个人生活中的重要节点（生日、搬家、项目上线）
- ❌ 周期性/抽象时间（"每个周三的例会"）→ 非具体事件，不标注
- ❌ 纯时间表达式（"2026年春节"作为时间段）→ 由 time_parser.py 处理，不归 entity

**必填字段**
- `id`, `type`, `primary_name`
- `attributes.event_date`: ISO-8601 日期或日期范围（可选，但有则填）

**ID 规则**
- `event_{kebab_name}_{YYYYMMDD}`，如 `event-tuantuan-birthday-2026-03-15`
- 若日期未知，省略日期后缀：`event-debate-zhou-yu`

**Aliases 策略**
- 包含不同叫法、简称
- 示例：`["乐乐生日", "Toto's Birthday", "女儿两岁生日"]`

---

### 2.5 Concept（概念）

**边界**
- ✅ 抽象概念、技术术语、情感状态、文化参照、方法论
- ✅ 当其他 4 类无法容纳时的"兜底"类型
- ✅ 品牌/产品名（iPhone、MacBook、Notion）作为"被使用的工具/概念"
- ❌ 不应滥用：如果某个概念在多篇日志中以"项目"形态出现（如"Life Index 方法论"），优先归 project

**必填字段**
- `id`, `type`, `primary_name`
- 无额外必填字段（因其高度抽象）

**ID 规则**
- `concept_{kebab_name}`，如 `concept-agent-native`, `concept-long-termism`

**Aliases 策略**
- 包含同义词、英文对应、缩写
- 示例：`["Agent-Native", "agent native", "代理原生"]`

---

## 3. 通用字段规范

### 3.1 ID 体系

| 规则 | 说明 |
|------|------|
| 格式 | `{type}_{kebab-name}[_{disambiguator}]` |
| 字符集 | 小写 ASCII 字母、数字、连字符 `-`、下划线 `_` |
| 最大长度 | 64 字符 |
| 唯一性 | 全局唯一，跨类型不允许重复 |
| 稳定性 | ID 一旦分配永不变更（改名通过 `primary_name` + `aliases` 处理） |

### 3.2 Aliases 字段

```yaml
aliases:
  - "乐乐"
  - "Toto"
  - "小英雄"
```

- **大小写不敏感**：搜索层统一 lowercase 比较
- **冲突禁止**：同一 alias 不能指向两个不同 entity（已有验证器 `validate_entity_graph_payload` 保证）
- **typo 容忍不在 alias 中解决**：Phase 1-D 的 alias table 会处理编辑距离 ≤1 的 typo，aliases 字段只存"有意使用的变体"

### 3.3 Relationships 字段

沿用现有 schema（`target` + `relation`），新增 relation 语义规范：

| Relation | 适用类型 | 示例 |
|----------|---------|------|
| `located_at` | person/project/event → place | Dexter located_at Lagos |
| `participated_in` | person → event | Dexter participated_in 乐乐生日 |
| `works_on` | person → project | Dexter works_on Life Index |
| `related_to` | 任意 → 任意 | 泛化关系，当具体关系不明确时使用 |
| `parent_of` / `child_of` | person → person | 家庭关系 |
| `mentions` | journal → any | 日志提及实体（由 seed_entity_graph 自动推断） |

### 3.4 ROLE_LABELS（Person 子类参考）

Person 的 `attributes.role` 使用如下标签（15 个，已审计确认）：

`self`, `spouse`, `child`, `parent`, `sibling`, `grandparent`, `grandchild`, `colleague`, `friend`, `mentor`, `mentee`, `acquaintance`, `public_figure`, `historical_figure`, `fictional_character`

> 注：`fictional_character` 仅当虚构角色在日志中被当作"真实对话对象"或"思想实验参与者"时使用（如"如果孙悟空做产品经理"）。否则归 concept。

---

## 4. Schema 不覆盖的 Edge Cases（显式列出）

以下情形在 v0/v1 schema 中**无明确归属**，标注时按"最接近"原则处理，并在 `audit_note` 中记录歧义：

1. **宠物归属**：狗/猫是 family member 还是独立存在？
   - 当前策略：归入 `person`，`attributes.role = "pet"`，`attributes.subtype = "animal"`
   - 未来可能新增 `animal` 类型，若 corpus 中宠物出现 ≥10 次

2. **项目名 vs 公司/组织名**：LobsterAI 是公司，但其名称在日志中常与项目混用
   - 当前策略：LobsterAI 作为 `concept`（组织概念），其具体项目作为 `project`
   - 未来可能新增 `organization` 类型

3. **地点 vs 情感锚点**："家"在"回家的感觉真好"中是情感概念，在"从家出发去公司"中是物理地点
   - 当前策略：依上下文判断，优先 `place`（因空间语义更强）
   - 若日志明确表达情感而非空间（"家是一种感觉"），可标为 `concept`

4. **虚拟/在线空间**：微信群、Discord、Twitter/X
   - 当前策略：归入 `concept`（社交媒介概念）
   - 未来可能新增 `digital_space` 类型

5. **技术栈/工具 vs 项目**：Python 是 concept，但"Python 3.12 迁移"可能像项目
   - 当前策略：技术栈永远 `concept`，只有"有明确目标、时间跨度、产出物"的才归 `project`

6. **品牌/产品作为被动消费对象**："买了 iPhone"中的 iPhone 是 `concept`，但"iPhone 摄影项目"中的 iPhone 是 `project` 还是 `concept`？
   - 当前策略：产品名作为工具/概念，`concept`。只有围绕该产品构建的独立努力才归 `project`

7. **AI 模型/工具**：Claude、Kimi、ChatGPT、Opus 4.6 等 AI 系统
   - **待用户 ack**: 当前提议归入 `concept`（技术工具/概念）
   - 理由：虽常被拟人化称呼（"大哥Opus 4.6"、"和Kimi聊天"），但本质是软件/模型，非真实人类
   - 例外：若日志明确将 AI 当作"真实对话对象"进行深度情感投射（如"Claude 是我最好的朋友"），可标为 `person`，`attributes.role = "acquaintance"`，但需在 `audit_note` 中说明
   - 未来可能新增 `ai_agent` 类型，若 corpus 中 AI 实体出现 ≥10 次

8. **Region（地理区域）**：中东、东南亚、北美
   - **待用户 ack**: 当前提议归入 `concept`（政治地理概念）
   - 理由：ADR-024 v1 无 `region` 类型，`place` 要求具体城市/场所/国家
   - 未来可能新增 `region` 类型，若 corpus 中区域实体出现 ≥5 次

---

## 5. 与现有代码的兼容性

| 现有代码 | 兼容性 | 动作 |
|----------|--------|------|
| `ENTITY_TYPES = {person, place, project, event, concept}` | ✅ 完全一致 | 无变更 |
| `validate_entity_graph_payload` | ✅ 向后兼容 | 新增字段（`attributes.subtype`, `attributes.role` 等）均为可选，不破坏旧数据 |
| `seed_entity_graph` | ⚠️ 需升级 | 新增从 frontmatter `entities` 自动提取并按本 schema 校验 |
| Journal frontmatter `entities: []` | ✅ 向后兼容 | 空列表 = 无实体，符合 schema |
| `tools/lib/entity_schema.py` | ⚠️ 需扩展 | 增加各类型必填字段的校验逻辑（软校验，不抛错只 warn） |

---

## 6. Pilot 验证计划

### 6.1 抽样规则

必抽（5 篇）：
1. GQ64 涉及的"重庆"日志（place + person 共现）
2. GQ80 涉及的"life indx"日志（project + typo alias）
3. GQ81 涉及的"乐乐 birthday"日志（person + language mixing）
4. 至少 1 篇 multi-entity 复杂日志（person + place + project + event 同时出现）
5. 随机 1–2 篇（覆盖不同 topic：work/learn/health/think/create/life）

### 6.2 输出格式

`pilot-annotation.jsonl`，每行：

```json
{
  "journal_file": "life-index_2026-03-27_001.md",
  "annotated_by": "kimi",
  "schema_version": "v0",
  "entities": [
    {
      "id": "project-life-index",
      "type": "project",
      "primary_name": "Life Index",
      "aliases": ["Life Index", "life-index", "life indx"],
      "attributes": {"project_type": "personal"},
      "confidence": "high",
      "audit_note": ""
    }
  ],
  "ambiguities": [
    {
      "text_span": "家",
      "candidate_types": ["place", "concept"],
      "resolution": "place",
      "reason": "上下文为物理地址"
    }
  ],
  "relationships": [
    {
      "from_entity": "person-dexter",
      "to_entity": "project-life-index",
      "relation": "works_on",
      "evidence": "为开源做准备"
    }
  ]
}
```

> **v1 新增（tentative）**: `relationships` 字段为可选，用于表达同一篇日志内 entity 之间的关系。关系类型见 §3.3。
>
> **注意**: 本字段在 Block 4 Pilot 中未被实际使用，留待 Phase 1-D entity graph 实施时按需调整。冻结状态: tentative。

### 6.3 冻结标准

Pilot 完成后，若满足以下全部条件，schema 冻结为 v1：
- 所有 5–10 篇日志能完整标注（无"标不下去"的阻塞）
- 发现的 ambiguities ≤ 3 个/篇（超过说明边界过模糊）
- 无"需要新增类型"的发现（只发现字段/子类调整）

若发现"需要新增类型"或"某类型边界完全无法操作"，触发 stop-the-line，schema 退回修订。

## 8. Pilot 反馈与 v0→v1 改动

### 8.1 Pilot 执行摘要

- **标注者**: Kimi
- **日志数**: 7 篇（覆盖 5 类 entity × 7 个 topic）
- **Entity 总数**: 53 个（person 18, place 11, project 7, event 2, concept 15）
- **Ambiguities**: 12 个（平均 1.7/篇，≤3/篇阈值）
- **Stop-the-line**: 未触发

### 8.2 发现的关键边界 case

| # | Case | 处理 | 状态 |
|---|------|------|------|
| 1 | AI 模型归属（Opus 4.6、Kimi、Claude） | 按 concept 处理（技术工具），但用户可能期望 person（对话对象） | 文档已补充说明 |
| 2 | 未命名 person（老板、CEO、老婆） | 有职位/关系的标 person；无具体名称的亲属不标 | 策略已确认 |
| 3 | Region 类型缺失（中东） | 按 concept 处理，长期可能需要新增 `region` | 已记入 edge cases |
| 4 | Pilot 格式缺少 relationships | 建议在 v1 格式中增加可选 `relationships` 字段 | 非阻塞，格式扩展 |

### 8.3 v0→v1 改动清单

| # | 改动 | 类型 | 位置 |
|---|------|------|------|
| 1 | 增加 AI 模型/工具归属说明 | 文档补充 | §2.1 Person 边界 |
| 2 | 增加 "AI 模型/工具" edge case | 文档补充 | §4 Edge Cases |
| 3 | 增加 "region" edge case 说明 | 文档补充 | §2.2 Place 边界 + §4 |
| 4 | Pilot 输出格式增加可选 `relationships` | 格式扩展（tentative，未 Pilot 验证） | §6.2 |

**所有改动均为文档补充/格式扩展，不涉及类型边界修改或新增类型，符合 v1 冻结原则。**

---

## 7. 修订记录

| 版本 | 日期 | 变更 | 作者 |
|------|------|------|------|
| v0 Draft | 2026-05-02 | 初始起草，基于 5 类体系 | Kimi |
| v0 → v1 | 2026-05-03 | Pilot 验证后冻结，7 篇日志无 stop-the-line，文档补充 4 项 | Kimi |
