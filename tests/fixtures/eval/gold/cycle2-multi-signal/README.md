# Cycle2 Multi-Signal Gold Fixture

This gold fixture is the reviewed Phase A input for the v1.2.0 search multi-signal fusion cycle. It is additive test data only: it does not change the v1.1.1 schema version, search runtime, ranking constants, or production user data.

## Provenance Chain

| Stage | Owner | Commit / Evidence | Verdict |
|---|---|---|---|
| A1 raw fixture generation | `码农B_Kimi` | `de0db3c` | Accepted as raw candidate input; placeholder provenance risk carried forward. |
| A1R1 raw replenishment | `码农B_Kimi` | `ddefcc0` | Accepted as corpus-grounded replenishment with real SHA256 prompt hashes. |
| A5 eval harness extension | `码农A_GLM` | `1121f70` | Accepted; cycle2 loader and per-category metric plumbing available. |
| A2 initial Stage 2a review | `码农C_DeepSeek` | `c61243d` | Accepted as `BLOCKED_FOR_REPLENISHMENT` evidence. |
| A2R1 Stage 2a refresh | `码农C_DeepSeek` | `c61c6f6` | Accepted as `A3_READY`, 20 reviewed candidates per category. |
| A3 Stage 2b review | `主审_GPT` | `ea3b0f4` | Accepted as `PASS_TO_CTO_STAGE2C`, 14 candidates per category. |
| A4 Stage 2c verdict | `CTO_Claude` | `.agent-reports/v120-search-fusion-m3/phase-a/PHASE_A_A4_CTO_STAGE2C_VERDICT_2026-05-23.md` | **PASS** |

## Accepted Caveats

1. **C2 is Chinese-only.** English paraphrase coverage is a known gap and is deferred to a future absorption cycle. Baseline interpretation must read C2 as Chinese paraphrase recall, not language-agnostic paraphrase recall.
2. **March-April corpus clustering is preserved.** This reflects the source corpus distribution rather than synthetic rebalancing. A6 reports per-category metrics so algorithm-side cluster overfit remains visible.
3. **C4 entity queries are intentionally compound.** The category is designed to measure entity/context retrieval behavior, including cases where BM25 can still match exact entity tokens.

## Layout

- `C1_keyword_exact.json`
- `C2_paraphrase.json`
- `C3_temporal.json`
- `C4_entity_heavy.json`

Each file contains eval-shaped query records with `id`, `query`, `category`, and `expected.must_contain_title`, plus the reviewed `candidate_expected_hits`, evidence notes, and original fixture provenance.

## Sign-Off

CTO_Claude: Stage 2c PASS, 2026-05-23.
