# Life Index v1.5.0 工作指南

> 本文档定义修复工作的执行标准、验收流程和禁止事项  
> **适用范围**: 所有 v1.5.0 修复任务

---

## 一、执行标准 (Execution Standards)

### 1.1 Commit 规范

每个修复必须**独立提交**，commit message 格式：

```
fix(search): unify semantic backend to pickle/numpy - FIX-01

- Delete search_semantic() from semantic_search.py (dead code)
- Delete hybrid_search() from semantic_search.py (dead code)
- Confirm semantic.py only uses vector_index_simple

Refs: docs/dev1.5.0/FIX_PLAN.md#FIX-01
```

**禁止**：
- ❌ 多个修复混在一个 commit
- ❌ 无 FIX-ID 引用的 commit
- ❌ 提交前未跑测试

### 1.2 分支策略

```bash
# 创建修复分支
git checkout -b fix/v1.5.0-FIX-01

# 修复完成后
pytest tests/ && mypy tools web
git add -A && git commit -m "..."

# 合并入 dev1.5.0 分支（不是 main）
git checkout dev1.5.0
git merge fix/v1.5.0-FIX-01 --no-ff
```

**禁止**：
- ❌ 直接在 main 分支工作
- ❌ 跳过 dev1.5.0 中间分支
- ❌ force push

### 1.3 测试验证

修复每个问题后必须执行：

```bash
# 必须通过
pytest tests/

# 必须 clean
mypy tools web

# 建议执行（验收测试）
python -m tools.search_journals --query "关键词" --level 3
python -m tools.write_journal --data '{"title":"验收测试","content":"测试内容","date":"2026-03-28"}'
```

---

## 二、验收流程 (Acceptance Flow)

### 2.1 单项验收

每完成一个 FIX-XX，执行以下验收：

| 步骤 | 操作 | 预期结果 |
|------|------|---------|
| 1 | `pytest tests/` | 全 PASS |
| 2 | `mypy tools web` | 无 error |
| 3 | 功能实测 | 正常工作 |
| 4 | 更新 FIX_PLAN.md 状态 | ✅ Completed |

### 2.2 版本验收

全部 P0 完成后，执行以下验收：

| 步骤 | 操作 | 预期结果 |
|------|------|---------|
| 1 | `pytest tests/ --cov=tools --cov=web` | ≥ 70% coverage |
| 2 | 全功能实测 | write/search/edit/weather 全正常 |
| 3 | Web GUI 实测 | localhost:8765 所有页面正常 |
| 4 | 更新 CHANGELOG.md | v1.5.0 entry |
| 5 | 创建 PR | 等待审核 |

---

## 三、禁止事项 (Prohibitions)

### 3.1 绝对禁止

| 禁止项 | 理由 |
|--------|------|
| 绕过 SSOT 直接解析 frontmatter | 违反项目核心原则 |
| 修改用户数据目录的日志文件 | 数据安全 |
| 使用 `as any` / `@ts-ignore` | 类型安全底线 |
| 删除测试文件 | 测试是资产 |
| force push main | 团队协作底线 |
| 未跑测试就 commit | 验收底线 |

### 3.2 本次修复禁止

| 禁止项 | 理由 |
|--------|------|
| 添加新功能 | 版本范围限定 |
| 重构未标记的代码 | 最小改动原则 |
| 修改 API 接口签名 | 向后兼容 |
| 修改 frontmatter 格式定义 | 格式稳定底线 |
| 引入新依赖 | 依赖控制 |

---

## 四、文件修改权限矩阵

| 文件类别 | 本次修复可修改 | 理由 |
|----------|---------------|------|
| `tools/lib/semantic_search.py` | ✅ 删除死代码 | FIX-01 |
| `tools/lib/vector_index_simple.py` | ✅ 预归一化 | FIX-04 |
| `tools/lib/search_index.py` | ✅ YAML 解析 | FIX-02 |
| `tools/lib/frontmatter.py` | ❌ 不动 | SSOT 定义，格式稳定 |
| `tools/lib/config.py` | ❌ 不动 | SSOT 定义 |
| `tools/lib/errors.py` | ❌ 不动 | SSOT 定义 |
| `tests/` | ❌ 不删除，✅ 可添加 | 测试保护 |
| `web/` | ❌ 不动 | 本次修复范围外 |
| `pyproject.toml` | ✅ 仅改版本号 | 发布时 |
| `docs/CHANGELOG.md` | ✅ 添加 v1.5.0 entry | 发布时 |

---

## 五、回滚策略

如果修复引入问题：

```bash
# 单项回滚
git revert <commit-hash>

# 整版本回滚
git checkout main
git branch -D dev1.5.0  # 删除问题分支
git checkout -b dev1.5.0  # 从 clean 状态重新开始
```

**回滚触发条件**：
- pytest 测试失败
- 功能实测异常
- 用户数据格式不一致

---

## 六、进度报告

每完成一个 FIX-XX，更新 `FIX_PLAN.md` 的进度跟踪表：

```markdown
| 日期 | 完成项 | 备注 |
|------|--------|------|
| 2026-03-28 | FIX-01 | 统一语义后端完成 |
| 2026-03-28 | FIX-02 | YAML 解析统一完成 |
| — | — | — |
```

---

## 七、问答 / 决策记录

修复过程中遇到的问题和决策记录在此：

```markdown
### Q1: sqlite-vec 是否应该完全删除？
- 决策: 保留 update_vector_index() 作为可选构建路径
- 理由: Windows 兼容性不确定，保留 fallback
- 时间: 2026-03-28
```

---

*本文档随修复进度更新。完成后归档至 `docs/archive/v1.5.0/`*