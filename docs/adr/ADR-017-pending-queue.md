# ADR-017: 废弃 Write-Through 索引更新，改用 Pending Queue

**Status**: Accepted
**Date**: 2026-04-18
**Round/Phase**: Round 12 Phase 0 → Phase 1

## Context

Round 12 诊断发现索引子系统存在 7 个结构性 bug（详见 `Round_12_PRD.md` §0）。其中最严重的是 **A1**：write-through FTS INSERT 语句自 v2 schema 升级以来从未成功过 — 13 个占位符对应 14 个列，每次写入触发 `IntegrityError` 被静默吞掉。

此外：
- **A3**: `edit_journal` 从不更新 FTS（只更新向量），导致编辑后 FTS 内容过时
- **A7**: 搜索自动更新只修复 FTS，不修复向量
- **A4**: FTS + 向量索引无原子性保证

这意味着"Write-Through 自动更新"是一个从未兑现的承诺。SKILL.md 工作流5 中的 "无需手动维护" 描述具有误导性。

## Decision

1. **废弃 write-through 机制**（Phase 1 执行）：从 `write_journal/core.py` 和 `index_updater.py` 中移除 write-through 代码路径
2. **引入 Pending Queue**：写入/编辑后只标记"索引待更新"（文件级标记），搜索前自动触发增量索引更新
3. **新增诊断工具**（Phase 0 已完成）：
   - `index --check` — 只读一致性检查
   - `health --data-audit` — 数据目录清洁度审计
4. **SKILL.md 工作流5 更新**：移除"Write-Through 自动更新"声明，改为 Pending Queue 描述

## Consequences

### 正面
- 消除 write-through 的静默失败问题（7 个 bug 中修复 A1, A2, A3, A7）
- 索引更新时机明确可控：写入 → 标记待更新 → 搜索前增量更新
- 诊断工具可以量化"索引有多烂"，为后续修复提供基线

### 负面
- Phase 0 → Phase 1 过渡期间，用户写入后需手动 `life-index index` 增量更新
- Pending Queue 需要额外的标记文件管理（设计见 Phase 1 TDD）

### 风险
- Pending Queue 标记文件损坏 → 回退到全量 `index --rebuild`
- 搜索前自动增量更新增加首次搜索延迟（预计 < 2s for 增量）

## 相关

- `Round_12_PRD.md` §1 问题 A（索引完整性）
- `Round_12_Phase_0_TDD.md`（诊断工具）
- `Round_12_Phase_1_TDD.md`（Pending Queue 实现）
