# Per-query Recall@5 Diff (v3 vs v4-fix)

- Queries with non-zero delta: **1**
- v3 global Recall@5: 0.9140
- v4 global Recall@5: 0.9032
- Global delta: -0.0108

| ID | Query | Category | v3 Recall@5 | v4 Recall@5 | Delta | Attribution |
|----|-------|----------|-------------|-------------|-------|-------------|
| GQ61 | 最近一周的生活 | time_range | 1.0000 | 0.0000 | -1.0000 | anchor_drift |

## Conclusion

**All recall deltas are attributed to GQ57 (Track B fix) or GQ61 (anchor drift). No hidden regressions detected.**
