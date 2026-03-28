# Life Index v1.5.0 修复计划

> **版本目标**: 修复审计报告中的 HIGH/MEDIUM 问题，夯实系统基础  
> **预计工期**: 1-2 周  
> **最后更新**: 2026-03-28

---

## 修复原则 (Guiding Principles)

修复工作必须遵循以下护栏：

### 1. 最小改动原则
- **只修审计报告标记的问题**，不重构、不优化、不添加新功能
- 每个修复必须是**原子性**的——一个 commit 只修一个问题
- 修复完成后立即运行测试验证

### 2. SSOT 不妥协
- 所有 YAML/frontmatter 解析必须调用 `tools/lib/frontmatter.py`
- 所有路径必须通过 `tools/lib/config.py` 解析
- 所有错误必须使用 `tools/lib/errors.py` 结构化错误码

### 3. 删除优于注释
- 死代码直接删除，不保留"注释掉的代码"
- 不删除测试文件（即使是测试死代码的）
- 删除代码前确认无调用者（grep 全仓库）

### 4. 测试先行
- 修复前确认相关测试存在且能运行
- 修复后必须跑 `pytest tests/` 确认无回归
- `lsp_diagnostics` 必须 clean

### 5. 日志保留原样
- 用户目录 `~/Documents/Life-Index/` 的日志文件**不触碰**
- 修复只影响代码，不影响历史数据
- 格式变更必须有 migration 机制

---

## P0 必修项 (Critical Fixes)

### FIX-01: 统一语义后端为 pickle/numpy

**问题**: H1 - 双后端分裂，搜索走 pickle，构建写 sqlite-vec  
**影响**: 功能正确性  
**工作量**: 2-4h  
**状态**: ✅ Completed (2026-03-28)

**修复范围**:
- 删除 `tools/lib/semantic_search.py` 中的 `search_semantic()` 函数
- 删除 `tools/lib/semantic_search.py` 中的 `hybrid_search()` 函数
- 保留 `semantic_search.py` 中的 `update_vector_index()` 作为可选构建路径（如果 sqlite-vec 可用）
- 确认 `tools/search_journals/semantic.py` 只使用 `vector_index_simple`

**验收标准**:
- `grep -r "search_semantic" tools/` 只返回定义（无调用）
- `grep -r "hybrid_search" tools/` 只返回定义（无调用）
- `pytest tests/` 全通过
- 搜索功能实测正常（搜索任意关键词返回结果）

---

### FIX-02: 统一 YAML/frontmatter 解析

**问题**: S2 - 手写解析违反 SSOT  
**影响**: 维护负担  
**工作量**: 2-4h  
**状态**: ✅ Completed (2026-03-28)

**修复范围**:
- `tools/lib/search_index.py` 第 100-117 行的手写 frontmatter 解析
- `tools/lib/semantic_search.py` 第 207-228 行的手写 frontmatter 解析
- 替换为 `tools/lib/frontmatter.py` 的标准函数

**验收标准**:
- `grep -n "split.*---.*2" tools/lib/` 返回空（无手写解析）
- `pytest tests/` 全通过
- 搜索返回的元数据字段完整（title, date, tags, topic, mood, people, location, weather, abstract）

---

## P1 应修项 (Should Fix)

### FIX-03: 删除时间衰减死代码

**问题**: H3 - time_factor = 1.0 永远不衰减  
**影响**: 认知负载  
**工作量**: 30min  
**状态**: ⬜ Pending

**修复范围**:
- `tools/lib/semantic_search.py` 第 509-517 行的空实现
- 删除 `time_factor` 变量和相关计算

**验收标准**:
- `grep -n "time_factor" tools/` 返回空
- `pytest tests/` 全通过

---

### FIX-04: 预归一化向量

**问题**: H2 - 查询时重复归一化  
**影响**: 性能（当前无感知）  
**工作量**: 1h  
**状态**: ⬜ Pending

**修复范围**:
- `tools/lib/vector_index_simple.py` 的 `SimpleVectorIndex.add()` 方法
- 存储时预归一化，查询时直接使用
- 注意：此修改会导致旧索引不兼容，需要 `life-index index --rebuild`

**验收标准**:
- `SimpleVectorIndex.search()` 中无 `doc_vec = doc_vec / np.linalg.norm(...)` 语句
- `pytest tests/` 全通过
- 搜索返回结果与修复前一致（排序可能略有差异）

---

## P2 观望项 (Watch List)

暂不修复，记录问题供未来参考：

| ID | 问题 | 触发修复条件 |
|----|------|-------------|
| M1 | 加权 RRF 0.6/0.4 未验证 | 用户反馈搜索排序不合理 |
| M2 | BM25→relevance 映射任意 | 搜索结果 relevance 分数与直觉不符 |
| M3 | 哈希算法不一致 | 增量更新出现重复索引 |
| M4 | 单例线程安全靠 GIL | 出现并发问题 |
| M5 | FTS 回退阈值硬编码 <5 | 搜索结果不足且用户不满 |

---

## P3 可选改进 (Optional)

低优先级，有空再做：

### FIX-05: 统一哈希算法

**工作量**: 1h  
**状态**: ⬜ Pending

- FTS 索引（MD5）和向量索引（SHA256）统一为 SHA256[:16]

### FIX-06: 清理项目根目录

**工作量**: 15min  
**状态**: ⬜ Pending

- `server.log`, `tmp_*` 加入 `.gitignore`
- 删除已存在的临时文件

---

## 进度跟踪

| 日期 | 完成项 | 备注 |
|------|--------|------|
| 2026-03-28 | 创建文档体系 | AUDIT_REPORT + FIX_PLAN |
| 2026-03-28 | FIX-01 | 统一语义后端完成，删除 search_semantic/hybrid_search 死代码 |
| 2026-03-28 | FIX-02 | 统一 frontmatter 解析为 SSOT (search_index, semantic_search, vector_index_simple) |

---

## 发布 Checklist

修复完成后，发布 v1.5.0 前必须确认：

- [ ] 所有 P0 项（FIX-01, FIX-02）完成
- [ ] `pytest tests/` 全通过
- [ ] `mypy tools web` 无错误
- [ ] 实测搜索功能正常
- [ ] 实测写入功能正常
- [ ] 实测 Web GUI 正常
- [ ] 更新 `docs/CHANGELOG.md`
- [ ] 更新 `pyproject.toml` 版本号为 1.5.0
- [ ] 创建 PR，标题格式: `v1.5.0: Fix search backend split + YAML parsing SSOT`
- [ ] 合并后打 tag `v1.5.0`

---

## 文档归档计划

v1.5.0 发布后：

```
docs/dev1.5.0/ → docs/archive/v1.5.0/
├── AUDIT_REPORT.md   → archive/v1.5.0/AUDIT_REPORT.md
├── FIX_PLAN.md       → archive/v1.5.0/FIX_PLAN.md (添加"COMPLETED"标记)
└── CHANGELOG.md      → 合并入 docs/CHANGELOG.md
```