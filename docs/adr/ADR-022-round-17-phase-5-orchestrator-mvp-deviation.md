# ADR-022: Round 17 Phase 5 Orchestrator Recall@10 提升目标偏离

> **状态**: 已接受
> **日期**: 2026-05-01
> **作者**: Sisyphus (GLM-5.1) / 审计补录: Kimi Code CLI

---

## 背景

PRD Task 4 要求搜索编排器（Orchestrator）实现 **Recall@10 提升 ≥ +15pp**（相比纯双管道）。

Phase 5 实际交付：
- `SmartSearchOrchestrator` MVP 骨架：✅ 完成（~300 行，三段式流程接口）
- `smart-search` CLI 子命令：✅ 注册完成
- 降级路径（LLM 不可用时回退到 `hierarchical_search`）：✅ 100% 可用
- Mock 测试：7/7 通过
- **Recall@10 提升实测**：❌ 未进行
- **LLM prompt 调优**：❌ 未进行
- **20 query 人工评分（≥3.5/5）**：❌ 未进行

## 偏离原因

1. **LLM API 不可用**：Round 17 执行环境无可用 LLM API（需 OpenAI-compatible endpoint + `OPENAI_API_KEY`），无法运行真实 rewrite/filter/summarize pipeline
2. **Gold Set 不完整**：Phase 5 执行时 Gold Set 仅 24 条，不足以支撑 orchestrator A/B 的统计置信度
3. **MVP 优先策略**：团队决定先建立编排器骨架和接口契约，确保 Round 18 可以在稳定基座上迭代，而非在 Round 17 内同时解决"基础设施"和"效果优化"两个问题

## 决策

接受偏离，效果验证延期至 **Round 18**。

Round 18 重新评估条件：
- LLM API 可用（本地部署或远程 endpoint）
- Gold Set ≥ 150 条（提供 A/B 统计量）
- Recall@10 测量能力已就绪（`run_eval.py` 已补齐，见 ADR-023 相关修补）

## 后果

- Orchestrator 骨架存在但效果未经验证，当前仅作为接口层使用
- 降级路径 100% 可用，用户不会因 LLM 不可用而遭受功能损失
- Round 18 需投入专门时间进行 prompt A/B 和真实 query 对比

## 关联 ADR

- ADR-021：参数瘦身延期（同属 Round 17 范围收缩）
- （待 Round 18）ADR-02x：Orchestrator prompt 调优决策记录

## 替代方案（已排除）

- **用 mock LLM 完成效果验证**：mock 无法反映真实 rewrite/filter 质量，结果无工程意义
- **降低目标到 +5pp**：无数据支撑为何是 +5pp 而非 +15pp，属于随意调整阈值
