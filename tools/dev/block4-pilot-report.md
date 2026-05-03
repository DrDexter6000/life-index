# Block 4 Pilot 标注报告

> **日期**: 2026-05-03
> **标注者**: Kimi
> **Schema 版本**: v0
> **日志总数**: 7 篇
> **Stop-the-line 状态**: 未触发

---

## 1. 选取理由

| # | 日志文件 | 标题 | 选取理由 | Topic |
|---|----------|------|----------|-------|
| 1 | `2026-04-25/life-index_2026-04-25_001.md` | 乐乐最爱的玩具陪我继续睡觉 | GQ64 相关：含"重庆"地点 + "乐乐"人物，测试 place + person 共现 | relation |
| 2 | `2026-02-25/life-index_2026-02-25_001.md` | Life Index 项目重构启动 | GQ80 相关：含"Life Index"项目 + typo alias "life indx"，测试 project + alias | work, create, think |
| 3 | `2026-03-11/life-index_2026-03-11_001.md` | 计划回重庆给小朋友过生日与生活反思 | GQ81 相关：含"乐乐" + "birthday"混合语言，测试 person + event + 中英文 alias | relation, life |
| 4 | `2026-04-05/life-index_2026-04-05_002.md` | 归家之旅一半喜一半忧 | 多 entity 复杂：person(3) + place(3) + project(1) + concept(2) + event(1) = 10 entity | life |
| 5 | `2026-04-20/life-index_2026-04-20_001.md` | 内驱力与家庭：写在Life Index启航时 | Health 覆盖：含健康反思、公众人物引用、概念抽象 | think, health |
| 6 | `2026-03-14/life-index_2026-03-14_001.md` | Claude Opus 4.6 对 Life Index 的 CTO 级别技术评审 | Learn 覆盖：含 AI 模型、技术平台、评审报告 | work, learn |
| 7 | `2026-03-16/life-index_2026-03-16_001.md` | Carloha Wiki诞生记：AI赋能的一天 | Create 覆盖：含工作项目、同事群像、AI 工具、跨国场景 | work, create |

**覆盖检查**：
- Entity 类型：person ✅ place ✅ project ✅ event ✅ concept ✅（5/5 全部出现）
- Topic：work ✅ learn ✅ health ✅ relation ✅ think ✅ create ✅ life ✅（7/7 全部出现）
- 复杂度：单篇 entity 数 4–12，平均 7.6 个

---

## 2. 每篇日志标注过程中的歧义/边界 case

### Journal 1: 乐乐最爱的玩具陪我继续睡觉
- **边界 case**: "母女俩" — 母亲未在 people 列表中 named，只标注了已命名的乐乐。
- **处理**: 记入 ambiguities，未创建未命名 person entity。

### Journal 2: Life Index 项目重构启动
- **边界 case**: "X平台" — 社交平台引用模糊，未明确 name（可能是 Twitter/X）。
- **边界 case**: "大神" — 泛指匿名技术博主，无具体名称。
- **处理**: 两者均记入 ambiguities，未标注。

### Journal 3: 计划回重庆给小朋友过生日与生活反思
- **边界 case**: "中东" — 政治地理区域/局势，非具体城市或场所。ADR-024 无 region 类型，最接近 concept。
- **边界 case**: "两个小娃娃" — 指乐乐和另一个未命名孩子，只标注已命名的乐乐。
- **处理**: "中东" 标为 concept，"两个小娃娃" 记入 ambiguities。

### Journal 4: 归家之旅一半喜一半忧
- **边界 case**: "生产队的驴" — 修辞比喻（自嘲），非稳定 entity 名称。指代作者自己，但作为比喻归入 concept。
- **处理**: 标为 concept，记入 ambiguities 说明原因。

### Journal 5: 内驱力与家庭：写在Life Index启航时
- **边界 case**: "大自然母亲" — 拟人化修辞，非真实对话对象。
- **边界 case**: "老婆" — 未命名，只称"老婆"，无具体名称。
- **边界 case**: "成功人士" — 泛指群体，非具体个体。
- **处理**: "大自然母亲" 标为 concept；"老婆"和"成功人士"记入 ambiguities，未标注。

### Journal 6: Claude Opus 4.6 对 Life Index 的 CTO 级别技术评审
- **边界 case**: "Opus 4.6" — AI 模型/工具，虽被拟人化称呼"大哥"，但本质是技术概念。ADR-024 未定义 AI 模型归属。
- **处理**: 按最接近原则归入 concept，记入 ambiguities 说明理由。

### Journal 7: Carloha Wiki诞生记：AI赋能的一天
- **边界 case**: "Kimi" — AI 工具/模型，以对话对象出现（"和Kimi聊天"），但本质是技术概念。同 Opus 4.6 边界 case。
- **边界 case**: "销售团队" — 泛指群体，非具体个体。
- **处理**: "Kimi" 标为 concept；"销售团队"记入 ambiguities，未标注。

---

## 3. Schema 字段使用情况

### 3.1 每字段使用频率

| 字段 | 使用次数 | 使用率 | 说明 |
|------|----------|--------|------|
| `id` | 53/53 | 100% | 全部 entity 都有 |
| `type` | 53/53 | 100% | 全部 entity 都有 |
| `primary_name` | 53/53 | 100% | 全部 entity 都有 |
| `aliases` | 53/53 | 100% | 全部 entity 都有 |
| `attributes` | 53/53 | 100% | 全部 entity 都有（空对象 {} 也算使用） |
| `confidence` | 53/53 | 100% | 全部 entity 都有 |
| `audit_note` | 53/53 | 100% | 全部 entity 都有（空字符串也算使用） |

**结论**: 所有字段每篇都用上了，无死字段。

### 3.2 按类型分字段使用

**Person 必填字段 `attributes.role`**:
- 使用：18/18 person entity（100%）
- 值分布：self(7), child(3), colleague(4), public_figure(2)
- 问题：无

**Person 可选字段 `attributes.subtype`**:
- 使用：5/16 person entity（31%）
- 用于：family(5)
- 问题：未使用时不填，符合预期

**Place 必填字段 `attributes.place_type`**:
- 使用：11/11 place entity（100%）
- 值分布：city(7), country(1)
- 问题："home" 和 "workplace" 未在 Pilot 中出现（因为作者是海外独居，家中场景未单独标注为 place）

**Project 必填字段 `attributes.project_type`**:
- 使用：7/7 project entity（100%）
- 值分布：personal(3), work(2)
- 问题：无

**Event 必填字段 `attributes.event_date`**:
- 使用：2/2 event entity（100%）
- 格式：YYYY-MM-DD 和 YYYY-MM
- 问题：无

### 3.3 字段语义清晰度

| 字段 | 清晰度 | 说明 |
|------|--------|------|
| `id` | ✅ 清晰 | kebab-case 规则明确 |
| `type` | ✅ 清晰 | 5 类枚举明确 |
| `primary_name` | ✅ 清晰 | 直观 |
| `aliases` | ✅ 清晰 | "有意使用的变体"定义明确 |
| `attributes` | ⚠️ 需说明 | 不同类型有不同必填子字段，需查表 |
| `confidence` | ✅ 清晰 | high/medium/low 三档 |
| `audit_note` | ✅ 清晰 | 自由文本，记录边界判断理由 |

**无字段在标注过程中需要"现场解释"才能填** — 所有字段语义在 ADR-024 中已有明确定义。

---

## 4. Stop-the-line 检查

| 判据 | 检查 | 结果 | 说明 |
|------|------|------|------|
| S1 | ≥2 篇出现无法用现有类目分类的实体 | ❌ 未触发 | 所有 entity 均可归入 5 类 |
| S2 | 同一 entity 在不同篇中需要不同字段语义 | ❌ 未触发 | "老板"始终 person/role=colleague；"乐乐"始终 person/role=child |
| S3 | 出现需要新增结构性字段 | ❌ 未触发 | 所有字段均在 ADR-024 v0 中已有定义 |
| S4 | 同一篇日志的 entity 关系无法用现有字段表达 | ⚠️ 发现 gaps | Pilot 格式无 `relationships` 字段；ADR-024 §3.3 定义了关系类型但 pilot JSON 未包含 |

**S4 说明**: 这不是 schema 本身的 stop-the-line，而是 pilot 输出格式的问题。ADR-024 §6.2 的 pilot 格式示例未包含 `relationships` 字段（如 `located_at`, `works_on`）。建议在 v1 格式中增加可选的 `relationships` 字段，或在 graph-level 处理关系。

**结论**: Stop-the-line 未触发。Schema v0 在 7 篇 Pilot 中可操作。

---

## 5. 关键发现（5 条）

1. **AI 模型归属是边界 case**: "Opus 4.6"、"Kimi"、"Claude" 等 AI 模型/工具被拟人化称呼（"大哥"、"和Kimi聊天"），但 ADR-024 未定义 AI 模型归属。按"最接近"原则归入 concept，但用户可能期望标为 person（作为"对话对象"）。这是 v0→v1 需要明确的点。

2. **未命名 person 的处理**: "老板"、"CEO"、"老婆" 等未命名但可识别的 person 出现频率高。当前策略是：有职位的标 person（如 CEO），无职位的未命名亲属不标（如"老婆"）。这个策略需要用户确认是否一致。

3. **Region 类型缺失**: "中东"作为政治地理区域无法归入现有 5 类。当前按 concept 处理，但长期可能需要新增 `region` 类型或子类。

4. **Pilot 格式缺少 relationships**: 7 篇日志中有大量 entity 间关系（如 Dexter works_on Life Index、乐乐 located_at 重庆），但 pilot JSON 格式无法表达。这不是 stop，但建议在 v1 中增加。

5. **Attributes.place_type 中 "home" 和 "workplace" 未出现**: 7 篇日志中 place_type 只用了 city 和 country，"home" 和 "workplace" 未触发。这是因为作者的 location 字段始终标 Lagos，而家中/公司场景未在正文中单独标注为 place。这不是 schema 问题，是 corpus 特性。

---

## 6. Schema v0 → v1 改动建议

基于 Pilot 反馈，建议以下微调（均不触发 stop-the-line）：

| # | 改动 | 类型 | 理由 |
|---|------|------|------|
| 1 | ADR-024 §2.1 Person 边界增加 AI 模型/工具说明 | 文档补充 | Opus 4.6、Kimi 等 AI 模型的归属需要明确 |
| 2 | ADR-024 §4 Edge Cases 增加 "AI 模型/工具" | 文档补充 | 与 #1 配套 |
| 3 | Pilot 输出格式增加可选 `relationships` 字段 | 格式扩展 | 表达 entity 间关系（非结构性字段，不影响 schema 冻结） |
| 4 | ADR-024 §2.2 Place 边界增加 "region" 说明 | 文档补充 | "中东"等区域的归属需要明确 |

**以上改动均为文档补充/格式扩展，不涉及类型边界修改或新增类型，符合 v1 冻结后"只能新增字段/类型，不能修改既有类型的语义边界"的原则。**

---

## 7. 交付清单

- [x] 7 篇日志全部标注完成
- [x] 无 stop-the-line 触发
- [x] ADR-024 所有字段至少在 1 篇日志中被使用过
- [x] 没有任何字段语义在标注过程中需要"现场解释"才能填
- [x] Pilot 报告完成
