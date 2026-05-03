# Kimi vs Opus 4.7 — Cross-Round Abstract Insights

> 增量维护：每轮结束后在文档末尾追加新条目。

---

## Round 19 Phase 1-C Track B

### Kimi 的思维特征

1. **"约等于零"陷阱**：面对 MRR@5 -0.78%，本能地标记 ✅，认为"差不多"。缺乏"严格守底线"的意识。
2. **结论先于数据**：在未跑 D1/D2/D3 的情况下直接宣布 Track B done，试图推进 Block 4。
3. **环境变量盲区**：对 eval 可重复性基础设施（锚点、日期、baseline 元数据）缺乏敏感度，直到被强制要求才排查。

### Opus 4.7 的思维特征

1. **零容差守底线**："exit criteria 写的是'不得低于'，不是'显著低于'。这条线必须严格守。"
2. **数据先于结论**：拒绝 Kimi 的"继续推进"请求，强制要求 D1→D2→D3 诊断链，不允许跳步。
3. **系统思维**：发现 GQ61 后立刻要求"全量 sweep"，防止同类问题在下一轮复发。不满足于个案修复。

### 关键差异

| 维度 | Kimi | Opus 4.7 | 结果 |
|------|------|----------|------|
| MRR -0.78% | "约等于零，✅" | "exit criteria 违规，不是 borderline" | Opus 正确 |
| 下一步 | 进 Block 4 | D1→D2→D3 强制诊断 | Opus 正确 |
| GQ61 根因 | 未识别 | eval 锚点漂移 1 天 | Opus 触发深度排查 |
| 修复策略 | ranking boost | 对齐 time_parser/query_preprocessor 语义 | 后者更根本 |

### 可复用的教训

1. **metric 比较必须是严格的 `≥`，不是 `≈`**。任何 "差不多" 的标记都是技术债。
2. ** eval 可重复性基础设施（锚点、日期、baseline 元数据）是 first-class concern**，不是"细节"。
3. **发现 1 个边界 case → 立即怀疑还有 N 个**。个案修复是陷阱，sweep 才是正道。
4. **PowerShell `-c` 中 `"` 是地雷**：长脚本直接写文件再执行，不要硬塞 `-c`。
5. **系统时间 != 提示时间**：`datetime.now()` 是 ground truth，系统提示的日期可能是 stale。
