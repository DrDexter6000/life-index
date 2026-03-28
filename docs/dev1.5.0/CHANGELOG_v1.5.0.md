# Life Index v1.5.0 变更记录

> 本文档记录 v1.5.0 的所有变更  
> **完成后合并入 `docs/CHANGELOG.md`**

---

## v1.5.0 (待发布)

### 修复 (Fixes)

#### 检索系统

- **FIX-01**: 统一语义搜索后端为 pickle/numpy
  - 删除 `semantic_search.py` 中的 `search_semantic()` 死代码
  - 删除 `semantic_search.py` 中的 `hybrid_search()` 死代码
  - 确认搜索运行时只使用 `vector_index_simple.py`
  - 影响: 修复双后端分裂问题，搜索路径与构建路径一致
  - 参考: AUDIT_REPORT.md H1

- **FIX-02**: 统一 YAML/frontmatter 解析为 SSOT
  - 替换 `search_index.py` 手写解析为 `frontmatter.parse_frontmatter()`
  - 替换 `semantic_search.py` 手写解析为 `frontmatter.parse_frontmatter()`
  - 影响: 元数据解析一致，维护负担降低
  - 参考: AUDIT_REPORT.md S2

- **FIX-03**: 删除时间衰减死代码
  - 删除 `semantic_search.py` 中 `time_factor = 1.0` 空实现
  - 影响: 代码认知负载降低
  - 参考: AUDIT_REPORT.md H3

- **FIX-04**: 预归一化向量存储
  - `SimpleVectorIndex.add()` 时归一化向量
  - `SimpleVectorIndex.search()` 时省去逐文档归一化
  - 影响: 搜索性能提升 ~2x
  - 注意: 需运行 `life-index index --rebuild` 重建索引
  - 参考: AUDIT_REPORT.md H2

#### 代码清理

- **FIX-05**: 统一哈希算法为 SHA256[:16]
  - FTS 索引和向量索引使用相同哈希算法
  - 影响: 增量更新逻辑一致
  - 参考: AUDIT_REPORT.md M3

- **FIX-06**: 清理项目根目录临时文件
  - 添加 `server.log`, `tmp_*` 到 `.gitignore`
  - 删除残留临时文件
  - 影响: 项目目录整洁

---

### 变更详情 (Details)

<!-- 修复完成后填写具体变更 -->

```diff
# FIX-01 示例
tools/lib/semantic_search.py:
  - 删除 search_semantic() 函数 (第 434-550 行)
  - 删除 hybrid_search() 函数 (第 552-620 行)
  
tools/search_journals/semantic.py:
  - 无变更（已使用 vector_index_simple）
```

---

### 验收记录 (Acceptance)

| 检查项 | 结果 | 时间 |
|--------|------|------|
| pytest tests/ | — | — |
| mypy tools web | — | — |
| 搜索实测 | — | — |
| 写入实测 | — | — |
| Web GUI 实测 | — | — |

---

### 用户影响 (User Impact)

- **需要操作**: 运行 `life-index index --rebuild` 重建语义索引（FIX-04 导致向量格式变更）
- **数据兼容**: 日志文件格式无变更，历史日志无需迁移
- **功能变更**: 无，所有功能行为与 v1.4.0 一致

---

### 审计来源 (Audit Reference)

本次版本修复问题来源于:
- `docs/dev1.5.0/AUDIT_REPORT.md` - CTO 全面审计报告
- `docs/dev1.5.0/FIX_PLAN.md` - 修复计划

---

*完成发布后，本文档内容合并入 `docs/CHANGELOG.md`，此文件归档至 `docs/archive/v1.5.0/`*