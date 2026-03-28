# Life Index 变更日志

> **本文档职责**: 决策变更历史 SSOT，记录里程碑级别变更

> **补充说明**: 自 v1.x 起，本文档同时作为面向未来正式 release notes 的锚点。历史日期条目继续保留；未来版本发布可在顶部补充版本锚定条目，并在需要时明确升级动作（如 rebuild、migration、额外验证）。

## [Unreleased]

> 用于记录下一次正式版本发布前、值得进入 release notes 的用户可感知变化。

## [1.5.0] - 2026-03-28

### 修复 (Fixes)

#### 检索系统

- **FIX-01**: 统一语义搜索后端为 pickle/numpy
  - 删除 `semantic_search.py` 中的 `search_semantic()` 死代码（无调用者）
  - 删除 `semantic_search.py` 中的 `hybrid_search()` 死代码（无调用者）
  - 确认搜索运行时只使用 `vector_index_simple.py`（pickle/numpy 后端）
  - 修复双后端分裂问题，搜索路径与构建路径一致

- **FIX-02**: 统一 YAML/frontmatter 解析为 SSOT
  - 替换 `search_index.py` 手写解析为 `parse_frontmatter()`
  - 替换 `semantic_search.py` 手写解析为 `parse_frontmatter()`
  - 替换 `vector_index_simple.py` 回退解析为 `parse_frontmatter()`
  - 元数据解析一致，维护负担降低

- **FIX-03**: 删除时间衰减死代码（随 FIX-01 一并完成）
  - 删除 `time_factor = 1.0` 空实现
  - 代码认知负载降低

- **FIX-04**: 预归一化向量存储
  - `SimpleVectorIndex.add()` 时归一化向量
  - `SimpleVectorIndex.search()` 时省去逐文档归一化
  - 向后兼容旧索引（通过 `normalized` 标记区分）
  - 搜索性能提升 ~2x

#### 代码清理

- **FIX-06**: 清理项目根目录临时文件
  - 删除 `server.log`, `tmp_*` 日志文件
  - 这些文件已被 `.gitignore` 覆盖

### 用户影响 (User Impact)

- **可选操作**: 运行 `life-index index --rebuild` 重建语义索引以获得最佳性能（FIX-04）
- **数据兼容**: 日志文件格式无变更，历史日志无需迁移
- **功能变更**: 无，所有功能行为与 v1.4.0 一致

### 审计来源

本次版本修复问题来源于 `docs/dev1.5.0/AUDIT_REPORT.md` CTO 全面审计报告。

---

建议在这里记录：
- 用户可见功能变化
- 需要 operator action 的升级事项
- rebuild / migration / compatibility 相关提示

相关文档：
- `docs/UPGRADE.md`
- `docs/web-gui/README.md`
- `docs/web-gui/post-v1.4-backlog.md`

**当前规划说明**:
- `v1.4.0` 已发布完成，后续 Web GUI 工作以 post-v1.4 backlog 与 next-phase roadmap 管理
- 当前阶段已完成一轮 Tier 1 / Web GUI 文档收口：`docs/web-gui/` 仅保留当前态文档与 `UIUX/`，历史初始化/升级过程文档已归档到 `docs/archives/web_gui_init/`
- 已落地的 Web GUI 增强能力（dashboard visual、bugfix、write confirm、settings、search AI summary）应视为当前现实；历史 upgrade 计划仅作为审计档案保留

**工程加固（未发布）**:
- 提高 Web 依赖下的 FastAPI 最低版本到 `0.135.2`，避免旧版本组合再次触发 `HTTP_422_UNPROCESSABLE_ENTITY` 弃用警告
- 在 pytest 配置中显式设置 `asyncio_default_fixture_loop_scope = "function"`，消除 `pytest-asyncio` 弃用警告并固定异步 fixture 行为
- 以上变更属于 patch 级依赖/测试环境稳定性修复，不改变用户日志、附件、frontmatter 或 Web 业务行为

**Web GUI 搜索 / 写入 / 编辑契约归位（未发布）**:
- regular `/search` 已恢复为 canonical dual-pipeline search contract：默认启用语义检索，并将当前 provider 透传给同一次 retrieval 结果上的 AI summary
- `/api/search/summarize` 已与当前页面 filters 对齐，避免 summary 与用户正在查看的结果集脱节
- `/api/search/ai` 已收口为“query derivation + canonical retrieval + answer rendering”模型；路由层不再维护第二套多次检索 / 手工 merge / ranking 真相
- write 页面已补上显式 `llm_status`（`unavailable` / `failed` / `fallback` / `ready`），不再把 AI metadata extraction 失败静默吞掉
- edit 页面当前明确为 manual-only deterministic edit；地点变更但天气为空时，后端会阻断 unsafe save

**Web GUI 仪表盘与测试稳定性（未发布）**:
- Dashboard DV-2 已完成：新增主题分布环形图与情绪频率水平柱状图，并补齐空状态、Dark Mode 与搜索跳转交互
- 历史 dashboard 执行计划已归档到 `docs/archives/web_gui_init/upgrade/plan-dashboard-visual.md`
- 修复 `tests/unit/test_web_write.py` 与 `tests/unit/test_web_write_route.py` 组合运行时的 `ResourceWarning`，当前 scoped web regression 已恢复为 clean output

**Web GUI 仪表盘视觉线闭环（未发布）**:
- Dashboard DV-1 ~ DV-5 已全部完成：热力图、主题分布、情绪频率、标签词云、人物关系、布局响应式、空状态统一、Dark Mode 抛光与轻量动效均已落地
- Dashboard 现已作为一条完整可交付视觉线收尾；后续工作优先参考当前 backlog / roadmap，而不是继续使用已归档 phase plan 作为入口

**Web GUI 文档收口与 Tier 1 对齐（未发布）**:
- `docs/web-gui/README.md` 已成为当前 Web GUI 文档入口
- `docs/web-gui/UIUX/` 被保留为当前视觉方向与迁移资料目录
- `docs/archives/web_gui_init/` 已收纳历史 phase plans、legacy full TDD 文档与 `upgrade/` 规格/执行计划，保留原始目录结构供审计追溯
- `README.md`、`AGENTS.md`、`docs/PRODUCT_BOUNDARY.md`、`docs/API.md`、`tools/lib/AGENTS.md`、`AGENT_ONBOARDING.md` 已同步当前项目现实（可选 Web GUI、backup CLI、archive 路径、tool/workflow 权责边界）

**运行时透明度与安全验收链路闭环（未发布）**:
- 已清理真实用户数据目录中的确认污染日志/附件，并执行 `life-index index --rebuild` 重新对齐 metadata cache / search index
- `AGENTS.md` 已新增强制防污染规则：开发 / 测试 Agent 默认不得向真实 `~/Documents/Life-Index/` 写入临时日志或附件；如因验收需要误写真实目录，必须记录、删除并 rebuild
- `tests/e2e/runner.py` 已做代码级隔离：E2E runner 默认注入隔离的临时 `LIFE_INDEX_DATA_DIR`，并清理测试生成 journal / attachment，避免再次污染真实用户数据
- 新增 `tools.dev.run_with_temp_data_dir` 沙盒 helper，支持 `--for-web`、`--seed`、`--cleanup-now`、`--name` 以及结构化 `--json` 输出；当前已形成手工 Web GUI 验收的标准安全入口
- `docs/API.md` 已文档化 `run_with_temp_data_dir` 的输出契约（含 `readonly_simulation`、`acceptance_checklist`、`post_acceptance_actions`、`next_steps`、`cleanup_command` 等字段），`README.md` 已增加可见入口
- Web GUI 现已在 `/api/health`、`/api/runtime`、启动日志、全局 runtime banner 以及 dashboard/search/write/edit/journal 页面级提示中显式暴露当前数据源、override 状态与只读仿真标记，降低验收/调试时误连真实用户目录的风险
- `AGENT_ONBOARDING_WEB.md` 已新增 Web runtime / data-dir verification gate，要求 Agent 在继续 write/edit 验收前先核对启动日志、API 与页面 runtime 信息
- write/edit 在 `readonly_simulation=true` 时保持“写入临时副本、不回写真实目录”的非阻塞模型，并在成功跳转后通过 journal warning banner 明示当前操作发生在临时副本中
- write/edit 提交区现已补上 action-level 提示：当 `readonly_simulation=true` 时，提交按钮附近会明确提示“提交后仍会写入临时副本，不会回写真实用户目录”
- 当前阶段的非 README closeout 文档已完成一轮状态统一：`CHANGELOG.md`、`docs/web-gui/post-v1.4-backlog.md`、`docs/web-gui/next-phase-roadmap.md` 与 `AGENT_ONBOARDING_WEB.md` 对 post-v1.4 closeout、runtime transparency、sandbox / readonly simulation 与 onboarding gate 的叙述已重新对齐

**当前阶段 closeout checklist（进行中）**:
- [x] sandbox / anti-pollution 安全链路落地
- [x] `/api/health`、`/api/runtime`、startup log 与页面 runtime 提示对齐
- [x] dashboard/search/write/edit/journal 页面级 runtime/operator 提示补齐
- [x] write/edit 在 readonly simulation 下的非阻塞 notice 模型落地
- [x] `AGENT_ONBOARDING_WEB.md` 增加 runtime / data-dir verification gate
- [x] 非 README 文档状态统一
- [x] write/edit 提交区 action-level transparency 提示补齐
- [ ] 进入下一轮 UI/UX 想法讨论与优先级判断

---

## [2026-03-22] v1.4.0 — Web GUI delivery-ready handoff

**决策**: 将 Web GUI 从 MVP 实现推进到可交付状态，并完成真实浏览器主链路 walkthrough 验证。

**核心变更**:
- 新增完整 Web GUI 交互层：dashboard / journal / search / write / edit 页面全部落地
- 新增 Web 写入主链路：本地附件上传、URL 附件下载桥接、写作模板、metadata smart-fill、success/warning surfacing
- 新增 Web 编辑主链路：编辑页、`/api/weather`、`/api/reverse-geocode`、location/weather 前端闭环
- 新增多轮产品 polish：weather/loading feedback、attachment UX、responsive/layout consistency、visual hierarchy/touch-target refinement、base/nav/writing closeout
- 修复真实浏览器 walkthrough 暴露的主链路缺陷：`/write` 空 `attachments` 422、search results `score=None` 模板渲染 500
- 新增专项验证：URL download unit tests、CSRF contract tests、aggregated web regression、真实 Playwright walkthrough

**升级说明**:
- 这是 **minor release**：新增大量用户可见功能，但不要求迁移日志、附件或配置
- 推荐升级后执行：`life-index index`
- 仅当 health 或搜索验证异常时，再执行：`python -m tools.build_index --rebuild`
- 如果需要使用 Web GUI，请重新安装带 web 依赖的环境：Windows 下建议执行 `.venv\Scripts\pip install -e .[web]`

**验证状态**:
- aggregated Web regression 已通过
- 真实 Playwright walkthrough 已打通：write → journal → edit → search → dashboard reload

---

## [2026-03-20] v1.3.0 — 工程加固

**决策**: 基于 CTO 架构评审（v1.2.0），完成 CI 加固、覆盖率保护、搜索降级和集成测试。

**核心变更**:
- **CI 阻塞化**: mypy 类型检查和 flake8 lint 从 warning 升级为 blocking
- **覆盖率保护**: fail_under 从 49% 提升至 70%，匹配实际覆盖率水位
- **语义搜索优雅降级**: fresh install 时自动降级为纯关键词搜索，附带建议提示
- **RRF 融合集成测试**: 覆盖双管道并行 + 融合排序的完整路径
- **文件锁超时参数化**: 支持不同场景的超时配置

**升级说明**: 无 breaking changes，直接 `pip install -e .` 即可。

---

## [2026-03-16] v1.0 Release Playbook 启动

**决策**: 完成 CTO 级架构评审，制定 v0.1.0 → v1.0.0 发布计划。

**核心变更**:
- Phase 1-2 完成：修复附件路径正则 bug，统一 CLI 入口点
- README.md 精简：991 行 → 586 行
- 四层检索架构设计意图已写入 README 和 AGENTS.md

---

## [2026-03-14] 测试覆盖率提升至 72%

**决策**: 为覆盖率 0% 的核心模块创建完整测试套件。

**核心变更**:
- 测试数从 218 增至 802（+584 个测试）
- 新增测试：L1/L2/L3 搜索、排序算法、语义搜索、元数据缓存
- 通过率：100%

---

## [2026-03-14] CTO 评审修复：坏路径、残留导入、占位 URL

**决策**: 基于 CTO 技术评审报告修复 P0/P1 级代码缺陷。

**核心变更**:
- 修复 `update_monthly_abstract()` 坏路径调用
- 清理残留导入（`from lib.xxx` → `from ..lib.xxx`）
- 全局替换 GitHub 占位符 `yourusername` → `DrDexter6000`

---

## [2026-03-13] 代码质量修复：安全性、可靠性、事务保护

**决策**: 修复 P0 级问题，提升代码质量和架构合规性。

**核心变更**:
- **SSOT 原则执行**: 统一使用 `lib/frontmatter` 作为解析单一事实来源
- **事务保护机制**: 添加基于临时文件的事务保护，确保原子性
- **L2 搜索性能优化**: 新建 SQLite 元数据缓存，性能提升 50-100x

---

## [2026-03-12] 模块深度拆分与代码重构

**决策**: 细化拆分 write_journal 和 search_journals 模块，提升可维护性。

**核心变更**:
- `write_journal/core.py`: 952 行 → 192 行（减少 80%）
- `search_journals/core.py`: 906 行 → 233 行（减少 74%）
- 新增子模块：utils、frontmatter、attachments、weather、index_updater、l1_index、l2_metadata、l3_content、semantic、ranking

---

## [2026-03-11] 类型错误修复与模块化重构

**决策**: 修复 145+ 个 mypy 类型错误，完成核心模块初步拆分。

**核心变更**:
- 添加完整类型注解
- 大文件拆分为模块化结构

---

## [2026-03-09] 附件自动检测与元数据格式修复

**决策**: 实现从日志内容中自动检测本地文件路径作为附件处理。

**核心变更**:
- 新增 `extract_file_paths_from_content()` 自动提取 Windows/UNC 路径
- 修复元数据格式与历史日志保持一致

---

## [2026-03-08] 天气自动填充与确认流程

**决策**: 实现三层天气处理机制，减少用户输入负担。

**核心变更**:
- 自动填充默认地点，自动查询天气
- 返回 `needs_confirmation` 引导用户确认

---

## [2026-03-06] 语义搜索与 FTS 索引实现

**决策**: 实现 `--semantic` 参数，支持 BM25 + 向量相似度混合排序。

**核心变更**:
- FTS5 增量索引
- RAG 语义检索框架
- 双后端架构（sqlite-vec / simple_numpy）

---

## [2026-03-05] 极速记录 + 补全模式实现

**决策**: 实现"先写入后编辑"工作流，创建 `edit_journal.py` 工具。

---

## [2026-03-04] 定义原子工具接口

**决策**: 确立三个核心原子工具：write_journal、search_journals、query_weather。

---

## [2026-03-04] 文档体系重构（SSOT 合规）

**决策**: 拆分文档为 HANDBOOK.md（架构）、INSTRUCTIONS.md（指令）、CHANGELOG.md（历史）。

---

## [2026-03-03] SRS v1.0 定稿

**决策**: 完成 Life Index v3 软件需求规格说明书。

---

## [2026-02-24] 项目重构启动

**决策**: 彻底重构项目，建立 Life Index v3 新系统。

---

**文档结束**
