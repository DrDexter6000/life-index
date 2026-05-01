<!-- AGENTS.md - Life Index Agent 导航入口 -->

> 本文档为 AI 编码代理提供**快速导航入口**。详细规范已归源到 SSOT 文档，本文件仅保留指引与 Agent 行为约束。
> **最后更新**: 2026-04-23 | **版本**: v3.0 | **状态**: 活跃维护
>
> 本地专属配置（含部署路径）见 `.agents.local.md`（已 gitignored，仅本地可用）。

---

## 🏛️ 宪章优先（Charter First）

**[`CHARTER.md`](CHARTER.md) 是最高治理文件**，效力高于本文件及所有其他文档。动手写代码前，若触及 L2/L3 边界、搜索参数、架构变更，**必须先通读 CHARTER.md**。

---

> **战略文档协同规则**：任何 Agent 接手 CLI 开发时，必须先阅读 `.strategy/strategy.md` 与 `.strategy/ROADMAP.md`（本地 NTFS junction，仅本地可用），禁止跳过共享战略文档直接开始开发。
>
> **CLI / GUI 共享规则**：所有高层战略、路线图、阶段进展统一记录在共享 `.strategy/` 中；CLI 侧不得维护一份独立平行战略文档。

## 项目概述

**Life Index** 是一个 Agent-Native、local-first 的个人人生日志与检索系统。

- **CLI 原子工具**：write / search / smart-search / edit / abstract / weather / index / backup / migrate
- 用户通过自然语言 + Agent 调用 Python CLI 工具

**核心理念**:
- **Agent-Native**：CLI 是 Agent 的母语。发挥 Agent 自然语言理解能力，仅在需要原子性/准确性时开发专用工具
- **本地优先**：所有数据存储在 `~/Documents/Life-Index/`
- **纯文本格式**：Markdown + YAML Frontmatter，永不过时

---

## 📚 Agent 必读导航

| 场景 | 必读文档 | 说明 |
|------|----------|------|
| **首次接手项目** | `CHARTER.md` → `AGENT_ONBOARDING.md` → `SKILL.md` | 先理解治理规则，再执行安装，最后掌握技能接口 |
| **涉及架构/模块变更** | `CHARTER.md` §1-§2 + `docs/ARCHITECTURE.md` | 宪章分层边界 + 技术实现细节 |
| **修改搜索参数/阈值** | `CHARTER.md` §3 + `docs/ARCHITECTURE.md` §4-§5 | 搜索子系统不变量 + 架构参数 |
| **新增/修改 CLI 命令** | `docs/API.md` + `CHARTER.md` §1.3 | 接口契约 + CLI 为 SSOT 规则 |
| **修改数据格式/Schema** | `CHARTER.md` §1.1-§1.2 + `docs/ARCHITECTURE.md` §6.3 | 数据隔离不变量 + 日志格式规范 |
| **代码风格疑问** | `docs/ARCHITECTURE.md` §6.1 | 命名、类型注解、路径处理等 |
| **模块结构疑问** | `docs/ARCHITECTURE.md` §6.2 | tools/ 目录树 |
| **本地部署到实机** | `.agents.local.md` | 本地 OpenClaw/WSL 部署路径（已 gitignored） |

> **重要**：`docs/archive/` 目录包含历史开发文档，仅供考古参考。除非用户明确要求，Agent 不应阅读该目录内的文件，以避免浪费上下文和 token。

---

## 文档层级（高→低）

| 层级 | 文档 | 内容 | SSOT 归属 |
|:---:|------|------|----------|
| 🏛️ **L0** | [`CHARTER.md`](CHARTER.md) | **项目宪章**：不变量、分层宪章、反模式、修订流程、工程纪律 | 最高权威 |
| 📐 **L1** | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | **技术实现 SSOT**：架构、参数、代码风格、模块结构、日志格式 | 从属于 CHARTER |
| 📡 **L1** | [`docs/API.md`](docs/API.md) | **接口契约 SSOT**：CLI 参数、错误码、返回值 | 从属于 CHARTER |
| 🗺️ **L2** | `.strategy/strategy.md` | 双产品线战略枢纽（本地 junction） | 本地只读 |
| 🗺️ **L2** | `.strategy/ROADMAP.md` | CLI + GUI 综合路线图（本地 junction） | 本地只读 |
| 📖 **L3** | [`SKILL.md`](SKILL.md) | Agent 技能定义、触发词、工具接口 | Agent 调用入口 |
| 📖 **L3** | [`AGENT_ONBOARDING.md`](AGENT_ONBOARDING.md) | 安装与初始化指南 | 面向 Agent |
| 📖 **L3** | [`README.md`](README.md) | 用户入口、快速开始、常用命令 | 面向人类用户 |
| 🏠 **本地** | `.agents.local.md` | 本地部署路径、环境配置 | 已 gitignored |

---

## 核心工具命令速查

```bash
life-index write --data '{"title":"...","content":"...","date":"2026-03-07","topic":"work"}'
life-index search --query "关键词" --level 3
life-index edit --journal "Journals/2026/03/life-index_2026-03-07_001.md" --set-weather "晴天"
life-index abstract --month 2026-03
life-index weather --location "Lagos,Nigeria"
life-index backup --dest "D:/Backups/Life-Index"
life-index index           # 增量更新
life-index index --rebuild # 全量重建
life-index migrate --dry-run
life-index entity --audit
life-index smart-search --query "自然语言查询"
life-index eval

# 开发者模式（无需安装）
python -m tools.write_journal --data '{...}'
```

完整命令列表与参数详情见 [`docs/API.md`](docs/API.md)。

---

## Agent 行为约束

### 工具调用规则

```bash
# ✅ 正确
python -m tools.write_journal --data '{...}'

# ❌ 错误 - 直接调用脚本
python tools/write_journal.py --data '{...}'
```

### 内容保留原则

- 用户原始输入的 `content` 必须 100% 原样传递
- 禁止修改段落结构、Markdown 标题、列表格式

### 数据隔离

- 用户数据: `~/Documents/Life-Index/`
- 项目代码: 仓库目录
- 两者物理隔离，不可混淆

### 测试防污染规则（强制）

- **严禁**向真实用户数据目录写入测试数据
- 自动化测试必须使用临时目录（`tmp_path`、`LIFE_INDEX_DATA_DIR` override）
- 如因调试不得不在真实目录创建临时文件，任务结束前必须清理并 `life-index index --rebuild`
- 手工验收优先使用隔离沙盒：`python -m tools.dev.run_with_temp_data_dir`

### 仓库卫生规则（强制）

详见 [`CHARTER.md`](CHARTER.md) 附录 D。摘要：
- Push 前执行 `git ls-files | git check-ignore --stdin`，输出必须为空
- 禁止提交 `.handoff.md`、`.pytest_tmp/`、`.recovery/`、调试标记等过程性/临时文件
- 禁止提交个人环境配置（用户名、本地路径等）

---

## 设计底线

详见 [`CHARTER.md`](CHARTER.md) 附录 D.1。

```
宁可功能简单，不可系统复杂
宁可人工维护，不可自动化陷阱
宁可牺牲性能，不可牺牲可靠性
```
