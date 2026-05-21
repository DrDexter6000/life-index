# Phase E TDD Brief — Search modes + recall module (#5)

> **Phase**: E | **gbrain Candidate**: #5
> **Worktree**: `.claude/worktrees/gbrain-E/`
> **Branch**: `claude/gbrain-E`
> **Wave**: 1 (independent)
> **PRD**: `docs/projects/gbrain-absorption/PRD.md` §5 Phase E + §3.1 (recall 模块边界)

## 派发纪律 3 门（PRD §5 引用）

- **可证伪退出**: `recall --mode={default|recall|deep}` 通过 subprocess 调 L2；`test_recall_contract.py` ≥ 9 通过（3 modes × 3 case：basic / no_results / opt-in 边界）；deep 模式不带 `--use-llm` 时降级到 recall；零默认 LLM 断言通过
- **真实消费者**: recall 模块本身（Step 3 真模块的 v1）
- **有界自主**:
  - 可写：`tools/recall/`（新建模块）, `tests/contract/test_recall_contract.py`
  - 可读：L2 `search` / `smart-search` 的 CLI 文档（不读源）
  - **不动**：L2 search / smart-search 源码本体

## Task 清单

1. **Scaffold**：`tools/recall/{__init__.py, __main__.py, core.py}`
2. **Test (RED)**：`tests/contract/test_recall_contract.py`：
   - 3 modes × 3 case = 9 tests minimum
   - `test_default_basic` / `test_default_no_results` / `test_default_opt_in_boundary`
   - `test_recall_basic` / `test_recall_no_results` / `test_recall_opt_in_boundary`
   - `test_deep_basic_with_llm` / `test_deep_no_llm_degrades_to_recall` / `test_deep_explicit_opt_in_required`
   - 测无 `--use-llm` 时 deep 自动降级 + 零 LLM trace
3. **Implement (GREEN)**：
   - `core.py` `run_recall(mode, query, use_llm)` 函数
   - default mode: subprocess `search --no-semantic`（纯 FTS）
   - recall mode: subprocess `search`（默认 hybrid）
   - deep mode + `--use-llm`：subprocess `smart-search --use-llm`
   - deep mode 无 `--use-llm`：调用 recall mode，stderr 输出"deep mode degraded to recall"
   - `__main__.py` CLI 入口
4. **CLI 注册**：`tools/__main__.py` 加 `recall` 子命令；schema_version 戳
5. **Docs**：`docs/API.md` 加 `recall` 命令；`CHANGELOG.md` 加条目；说明 mode 语义
6. **Self-check**
7. **PR**

## 红绿测试要求

- TDD 严格
- 必含"零默认 LLM"测试（mode={default,recall} 时不应有任何 anthropic/openai 调用 trace）
- 必含 deep 降级测试

## 验收标准

- `recall --mode=default` 工作（纯 FTS）
- `recall --mode=recall` 工作（hybrid）
- `recall --mode=deep --use-llm` 工作（带 LLM）
- `recall --mode=deep` 不带 `--use-llm` → 降级到 recall + stderr 警告
- `test_recall_contract.py` ≥ 9 PASS
- `test_layer_invariants.py` PASS（含 recall 默认无 LLM 断言）
- `docs/API.md` 已更新
- `CHANGELOG.md` 已更新

## 自检 Checkbox

- [ ] 契约测试 ≥ 9 PASS
- [ ] Layer invariant PASS
- [ ] mode=default 输出与 `search --no-semantic` 一致（spot check）
- [ ] mode=recall 输出与 `search` 默认行为一致（spot check）
- [ ] mode=deep + `--use-llm` 工作
- [ ] mode=deep 无 `--use-llm` 降级 + 零 LLM trace
- [ ] subprocess 模式（不直接 import L2 search/smart-search 内部）
- [ ] 默认无 LLM import
- [ ] `docs/API.md` 已更新
- [ ] `CHANGELOG.md` 已更新

## 下一 Task 指针

PR merged → 主控勾 Phase E → recall 模块作为 v1 可用，等 M4 集成。

## 执行总结（subagent 完成后填）

```
完成时间: <TBD>
实际 LOC: <TBD>
遇到的难点: <TBD>
验收证据:
  - test_recall_contract.py output: <snippet>
  - sample recall --mode=default/recall/deep outputs: <snippets>
  - deep degrade test trace: <stderr snippet>
```
