"""Ad-hoc natural-language query smoke test.

Runs a batch of simulated user questions against the Life Index search CLI and
captures top hits + pipeline metadata to expose ranking / recall / semantic
failures. Not part of the standard test suite.
"""
from __future__ import annotations

import io
import json
import subprocess
import sys
import time
from pathlib import Path

# Force stdout/stderr to UTF-8 so CJK + bullet chars survive Windows' default GBK.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

ROOT = Path(__file__).resolve().parent.parent
PYTHON = sys.executable

# (label, query, expected_dates_hint) — expected_dates_hint is prose describing
# what a human reader would consider correct hits (used for manual scoring).
QUERIES: list[tuple[str, str, str]] = [
    ("睡眠_量化", "过去两个月睡眠不足，有多少天是晚于10点之后睡的？",
     "应命中 2026-03-11/03-14/03-24 等提及睡眠的条目；量化不应由搜索负责，但应返回相关条目。"),
    ("情绪_焦虑", "最近有什么让我焦虑的事？",
     "应命中 mood=忧虑/焦虑 的条目，特别是 03-11 中东局势。"),
    ("地点_工作", "上个月在尼日利亚都干了什么工作？",
     "应命中 topic=work 且 location=Lagos 的 3 月条目。"),
    ("架构_决策", "最近对 Life Index 架构有哪些重大决策？",
     "应命中 CTO 评审 03-14_001、搜索 Round 系列等工作条目。"),
    ("实体_模型", "我跟 Claude Opus 互动的记录有哪些？",
     "应命中 tags/body 含 Claude Opus 的条目，尤其 03-14_001。"),
    ("天气_雨天", "3月份有哪几天下雨？",
     "应命中 weather 含 rain/雨 的 3 月条目。"),
    ("生日_计划", "生日相关的计划有哪些？",
     "应命中 03-11 计划回重庆过生日。"),
    ("隐式时间", "上次生病或身体不舒服是什么时候？",
     "应命中 tags=健康 或 body 含 生病/不舒服 的条目。"),
    ("关系_家庭", "我和家人最近有哪些互动？",
     "应命中 topic=relation/family 或含家人、孩子、老婆的条目。"),
    ("项目_搜索", "Life Index 搜索系统最近做了哪些改进？",
     "应命中 Round 7/8/9 搜索相关条目。"),
    ("否定_测试", "我有没有提到过北京？",
     "若无命中应明确返回 0 结果（北京不是常驻地点）。"),
    ("模糊_情绪", "最近心情怎么样？",
     "应混合 mood 字段做聚合式召回。"),
]


def run_query(query: str, limit: int = 5, use_semantic: bool = True, timeout: int = 90) -> dict:
    args = [
        PYTHON, "-m", "tools.search_journals",
        "--query", query,
        "--limit", str(limit),
        "--explain",
    ]
    if not use_semantic:
        args.append("--no-semantic")
    t0 = time.time()
    try:
        proc = subprocess.run(
            args,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        elapsed = time.time() - t0
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout", "elapsed": timeout}

    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    brace = stdout.find("{")
    payload: dict = {}
    if brace >= 0:
        try:
            payload = json.loads(stdout[brace:])
        except json.JSONDecodeError as e:
            return {"ok": False, "error": f"json_decode:{e}", "stdout_head": stdout[:400]}
    else:
        return {"ok": False, "error": "no_json", "stderr_tail": stderr[-400:]}

    # Extract perf lines from stderr
    perf = [ln for ln in stderr.splitlines() if "SearchPerf" in ln]

    return {
        "ok": True,
        "elapsed": round(elapsed, 2),
        "perf": perf,
        "payload": payload,
    }


def summarize(payload: dict) -> dict:
    """Compact per-result summary from the full JSON payload."""
    out: dict = {}
    out["l1_count"] = len(payload.get("l1_results") or [])
    out["l2_count"] = len(payload.get("l2_results") or [])
    out["l3_count"] = len(payload.get("l3_results") or [])
    out["semantic_count"] = len(payload.get("semantic_results") or [])
    merged = payload.get("merged_results") or []
    out["merged_count"] = len(merged)
    out["semantic_available"] = payload.get("semantic_available")
    out["semantic_note"] = payload.get("semantic_note")
    out["entity_hints"] = payload.get("entity_hints") or []
    out["index_status"] = payload.get("index_status") or {}

    sem_only = sum(
        1 for r in merged
        if (r.get("fts_score") or 0) == 0 and (r.get("semantic_score") or 0) > 0
    )
    fts_only = sum(
        1 for r in merged
        if (r.get("fts_score") or 0) > 0 and (r.get("semantic_score") or 0) == 0
    )
    both = sum(
        1 for r in merged
        if (r.get("fts_score") or 0) > 0 and (r.get("semantic_score") or 0) > 0
    )
    out["mix"] = {"fts_only": fts_only, "semantic_only": sem_only, "both": both}

    top = []
    for r in merged[:5]:
        explain = r.get("explain") or {}
        fusion = explain.get("fusion") if isinstance(explain, dict) else {}
        top.append({
            "date": r.get("date"),
            "title": (r.get("title") or "")[:60],
            "fts": r.get("fts_score"),
            "sem": r.get("semantic_score"),
            "rrf": (fusion or {}).get("rrf_score") if isinstance(fusion, dict) else None,
            "has_rrf": (fusion or {}).get("has_rrf") if isinstance(fusion, dict) else None,
            "source": r.get("source"),
        })
    out["top"] = top

    warns = payload.get("warnings") or []
    out["warnings"] = warns if isinstance(warns, list) else [warns]
    return out


def main() -> int:
    results = []
    for idx, (label, q, hint) in enumerate(QUERIES, start=1):
        print(f"\n=== [{idx}/{len(QUERIES)}] {label}: {q}", flush=True)
        r = run_query(q, limit=10, use_semantic=True, timeout=120)
        if not r.get("ok"):
            print(f"  !! FAIL: {r}", flush=True)
            results.append({"label": label, "query": q, "hint": hint, "result": r})
            continue
        summary = summarize(r["payload"])
        print(
            f"  elapsed={r['elapsed']}s  l1={summary['l1_count']} l2={summary['l2_count']} l3={summary['l3_count']} sem={summary['semantic_count']} merged={summary['merged_count']} mix={summary['mix']}"
        )
        for hit in summary["top"]:
            print(
                f"    - {hit.get('date')} | {hit.get('title')}  fts={hit.get('fts')} sem={hit.get('sem')} rrf={hit.get('rrf')}"
            )
        if summary.get("entity_hints"):
            print(f"  entity_hints: {summary['entity_hints']}")
        if summary.get("warnings"):
            print(f"  warnings: {summary['warnings']}")
        for line in r["perf"]:
            # strip the leading [INFO] ts prefix if any
            print(f"  {line.strip()}")
        results.append({
            "label": label,
            "query": q,
            "hint": hint,
            "elapsed": r["elapsed"],
            "summary": summary,
            "perf": r["perf"],
        })

    out_path = ROOT / "tests" / "nl_query_smoke_results.json"
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n\nSaved -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
