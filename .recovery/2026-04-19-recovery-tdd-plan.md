# Life Index Recovery TDD Plan

> 状态：静态收尾完成（shell 验证受环境阻塞）
> 日期：2026-04-19
> 目标：恢复仓库秩序，保住可救历史成果，验证 Round 15 收口工作，并清除明显噪音。

---

## Phase 0 — 安全与基础设施

- [x] 建立 working tree 安全快照（diff / stat / untracked list）
- [x] 复现 pytest 阻塞问题
- [x] 确认根因：Windows + pytest 默认 `pytest-current` 清理冲突，而非业务测试失败
- [x] 确认默认 `pytest-current` 在 Windows 上会触发清理冲突
- [x] 否决固定 `.pytest_tmp` 方案：会导致目录复用后的权限死锁
- [x] 采用运行时策略：每次验证使用独立 `--basetemp`
- [x] 记录当前执行进度

## Phase 1 — 噪音清理

- [x] 删除明显无回收价值的产物文件
- [x] 再次检查 untracked 清单，确认只剩可疑价值文件

## Phase 2 — Round 15 Core 验证

- [x] 验证 `conftest.py` / `tools/lib/paths.py` / getter-env isolation
- [x] 验证 `tools/build_index/__init__.py` 与 `tools/search_journals/keyword_pipeline.py` 的残余路径迁移
- [x] 验证 Round 15 目标测试簇

## Phase 3 — 历史 Round 打捞验证

- [x] Round 14：paths / conftest lineage
- [x] Round 13：中文检索（tokenizer / stopwords / chinese time units）
- [x] Round 11：query understanding pipeline
- [x] Round 10：ranking / title promotion / rejection
- [x] Round 12：pending writes / manifest / freshness / contract

## Phase 4 — 混合运行时文件稳定化

- [x] 验证 mixed runtime files
- [x] 修复因当前整理引发的问题
- [x] 运行 unit / contract / integration smoke（在 shell 未卡死的颗粒度内已完成；全量 shell smoke 受环境阻塞）

## Phase 5 — 结果收口

- [x] 形成最终恢复报告
- [x] 明确保留簇 / 待后续处理簇 / 剩余风险
