#!/usr/bin/env python3
"""D2: Per-query MRR diff between v3 baseline and current code."""
import json
from pathlib import Path
from tools.eval.run_eval import run_evaluation


def main() -> None:
    # Load v3 baseline
    v3_path = Path("tests/eval/baselines/round-19-phase1c-baseline-v3.json")
    with open(v3_path, "r", encoding="utf-8") as f:
        v3 = json.load(f)

    v3_by_id = {q["id"]: q for q in v3["per_query"]}

    # Run current eval
    current = run_evaluation(
        use_semantic=True,
        queries_path=Path("tools/eval/golden_queries.yaml"),
        judge="keyword",
        phase=2,
    )

    current_by_id = {q["id"]: q for q in current["per_query"]}

    # Compare
    regressed = []
    improved = []
    unchanged = []

    for qid in sorted(v3_by_id.keys()):
        v3_q = v3_by_id[qid]
        cur_q = current_by_id.get(qid)
        if not cur_q:
            continue
        v3_mrr = v3_q["reciprocal_rank"]
        cur_mrr = cur_q["reciprocal_rank"]
        delta = cur_mrr - v3_mrr

        if abs(delta) > 0:
            item = (qid, v3_q["query"], v3_mrr, cur_mrr, delta, v3_q["category"])
            if delta < 0:
                regressed.append(item)
            else:
                improved.append(item)
        else:
            unchanged.append(qid)

    # Print summary
    print("=== D2: Per-query MRR Diff (v3 vs current) ===")
    print(f"Total active queries: {len(v3_by_id)}")
    print(f"Unchanged: {len(unchanged)}")
    print(f"Regressed: {len(regressed)}")
    print(f"Improved: {len(improved)}")
    print()

    print(f"--- Regressed ({len(regressed)}) ---")
    for item in sorted(regressed, key=lambda x: x[4]):
        qid, query, v3_m, cur_m, delta, cat = item
        print(f"{qid}: {query} | v3={v3_m:.4f} cur={cur_m:.4f} delta={delta:+.4f} | {cat}")

    print()
    print(f"--- Improved ({len(improved)}) ---")
    for item in sorted(improved, key=lambda x: x[4], reverse=True):
        qid, query, v3_m, cur_m, delta, cat = item
        print(f"{qid}: {query} | v3={v3_m:.4f} cur={cur_m:.4f} delta={delta:+.4f} | {cat}")

    print()
    print("--- Summary ---")
    total_delta = sum(x[4] for x in regressed + improved)
    v3_mrr = v3["metrics"]["mrr_at_5"]
    cur_mrr = current["metrics"]["mrr_at_5"]
    print(f"Total MRR delta sum: {total_delta:+.4f}")
    print(f"v3 MRR: {v3_mrr:.4f}")
    print(f"current MRR: {cur_mrr:.4f}")
    print(f"direct diff: {cur_mrr - v3_mrr:+.4f}")

    # Save to file
    report = {
        "regressed": [
            {
                "id": x[0],
                "query": x[1],
                "v3_mrr": x[2],
                "current_mrr": x[3],
                "delta": x[4],
                "category": x[5],
            }
            for x in regressed
        ],
        "improved": [
            {
                "id": x[0],
                "query": x[1],
                "v3_mrr": x[2],
                "current_mrr": x[3],
                "delta": x[4],
                "category": x[5],
            }
            for x in improved
        ],
        "unchanged_count": len(unchanged),
        "v3_mrr": v3_mrr,
        "current_mrr": cur_mrr,
    }
    out_path = Path("tools/dev/d2_per_query_diff.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"Report saved to {out_path}")


if __name__ == "__main__":
    main()
