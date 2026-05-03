# Month-Part Semantic Alignment Audit

> time_parser.py vs query_preprocessor.py

## Audit Method

Extract the date-range definitions for month-part qualifiers (初/中/末/底/下旬) from both modules and compare.

---

## Module Definitions

### query_preprocessor.py

| Qualifier | since | until | Source line |
|-----------|-------|-------|-------------|
| 初 | 1 | 10 | ~307 |
| 中 | 11 | 20 | ~339 |
| 下旬 | 15 | month-end | ~352 |
| 底 | 25 | month-end | ~369 |
| (Arabic) 底 | 25 | month-end | ~386 |

### time_parser.py

| Qualifier | since | until | Source line |
|-----------|-------|-------|-------------|
| 初 | 1 | 10 | _MONTH_PARTS["初"] (line 124, post-fix) |
| 中 | 11 | 20 | _MONTH_PARTS["中"] (line 125) |
| 末 | 21 | month-end | _MONTH_PARTS["末"] (line 126) |
| 底 | 21 | month-end | _MONTH_PARTS["底"] (line 127) |

---

## Alignment Matrix

| Qualifier | query_preprocessor | time_parser | Aligned? | Risk |
|-----------|-------------------|-------------|----------|------|
| **初** | 1-10 | 1-10 | ✅ YES | Fixed in this round |
| **中** | 11-20 | 11-20 | ✅ YES | No risk |
| **末** | 25-month_end | 21-month_end | ❌ NO | **4-day gap (21-24)** |
| **底** | 25-month_end | 21-month_end | ❌ NO | **4-day gap (21-24)** |
| **下旬** | 15-month_end | N/A | N/A | time_parser does NOT handle |

---

## Impact Assessment

### Current Golden Set Coverage

Searched all 133 queries for "末", "底", "下旬":

| ID | Query | time_parser match? | query_preprocessor match? | Risk |
|----|-------|-------------------|--------------------------|------|
| GQ58 | 三月下旬到四月的投资思考 | NO (range connector "到" → returns None) | YES (下旬 15-month_end) | **None** — time_parser bypassed by range-guard |
| GQ59 | 二月下旬的项目重组 | NO ("下旬" not in regex `[初中末底]`) | YES (下旬 15-month_end) | **None** — time_parser does not match "下旬" |
| GQ73 | 算力投资的底层逻辑 | NO ("底层" not a time expression) | NO | **None** — not a time query |

**Conclusion**: No active Golden Set query is affected by the 末/底 misalignment today.

### Future Risk

If a Golden Set query like "三月末的日志" or "月底总结" is added:
- time_parser would set range 21-month_end
- query_preprocessor would set range 25-month_end
- time_parser executes first in core.py → **overrides** query_preprocessor
- Wider range (21 vs 25) could introduce competing results → **potential rank regression**

This is the **same pattern** that caused GQ57 regression (初: 15 vs 10).

---

## Recommendation

**Option A (Conservative — align now)**
- Change time_parser "末"/"底" from 21 to 25
- Pro: Eliminates future GQ57-class regression risk
- Con: No Golden Set coverage to validate; 21-24 logs would be excluded from "末"/"底" searches

**Option B (Document — defer to next drift)**
- Keep current definitions
- Add explicit warning comment in both files documenting the 4-day gap
- Pro: No code change risk
- Con: Next round adding "末"/"底" query may repeat GQ57 regression

**Kimi recommendation**: Option A — align to 25 now. The cost is negligible (no current query affected), and the GQ57 lesson shows that semantic misalignment between time_parser and query_preprocessor is a **repeating regression pattern**.
