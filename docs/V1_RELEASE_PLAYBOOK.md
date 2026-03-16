# Life Index v1.0 Release Playbook

> **本文档是临时性阶段执行手册**，由 CTO 级架构评审会议产出。包含从当前状态（v0.1.0）到 v1.0.0 发布的所有优化步骤。每个步骤可由独立的 Agent 会话执行。完成后本文档应归档或删除。
>
> **创建时间**: 2026-03-16
> **创建背景**: 基于对项目代码、架构、测试、文档的全面评审，与项目 Owner 达成一致的优化方案
> **当前状态**: v0.1.0, 800+ tests, 72% coverage, 2 failing tests, 14 doc files
>
> **已完成的前置工作**（在本 playbook 创建同会话中完成）:
> - ✅ README.md / README.en.md 重构：情感→技术→情感节奏恢复，操作细节折叠，从 991 行精简到 586 行
> - ✅ AGENTS.md 新增"关键架构决策"段落（四层检索意图、数据格式选择、物理隔离原则）
> - ✅ 四层检索架构设计意图已写入 README（折叠式展示）和 AGENTS.md

---

## 执行顺序总览

| Phase | 步骤 | 难度 | 依赖 | 预计耗时 |
|:---:|:---|:---:|:---:|:---:|
| **P1** | 修复 2 个失败测试（附件路径正则 bug） | 简单 | 无 | 30 min |
| **P2** | 统一 CLI 入口点 | 中等 | 无 | 1-2 hr |
| **P3** | 文档精简与合并 | 中等 | 无 | 2-3 hr |
| **P4** | L2 搜索层安全限制 | 简单 | 无 | 30 min |
| **P5** | 语义搜索模型评估与 RRF 排序 | 较难 | P1 完成 | 3-4 hr |
| **P6** | 版本号升级 + GitHub Actions 发布配置 | 中等 | P1-P4 完成 | 1-2 hr |
| **P7** | 发布 v1.0.0 | 简单 | P1-P6 完成 | 15 min |

---

## Phase 1：修复附件路径正则 Bug

### 目标
修复 `tools/write_journal/attachments.py` 中 `extract_file_paths_from_content()` 函数的 Windows 路径提取正则，使 2 个失败测试通过。

### 问题根因
第 117 行正则 `windows_pattern` 的最后一段 `\.[^\\\/:*?"<>|\r\n]+` 没有排除**空格**，导致贪婪匹配到行尾。例如对 `C:\Users\test\file.mp4 for details`，正则匹配出 `C:\Users\test\file.mp4 for details`，然后 `looks_like_file_path()` 提取扩展名为 `mp4 for details`，不在有效扩展名列表里，返回 `False`。

### 操作步骤

1. **定位文件**: `tools/write_journal/attachments.py`, 第 117 行
2. **修复正则**: 扩展名部分应在空格或行尾处停止匹配。修改方案：
   - 方案 A（推荐）：将扩展名匹配改为 `\.\w+`（单词字符，不含空格）
   - 方案 B：在字符类中排除空格 `\.[^\\\/:*?"<>|\r\n\s]+`
   - **注意**：方案 B 更保守但可能影响包含空格的文件名路径匹配。需要同时考虑 `C:\Users\17865\Downloads\Opus 审计报告.txt` 这种中文文件名带空格的情况
   - **推荐策略**：路径中间部分允许空格（目录名、文件名主体），但**扩展名部分**（最后一个 `.` 之后）不允许空格。具体实现：将最后的 `\.[^\\\/:*?"<>|\r\n]+` 改为 `\.[\w]+`，同时确保路径主体部分（扩展名之前）仍允许空格

3. **验证**:
   ```bash
   python -m pytest tests/unit/test_attachments.py -xvs
   # 预期：全部通过，特别是：
   # - test_extract_windows_absolute_path
   # - test_extract_path_with_spaces
   ```

4. **回归测试**:
   ```bash
   python -m pytest tests/unit/ -v
   # 预期：804 passed, 0 failed (原来是 802 passed, 2 failed)
   ```

### 难度评价
**简单** — 单文件单函数修改，有现成失败测试作为验收标准。

### 验收标准
- [ ] `python -m pytest tests/unit/ -v` 全部通过（0 failed）
- [ ] `test_extract_windows_absolute_path` 通过
- [ ] `test_extract_path_with_spaces` 通过
- [ ] 不引入新的测试失败

---

## Phase 2：统一 CLI 入口点

### 目标
将分散的 `python -m tools.xxx` 调用方式统一为 `life-index <subcommand>` 模式。

### 背景
当前 `pyproject.toml` 定义了 `life-index-write`、`life-index-search` 等独立入口，但所有文档使用 `python -m tools.xxx`。两套入口共存造成混乱。

### 操作步骤

1. **创建统一路由** `tools/__main__.py`（如果不存在则创建）:
   ```python
   #!/usr/bin/env python3
   """Life Index - Unified CLI Entry Point"""
   import sys

   def main():
       if len(sys.argv) < 2:
           print_usage()
           sys.exit(1)

       subcmd = sys.argv[1]
       cmd_map = {
           "write": "tools.write_journal",
           "search": "tools.search_journals",
           "edit": "tools.edit_journal",
           "weather": "tools.query_weather",
           "index": "tools.build_index",
           "abstract": "tools.generate_abstract",
           "backup": "tools.backup",
       }

       if subcmd in cmd_map:
           # 重写 argv 让子模块的 argparse 正常工作
           sys.argv = [f"life-index {subcmd}"] + sys.argv[2:]
           module = __import__(cmd_map[subcmd], fromlist=["main"])
           module.main()
       elif subcmd in ("--help", "-h", "help"):
           print_usage()
       else:
           print(f"Unknown command: {subcmd}")
           print_usage()
           sys.exit(1)

   def print_usage():
       print("Usage: life-index <command> [options]")
       print()
       print("Commands:")
       print("  write     Write a journal entry")
       print("  search    Search journals")
       print("  edit      Edit a journal entry")
       print("  weather   Query weather information")
       print("  index     Build/rebuild search index")
       print("  abstract  Generate monthly/yearly summaries")
       print("  backup    Backup journal data")

   if __name__ == "__main__":
       main()
   ```

2. **更新 `pyproject.toml`**: 替换分散入口为单一入口
   ```toml
   [project.scripts]
   life-index = "tools.__main__:main"
   ```
   删除旧的 `life-index-write`, `life-index-search` 等。

3. **更新 SKILL.md 和 AGENTS.md**: 命令示例同时展示两种用法
   ```bash
   # 推荐（pip install 后）
   life-index write --data '{...}'

   # 开发者模式
   python -m tools.write_journal --data '{...}'
   ```

4. **重新安装验证**:
   ```bash
   pip install -e .
   life-index --help
   life-index weather --location "Beijing,China"
   ```

### 难度评价
**中等** — 需要创建新文件、修改 pyproject.toml、更新多处文档。注意各子模块的 `main()` 函数签名是否兼容。

### 验收标准
- [ ] `life-index --help` 输出正确的帮助信息
- [ ] `life-index write --data '{...}'` 正常工作
- [ ] `life-index search --query "测试"` 正常工作
- [ ] `python -m tools.write_journal --data '{...}'` 仍然正常工作（不破坏向后兼容）
- [ ] `python -m pytest tests/unit/ -v` 全部通过

---

## Phase 3：文档精简与合并

### 目标
将 14 个文档文件精简为 6-7 个，降低维护成本，消除重复内容。

### 背景
当前文档体系包含 AGENTS.md + SKILL.md + HANDBOOK.md + INSTRUCTIONS.md + API.md + CHANGELOG.md + 6 ADRs + lib/AGENTS.md + README.md = 14 个文件，约 3500 行。很多内容重复，维护成本过高。

### 操作步骤

#### Step 3.1: 合并 INSTRUCTIONS.md → SKILL.md
1. 读取 `docs/INSTRUCTIONS.md`，识别与 `SKILL.md` 不重复的内容
2. 将不重复内容（工作流步骤、Agent 执行指令）合并到 SKILL.md 的对应小节
3. 在原 `docs/INSTRUCTIONS.md` 位置创建重定向提示（或直接删除）
4. 更新所有引用 INSTRUCTIONS.md 的文档链接

#### Step 3.2: 合并 HANDBOOK.md + 关键 ADR → ARCHITECTURE.md
1. 创建 `docs/ARCHITECTURE.md`
2. 从 `docs/HANDBOOK.md` 提取核心架构内容（四层检索、Agent-first 原则、数据格式选择）
3. 从 `docs/adr/` 中提取关键决策摘要（ADR-001: Agent-first, ADR-003: YAML Frontmatter, ADR-004: MCP 评估）
4. 删除 `docs/HANDBOOK.md` 和 `docs/adr/` 目录（或归档到 git 历史）

#### Step 3.3: 精简 CHANGELOG.md
1. 保留里程碑级别的变更记录
2. 删除每次重构的细节描述
3. 目标控制在 ~100 行

#### Step 3.4: 精简 AGENTS.md
1. 移除与 SKILL.md 重复的工具调用示例
2. 保留：构建命令、代码风格、架构概览、目录结构
3. 目标控制在 ~200 行（当前 ~495 行）

#### Step 3.5: 更新 README.md 文档导航表
1. 更新"文档导航"小节，反映新的文件结构
2. 同步更新 README.en.md

### 目标结构
```
project-root/
├── AGENTS.md                # AI Agent 上下文（~200行）
├── SKILL.md                 # Agent Skill 定义 + 工作流（~350行）
├── README.md / README.en.md # 人类入口
├── docs/
│   ├── ARCHITECTURE.md      # 架构 + 关键决策（~200行）
│   ├── API.md               # 工具参考文档（保持现有）
│   └── CHANGELOG.md         # 仅里程碑（~100行）
└── tools/lib/AGENTS.md      # 共享库指南（保持现有）
```

### 难度评价
**中等** — 主要是阅读和内容整理工作，需要仔细判断哪些内容保留、哪些删除。合并时必须避免丢失关键信息。

### LLM 建议
- 先通读所有待合并文件，建立内容地图
- 用 grep 搜索所有对 `INSTRUCTIONS.md` 和 `HANDBOOK.md` 的引用，确保不遗漏链接更新
- 合并后运行 `grep -r "INSTRUCTIONS.md\|HANDBOOK.md" .` 确认无残留引用

### 验收标准
- [ ] 项目根目录和 docs/ 下文件数从 14 减少到 6-7
- [ ] 没有断裂的文档链接（grep 验证）
- [ ] AGENTS.md 控制在 200 行左右
- [ ] SKILL.md 包含完整工作流指令
- [ ] ARCHITECTURE.md 包含四层检索设计意图、Agent-first 原则、数据格式决策
- [ ] README.md 和 README.en.md 文档导航表已同步更新

---

## Phase 4：L2 搜索层安全限制

### 目标
防止无过滤条件的 L2 查询返回过多数据，耗尽 Agent 上下文窗口。

### 操作步骤

1. **修改文件**: `tools/search_journals/l2_metadata.py`
2. **添加 `max_results` 参数**: `search_l2_metadata(..., max_results=100)`
3. **当结果超过限制时**: 在返回结果中添加 `"truncated": true, "total_available": N` 字段
4. **更新 `core.py`**: 传递 `max_results` 参数

### 难度评价
**简单** — 添加一个参数和截断逻辑。

### 验收标准
- [ ] 无过滤条件搜索最多返回 100 条结果
- [ ] 超出时返回 `truncated: true` 提示
- [ ] 有过滤条件时不受限制
- [ ] 现有测试全部通过

---

## Phase 5：语义搜索改进

### 目标
1. 评估并替换嵌入模型（all-MiniLM-L6-v2 → 适合中英双语的模型）
2. 将混合排序算法从加权求和改为 RRF（Reciprocal Rank Fusion）

### 背景
- 当前 `all-MiniLM-L6-v2` 是纯英文模型，对中文语义理解很弱
- 当前加权混合排序 `w1*fts + w2*vec` 因量纲不同导致结果不稳定
- RRF 是行业标准方案，只看排名不看分数，天然跨量纲兼容

### 操作步骤

#### Step 5.1: 评估嵌入模型（研究阶段，可选执行）

推荐候选模型：

| 模型 | 参数量 | 维度 | 中英混合 | 安装大小 |
|:---:|:---:|:---:|:---:|:---:|
| `BAAI/bge-m3`（首选） | 568M | 1024 | 强 | ~2GB |
| `Alibaba-NLP/gte-multilingual-base`（备选） | 305M | 768 | 强 | ~1.2GB |

**注意**：更换模型需要：
- 修改 `tools/lib/config.py` 中的 `EMBEDDING_MODEL` 配置
- 修改 `tools/lib/semantic_search.py` 中的模型加载逻辑
- **重建全部向量索引**（维度从 384 变为 1024 或 768）
- 更新 `tools/lib/vector_index_simple.py` 中的维度常量

**此步骤风险较高，建议作为 v1.1 后续迭代。v1.0 可以先只做 Step 5.2。**

#### Step 5.2: 实现 RRF 混合排序

1. **修改文件**: `tools/search_journals/ranking.py`
2. **替换** `merge_and_rank_results_hybrid()` 中的加权求和逻辑
3. **实现 RRF**:
   ```python
   def reciprocal_rank_fusion(ranked_lists, k=60, top_k=10):
       """
       Reciprocal Rank Fusion (Cormack et al. SIGIR 2009)
       score(d) = sum(1 / (k + rank(d))) across all ranked lists
       k=60 is the canonical value
       """
       scores = {}
       for ranked_list in ranked_lists:
           for rank, item in enumerate(ranked_list):
               doc_id = item.get("path") or item.get("rel_path")
               if doc_id:
                   scores[doc_id] = scores.get(doc_id, 0) + 1.0 / (k + rank)
       return sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
   ```
4. **保持向后兼容**: `fts_weight` 和 `semantic_weight` 参数保留但标记为 deprecated

### 难度评价
- **Step 5.1（模型替换）**: **较难** — 涉及多文件修改 + 向量重建。建议 v1.1。
- **Step 5.2（RRF 排序）**: **中等** — 替换一个排序函数，但需要确保结果格式兼容。

### 验收标准
- [ ] `python -m tools.search_journals --query "测试" --semantic` 正常工作
- [ ] RRF 排序产出合理结果（同时出现在 FTS 和语义结果中的条目排名更高）
- [ ] 现有搜索测试全部通过
- [ ] `merge_and_rank_results_hybrid()` 使用 RRF 而非加权求和

---

## Phase 6：发布配置

### 目标
配置 GitHub Actions 自动发布工作流，准备 PyPI Trusted Publisher。

### 操作步骤

#### Step 6.1: 更新版本号
1. `pyproject.toml`: `version = "1.0.0"`
2. 更新 README.md 中过时的测试覆盖率数据（已在本 playbook 前置步骤中完成）

#### Step 6.2: 创建 GitHub Actions 发布工作流
创建 `.github/workflows/release.yml`:

```yaml
name: Publish to PyPI

on:
  push:
    tags:
      - 'v*.*.*'

jobs:
  build:
    name: Build distribution
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: "3.x"
    - name: Install build
      run: python -m pip install build
    - name: Build
      run: python -m build
    - name: Store artifacts
      uses: actions/upload-artifact@v4
      with:
        name: python-package-distributions
        path: dist/

  publish:
    name: Publish to PyPI
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: pypi
      url: https://pypi.org/p/life-index
    permissions:
      id-token: write
    steps:
    - uses: actions/download-artifact@v4
      with:
        name: python-package-distributions
        path: dist/
    - uses: pypa/gh-action-pypi-publish@release/v1

  github-release:
    name: Create GitHub Release
    needs: publish
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
    - uses: actions/download-artifact@v4
      with:
        name: python-package-distributions
        path: dist/
    - name: Create Release
      env:
        GITHUB_TOKEN: ${{ github.token }}
      run: >-
        gh release create '${{ github.ref_name }}'
        --repo '${{ github.repository }}'
        --generate-notes
        dist/*
```

#### Step 6.3: 配置 PyPI Trusted Publisher
**这一步需要 Owner 手动在 PyPI 网站操作：**
1. 访问 https://pypi.org/manage/account/publishing/
2. 创建 Pending Publisher:
   - Owner: `DrDexter6000`
   - Repository: `life-index`
   - Workflow name: `release.yml`
   - Environment: `pypi`

### 难度评价
**中等** — YAML 配置 + 网站操作。关键是 PyPI Trusted Publisher 必须由 Owner 手动配置。

### 验收标准
- [ ] `.github/workflows/release.yml` 存在且语法正确
- [ ] `pyproject.toml` 版本号为 `1.0.0`
- [ ] 本地 `python -m build` 成功生成 wheel 和 sdist
- [ ] PyPI Trusted Publisher 已配置（Owner 确认）

---

## Phase 7：发布 v1.0.0

### 前置条件
- [ ] P1-P4 全部完成并验证
- [ ] P5 至少 Step 5.2 完成（RRF 排序）
- [ ] P6 全部完成
- [ ] `python -m pytest tests/unit/ -v` 全部通过（0 failed）
- [ ] `python -m build` 成功

### 操作步骤

```bash
# 1. 确保所有改动已提交
git add -A
git commit -m "chore: prepare v1.0.0 release"

# 2. 创建带注释的 tag
git tag -a v1.0.0 -m "Release v1.0.0 - First stable release"

# 3. 推送
git push origin main
git push origin v1.0.0

# GitHub Actions 自动执行：
# → 构建 wheel + sdist
# → 发布到 PyPI
# → 创建 GitHub Release（自动生成 release notes）
```

### 发布后验证

```bash
# 等待 GitHub Actions 完成（约 2-3 分钟）

# 验证 PyPI
pip install life-index
life-index --help
life-index weather --location "Beijing,China"

# 验证 GitHub Release
# 访问 https://github.com/DrDexter6000/life-index/releases
```

### 验收标准
- [ ] PyPI 上可以 `pip install life-index`
- [ ] `life-index --help` 正常工作
- [ ] GitHub Release 页面显示 v1.0.0
- [ ] Release notes 包含主要特性说明

---

## 附录 A：未来迭代建议（v1.1+）

以下优化在 v1.0 后、根据实际使用反馈再执行：

| 项目 | 优先级 | 说明 |
|:---|:---:|:---|
| 嵌入模型替换（bge-m3） | P1 | 显著提升中文语义搜索质量 |
| MCP Server 支持 | P2 | 当 Claude Desktop 用户有需求时再考虑 |
| sqlite-vec 迁移 | P3 | 当日志数量超过 5000 篇时考虑 |
| 向量索引增量更新优化 | P3 | 目前全量重建，大数据量时需要增量 |

## 附录 B：关键文件清单

| 文件 | 涉及的 Phase |
|:---|:---:|
| `tools/write_journal/attachments.py` | P1 |
| `tools/__main__.py`（新建） | P2 |
| `pyproject.toml` | P2, P6 |
| `SKILL.md` | P2, P3 |
| `AGENTS.md` | P3 |
| `docs/INSTRUCTIONS.md` | P3（合并后删除） |
| `docs/HANDBOOK.md` | P3（合并后删除） |
| `docs/ARCHITECTURE.md`（新建） | P3 |
| `docs/CHANGELOG.md` | P3 |
| `README.md` / `README.en.md` | P3 |
| `tools/search_journals/l2_metadata.py` | P4 |
| `tools/search_journals/core.py` | P4 |
| `tools/search_journals/ranking.py` | P5 |
| `.github/workflows/release.yml`（新建） | P6 |
