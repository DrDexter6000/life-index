#!/usr/bin/env python3
"""Minimal evaluation runner for search quality."""

from __future__ import annotations

import importlib
import json
import math
import os
import platform
import subprocess
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import yaml

GOLDEN_QUERIES_PATH = Path(__file__).with_name("golden_queries.yaml")
TOP_K = 5
MODULES_TO_RELOAD = (
    "tools.lib.paths",
    "tools.lib.config",
    "tools.lib.metadata_cache",
    "tools.lib.vector_index_simple",
    "tools.lib.entity_runtime",
    "tools.lib.search_index",
    "tools.lib.fts_update",
    "tools.lib.fts_search",
    "tools.search_journals.query_preprocessor",
    "tools.search_journals.semantic",
    "tools.search_journals.semantic_pipeline",
    "tools.search_journals.keyword_pipeline",
    "tools.search_journals.core",
)


# --- Broad eval predicate helpers (Phase 1 report-only) ---


def _doc_date(doc: dict[str, Any]) -> date:
    """Extract date from a result or journal document."""
    d = doc.get("date")
    if isinstance(d, date):
        return d
    if isinstance(d, datetime):
        return d.date()
    if d is None:
        return date.min
    try:
        s = str(d)[:10]
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return date.min


def _doc_topics(doc: dict[str, Any]) -> list[str]:
    """Extract topics from a result or journal document."""
    topic = doc.get("topic")
    if isinstance(topic, str):
        return [topic]
    if isinstance(topic, list):
        return [str(t) for t in topic]
    return []


def _build_predicate(be_predicate: dict[str, Any]) -> Any:
    """Build a predicate function from broad_eval predicate spec."""
    ptype = be_predicate["type"]
    if ptype == "date_range":
        since = datetime.strptime(be_predicate["date_range"]["since"], "%Y-%m-%d").date()
        until = datetime.strptime(be_predicate["date_range"]["until"], "%Y-%m-%d").date()
        return lambda doc: since <= _doc_date(doc) <= until
    if ptype == "topic":
        hints = set(be_predicate["topic_hints"])
        return lambda doc: bool(hints & set(_doc_topics(doc)))
    if ptype == "date_topic":
        since = datetime.strptime(be_predicate["date_range"]["since"], "%Y-%m-%d").date()
        until = datetime.strptime(be_predicate["date_range"]["until"], "%Y-%m-%d").date()
        hints = set(be_predicate["topic_hints"])
        return lambda doc: (since <= _doc_date(doc) <= until) and bool(
            hints & set(_doc_topics(doc))
        )
    if ptype == "season":
        since = datetime.strptime(be_predicate["date_range"]["since"], "%Y-%m-%d").date()
        until = datetime.strptime(be_predicate["date_range"]["until"], "%Y-%m-%d").date()
        return lambda doc: since <= _doc_date(doc) <= until
    raise ValueError(f"Unknown predicate type: {ptype}")


def _compute_predicate_precision(
    top_results: list[dict[str, Any]], predicate: Any
) -> tuple[float, int, int]:
    """Return (precision, matched_count, returned_count)."""
    returned_count = len(top_results)
    if returned_count == 0:
        return 0.0, 0, 0
    matched_count = sum(1 for doc in top_results if predicate(doc))
    return matched_count / returned_count, matched_count, returned_count


def _compute_global_matched_count(all_docs: list[dict[str, Any]], predicate: Any) -> int:
    """Count how many docs in the full corpus satisfy the predicate."""
    return sum(1 for doc in all_docs if predicate(doc))


def _collect_all_indexed_docs() -> list[dict[str, Any]]:
    """Collect all journal documents by scanning markdown files.

    Uses frontmatter scanning rather than metadata_cache to avoid
    depending on an unstable/undocumented API.
    """
    from tools.lib.frontmatter import parse_journal_file
    from tools.lib.paths import resolve_journals_dir

    journals_dir = resolve_journals_dir()
    if not journals_dir.exists():
        return []

    docs: list[dict[str, Any]] = []
    for file_path in sorted(journals_dir.glob("**/life-index_*.md")):
        try:
            metadata = parse_journal_file(file_path)
        except Exception:
            continue
        docs.append(
            {
                "title": str(metadata.get("title") or metadata.get("_title") or ""),
                "date": metadata.get("date"),
                "topic": metadata.get("topic", []),
            }
        )
    return docs


def _collect_broad_eval_metrics(per_query: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate broad_eval stats across per-query results."""
    broad_items = [item for item in per_query if item.get("eval_mode") == "predicate_precision"]
    if not broad_items:
        return {}

    strict_passes = sum(1 for item in broad_items if item.get("strict_pass"))
    soft_passes = sum(1 for item in broad_items if item.get("soft_pass"))
    errors = sum(1 for item in broad_items if item.get("broad_eval_error"))

    return {
        "query_count": len(broad_items),
        "strict_pass_rate": _round_metric(_safe_float_divide(strict_passes, len(broad_items))),
        "soft_pass_rate": _round_metric(_safe_float_divide(soft_passes, len(broad_items))),
        "strict_passes": strict_passes,
        "soft_passes": soft_passes,
        "errors": errors,
        "fails": len(broad_items) - soft_passes - errors,
    }


# --- End broad eval helpers ---


def _get_llm_client_module() -> Any:
    return importlib.import_module("tools.eval.llm_client")


def _get_prompts_module() -> Any:
    return importlib.import_module("tools.eval.prompts")


def load_golden_queries(file_path: Path | None = None) -> list[dict[str, Any]]:
    """Load the golden query set from YAML."""
    payload = yaml.safe_load((file_path or GOLDEN_QUERIES_PATH).read_text(encoding="utf-8"))
    queries = payload.get("queries", []) if isinstance(payload, dict) else []
    if not isinstance(queries, list):
        raise ValueError("golden_queries.yaml must contain a 'queries' list")
    return queries


def _load_queries_with_overlay(
    queries_path: Path | None = None,
    overlay_path: Path | None = None,
    use_overlay: bool = True,
) -> tuple[list[dict[str, Any]], int, list[str], set[str]]:
    """Load golden queries and optionally apply a private overlay.

    Returns (queries, overlay_applied_count, overlay_warnings, applied_query_ids).
    """
    queries = load_golden_queries(queries_path)
    if not use_overlay:
        return queries, 0, [], set()

    from tools.eval.overlay import load_overlay, apply_overlay

    overlay = load_overlay(overlay_path)
    modified_queries, applied_count, warnings_list, applied_ids = apply_overlay(queries, overlay)
    return modified_queries, applied_count, warnings_list, applied_ids


def _get_git_commit() -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            check=True,
            text=True,
            encoding="utf-8",
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return "unknown"
    return completed.stdout.strip() or "unknown"


def _find_latest_baseline() -> Path | None:
    """Locate the most recent baseline file in the standard directories."""
    candidate_dirs = [
        Path(__file__).parent / "baselines",
        Path(__file__).parent.parent.parent / "tests" / "eval" / "baselines",
    ]
    candidates: list[Path] = []
    for d in candidate_dirs:
        if d.exists():
            candidates.extend(d.glob("round-*-baseline*.json"))
    if not candidates:
        return None
    # Sort by mtime descending
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def _get_eval_anchor_date() -> date:
    """Return the deterministic anchor date for evaluation.

    Priority:
      1. ``LIFE_INDEX_TIME_ANCHOR`` environment variable.
      2. ``frozen_at`` field from the latest baseline file.
      3. ``date.today()`` (with a warning).
    """
    env = os.environ.get("LIFE_INDEX_TIME_ANCHOR")
    if env:
        return date.fromisoformat(env)

    baseline_path = _find_latest_baseline()
    if baseline_path is not None:
        try:
            baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
            frozen_at = baseline.get("frozen_at") or baseline.get("anchor_date")
            if frozen_at:
                return date.fromisoformat(frozen_at)
        except (OSError, ValueError, json.JSONDecodeError):
            pass

    import warnings

    warnings.warn(
        "LIFE_INDEX_TIME_ANCHOR not set and no baseline frozen_at found. "
        "Falling back to date.today() — eval results will drift across runs.",
        stacklevel=2,
    )
    return date.today()


def _inject_eval_anchor(anchor: date) -> None:
    """Pin the evaluation anchor in the process environment."""
    os.environ["LIFE_INDEX_TIME_ANCHOR"] = anchor.isoformat()


def _round_metric(value: float) -> float:
    return round(value, 4)


def _safe_float_divide(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def _query_expected(query_case: dict[str, Any]) -> dict[str, Any]:
    expected = query_case.get("expected", {})
    return expected if isinstance(expected, dict) else {}


def _must_contain_titles(query_case: dict[str, Any]) -> list[str]:
    expected = _query_expected(query_case)
    raw_value = expected.get("must_contain_title", [])
    if not raw_value:
        return []
    if not isinstance(raw_value, list):
        raise ValueError("must_contain_title must be a list when present")
    return [str(item) for item in raw_value]


def _min_results(query_case: dict[str, Any]) -> int:
    return int(_query_expected(query_case).get("min_results", 0))


def _effective_expected_min_results(query_case: dict[str, Any], *, judge: str, live: bool) -> int:
    if judge == "llm" and live:
        return 1
    return _min_results(query_case)


def _result_is_relevant(result: dict[str, Any], query_case: dict[str, Any]) -> bool:
    title = str(result.get("title", ""))
    must_contain_titles = _must_contain_titles(query_case)
    if must_contain_titles:
        return any(fragment in title for fragment in must_contain_titles)
    return _min_results(query_case) > 0


def _first_relevant_rank(
    top_results: list[dict[str, Any]], query_case: dict[str, Any]
) -> int | None:
    for index, result in enumerate(top_results, start=1):
        if _result_is_relevant(result, query_case):
            return index
    return None


def _query_precision_at_5(top_results: list[dict[str, Any]], query_case: dict[str, Any]) -> float:
    if not top_results:
        return 0.0

    must_contain_titles = _must_contain_titles(query_case)
    if not must_contain_titles:
        return 1.0 if _min_results(query_case) > 0 else 0.0

    relevant_count = sum(1 for result in top_results if _result_is_relevant(result, query_case))
    return relevant_count / min(len(top_results), TOP_K)


def _llm_query_precision_at_5(llm_scores: list[int]) -> float:
    if not llm_scores:
        return 0.0
    relevant_count = sum(1 for score in llm_scores if score >= 2)
    return relevant_count / TOP_K


def _compute_ndcg_at_5(llm_scores: list[int]) -> float:
    if not llm_scores:
        return 0.0

    def _dcg(scores: list[int]) -> float:
        total = 0.0
        for rank, score in enumerate(scores[:TOP_K], start=1):
            if score <= 0:
                continue
            if rank == 1:
                total += float(score)
            else:
                total += float(score) / math.log2(rank + 1)
        return total

    dcg = _dcg(llm_scores)
    idcg = _dcg(sorted(llm_scores, reverse=True))
    return _round_metric(_safe_float_divide(dcg, idcg))


def _llm_first_relevant_rank(llm_scores: list[int]) -> int | None:
    for index, score in enumerate(llm_scores, start=1):
        if score >= 2:
            return index
    return None


def _build_precision_prompt(query: str, result: dict[str, Any]) -> str:
    abstract = str(result.get("abstract", ""))
    snippet = str(result.get("snippet", result.get("content", abstract)))[:200]
    result_str: str = _get_prompts_module().PRECISION_JUDGE_PROMPT.format(
        query=query,
        title=str(result.get("title", "")),
        date=str(result.get("date", "")),
        abstract=abstract,
        snippet=snippet,
    )
    return result_str


def _llm_score_result(
    *,
    query: str,
    result: dict[str, Any],
    llm_client: Any | None,
) -> int:
    prompt = _build_precision_prompt(query, result)
    llm_module = _get_llm_client_module()
    raw_response = (
        llm_client.query(prompt, model="gpt-4o-mini", temperature=0.0)
        if llm_client is not None
        else llm_module.query_llm(prompt, model="gpt-4o-mini", temperature=0.0)
    )
    payload = llm_module.parse_json_response(raw_response)
    try:
        score = int(payload.get("score", 0))
    except (TypeError, ValueError):
        return 0
    return max(0, min(score, 3))


def _query_passes(
    *, top_results: list[dict[str, Any]], query_case: dict[str, Any], results_found: int
) -> tuple[bool, str | None]:
    expected_min_results = _min_results(query_case)
    if expected_min_results == 0:
        if results_found == 0:
            return True, None
        return False, f"Expected 0 results, got {results_found}"

    if results_found < expected_min_results:
        return False, f"Expected >= {expected_min_results} results, got {results_found}"

    if _must_contain_titles(query_case) and _first_relevant_rank(top_results, query_case) is None:
        return (
            False,
            "Expected one of must_contain_title within top 5, but none matched",
        )

    return True, None


def _collect_metrics(per_query: list[dict[str, Any]]) -> dict[str, float]:
    mrr_total = sum(float(item["reciprocal_rank"]) for item in per_query)
    recall_candidates = [item for item in per_query if int(item["expected_min_results"]) > 0]
    recall_hits_5 = [item for item in recall_candidates if item["first_relevant_rank"] is not None]
    recall_hits_10 = [
        item for item in recall_candidates if item.get("first_relevant_rank_at_10") is not None
    ]
    precision_candidates = [item for item in per_query if int(item["results_found"]) > 0]
    precision_total = sum(float(item["precision_at_5"]) for item in precision_candidates)
    ndcg_total = sum(
        float(item["ndcg_at_5"]) for item in per_query if item.get("ndcg_at_5") is not None
    )
    ndcg_count = sum(1 for item in per_query if item.get("ndcg_at_5") is not None)

    return {
        "mrr_at_5": _round_metric(_safe_float_divide(mrr_total, len(per_query))),
        "recall_at_5": _round_metric(
            _safe_float_divide(len(recall_hits_5), len(recall_candidates))
        ),
        "recall_at_10": _round_metric(
            _safe_float_divide(len(recall_hits_10), len(recall_candidates))
        ),
        "precision_at_5": _round_metric(
            _safe_float_divide(precision_total, len(precision_candidates))
        ),
        "ndcg_at_5": (
            _round_metric(_safe_float_divide(ndcg_total, ndcg_count)) if ndcg_count > 0 else 0.0
        ),
    }


def _collect_llm_metrics(per_query: list[dict[str, Any]]) -> dict[str, float]:
    mrr_total = sum(float(item["reciprocal_rank"]) for item in per_query)
    recall_candidates = [item for item in per_query if int(item["expected_min_results"]) > 0]
    recall_hits_5 = [item for item in recall_candidates if item["first_relevant_rank"] is not None]
    recall_hits_10 = [
        item for item in recall_candidates if item.get("first_relevant_rank_at_10") is not None
    ]
    precision_total = sum(float(item["precision_at_5"]) for item in per_query)
    ndcg_total = sum(float(item.get("ndcg_at_5", 0.0)) for item in per_query)

    return {
        "mrr_at_5": _round_metric(_safe_float_divide(mrr_total, len(per_query))),
        "recall_at_5": _round_metric(
            _safe_float_divide(len(recall_hits_5), len(recall_candidates))
        ),
        "recall_at_10": _round_metric(
            _safe_float_divide(len(recall_hits_10), len(recall_candidates))
        ),
        "precision_at_5": _round_metric(_safe_float_divide(precision_total, len(per_query))),
        "ndcg_at_5": _round_metric(_safe_float_divide(ndcg_total, len(per_query))),
    }


def _compute_recall_ratio(expected_hits: list[str], returned_titles: list[str]) -> float:
    if not expected_hits:
        return 0.0
    matched = sum(1 for title in returned_titles if title in set(expected_hits))
    return round(matched / len(expected_hits), 2)


def _collect_all_journal_titles() -> list[str]:
    from tools.lib.frontmatter import parse_journal_file
    from tools.lib.paths import resolve_journals_dir

    journals_dir = resolve_journals_dir()
    if not journals_dir.exists():
        return []

    titles: list[str] = []
    for file_path in sorted(journals_dir.glob("**/life-index_*.md")):
        metadata = parse_journal_file(file_path)
        title = str(metadata.get("title") or metadata.get("_title") or "").strip()
        if title:
            titles.append(title)
    return titles


def _detect_recall_gaps(
    *,
    queries: list[dict[str, Any]],
    per_query: list[dict[str, Any]],
    llm_client: Any | None,
) -> list[dict[str, Any]]:
    llm_module = _get_llm_client_module()
    prompt_template = _get_prompts_module().RECALL_GAP_PROMPT
    all_titles = _collect_all_journal_titles()
    if not all_titles:
        return []

    per_query_by_id = {str(item["id"]): item for item in per_query if "id" in item}
    recall_gaps: list[dict[str, Any]] = []

    for query_case in queries:
        prompt = prompt_template.format(
            query=str(query_case["query"]),
            all_titles="\n".join(f"- {title}" for title in all_titles),
        )
        raw_response = (
            llm_client.query(prompt, model="gpt-4o-mini", temperature=0.0)
            if llm_client is not None
            else llm_module.query_llm(prompt, model="gpt-4o-mini", temperature=0.0)
        )
        payload = llm_module.parse_json_response(raw_response)
        raw_hits = payload.get("expected_hits", [])
        if not isinstance(raw_hits, list):
            continue
        expected_hits = [str(title) for title in raw_hits if str(title).strip()]
        if not expected_hits:
            continue

        query_result = per_query_by_id.get(str(query_case["id"]), {})
        returned_titles = [str(title) for title in query_result.get("top_titles", [])]
        returned_set = set(returned_titles)
        expected_but_missed = [title for title in expected_hits if title not in returned_set]
        if not expected_but_missed:
            continue

        recall_gaps.append(
            {
                "query_id": str(query_case["id"]),
                "query": str(query_case["query"]),
                "expected_but_missed": expected_but_missed,
                "returned": returned_titles,
                "recall_ratio": _compute_recall_ratio(expected_hits, returned_titles),
            }
        )

    return recall_gaps


def _build_summary_lines(result: dict[str, Any]) -> list[str]:
    metrics = result["metrics"]
    lines = [
        f"Queries: {result['total_queries']}",
        f"MRR@5: {metrics['mrr_at_5']:.4f}",
        f"Recall@5: {metrics['recall_at_5']:.4f}",
        f"Precision@5: {metrics['precision_at_5']:.4f}",
    ]
    if "ndcg_at_5" in metrics:
        lines.append(f"nDCG@5: {metrics['ndcg_at_5']:.4f}")
    if result["failures"]:
        lines.append(f"Failures: {len(result['failures'])}")
        for failure in result["failures"][:5]:
            lines.append(f'FAIL {failure["id"]} "{failure["query"]}" — {failure["reason"]}')
    else:
        lines.append("Failures: 0")

    be_metrics = result.get("broad_eval_metrics")
    if be_metrics:
        lines.append("")
        lines.append(f"Broad Eval ({be_metrics['query_count']} queries):")
        lines.append(
            f"  Strict pass: {be_metrics['strict_passes']}/{be_metrics['query_count']} "
            f"({be_metrics['strict_pass_rate']:.0%})"
        )
        lines.append(
            f"  Soft pass:   {be_metrics['soft_passes']}/{be_metrics['query_count']} "
            f"({be_metrics['soft_pass_rate']:.0%})"
        )
        if be_metrics.get("errors"):
            lines.append(f"  Errors:      {be_metrics['errors']}/{be_metrics['query_count']}")
        lines.append(f"  Fail:        {be_metrics['fails']}/{be_metrics['query_count']}")

    return lines


def _reload_runtime_modules() -> None:
    for module_name in MODULES_TO_RELOAD:
        module = importlib.import_module(module_name)
        importlib.reload(module)

    from tools.lib.chinese_tokenizer import reset_tokenizer_state

    reset_tokenizer_state()


@contextmanager
def _temporary_data_dir(data_dir: Path | None) -> Iterator[None]:
    if data_dir is None:
        yield
        return

    original_env = os.environ.get("LIFE_INDEX_DATA_DIR")
    os.environ["LIFE_INDEX_DATA_DIR"] = str(Path(data_dir))
    _reload_runtime_modules()
    try:
        yield
    finally:
        if original_env is None:
            os.environ.pop("LIFE_INDEX_DATA_DIR", None)
        else:
            os.environ["LIFE_INDEX_DATA_DIR"] = original_env
        _reload_runtime_modules()


@contextmanager
def _live_data_dir() -> Iterator[None]:
    import pathlib

    original_env = os.environ.get("LIFE_INDEX_DATA_DIR")
    # Instead of popping (which triggers pytest guard on reload),
    # set to the real user data directory.
    real_dir = pathlib.Path.home() / "Documents" / "Life-Index"
    os.environ["LIFE_INDEX_DATA_DIR"] = str(real_dir)
    _reload_runtime_modules()
    try:
        yield
    finally:
        if original_env is not None:
            os.environ["LIFE_INDEX_DATA_DIR"] = original_env
        else:
            os.environ.pop("LIFE_INDEX_DATA_DIR", None)
        _reload_runtime_modules()


def _evaluate_queries(
    queries: list[dict[str, Any]],
    *,
    use_semantic: bool,
    judge: str,
    live: bool,
    llm_client: Any | None,
    all_docs: list[dict[str, Any]] | None = None,
    applied_query_ids: set[str] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    from tools.search_journals.core import hierarchical_search

    per_query: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    for query_case in queries:
        raw_result = hierarchical_search(
            query=str(query_case["query"]),
            level=3,
            semantic=use_semantic,
        )
        merged_results = list(raw_result.get("merged_results", []))
        top_results = merged_results[:TOP_K]
        top_results_10 = merged_results[:10]
        results_found = len(merged_results)
        llm_scores: list[int] = []

        if judge == "llm":
            llm_scores = [
                _llm_score_result(
                    query=str(query_case["query"]),
                    result=result,
                    llm_client=llm_client,
                )
                for result in top_results
            ]
            first_relevant_rank = _llm_first_relevant_rank(llm_scores)
            first_relevant_rank_at_10 = first_relevant_rank  # LLM scores only computed on top 5
            precision_at_5 = _llm_query_precision_at_5(llm_scores)
            ndcg_at_5 = _compute_ndcg_at_5(llm_scores)
        else:
            first_relevant_rank = _first_relevant_rank(top_results, query_case)
            first_relevant_rank_at_10 = _first_relevant_rank(top_results_10, query_case)
            precision_at_5 = _query_precision_at_5(top_results, query_case)
            keyword_relevance_scores = [
                1 if _result_is_relevant(r, query_case) else 0 for r in top_results
            ]
            ndcg_at_5 = _compute_ndcg_at_5(keyword_relevance_scores)

        reciprocal_rank = 0.0 if first_relevant_rank is None else 1.0 / first_relevant_rank

        effective_expected_min_results = _effective_expected_min_results(
            query_case, judge=judge, live=live
        )

        if judge == "llm":
            if effective_expected_min_results == 0:
                passed = first_relevant_rank is None
                failure_reason = (
                    None
                    if passed
                    else "Expected no relevant results under LLM judge, but found relevant hit"
                )
            else:
                passed = first_relevant_rank is not None
                failure_reason = (
                    None if passed else "Expected at least one relevant result under LLM judge"
                )
        else:
            passed, failure_reason = _query_passes(
                top_results=top_results,
                query_case=query_case,
                results_found=results_found,
            )

        entry = {
            "id": query_case["id"],
            "query": query_case["query"],
            "category": query_case["category"],
            "results_found": results_found,
            "top_titles": [str(item.get("title", "")) for item in top_results],
            "first_relevant_rank": first_relevant_rank,
            "first_relevant_rank_at_10": first_relevant_rank_at_10,
            "reciprocal_rank": _round_metric(reciprocal_rank),
            "precision_at_5": _round_metric(precision_at_5),
            "ndcg_at_5": _round_metric(ndcg_at_5) if ndcg_at_5 is not None else None,
            "expected_min_results": effective_expected_min_results,
            "pass": passed,
            "overlay_applied": str(query_case["id"]) in (applied_query_ids or set()),
        }
        if "_public_query" in query_case:
            entry["public_query"] = query_case["_public_query"]
        if judge == "llm":
            entry["llm_scores"] = llm_scores

        # --- Phase 1/2: broad_eval fields + soft gate ---
        broad_eval = query_case.get("broad_eval")
        if broad_eval and all_docs is not None:
            try:
                predicate = _build_predicate(broad_eval["predicate"])
                precision, matched_count, returned_count = _compute_predicate_precision(
                    top_results, predicate
                )
                global_matched = _compute_global_matched_count(all_docs, predicate)
                required_count = min(5, global_matched)
                min_results_ok = returned_count >= required_count
                strict_pass = (precision == 1.0) and min_results_ok
                soft_pass = (precision >= 0.8) and min_results_ok
                entry["eval_mode"] = "predicate_precision"
                entry["predicate_precision"] = _round_metric(precision)
                entry["global_matched_count"] = global_matched
                entry["returned_count"] = returned_count
                entry["matched_count"] = matched_count
                entry["min_results_ok"] = min_results_ok
                entry["strict_pass"] = strict_pass
                entry["soft_pass"] = soft_pass
                # Phase 2 soft gate: soft_pass governs pass/fail for broad_eval queries
                if soft_pass:
                    entry["pass"] = True
                    failure_reason = None
                else:
                    entry["pass"] = False
                    if not min_results_ok:
                        failure_reason = (
                            f"broad_eval min_results fail: returned {returned_count} "
                            f"< required {required_count}"
                        )
                    else:
                        failure_reason = (
                            f"broad_eval soft gate fail: precision {precision:.2f} "
                            f"< 0.80 (matched {matched_count}/{returned_count})"
                        )
            except Exception as exc:
                # Report-only must not silently lose observability on errors
                entry["eval_mode"] = "predicate_precision"
                entry["broad_eval_error"] = str(exc)
                entry["strict_pass"] = False
                entry["soft_pass"] = False
                entry["pass"] = False
                failure_reason = f"broad_eval error: {exc}"
        else:
            entry["eval_mode"] = "exact_mrr"
        # --- End broad_eval ---

        per_query.append(entry)

        if failure_reason:
            failures.append(
                {
                    "id": query_case["id"],
                    "query": query_case["query"],
                    "reason": failure_reason,
                }
            )

    return per_query, failures


def _build_semantic_report(
    keyword_result: dict[str, Any],
    semantic_result: dict[str, Any],
) -> dict[str, Any]:
    """Build report-only semantic comparison from keyword and semantic eval results."""
    kw_metrics = keyword_result["metrics"]
    sem_metrics = semantic_result["metrics"]

    kw_failure_ids = {f["id"] for f in keyword_result["failures"]}
    sem_failure_ids = {f["id"] for f in semantic_result["failures"]}

    fixed_by_semantic = sorted(kw_failure_ids - sem_failure_ids)
    regressed_by_semantic = sorted(sem_failure_ids - kw_failure_ids)
    still_failing_both = sorted(kw_failure_ids & sem_failure_ids)

    delta: dict[str, Any] = {}
    for metric_name in ("mrr_at_5", "recall_at_5", "precision_at_5", "ndcg_at_5"):
        kw_val = float(kw_metrics.get(metric_name, 0.0))
        sem_val = float(sem_metrics.get(metric_name, 0.0))
        delta[metric_name] = _round_metric(sem_val - kw_val)
    delta["failure_count"] = len(sem_failure_ids) - len(kw_failure_ids)

    return {
        "enabled": True,
        "metrics": sem_metrics,
        "failure_count": len(sem_failure_ids),
        "failure_ids": sorted(sem_failure_ids),
        "fixed_by_semantic": fixed_by_semantic,
        "regressed_by_semantic": regressed_by_semantic,
        "still_failing_both": still_failing_both,
        "delta": delta,
    }


def run_evaluation(
    *,
    data_dir: Path | None = None,
    save_baseline: Path | None = None,
    use_semantic: bool = False,
    queries_path: Path | None = None,
    judge: str = "keyword",
    live: bool = False,
    llm_client: Any | None = None,
    phase: int = 2,
    overlay_path: Path | None = None,
    use_overlay: bool | None = None,
    semantic_report: bool = False,
) -> dict[str, Any]:
    """Run the search evaluation suite and optionally persist a baseline.

    Overlay behavior (hard rules):
      - Disabled in CI or when save_baseline is set (cannot be overridden).
      - Default: enabled for local eval when neither CI nor save_baseline.
      - Pass use_overlay=False to explicitly disable.

    semantic_report: Run a second eval pass with use_semantic=True and append
      a ``semantic_report`` dict to the result.  The top-level metrics, failures,
      and pass/fail gate remain from the keyword (use_semantic=False) run.
      Cannot be combined with save_baseline.
    """
    if semantic_report and use_semantic:
        raise ValueError(
            "semantic report requires keyword/default top-level eval (use_semantic must be False)"
        )

    if semantic_report and save_baseline is not None:
        raise ValueError("semantic report is diagnostic-only and cannot be saved as baseline")

    from tools.eval.overlay import is_ci_environment

    # Hard disable: overlay must never affect public baselines or CI runs
    if is_ci_environment() or save_baseline is not None:
        use_overlay = False
    elif use_overlay is None:
        use_overlay = True
    # F1: Deterministic eval anchor injection
    _anchor = _get_eval_anchor_date()
    _inject_eval_anchor(_anchor)

    all_queries, overlay_applied_count, overlay_warnings, applied_query_ids = (
        _load_queries_with_overlay(
            queries_path=queries_path,
            overlay_path=overlay_path,
            use_overlay=use_overlay,
        )
    )
    queries = []
    skipped_queries: list[dict[str, Any]] = []
    for q in all_queries:
        skip_phase = q.get("skip_until_phase")
        if skip_phase is not None and skip_phase > phase:
            skipped_queries.append(q)
        else:
            queries.append(q)

    if judge not in {"keyword", "llm"}:
        raise ValueError("judge must be 'keyword' or 'llm'")

    context = _live_data_dir() if live else _temporary_data_dir(data_dir)

    with context:
        all_docs = _collect_all_indexed_docs()
        per_query, failures = _evaluate_queries(
            queries,
            use_semantic=use_semantic,
            judge=judge,
            live=live,
            llm_client=llm_client,
            all_docs=all_docs,
            applied_query_ids=applied_query_ids,
        )

    by_category: dict[str, list[dict[str, Any]]] = {}
    for item in per_query:
        by_category.setdefault(str(item["category"]), []).append(item)

    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "frozen_at": _anchor.isoformat(),
        "anchor_date": _anchor.isoformat(),
        "commit": _get_git_commit(),
        "python_version": platform.python_version(),
        "tokenizer_version": importlib.import_module(
            "tools.lib.search_constants"
        ).TOKENIZER_VERSION,
        "judge_mode": judge,
        "live_mode": live,
        "semantic_enabled": use_semantic,
        "total_queries": len(per_query),
        "skipped_queries": len(skipped_queries),
        "metrics": (
            _collect_llm_metrics(per_query) if judge == "llm" else _collect_metrics(per_query)
        ),
        "broad_eval_metrics": _collect_broad_eval_metrics(per_query),
        "by_category": {},
        "per_query": per_query,
        "failures": failures,
        "recall_gaps": [],
        "overlay_applied_count": overlay_applied_count,
        "overlay_warnings": overlay_warnings,
    }

    for category, items in by_category.items():
        result["by_category"][category] = {
            **(_collect_llm_metrics(items) if judge == "llm" else _collect_metrics(items)),
            "query_count": len(items),
        }

    result["summary_lines"] = _build_summary_lines(result)

    # Emit overlay warnings into summary so they are visible in CLI output
    if overlay_warnings:
        result["summary_lines"].append("")
        result["summary_lines"].append("Overlay warnings:")
        for w in overlay_warnings:
            result["summary_lines"].append(f"  ⚠ {w}")

    if live and judge == "llm":
        result["recall_gaps"] = _detect_recall_gaps(
            queries=queries,
            per_query=per_query,
            llm_client=llm_client,
        )

    if semantic_report:
        sem_context = _live_data_dir() if live else _temporary_data_dir(data_dir)
        with sem_context:
            sem_per_query, sem_failures = _evaluate_queries(
                queries,
                use_semantic=True,
                judge=judge,
                live=live,
                llm_client=llm_client,
                all_docs=all_docs,
                applied_query_ids=applied_query_ids,
            )
        sem_metrics = (
            _collect_llm_metrics(sem_per_query)
            if judge == "llm"
            else _collect_metrics(sem_per_query)
        )
        semantic_result = {
            "metrics": sem_metrics,
            "failures": sem_failures,
        }
        result["semantic_report"] = _build_semantic_report(result, semantic_result)

    if save_baseline is not None:
        save_baseline.parent.mkdir(parents=True, exist_ok=True)
        save_baseline.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    return result


def generate_summary_lines(diff: dict[str, Any]) -> list[str]:
    metric_labels = {
        "mrr_at_5": "MRR@5:",
        "recall_at_5": "Recall@5:",
        "precision_at_5": "Precision@5:",
        "ndcg_at_5": "nDCG@5:",
    }
    lines = ["═══ Search Eval Comparison ═══", "", "Overall Metrics:"]

    for metric_name in ("mrr_at_5", "recall_at_5", "precision_at_5", "ndcg_at_5"):
        if metric_name not in diff.get("metric_deltas", {}):
            continue
        payload = diff["metric_deltas"][metric_name]
        delta = float(payload["delta"])
        arrow = "▲" if delta > 0 else "▼" if delta < 0 else "→"
        lines.append(
            f"  {metric_labels[metric_name]:<14}"
            f"{float(payload['baseline']):.4f} → "
            f"{float(payload['current']):.4f}  "
            f"({arrow} {delta:+.4f})"
        )

    recall_gap_changes = diff.get("recall_gap_changes", [])
    if recall_gap_changes:
        lines.extend(["", "Recall Gaps (top 3 most impactful):"])
        ranked_changes = sorted(
            recall_gap_changes,
            key=lambda item: len(item.get("current_missed", [])),
            reverse=True,
        )[:3]
        for item in ranked_changes:
            current_missed = [str(title) for title in item.get("current_missed", [])]
            if not current_missed:
                continue
            expected_total = int(item.get("current_expected_total", len(current_missed)))
            lines.append(
                f'  {item.get("query_id", "")} '
                f'"{item.get("query", "")}": '
                f"漏检 {len(current_missed)}/{expected_total} "
                f"expected ({', '.join(current_missed)})"
            )

    lines.extend(["", f"Regressions: {len(diff.get('regressions', []))}"])
    return lines


def compare_against_baseline(
    *,
    baseline_path: Path,
    data_dir: Path | None = None,
    use_semantic: bool = False,
    queries_path: Path | None = None,
) -> dict[str, Any]:
    """Run evaluation and compare current results against a saved baseline."""
    baseline = json.loads(Path(baseline_path).read_text(encoding="utf-8"))
    # F1: Pin current eval to the same anchor as the baseline
    _baseline_anchor = baseline.get("frozen_at") or baseline.get("anchor_date")
    if _baseline_anchor:
        os.environ["LIFE_INDEX_TIME_ANCHOR"] = _baseline_anchor
    current = run_evaluation(
        data_dir=data_dir,
        use_semantic=use_semantic,
        queries_path=queries_path,
    )

    metric_deltas: dict[str, dict[str, float]] = {}
    for metric_name in ("mrr_at_5", "recall_at_5", "precision_at_5", "ndcg_at_5"):
        if metric_name not in baseline.get("metrics", {}) and metric_name not in current.get(
            "metrics", {}
        ):
            continue
        before = float(baseline.get("metrics", {}).get(metric_name, 0.0))
        after = float(current.get("metrics", {}).get(metric_name, 0.0))
        delta = after - before
        metric_deltas[metric_name] = {
            "baseline": _round_metric(before),
            "current": _round_metric(after),
            "delta": _round_metric(delta),
        }

    baseline_per_query = {
        str(item["id"]): item for item in baseline.get("per_query", []) if "id" in item
    }
    current_per_query = {
        str(item["id"]): item for item in current.get("per_query", []) if "id" in item
    }
    regressions: list[dict[str, Any]] = []
    new_failures: list[str] = []
    new_passes: list[str] = []

    for query_id, baseline_query in baseline_per_query.items():
        current_query = current_per_query.get(query_id)
        if current_query is None:
            regressions.append(
                {
                    "id": query_id,
                    "query": baseline_query.get("query", ""),
                    "reason": "Current evaluation missing query result",
                }
            )
            continue

        baseline_rank = baseline_query.get("first_relevant_rank")
        current_rank = current_query.get("first_relevant_rank")
        if baseline_query.get("pass") and not current_query.get("pass"):
            if baseline_rank and current_rank is None:
                reason = f"was rank {baseline_rank}, now not found"
            else:
                reason = f"was pass with rank {baseline_rank}, now rank {current_rank}"
            regressions.append(
                {
                    "id": query_id,
                    "query": current_query.get("query", baseline_query.get("query", "")),
                    "reason": reason,
                }
            )
            new_failures.append(query_id)
        elif (
            isinstance(baseline_rank, int)
            and isinstance(current_rank, int)
            and current_rank > baseline_rank
        ):
            regressions.append(
                {
                    "id": query_id,
                    "query": current_query.get("query", baseline_query.get("query", "")),
                    "reason": f"was rank {baseline_rank}, now rank {current_rank}",
                }
            )

    for query_id, current_query in current_per_query.items():
        baseline_query = baseline_per_query.get(query_id)
        if baseline_query is None:
            continue
        if not baseline_query.get("pass") and current_query.get("pass"):
            new_passes.append(query_id)

    baseline_recall_gaps = {
        str(item.get("query_id")): item for item in baseline.get("recall_gaps", [])
    }
    current_recall_gaps = {
        str(item.get("query_id")): item for item in current.get("recall_gaps", [])
    }
    recall_gap_changes: list[dict[str, Any]] = []
    for query_id in sorted(set(baseline_recall_gaps) | set(current_recall_gaps)):
        baseline_gap = baseline_recall_gaps.get(query_id, {})
        current_gap = current_recall_gaps.get(query_id, {})
        baseline_missed = [str(title) for title in baseline_gap.get("expected_but_missed", [])]
        current_missed = [str(title) for title in current_gap.get("expected_but_missed", [])]
        if baseline_missed == current_missed:
            continue
        recall_gap_changes.append(
            {
                "query_id": query_id,
                "query": current_gap.get("query", baseline_gap.get("query", "")),
                "baseline_missed": baseline_missed,
                "current_missed": current_missed,
                "current_expected_total": len(current_missed)
                + len(
                    [
                        title
                        for title in current_gap.get("returned", [])
                        if title not in set(current_missed)
                    ]
                ),
            }
        )

    diff = {
        "metric_deltas": metric_deltas,
        "regressions": regressions,
        "new_failures": new_failures,
        "new_passes": new_passes,
        "recall_gap_changes": recall_gap_changes,
    }
    diff_lines = generate_summary_lines(diff)

    return {
        "baseline": baseline,
        "current": current,
        "diff": diff,
        "diff_lines": diff_lines,
    }


if __name__ == "__main__":
    payload = run_evaluation()
    output_path = Path("tmp_eval_result.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"success": True, "data": payload}, f, ensure_ascii=False, indent=2)
    print(f"Eval result written to {output_path}")
