# Investigation Summary - 2026-03-18

> **日期**: 2026-03-18
> **范围**: Investigation #1, #3, #4, #5
> **状态**: 全部完成

---

## 执行的Investigations

### Investigation #1: Agent-layer confirmation/clarification correctness

**原Tier**: C → **结果Tier**: B

**验证范围**: WF-03, WF-02, WF-10

**发现**:
- WF-03 (确认流程): 通过 - 工具+文档完整
- WF-02 (歧义意图): 文档gap - 指导在review文档而非SSOT
- WF-10 (降级状态): 文档gap - 缺少字段解读

**修复**:
- SKILL.md新增"意图澄清"章节
- SKILL.md新增"写入结果解读"章节
- CANONICAL_WORKFLOWS.md标注为已采纳

---

### Investigation #3: Retrieval Quality

**原Tier**: C → **结果Tier**: B

**发现**:
- 架构实现正确 (双管道 + RRF k=60)
- 运行时发现向量索引污染问题

**关键发现**: 单元测试污染生产向量索引
- 187个向量中165个来自pytest临时目录
- 陈旧向量导致搜索返回不存在的文件

**修复**:
- `config.py`: 支持LIFE_INDEX_DATA_DIR环境变量
- `conftest.py`: 添加isolated_data_dir和isolated_vector_index fixture
- `vector_index_simple.py`: 添加_cleanup_stale_vectors()自动清理

---

### Investigation #4: Failure-injection Scenario Truthfulness

**原Tier**: C → **结果Tier**: B

**验证范围**: FI-01, FI-05, FI-06, FI-07

**结果**:
| Scenario | 判定 |
|:---|:---:|
| FI-01 Weather fails during write | ✅ 通过 |
| FI-05 Index side-effect failure | ✅ 通过 |
| FI-06 Confirmation pending | ✅ 通过 |
| FI-07 Search failure vs empty | ⚠️ 部分通过 |

**核心结论**: 系统正确区分关键状态
- unsaved vs saved ✅
- saved vs saved-but-unconfirmed ✅
- saved vs saved-with-degraded-enrichment ✅
- journal durability vs index completeness ✅

**错误码体系**: 34个错误码，5种恢复策略

---

### Investigation #5: Index-State Observability

**原Tier**: C → **结果Tier**: A

**发现**: `show_stats()` 在sqlite-vec不可用时抛出异常

**修复**: `build_index/__init__.py` Line 175 - 改为触发fallback

**可观测性评估**: 满足基本需求
- FTS: exists, documents, size, last_updated
- Vector: exists, vectors, size, backend, model_loaded

---

## 代码变更汇总

| 文件 | 变更 |
|:---|:---|
| `tools/lib/config.py` | +5行 环境变量支持 |
| `conftest.py` | +83行 隔离fixture |
| `tools/lib/vector_index_simple.py` | +26行 陈旧向量清理 |
| `tools/build_index/__init__.py` | +1行 show_stats修复 |
| `SKILL.md` | +31行 Agent行为指导 |
| `docs/review/execution/CANONICAL_WORKFLOWS.md` | +3行 状态标注 |

---

## 遗留问题

| 问题 | 优先级 | 说明 |
|:---|:---:|:---|
| 语义搜索相似度阈值 | 低 | 改善FI-07区分 |
| Investigation #2未执行 | 低 | 接受现状，无需调查 |

---

## 结论

所有关键investigations已完成。系统在以下方面已验证：
- Agent行为指导完整性 ✅
- 检索架构正确性 ✅
- 失败场景状态区分 ✅
- 索引可观测性 ✅

发现并修复的问题：
1. 向量索引污染 (测试隔离 + 自动清理)
2. show_stats bug (fallback修复)
3. SKILL.md文档gap (内容补充)