# Phase C TDD Brief — Candidate edges report (#3)

> **Phase**: C | **gbrain Candidate**: #3
> **Worktree**: `.claude/worktrees/gbrain-C/`
> **Branch**: `claude/gbrain-C`
> **Wave**: 1 (independent)
> **PRD**: `docs/projects/gbrain-absorption/PRD.md` §5 Phase C

## 派发纪律 3 门（PRD §5 引用）

- **可证伪退出**: `entity --candidate-edges --output=json` 输出 `[{type, source, target, evidence_paths[], confidence, suggested_action}]`；零 `entity_graph.yaml` 写入断言通过；`test_candidate_edges_contract.py` 通过
- **真实消费者**: 用户人工 review（采纳/拒绝候选边）+ Phase D maintenance 引用统计
- **有界自主**:
  - 可写：`tools/entity/__main__.py`（加 `--candidate-edges` 分支）, `tools/entity/candidate_edges.py`（新建）, `tests/contract/test_candidate_edges_contract.py`
  - 可读：全仓库（人物/related_entries/wikilink/共现 都要扫）
  - **不动**：Entity Graph 现有写入逻辑、`entity_graph.yaml` 文件本身

## Task 清单

1. **Scaffold**：`tools/entity/candidate_edges.py`，含：
   - `extract_candidates_from_people()` 扫 frontmatter `people` 字段
   - `extract_candidates_from_related_entries()` 扫 `related_entries`
   - `extract_candidates_from_wikilinks()` 扫正文 wikilink `[[X]]` 模式
   - `extract_candidates_from_cooccurrence()` 扫共现（同一篇日记多次提及）
2. **Test (RED)**：`tests/contract/test_candidate_edges_contract.py`：
   - 测 CLI flag `entity --candidate-edges` 输出 JSON
   - 测 JSON schema：`type`/`source`/`target`/`evidence_paths`/`confidence`/`suggested_action`
   - 测**零 production graph 写入**断言（运行前后 `entity_graph.yaml` 哈希不变）
   - 测每个 candidate 含至少 1 evidence_path
3. **Implement (GREEN)**：
   - 4 个 extractor 实现
   - `entity/__main__.py` 加 `--candidate-edges` flag，路由到 `candidate_edges.run()`
   - 输出聚合 + 去重
   - confidence 计算：基于 evidence 数量 + 来源类型
4. **suggested_action 设计**：
   - `evidence_count >= 3` → "auto-confirm-recommended"
   - `2 <= evidence_count < 3` → "review-recommended"
   - `evidence_count < 2` → "review-required-low-confidence"
5. **Docs**：`docs/API.md` 加 `entity --candidate-edges` 文档；`CHANGELOG.md` 加条目
6. **Self-check**
7. **PR**

## 红绿测试要求

- TDD 严格
- 必含"零写入"测试（before/after `entity_graph.yaml` 哈希对比）

## 验收标准

- `entity --candidate-edges --output=json` 输出合法 JSON
- 每 candidate 含 6 字段
- 零 `entity_graph.yaml` 写入（hash test PASS）
- `test_candidate_edges_contract.py` PASS
- `test_layer_invariants.py` PASS（无 LLM）
- `docs/API.md` 已更新
- `CHANGELOG.md` 已更新

## 自检 Checkbox

- [ ] 契约测试 PASS
- [ ] Layer invariant PASS
- [ ] **零写入测试 PASS**（`entity_graph.yaml` hash before == after）
- [ ] 4 extractor 各自有测试覆盖
- [ ] confidence 分级合理（手动抽样 ≥ 5 候选验证）
- [ ] `docs/API.md` 已更新
- [ ] `CHANGELOG.md` 已更新
- [ ] PR 描述含 red→green + 抽样 candidate JSON snippet

## 下一 Task 指针

PR merged → 主控勾 Phase C → Phase D 解锁（若 Phase A 也已 merged）。

## 执行总结（subagent 完成后填）

```
完成时间: <TBD>
实际 LOC: <TBD>
遇到的难点: <TBD>
验收证据:
  - test_candidate_edges_contract.py output: <snippet>
  - 抽样 candidate JSON (3-5 条): <snippet>
  - entity_graph.yaml hash before/after: <hashes>
```
