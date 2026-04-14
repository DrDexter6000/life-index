# Life Index Strategy Hub

> **本目录是项目的核心战略与开发文档中心，不公开（已加入 .gitignore）。**
> **任何 Agent 接手开发时，应首先阅读此文件了解全局上下文。**
> **物理位置**：`D:\Loster AI\Projects\.strategy\`（通过 NTFS junction 在 `life-index` 与 `life-index_gui` 中均显示为 `.strategy/`）。
> **治理规则**：CLI 与 GUI 虽分开开发，但战略、路线图与 progress 统一在此维护；禁止为两条产品线各自复制第二份战略文档。

---

## 读取顺序

1. **先读本文件** — 了解双产品线战略和当前进度
2. **再读完整路线图** — `.strategy/ROADMAP.md`（架构决策依据 + 技术评估 + 演进路线）
3. **再读当前阶段目录** — `.strategy/cli/TDD.md`（当前 CLI 活跃执行计划）、`.strategy/gui/`，或 `.strategy/cli/archive/`（若需查阅已完成的 CLI 历史文档）
4. **最后读具体任务文档** — 当前阶段子目录中的 PRD/TDD/验收报告，或 CLI archive 中的历史记录

---

## 双产品线战略（2026-03-31 确立）

### v1.x — CLI Core（极客工具）

**定位**：agent-first / agent-native 的纯粹 CLI 工具，面向开发者/极客。
**仓库**：当前仓库 `life-index`
**目标**：快速打磨至 production-ready，发布后转入维护模式。

**完成状态**：
- [x] 阶段 1: 搜索质量修复（embedding 模型升级 + FTS AND-first + 阈值重标定）
- [x] 阶段 2: Entity Graph（实体注册 + 别名解析 + 关系图谱 + query expansion）
- [x] 阶段 3: 写入增强（sentiment_score / themes / 写入时自动检测新实体 / .revisions）
- [x] 阶段 4: Tool Schema 标准化（每个工具一个 schema.json）
- [x] 阶段 5: 清理与发布（Web GUI 剥离 + README 重写 + 正式发布）

### v2.0 — Experience Layer（大众体验）

**定位**：数字化人生档案馆，纪念碑谷级视觉品质，叠加在 CLI 之上的可选件。
**仓库**：life-index_gui（本地工作目录已建立）
**目标**：终局品质，每一帧都是作品。

**三阶段**：
- Phase 1 "第一眼心动"：禅意 UI + 社媒导入 + EXIF + 时间轴/实体关系可视化
- Phase 2 "越用越深"：智能搜索 + 关联推荐 + 回忆录 + 情绪仪表盘
- Phase 3 "不可替代"：数字人格 + 人格画像 + 心理健康 + 人生群像

---

## 当前状态

**活跃产品线**：CLI 维护线 + GUI 规划线并行
**CLI 当前阶段**：Round 7 已完成并归档关闭；Round 8 进入准备阶段（见 `.strategy/cli/Round_8_TDD_prep.md`）
**GUI 当前阶段**：Phase 1 React/Vite 工程实现已落地，首轮视觉验收与自动化修复记录已形成；当前进入文档收口与持续视觉打磨阶段
**阻塞项**：无结构性阻塞；GUI 实现仍需严格遵守 CLI 是 SSOT 的边界

### 2026-04-09 共享战略治理落地

- .strategy/ 已提升为 Projects 级 canonical hub：D:\Loster AI\Projects\.strategy\
- life-index 与 life-index_gui 均通过本地 .strategy/ 入口读取同一套战略文档
- 高层战略、路线图、阶段 progress 统一在共享 .strategy/ 中维护
- 战略子目录已从 v1.x/、v2.0/ 重命名为 cli/、gui/，目录语义按产品线表达

### 2026-04-14 Round 7 状态校准

- cli/TDD.md 对应的 **Round 7: Entity Graph Evolution** 已完成并通过归档审计
- `.strategy/cli/Round_7_Audit.md` 为 Round 7 最终归档审计报告
- `.strategy/cli/Round_7_Optimization_TDD.md` 已转为归档校准记录，不再作为活跃开发计划
- 当前 CLI 正确状态应理解为：**Round 7 已完成，Round 8 处于准备阶段**

### 2026-04-08 Round 6 状态校准

- cli/Round_6_PRD.md 已完成
- cli/TDD.md 已完成
- cli/Phase_1_TDD.md / Phase_2_TDD.md / Phase_3_TDD.md 已完成
- 当前正确状态应理解为：**Round 6 规划完成，等待执行**

### 2026-04-04 Maintenance Round 3 完成记录

- **Task 1.1 完成**：compound commands 运行时测试补齐
  - `write --auto-index` / `search --read-top` 改为真实运行时断言
  - 补齐 `build_all()` 异常时保留 write success 的行为

- **Task 1.2 完成**：verify 命令信任修复
  - 补全 `vector_consistency`
  - 补全正文附件引用校验
  - 补全 `by-topic` orphan 校验
  - 输出恢复为 6 项 checks

- **Task 1.3 完成**：`search --explain` 运行时测试补齐
  - explain 输出结构改为真实行为验证，不再检查源码字符串

- **Task 1.4 完成**：ONNX Spike 改为真实实验
  - `optimum[onnxruntime]` 安装成功
  - 基础 ONNX 导出可运行且与 PyTorch 精度一致
  - O2 优化模型在当前环境中运行时失败，已记录为不建议 v1.x 切换

- **Task 1.5 完成**：Entity Graph benchmark 重新实测
  - 3 次跑数，中位数：500 entities load = 117.14ms
  - 结论修正为“可接受但属中风险区间”

- **Task 1.6 完成**：timeline 运行时测试补齐
  - range / chronological order / abstract+mood / empty range / topic filter 全部以真实运行时断言覆盖

- **Task 1.7 完成**：critical marker 审计落地
  - `pyproject.toml` 已实际注册 `critical`
  - 核心 write/search/index/edit 测试已标注
  - `pytest -m critical tests/unit/` 实测 63 个测试，1.49s 跑完

### 2026-04-03 状态校准（main）

- 当前工作 branch：`main`
- 已完成现实进展：
  - Phase 1 搜索质量修复完成
  - Phase 3 写入增强完成
  - Phase 4 Tool Schema 完成
  - Phase 5 清理发布工程面完成
- 在此基础上又完成了一轮 **confirm / relation contract 强化**：
  - Package Q：confirm runtime contract（`complete/partial/noop/failed`）
  - Package R：confirm 返回 fresh relation summary
  - Package S：candidate approval UX（candidate id / approved / rejected summary）
  - Package U：write / confirm / edit / search golden snapshots
- 以上 Q/R/S/U 属于对 Phase 3/4/5 交界面的 runtime contract 强化；随后对 Phase 2 也完成了 fresh verification 与文档纠偏。
- 2026-04-03 收口后，v1.x 已进入 maintenance mode，相关历史文档已整体迁移至 `.strategy/cli/archive/`。

### 2026-04-03 Maintenance Round 2 完成记录

**Tier 1 - 必须做（守住已有价值）**

- **Task 1.1 完成**：Embedding版本变更自动Rebuild护栏
  - 新增 `ModelIntegrityResult` dataclass
  - 版本不匹配自动触发全量rebuild
  - 输出明确版本变更日志
  
- **Task 1.2 完成**：CLI复合命令
  - `write --auto-index`：写入后自动更新索引
  - `search --read-top N`：搜索后读取top N全文
  
- **Task 1.3 完成**：数据完整性校验一等公民
  - `life-index verify` 命令可用
  - 输出标准JSON格式校验结果
  - 包含frontmatter、FTS索引、附件引用检查

**Tier 2 - 应该做（扩大护城河）**

- **Task 2.1 完成**：search --explain 可观测性
  - 新增 `--explain` 参数显示评分详情
  - 输出keyword/semantic/fusion三部分分数
  
- **Task 2.2 完成**：ONNX推理Spike（预研）
- 产出报告：`.strategy/cli/ONNX-SPIKE-REPORT.md`
  - 决策：v1.x暂不实施（收益有限）
  
- **Task 2.3 完成**：Entity Graph性能基线
  - 500实体加载时间：117.90ms ✅
  - 决策：YAML方案足够，不需要SQLite缓存

**Tier 3 - 可以做（锦上添花）**

- **Task 3.1 跳过**：MCP Thin Adapter - 按用户要求直接忽略
- **Task 3.2 完成**：timeline命令
  - `life-index timeline --range START END` 可用
  - 支持按时间范围输出摘要流
- **Task 3.3 完成**：测试瘦身审计
- 产出报告：`.strategy/cli/TEST-AUDIT.md`
  - 核心路径测试已识别，marker已注册

- 执行结果已按 `.strategy/cli/TDD.md` 要求返写到各Task下方的 `[BRIEF]` 记录中。

---

## 目录结构

```
.strategy/
  STRATEGY.md           ← 本文件（入口，全局上下文）
  ROADMAP.md            ← 完整路线图（架构决策 + 技术评估）
  cli/                  ← CLI 当前活跃文档根目录
    TDD.md              ← Round 7 总纲（已完成并归档校准）
    archive/            ← 已完成的 v1.x 历史文档归档
      PHASE-OVERVIEW.md
      CURRENT-EXECUTION-STATE.md
      EXECUTION-GUIDE.md
      V1X_CLOSURE_SUMMARY_2026-04-03.md
      search-quality/
      entity-graph/
      write-enhance/
      tool-schema/
      cleanup-release/
  gui/                  ← GUI / Experience Layer 开发文档
    PHASE-OVERVIEW.md   ← GUI 各阶段概览与当前状态
    phase-0/            ← "考古与打捞"（.archive/ 资产扫描与提取）
    phase-1/            ← "第一眼心动"
    phase-2/            ← "越用越深"
    phase-3/            ← "不可替代"
```

每个子阶段目录结构：
```
search-quality/         （示例）
  PRD.md               ← 产品需求文档（做什么、为什么、验收标准）
  TDD.md               ← 技术设计文档（怎么做、架构影响、风险）
  PROGRESS.md          ← 执行进度追踪
  ACCEPTANCE.md        ← 验收报告（完成后填写）
```

---

## 关键决策记录

| 日期 | 决策 | 理由 |
|------|------|------|
| 2026-03-31 | 双产品线分离（v1.x CLI + v2.0 Experience） | 产品纯粹性 + 技术栈自由 + 开发节奏独立 |
| 2026-03-31 | 不用 Rust | I/O bound，Python 最优 |
| 2026-03-31 | 不做 MCP（v1.x 阶段） | 只有 2 个消费者，CLI 直调更高效 |
| 2026-03-31 | 搜索问题是参数/模型问题，不是架构问题 | 代码审计结论 |
| 2026-03-31 | 先完善 CLI 再全力 v2.0 | CLI 是 v2.0 的地基 |
| 2026-03-31 | v2.0 从终局体验倒推，不自下而上慢建 | Vibe coding 时代竞争压力 |
| 2026-03-31 | Entity Graph 用 YAML + SQLite 缓存，不用图数据库 | 实体量级 ~2000，YAML 人可读且符合 50 年承诺，SQLite 已有 |
| 2026-03-31 | 命名 `entity_graph.yaml` | 覆盖人物/地点/项目/事件/概念，比 knowledge_base 更精确 |
| 2026-04-01 | **Q1** Embedding 模型选定 `bge-m3` | 8192 tokens，中英文均衡，无需 chunking，fastembed 兼容 |
| 2026-04-01 | **Q2** 向量索引一次性全量重建 | 日志 ~200 篇，全量重建仅需数分钟，比增量迁移简单可靠 |
| 2026-04-01 | **Q3** 搜索标定测试集：Agent 从真实日志自动构建 + 用户审阅 | 避免合成数据偏差，用户审阅确保 ground truth 准确 |
| 2026-04-01 | **Q4** 初始 entity_graph.yaml：Agent 从现有日志提取 + 用户审阅 | 冷启动策略，确保数据准确性 |
| 2026-04-01 | **Q5** 关系类型：~15 种推荐类型 + 开放扩展（非推荐类型仅 warning 不 error） | 灵活性 + 引导性平衡 |
| 2026-04-01 | **Q6** Sentiment/Themes LLM 策略：在线优先，离线 = 留空（不做规则降级） | 减少 CLI 复杂度；未来 Agent 可搜索降级日志批量回填 |
| 2026-04-01 | **Q7** .revisions 存储：co-located（`YYYY/MM/.revisions/`） | 与日志同级，备份/迁移时自动跟随 |
| 2026-03-31 | **Q8** 旧 Web GUI 历史资产从主仓清理、仅保留本地/历史参考 | 远端 `life-index` 保持 CLI 纯净，本地备份与迁移空间继续保留 |
| 2026-04-01 | **Q9** PyPI 发布：life-index / Apache 2.0 / 中文 README — **降优先级，不阻塞工程** | 发布是锦上添花，不应成为工程瓶颈 |
| 2026-04-01 | **Q10** 全局 LLM 策略：在线优先 + 离线留空 | 与 Q6 一致，所有 LLM 依赖功能统一策略 |
| 2026-04-03 | **Q11** v2.0 接入方式优先 Agent-as-Backend | 当前明确不采用 MCP 作为 2.0 方案；GUI / Service 以后均以 CLI Tool Schema + Agent Runtime 为主 |
| 2026-04-03 | **Q12** Package T 延后，先做 Phase 2 Entity Graph | Phase 2 是 v1.x 剩余关键地基；GUI / service 承接不应先于实体层完成 |

---

## 关键数据文件

| 文件 | 位置 | 说明 |
|------|------|------|
| `entity_graph.yaml` | `~/Documents/Life-Index/` | 实体注册 + 别名 + 关系图谱（SSOT，人可读） |
| Journals | `~/Documents/Life-Index/Journals/` | 日志主数据 |
| FTS 索引 | `~/Documents/Life-Index/.index/journals_fts.db` | 全文搜索缓存 |
| 向量索引 | `~/Documents/Life-Index/.index/vectors_simple.pkl` | 语义搜索缓存 |
| Entity 缓存 | `~/Documents/Life-Index/entity_cache.db`（Round 2 决策：暂不启用） | entity_graph.yaml 的 SQLite 缓存预留位 |

---

## 铁律

> **铁律以本文件为权威版本。其他文档中的铁律章节均为本处的引用/摘要。**

1. **CLI 是 SSOT** — v2.0 所有写入必须经过 v1.x CLI，GUI 不直接修改日志文件或索引
2. **数据永久可读** — Markdown + YAML，50 年承诺；v2.0 不发明私有数据格式
3. **品味 > 功能** — 宁缺毋滥，不做"先凑合再迭代"
4. **终局品质** — 每一个发布的界面都是终局品质，截图即传播
5. **禁止直接复制粘贴 code.html** — Stitch/Bolt 等 AI 生成的 code.html 必须经过转化协议，不得原样入库
6. **Tailwind CDN 引用 = 工程事故** — 必须通过构建工具引入 Tailwind
7. **GUI 不做原始数据计算** — 所有聚合、排序、过滤由 CLI 或 metadata_cache.db 完成；GUI 只负责拿数据→渲染→交互
8. **Agent-as-Backend，非 MCP**（Phase 1-2）— Phase 3 再演进到 MCP
9. **DESIGN.md 是设计 SSOT** — `prototype/final_prototype.html`、`gui/reference_only/*`、`gui/phase-0/salvage/*`、`.archive/*` 都只能作为参考输入，不能反向覆盖 `DESIGN.md`
10. **文档权威分层** — 文档权威按以下层级执行：
    - **T0**：`strategy.md` —— 铁律、全局边界、产品双线关系
    - **T1**：`ROADMAP.md` + `gui/PHASE-OVERVIEW.md` + `gui/GUI_ARCHITECTURE.md` —— 产品范围、阶段状态、页面架构、数据契约
    - **T2**：`gui/DESIGN.md` —— 视觉规范、tokens、材质、交互细节
    - **T3**：`prototype/final_prototype.html` + `gui/reference_only/*` + `gui/phase-0/salvage/*` + `.archive/*` —— 参考实现、历史输入、打捞资产
    - 下层文档不得声明自己是上层的“最高准则”；`AGENTS.md` 仅为速查摘要，发生冲突时以 T0-T2 为准
