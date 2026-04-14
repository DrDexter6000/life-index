# Round 7 优化调整 TDD — 归档校准版

> **首次起草日期**：2026-04-14
> **归档校准日期**：2026-04-14
> **前置阅读**：`Round_7_Audit.md`、`TDD.md`、`Phase_1_TDD.md`、`Phase_2_TDD.md`
> **文档角色**：记录 Round 7 收尾阶段的纠偏、校准与验证工作；不再作为活跃开发计划
> **最终状态**：**全部完成，归档关闭**

---

## 背景说明

本文件最初是基于一版**存在误判的审计**起草的。当时误以为：

- `entity_runtime` 尚未接入 search 热路径
- `entity_candidates` 尚未接入 write 热路径
- `timing.py` 无任何业务消费者

后续通过**直接读取源码**与**独立复核**确认：

- `entity_runtime -> search_journals` 已真实存在
- `entity_candidates -> write_journal` 已真实存在
- `timing.py` 已被 `write_journal` 使用

因此，本文件已从“补做热路径集成计划”转变为“Round 7 收尾校准记录”。

---

## 一、原计划中不再执行的事项

### 原 Task 1 — entity_runtime + entity_cache 接入 search_journals

**状态**：取消执行（原因：工作已在 Round 7 主实现中完成）

**确认依据**：

- `search_journals/core.py` 已导入并使用 `entity_runtime`
- search 输出已包含 `entity_hints`
- 对应测试已通过

### 原 Task 2 — entity_candidates 接入 write_journal

**状态**：取消执行（原因：工作已在 Round 7 主实现中完成）

**确认依据**：

- `write_journal/core.py` 已导入并调用 `extract_entity_candidates()`
- write 输出已包含 `entity_candidates`
- 对应测试已通过

### 原 Task 6 — timing.py 标记 deprecated

**状态**：取消执行（原因：前提判断错误）

**确认依据**：

- `write_journal/core.py` 已实际使用 `Timer`
- 因此 `timing.py` 不是死代码，不能按 deprecated 处理

---

## 二、本轮实际完成的收尾任务

### Task A — AGENTS / MODULE REGISTRY 校准

已完成以下修正：

- `timing.py` 改为准确反映 `write_journal` 使用状态
- `trace.py` 加入 module registry
- `entity_runtime.py` / `entity_candidates.py` / `entity_relations.py` 等 Round 7 模块登记校准
- `entity_cache.py` 调整为准确描述：helper 已实现，但不是当前 search/write 主热路径

### Task B — Round 7 审计文档勘误

已完成以下修正：

- 清除“热路径未接入”的旧误判
- 将 Round 7 结论统一校准为“已完成，可关闭”
- 把 `entity_cache.py` 的状态修正为**实现完成但非当前主热路径**

### Task C — 脆弱测试修复

已完成以下修正：

- `test_cache_faster_than_parsing` 从相对耗时比较改为绝对阈值判断
- 全量 `pytest tests/unit/` 回归重新通过

### Task D — 顶层 SSOT 文档同步

已完成以下修正：

- `.strategy/strategy.md`：更新当前 CLI 状态为 Round 7 已完成
- `.strategy/ROADMAP.md`：更新 Round 7 三个 Phase 全部完成
- `.strategy/cli/TDD.md`：标注 Round 7 已完成，下一轮参考 `Round_8_TDD_prep.md`
- `docs/API.md`：补写 `entity_hints` / `entity_candidates` 等 Round 7 输出字段

---

## 三、最终完成检查清单

### 核心能力

- [x] `search_journals` 输出包含 `entity_hints`
- [x] `write_journal` 输出包含 `entity_candidates`
- [x] Entity CLI review / merge / delete / stats / check / review_io 全部可用
- [x] graph 缺失时 search / write 行为无回归

### 文档与 SSOT

- [x] `Round_7_Audit.md` 已清除残留误判
- [x] `Round_7_Optimization_TDD.md` 已转为归档校准版
- [x] `.strategy/strategy.md` / `.strategy/ROADMAP.md` / `.strategy/cli/TDD.md` 已同步当前状态
- [x] `tools/lib/AGENTS.md` 已校准模块登记
- [x] `docs/API.md` 已体现 Round 7 对外输出契约

### 验证

- [x] 关键 Round 7 测试通过
- [x] `pytest tests/unit/` 全量通过（4 个 Unix-only skip，0 fail）
- [x] flaky metadata cache 性能测试已修复

---

## 四、归档结论

| 项目 | 结论 |
|------|------|
| Round 7 是否仍有未完成 P0 | 否 |
| 本文件是否仍是活跃开发计划 | 否 |
| 本文件当前角色 | Round 7 收尾与校准归档记录 |
| 下一轮入口 | `Round_8_TDD_prep.md` |

**结论**：Round 7 的所谓“优化调整”最终主要是一次**审计纠偏 + 文档校准 + 测试加固**，而不是继续补做核心功能。至此本文件也应随 Round 7 一起归档关闭。

---

*本文件保留的目的，是记录 Round 7 收尾阶段曾经出现过的误判，以及最终如何完成纠偏与归档校准。*
