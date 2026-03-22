# Life Index Upgrade Guide

> **文档角色**: Life Index v1.x 的版本语义、兼容性承诺与升级操作指南
> **目标读者**: 项目 Owner、贡献者、操作者、代用户执行升级的 Agent
> **Authority**: 版本含义、兼容性边界、升级流程的统一参考；版本号值以 `pyproject.toml` 为准

---

## 1. 版本语义

Life Index 在 v1.x 期间使用 **SemVer-lite**，版本判断以用户数据安全和操作者工作流影响为主要依据，而非内部实现变化。

### Patch

以下变更使用 patch 版本：

- Bug 修复
- 文档修正或措辞优化
- 无需用户操作的内部重构
- 不改变迁移需求的性能/可靠性改进

Patch 发布不应要求用户手动迁移日志或配置。建议的升级后操作仅限轻量级验证或重建非持久性索引/缓存。

### Minor

以下变更使用 minor 版本：

- 新增用户可见功能
- 已有命令或工作流的有意义扩展
- 向后兼容的元数据或搜索行为变化

Minor 发布可能需要用户阅读 release notes 或执行 `life-index index` 等轻量维护操作，但不应要求手动迁移持久性用户资产。

### Major

以下变更使用 major 版本：

- 日志、frontmatter、配置或附件需要手动迁移
- CLI 行为被故意破坏或移除
- 现有安装/升级流程不再适用
- 持久性用户资产的兼容性承诺无法维持

Major 发布必须附带明确的迁移指南。

### 破坏性变更的定义

对本项目而言，破坏性变更由**用户资产兼容性**和**操作者工作流中断**定义，而非仅由内部重构定义。

通常属于破坏性变更：
- 日志或 frontmatter 不兼容
- 配置不兼容
- 超出正常升级路径的必要操作者动作
- 使现有正常用法失效的 CLI 行为变化

通常不单独构成破坏性变更：
- 内部模块重构
- 用户可见行为不变的实现清理
- 仅需重建的索引/缓存变更（持久性用户资产完好）

### 版本判断规则

1. 是否需要用户迁移日志、配置或附件？→ Major
2. 是否新增有意义的用户可见功能，且持久性资产兼容？→ Minor
3. 主要是修复、澄清或内部改进，无迁移负担？→ Patch

如果不确定，选择对本地优先系统用户更安全、更清晰的解释。

---

## 2. 兼容性承诺

### 核心原则

Life Index 是本地优先系统。v1.x 期间，兼容性决策优先保护用户拥有的持久性资产，而非每一个内部缓存或索引产物。

### 持久性资产（默认向后兼容）

以下资产在整个 v1.x 期间应保持向后兼容：

- `~/Documents/Life-Index/Journals/`
- 日志关联的附件文件
- `~/Documents/Life-Index/.life-index/config.yaml`

普通的 patch 和 minor 发布不应强制用户手动重写或迁移这些资产。如果某个变更需要此类迁移，应作为更强的发布事件处理并明确记录。

### 可重建的运行状态

以下状态可以被视为可重建的运行状态，而非持久性兼容关键资产：

- `.index/`
- 元数据缓存产物
- 搜索索引产物
- 向量索引产物

如果这些状态变得过时或与新内部实现不兼容，首选的补救方式是刷新、重建索引，而非冒险修改用户拥有的日志或配置。

### 迁移说明触发条件

当发布影响以下任一项时，release notes 和升级指南变为强制性：

- frontmatter 契约
- 配置 schema 或语义
- 需要操作者明确操作的搜索/索引行为
- 与正常升级路径不同的安装或 CLI 用法

### 迁移工具触发条件

仅当以下至少一项为真时，才应考虑自动迁移工具：

- 手动迁移可能损坏日志或配置
- 所需迁移过于重复或脆弱
- 不能合理期望用户安全地手动执行变更

如果清晰的手动指南足够且安全，在 v1.x 期间优先使用手动指南。

---

## 3. 升级工作流

> **在文档体系中的角色**：本文档现在主要作为 `AGENT_ONBOARDING.md` 与 `AGENT_ONBOARDING_WEB.md` 在 Step 0 自动分流后的**升级 / 修复权威说明**。普通用户通常不需要先自己判断是否该读本文档；Agent 应先做本地状态检测，再决定是否切换到这里执行。

### 当前支持的升级模型

- **repo-first**
- **正式发布时打 release tag**
- **本地虚拟环境中的可编辑安装**

用户通过更新已有的仓库 checkout 来升级，而非切换到其他分发机制。

### Step 1 — 备份用户数据

升级前备份：

- `~/Documents/Life-Index/`

### Step 2 — 更新仓库

```bash
git pull
```

如果需要特定 release tag，应明确 checkout 该目标，而非盲目跟随移动的分支 tip。

### Step 3 — 重新安装到 venv

#### 基础路径（默认）

**Linux/macOS/WSL**:

```bash
.venv/bin/pip install -e .
```

**Windows**:

```powershell
.venv\Scripts\pip install -e .
```

#### Web GUI 用户路径（可选）

如果你平时会使用本地 Web GUI，请在升级时重装 web extras，而不是只做基础安装。

**Linux/macOS/WSL**:

```bash
.venv/bin/pip install -e ".[web]"
```

**Windows**:

```powershell
.venv\Scripts\pip install -e ".[web]"
```

### Step 4 — 运行健康检查

**Linux/macOS/WSL**:

```bash
.venv/bin/life-index health
```

**Windows**:

```powershell
.venv\Scripts\life-index health
```

### Step 5 — 刷新索引

**Linux/macOS/WSL**:

```bash
.venv/bin/life-index index
```

**Windows**:

```powershell
.venv\Scripts\life-index index
```

### Step 6 — 仅在需要时重建

仅当以下至少一项为真时使用重建流程：

- release notes 明确要求
- `health` 指示搜索/索引问题
- 升级后搜索验证仍有异常

```bash
python -m tools.build_index --rebuild
```

### Step 7 — 验证现有数据

对至少一条已有日志执行已知搜索，确认预期结果仍然出现。

### Step 8 — Web GUI 用户的附加验证（可选但推荐）

如果你会使用本地 Web GUI，建议额外验证一次：

1. 使用 venv 路径运行 `life-index serve`
2. 打开或请求 `http://127.0.0.1:8765/api/health`
3. 确认返回 HTTP 200 且 `status` 为 `ok`

这一步主要用于确认：

- Web 依赖仍然完整
- 本地浏览器界面仍可启动
- 当前升级没有破坏 `serve` 入口

---

## 4. 升级后验证清单

### 最低验证（每次升级必须通过）

1. `life-index health` 成功且未报告不健康状态
2. 对现有数据的一次已知搜索返回预期结果
3. 如果 release notes 提到检索/索引/搜索变更，已运行 `life-index index`
4. 如果 health 或搜索仍有异常，已考虑或执行重建流程

### 增强验证（可选，谨慎操作者推荐）

1. 确认当前配置可正常读取
2. 执行一次小型写入测试
3. 对新写入的条目执行一次搜索

除非 release notes 另有说明，增强验证为可选。

---

## 5. 虚拟环境损坏恢复

如果虚拟环境在 Python 版本变更、安装中断或依赖解析失败后损坏：

1. 删除 `.venv/`
2. 重新创建虚拟环境
3. 重新安装：`pip install -e .`
4. 继续标准的升级后验证流程

如果你使用 Web GUI，则在第 3 步改为：`pip install -e ".[web]"`。

如果是由 onboarding 文档的 Step 0 自动分流进入本文档，并且当前状态属于 **repair / ambiguous**，默认优先使用本节作为恢复基线，而不是回退到 fresh install 思路。

---

## 6. Release Notes 优先规则

当 release notes 明确要求以下操作时，应视为权威指令：

- 重建索引
- 额外的兼容性检查
- 特殊迁移动作
- 特定版本的临时操作者变通方案

如果 release notes 的要求超出本文档，以该版本的 release notes 为准。

---

## 7. 维护者经验法则

发布前的检查清单：

1. 此变更是否可能影响日志、附件或配置？
2. 如果是，变更是否仍然向后兼容？
3. 如果不兼容，发布分级是否正确？是否附带明确的迁移指南？
4. 如果问题仅涉及索引/缓存，重建是否可以作为安全的默认方案？

如果不确定，优先选择保护持久性用户资产并使操作者必要动作明确的路径。

---

## 8. 相关文档

- `docs/CHANGELOG.md` — 发布历史和面向发布的升级说明
- `AGENT_ONBOARDING.md` — 基础入口文档（先做 Step 0 检测，再分流到 fresh install / upgrade / repair）
- `AGENT_ONBOARDING_WEB.md` — Web GUI 入口文档（先做 Step 0 检测，再分流到 fresh install / add-web / upgrade / repair）
- `pyproject.toml` — 当前版本号 SSOT
