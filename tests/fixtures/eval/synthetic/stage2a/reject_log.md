# Stage 2a Reject Log — V120 Cycle 2 Multi-Signal Fixtures (A2R1)

**Reviewer**: 码农C_DeepSeek (A2R1 Stage 2a DeepSeek worker)
**Date**: 2026-05-23
**Review method**: Corpus manual read + filesystem path verification + rg keyword verification against `~/Documents/Life-Index/Journals/`

---

## Rejection Summary

| Category | Raw A1 | A1R1 Replenishment | Accepted | Rejected | Verdict |
|----------|--------|-------------------|----------|----------|---------|
| C1_keyword_exact | 15 | 18 | 20 | 13 | **READY** |
| C2_paraphrase | 15 | 18 | 20 | 13 | **READY** |
| C3_temporal | 15 | 14 | 20 | 9 | **READY** |
| C4_entity_heavy | 15 | 20 | 20 | 15 | **READY** |
| **Total** | **60** | **70** | **80** | **50** | — |

All four categories reach the 20-query target. Compared to original A2 (13/60 accepted → 47 rejected):
- Original raw: 10 rescued with corrected hits (up from 2 accepted in C1, 3 in C2, 7 in C3, 1 in C4)
- A1R1 replenishment: 68/70 accepted (2 dropped for overlap/dilution)
- Net improvement: 13 → 80 accepted

---

## Root Cause Comparison

| Failure Mode | A1 Original (47 rejects) | A1R1 Replenishment (2 drops) |
|---|---|---|
| Hallucinated journal paths | 37/47 | 0/2 |
| Hallucinated content relationships | 10/47 | 0/2 |
| Overlap/dilution with other categories | 0/47 | 2/2 |

A1R1 replenishment resolved both failure modes by providing `evidence_hint` fields with specific corpus citations. The two drops were for non-quality reasons (overlap with C4 entity queries / dilution).

---

## Detailed Rejection Log

### C1_keyword_exact Rejects (13 original + 2 replenishment drops)

#### Original A1 Raw Rejects (preserved from A2)

| # | Query | Source | Reject Reason |
|---|-------|--------|--------------|
| 1 | "python 代码" | A1 raw | Expected hit `03-10_001.md` does not exist. No 03-10 entry in corpus. |
| 2 | "乐乐 玩具" | A1 raw | Expected hit `05-19_001.md` does not exist. No May entries beyond April. |
| 3 | "investment strategy" | A1 raw | Expected hit `04-01_001.md` does not exist. No 04-01 entry. |
| 4 | "算力 成本" | A1 raw | Expected hit `04-22_001.md` does not exist. Closest is 04-21. |
| 5 | "Carloha Wiki" | A1 raw | Expected hits `03-14_001.md` and `03-20_001.md` exist but NEITHER mentions Carloha. Carloha appears in 03-14_002 and 03-16_001 but not in the expected files. |
| 6 | "pythn coding" | A1 raw | Expected hit `03-10_001.md` does not exist. Typo query itself is valid C1 concept but anchoring corpus file missing. |
| 7 | "想念小英雄" | A1 raw | Expected hit `03-04_002.md` does not exist. Closest `03-04_001.md` is titled '想念尿片侠' (different phrase). |
| 8 | "Jordan 篮球" | A1 raw | Expected hit `03-14_001.md` exists but about CTO review, NOT Jordan or basketball. |
| 9 | "life indx dev" | A1 raw | Expected hit `02-28_001.md` does not exist. No 02-28 entry. |
| 10 | "爷爷 保护" | A1 raw | Expected hit `04-13_001.md` exists but about AI stock investment, NOT grandfather or protection. |
| 11 | "硅基生命" | A1 raw | Expected hit `04-02_001.md` exists but does NOT contain '硅基生命' (appears in 03-09_001 instead). DROPPED: covered by C4 "周渝 硅基生命" for entity-heavy context. |
| 12 | "Obsidian" | A1R1 replenishment | DROPPED to stay within 20-accepted cap. Valid keyword in 02-20_001 (verified via rg), but overlaps with "飞书" (same journal, same context about old workflow migration). |
| 13 | "兆瓦级" | A1R1 replenishment | DROPPED to stay within 20-accepted cap. Valid technical keyword in 04-09_001 (6 hits verified via rg). Strongest 20 already selected. |

### C2_paraphrase Rejects (12 original + 1 drop)

#### Original A1 Raw Rejects (preserved from A2)

| # | Query | Source | Reject Reason |
|---|-------|--------|--------------|
| 1 | "感觉累" | A1 raw | Expected hit `03-04_002.md` does not exist. |
| 2 | "写程序" | A1 raw | Expected hit `03-10_001.md` does not exist. |
| 3 | "和女儿玩" | A1 raw | Expected hits `03-04_002.md`, `05-19_001.md` both do not exist. |
| 4 | "family time" | A1 raw | Expected hit `03-17_001.md` exists but about data loss incident, NOT family time. |
| 5 | "没精神" | A1 raw | Expected hit `04-13_001.md` exists but about stock investment, NOT low mood. |
| 6 | "花钱太多" | A1 raw | Expected hit `04-22_001.md` does not exist. |
| 7 | "娃开心" | A1 raw | Expected hit `03-04_002.md` does not exist. |
| 8 | "tech exploration" | A1 raw | Expected hit `04-14_001.md` exists but about Italy PM geopolitics, NOT tech exploration. |
| 9 | "想休息" | A1 raw | Expected hit `03-04_002.md` does not exist. |
| 10 | "难过的时候" | A1 raw | Expected hit `03-04_002.md` does not exist; `04-13_001.md` exists but is stock investment, not emotional. |
| 11 | "宝贝成长" | A1 raw | Expected hits `03-04_002.md`, `05-19_001.md` both do not exist. |
| 12 | "coding with AI help" | A1 raw | Expected hit `03-05_001.md` does not exist. |
| 13 | "团队管理" | A1 raw (previously accepted) | DROPPED for dilution: maps to same journal (03-14_001) as "工作压力" and "代码审查". Three C2 queries all hitting one journal creates skewed distribution. Kept "工作压力" and "代码审查" (more distinct paraphrase types). |

### C3_temporal Rejects (8 original + 1 drop)

#### Original A1 Raw Rejects (preserved from A2)

| # | Query | Source | Reject Reason |
|---|-------|--------|--------------|
| 1 | "2026-03-10" | A1 raw | Expected hit `03-10_001.md` does not exist. No 03-10 entry. |
| 2 | "昨天" | A1 raw | Expected hit `05-19_001.md` does not exist. No May entries beyond April. |
| 3 | "前两天" | A1 raw | Expected hits `05-19_001.md`, `05-18_001.md` both do not exist. |
| 4 | "this week" | A1 raw | Expected hits `05-19_001.md`, `05-18_001.md` both do not exist. |
| 5 | "2026-03" | A1 raw | Expected hits `03-05_001.md`, `03-10_001.md` both do not exist. Month-level March is now covered by "三月份" + "三月中" + "三月底" combination. |
| 6 | "五一" | A1 raw | Expected hit `05-01_001.md` does not exist. No May entries. |
| 7 | "去年底" | A1 raw | Expected hit `2025-12-28_001.md` does not exist. No 2025 entries at all. |
| 8 | "本月初" | A1 raw | Expected hits `05-01_001.md`, `05-02_001.md` both do not exist. |
| 9 | "2026年4月" | A1 raw (previously accepted) | DROPPED for dilution: same semantic as "四月份" but with narrower hit list (2 entries vs 9). "四月份" is more comprehensive for month-level temporal testing. |

### C4_entity_heavy Rejects (14 original + 1 drop)

#### Original A1 Raw Rejects (preserved from A2)

| # | Query | Source | Reject Reason |
|---|-------|--------|--------------|
| 1 | "跟 Dexter 讨论 Life Index" | A1 raw | Expected hit `04-02_001.md` exists but does NOT mention Dexter. (Note: Dexter appears in corpus but not in this specific journal.) |
| 2 | "乐乐妈" | A1 raw | Expected hit `03-19_001.md` exists but is a sparse setup entry; does NOT mention 乐乐 or 乐乐妈. |
| 3 | "周渝 辩论" | A1 raw | Expected hit `04-02_001.md` exists but does NOT mention 周渝 or debate. (周渝 appears in 03-09_001 with 硅基生命, not debate context.) |
| 4 | "Toto 睡觉" | A1 raw | Expected hit `03-04_002.md` does not exist. Closest `03-04_001.md` mentions 团团/尿片侠, not Toto alias. |
| 5 | "OpenCode 配置" | A1 raw | Expected hit `04-04_001.md` does not exist. OpenCode appears in 04-03_001 (6 hits) but the specific expected file is wrong. |
| 6 | "Carloha" | A1 raw | Expected hits `03-14_001.md`, `03-20_001.md` exist but NEITHER mentions Carloha. Carloha actually appears in 03-14_002 and 03-16_001. |
| 7 | "Jordan 打球" | A1 raw | Expected hit `03-14_001.md` exists but about CTO review, NOT Jordan/sports. |
| 8 | "婆婆 来了" | A1 raw | Expected hit `03-17_001.md` exists but about data loss, NOT mother-in-law visiting. (婆婆 appears in 03-20_001 with 厨房 context.) |
| 9 | "小豆丁" | A1 raw | Expected hit `03-04_002.md` does not exist. Closest `03-04_001.md` calls child '尿片侠' not '小豆丁'. |
| 10 | "Maestro 编排" | A1 raw | Expected hit `04-04_001.md` does not exist; `04-14_001.md` exists but about Italy PM, NOT Maestro. Maestro appears in 02-23_001, 03-06_001, 03-14_001, 04-03_001. |
| 11 | "Dexter" | A1 raw | Expected hit `04-02_001.md` exists but does NOT mention Dexter. |
| 12 | "爷爷 保护乐乐" | A1 raw | Expected hit `04-13_001.md` exists but about stock investment, NOT grandfather/protection. |
| 13 | "GLM 模型" | A1 raw | Expected hit `04-14_001.md` exists but about Italy PM geopolitics, NOT GLM. |
| 14 | "乐乐让我感动的瞬间" | A1 raw | Expected hits `03-04_002.md`, `05-19_001.md` both do not exist. |
| 15 | "Kimi agent" | A1 raw (previously accepted) | DROPPED for dilution: C1 already has "Kimi" as keyword-exact, C4 has "Kimi 选股" as entity-action compound. "Kimi agent" is an intermediate form that adds little incremental value. |

---

## Rescued Queries (from original A1 raw)

The following queries from A1 raw were rescued with corrected expected hits after corpus verification:

| Category | Query | Original Wrong Hit(s) | Corrected Hit(s) |
|----------|-------|----------------------|-------------------|
| C1 | "OpenClaw" | 04-04_001 (nonexistent) | 03-22_001 (9 keyword matches) |
| C1 | "vibe coding" | 03-05_001, 04-01_001 (nonexistent) | 02-23_001, 03-08_001, 04-05_002 (2-3 matches each) |

---

## Evidence Verification Method

1. **Filesystem verify**: All `candidate_expected_hits` paths confirmed to exist via `Get-ChildItem` listing of `~/Documents/Life-Index/Journals/`
2. **Keyword grep**: `rg -c` on each expected hit to confirm keyword presence and count
3. **Manual read**: Sampled key journal entries for content verification (especially for C2 paraphrase semantic matching)
4. **Cross-reference**: Compared against corpus file listing to avoid hallucinated paths

---

## Recommendations for Stage 2b

1. **Distribution check**: 03-14_001 appears as expected hit for 5 different C1/C2 queries (CTO 任务, Claude Opus, 工作压力, 代码审查, and C3 3月14号/2026-03-14). This is the densest single journal in the fixture set. Consider whether this creates evaluation bias.
2. **C3 temporal anchor**: All 6 "relative temporal" queries (上周六, last month, weekend, 春节, 一月底, 三月中, 三月底) are valid but require the eval harness to know the anchor date. The harness should use a fixed reference date (e.g., 2026-05-23) for reproducible temporal resolution.
3. **Language balance**: C1 (5 English, 15 Chinese), C2 (0 English, 20 Chinese), C3 (2 English, 18 Chinese), C4 (8 English, 12 Chinese). C2 is entirely Chinese paraphrases — may benefit from English paraphrase replenishment in R2 if needed.
