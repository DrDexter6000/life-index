# CHARTER §1.9 Interpretation Supplement — RFC-2026-06-03

- **Date**: 2026-06-03
- **RFC**: RFC-2026-06-03
- **Note**: additive interpretation; owner-authorized via CHARTER §5; does not weaken §1.9

---

## Inserted Block

**§1.9 解释补充（RFC-2026-06-03）— 智能交接的 sanctioned 实现**

§1.9 所称「calling agent 负责语言合成」与「无 calling agent 用户的 provider opt-in fallback」，其 sanctioned 实现由 RFC-2026-06-03 定义为确定性解析顺序 **P0→P1→P2→deterministic-only**：
- **P0** = in-context calling agent（默认，本条不变）；
- **P1** = 经用户自有 agent 端点抵达**同一** calling agent（仍属「calling agent」，非新增 LLM 持有）；
- **P2** = §1.9 既有 provider opt-in fallback。

本补充**不改变** §1.9 任何核心规则 / 禁止项 / 默认路径：默认仍 P0；模块默认仍不持 LLM；L2 仍零 LLM；无 provider 仍以确定性输出满足合宪判断。它仅锁定「**P1/P2 是被允许的实现、不得倒置为默认路径**」这一解释。
