#!/usr/bin/env python3
"""Per-query Recall@5 diff between v3 baseline and current code."""

import json
from pathlib import Path
from tools.eval.run_eval import run_evaluation


def compute_query_recall(result_item: dict, expected_titles: list[str]) -> float:
    """Compute per-query recall@5."""
    top5 = result_item.get("top_titles", [])[:5]
    if not expected_titles:
        return 1.0  # No expected titles = perfect recall
    hits = sum(1 for t in expected_titles if t in top5)
    return hits / len(expected_titles)


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

    # Load expected titles from golden_queries.yaml
    import yaml

    gq = yaml.safe_load(open(Path("tools/eval/golden_queries.yaml"), "r", encoding="utf-8"))
    expected_by_id = {}
    for q in gq["queries"]:
        if q.get("skip"):
            continue
        e = q.get("expected", {})
        titles = e.get("must_contain_title", [])
        expected_by_id[q.get("id")] = titles

    # Compare per-query recall
    diffs = []
    for qid in sorted(v3_by_id.keys()):
        v3_q = v3_by_id[qid]
        cur_q = current_by_id.get(qid)
        if not cur_q:
            continue

        # Compute per-query recall@5 manually
        v3_rec = compute_query_recall(v3_q, expected_by_id.get(qid, []))
        cur_rec = compute_query_recall(cur_q, expected_by_id.get(qid, []))
        delta = cur_rec - v3_rec

        if abs(delta) > 0:
            diffs.append(
                {
                    "id": qid,
                    "query": v3_q["query"],
                    "category": v3_q["category"],
                    "v3_rec": v3_rec,
                    "cur_rec": cur_rec,
                    "delta": delta,
                }
            )

    # Print summary
    print("=== Per-query Recall@5 Diff (v3 vs current) ===")
    print(f"Total queries with recall delta != 0: {len(diffs)}")
    print()

    for d in sorted(diffs, key=lambda x: x["delta"]):
        print(
            f"{d['id']}: {d['query']} | "
            f"v3={d['v3_rec']:.4f} cur={d['cur_rec']:.4f} "
            f"delta={d['delta']:+.4f} | {d['category']}"
        )

    print()
    print("--- Summary ---")
    total_delta = sum(d["delta"] for d in diffs)
    print(f"Total recall delta sum: {total_delta:+.4f}")
    print(f"v3 global Recall@5: {v3['metrics']['recall_at_5']:.4f}")
    print(f"current global Recall@5: {current['metrics']['recall_at_5']:.4f}")

    # Save report
    report = {
        "diffs": diffs,
        "total_delta": total_delta,
        "v3_recall": v3["metrics"]["recall_at_5"],
        "current_recall": current["metrics"]["recall_at_5"],
    }
    with open("tools/dev/v4-recall-diff.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print("Saved to tools/dev/v4-recall-diff.json")

    # Also write markdown
    with open("tools/dev/v4-recall-diff.md", "w", encoding="utf-8") as f:
        f.write("# Per-query Recall@5 Diff (v3 vs v4-fix)\n\n")
        f.write(f"- Queries with non-zero delta: **{len(diffs)}**\n")
        f.write(f"- v3 global Recall@5: {v3['metrics']['recall_at_5']:.4f}\n")
        f.write(f"- v4 global Recall@5: {current['metrics']['recall_at_5']:.4f}\n")
        delta = current["metrics"]["recall_at_5"] - v3["metrics"]["recall_at_5"]
        f.write(f"- Global delta: {delta:+.4f}\n\n")

        f.write("| ID | Query | Category | v3 Recall@5 | v4 Recall@5 | Delta | Attribution |\n")
        f.write("|----|-------|----------|-------------|-------------|-------|-------------|\n")
        for d in sorted(diffs, key=lambda x: x["delta"]):
            if d["id"] in ("GQ57", "GQ61"):
                attr = "Track B time_parser" if d["id"] == "GQ57" else "anchor_drift"
            else:
                attr = "UNKNOWN — needs audit"
            f.write(
                f"| {d['id']} | {d['query']} | {d['category']} |"
                f" {d['v3_rec']:.4f} | {d['cur_rec']:.4f} |"
                f" {d['delta']:+.4f} | {attr} |\n"
            )

        f.write("\n## Conclusion\n\n")
        if all(d["id"] in ("GQ57", "GQ61") for d in diffs):
            f.write(
                "**All recall deltas are attributed to GQ57 "
                "(Track B fix) or GQ61 (anchor drift)."
                " No hidden regressions detected.**\n"
            )
        else:
            f.write(
                "**WARNING: Non-anchor-drift queries show "
                "recall regression. Needs further audit.**\n"
            )
    print("Saved to tools/dev/v4-recall-diff.md")


if __name__ == "__main__":
    main()
