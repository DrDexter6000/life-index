"""Search route."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any
from html import escape
from datetime import datetime, timedelta
import re

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from tools.lib.config import JOURNALS_DIR, USER_DATA_DIR
from tools.lib.frontmatter import parse_journal_file
from tools.lib.metadata_cache import METADATA_DB_PATH
from web.services.llm_provider import get_provider
from web.services.search import search_ai_journals_web, search_journals_web

router = APIRouter()

CACHE_DB = USER_DATA_DIR / ".cache" / "metadata_cache.db"


def _get_distinct_values(column: str) -> list[str]:
    """Return sorted distinct non-empty values for a metadata column."""
    if not METADATA_DB_PATH.exists():
        return []
    try:
        conn = sqlite3.connect(str(METADATA_DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            f"SELECT DISTINCT {column} FROM metadata_cache "
            f"WHERE {column} IS NOT NULL AND {column} != '' ORDER BY {column}"
        )
        rows = cursor.fetchall()
        conn.close()
        return [row[0] for row in rows if row[0]]
    except Exception:
        return []


def _compact_location(value: str) -> str:
    normalized = str(value or "").replace("，", ",")
    parts = [part.strip() for part in normalized.split(",") if part.strip()]
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    return f"{parts[0]}, {parts[-1]}"


def _drilldown_links() -> dict[str, str]:
    return {
        "topic": "/search?tab=keyword&topic={value}",
        "mood": "/search?tab=keyword&mood={value}",
        "tag": "/search?tab=keyword&tag={value}",
        "people": "/search?tab=keyword&people={value}",
        "date": "/search?tab=keyword&date={value}",
        "project": "/search?tab=keyword&project={value}",
        "location": "/search?tab=keyword&location={value}",
    }


def _normalize_result_title(value: str) -> str:
    return str(value or "").strip().strip('"').strip("'").strip("‘").strip("’")


def _behavioral_query_expansions(user_query: str) -> list[str]:
    # Deliberately avoid query-specific hardcoding here.
    # Behavioral expansion should come from the generic LLM-based query derivation path.
    return []


async def _derive_search_plan(provider: Any, user_query: str) -> dict[str, Any]:
    """
    LLM 统一提取查询计划（日期范围 + 搜索关键词）

    Returns:
        {
            "date_from": "YYYY-MM-DD" | None,
            "date_to": "YYYY-MM-DD" | None,
            "queries": ["keyword1", "keyword2", ...]
        }
    """
    api_key = getattr(provider, "api_key", "")
    base_url = getattr(provider, "base_url", "")
    model = getattr(provider, "model", "")
    if not (api_key and base_url and model):
        return {"date_from": None, "date_to": None, "queries": []}

    import httpx

    today = datetime.now().strftime("%Y-%m-%d")
    prompt = f"""Analyze the user's question for a personal journal search system.
Today is {today}.

Extract:
1. Date range (if mentioned in the question)
2. Search keywords (1-5 words or short phrases)

Return JSON only:
{{"date_from": "YYYY-MM-DD or null", "date_to": "YYYY-MM-DD or null", "queries": ["keyword1", "keyword2"]}}

Date parsing rules:
- "过去三天" / "last 3 days" → date_from = 3 days ago, date_to = today
- "上周" / "last week" → date_from = last Monday, date_to = last Sunday  
- "本月" / "this month" → date_from = 1st of this month, date_to = today
- If no date mentioned, return null for both
- Always use YYYY-MM-DD format

Query extraction rules:
- Extract 1-5 keywords likely to appear in journal text
- Use the language the user used

User question: {user_query}"""

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                f"{base_url.rstrip('/')}/chat/completions",
                json={
                    "model": model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "Return valid JSON only. No explanation.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 200,
                    "temperature": 0.3,
                },
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            text = (
                response.json()
                .get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )
    except Exception:
        return {"date_from": None, "date_to": None, "queries": []}

    # Parse JSON response
    try:
        # Remove markdown code blocks if present
        import re

        text = re.sub(r"^```(?:json)?\s*", "", str(text), flags=re.IGNORECASE)
        text = re.sub(r"```\s*$", "", text).strip()
        parsed = json.loads(text)

        date_from = parsed.get("date_from")
        date_to = parsed.get("date_to")
        queries = parsed.get("queries", [])

        # Validate date format
        if date_from and not re.match(r"^\d{4}-\d{2}-\d{2}$", str(date_from)):
            date_from = None
        if date_to and not re.match(r"^\d{4}-\d{2}-\d{2}$", str(date_to)):
            date_to = None

        # Validate queries
        if not isinstance(queries, list):
            queries = []
        queries = [str(q) for q in queries if q and len(str(q)) <= 40][:5]

        return {
            "date_from": date_from,
            "date_to": date_to,
            "queries": queries,
        }
    except (json.JSONDecodeError, TypeError):
        return {"date_from": None, "date_to": None, "queries": []}


# 保留旧函数作为 fallback
async def _derive_search_queries(provider: Any, user_query: str) -> list[str]:
    api_key = getattr(provider, "api_key", "")
    base_url = getattr(provider, "base_url", "")
    model = getattr(provider, "model", "")
    if not (api_key and base_url and model):
        return []

    import httpx

    today = datetime.now().strftime("%Y-%m-%d")
    prompt = (
        "You generate retrieval queries for a personal journal search system.\n"
        f"Today is {today}.\n"
        "Return 1 to 5 short retrieval queries, one per line, no numbering, no commentary.\n"
        "Queries should be words or very short phrases likely to literally appear in journal text.\n"
        "Expand behavioral or fuzzy questions into likely wording variants.\n"
        f"User question: {user_query}"
    )

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                f"{base_url.rstrip('/')}/chat/completions",
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": "Return only plain text lines."},
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 120,
                },
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            text = response.json()["choices"][0]["message"]["content"]
    except Exception:
        return []

    text = re.sub(
        r"<think>.*?</think>", "", str(text), flags=re.DOTALL | re.IGNORECASE
    ).strip()
    queries: list[str] = []
    for line in text.splitlines():
        cleaned = re.sub(r"^[-*\d.\s]+", "", line).strip().strip('"')
        if not cleaned:
            continue
        if len(cleaned) > 40:
            continue
        if cleaned.lower().startswith(("the user", "given the", "return", "query:")):
            continue
        if cleaned and cleaned not in queries:
            queries.append(cleaned)
    return queries[:5]


def _get_distinct_values_from_journals(column: str) -> list[str]:
    values: set[str] = set()
    try:
        for path in JOURNALS_DIR.glob("**/*.md"):
            parsed = parse_journal_file(path)
            raw_value = parsed.get(column)
            if not raw_value:
                continue
            if column == "location":
                normalized = _compact_location(str(raw_value))
                if normalized:
                    values.add(normalized)
            else:
                normalized = str(raw_value).strip()
                if normalized:
                    values.add(normalized)
    except Exception:
        return []
    return sorted(values)


def _get_search_facet_values() -> tuple[list[str], list[str]]:
    projects = _get_distinct_values("project")
    locations = [
        _compact_location(loc) for loc in _get_distinct_values("location") if loc
    ]
    locations = sorted({loc for loc in locations if loc})

    if not projects:
        projects = _get_distinct_values_from_journals("project")
    if not locations:
        locations = _get_distinct_values_from_journals("location")

    return projects, locations


@router.get("/search", response_class=HTMLResponse)
async def search_page(request: Request) -> HTMLResponse:
    """Render search page (full page or HTMX partial based on request headers)."""
    tab = request.query_params.get("tab", "keyword")
    ai_query = request.query_params.get("ai_query", "")
    query = request.query_params.get("q", "")
    topic = request.query_params.get("topic", "")
    mood = request.query_params.get("mood", "")
    tag = request.query_params.get("tag", "")
    tags = request.query_params.get("tags", "") or tag
    people = request.query_params.get("people", "")
    single_date = request.query_params.get("date", "")
    date_from = request.query_params.get("date_from", "") or single_date
    date_to = request.query_params.get("date_to", "") or single_date
    project = request.query_params.get("project", "")
    location = request.query_params.get("location", "")

    active_filters = {
        "query": query,
        "topic": topic,
        "date_from": date_from,
        "date_to": date_to,
        "mood": mood,
        "tags": tags,
        "people": people,
        "project": project,
        "location": location,
    }
    has_active_filters = any(active_filters.values())

    # Dropdown data
    projects, locations = _get_search_facet_values()

    # Determine if this is an HTMX request
    is_htmx = request.headers.get("HX-Request") == "true"

    # Perform search if query or filters provided
    search_result: dict[str, Any] | None = None
    provider = await get_provider()
    if has_active_filters and tab != "ai":
        # Keyword search: fast results without AI summary
        search_result = await search_journals_web(
            query=query or None,
            topic=topic or None,
            date_from=date_from or None,
            date_to=date_to or None,
            mood=mood or None,
            tags=tags or None,
            people=people or None,
            project=project or None,
            location=location or None,
            weather=None,
            semantic=True,
            provider=provider,
            enable_ai_summary=False,
        )

    if is_htmx:
        # Return partial for HTMX requests
        if search_result:
            return request.app.state.templates.TemplateResponse(
                request,
                "partials/search_results.html",
                {
                    "request": request,
                    "current_page": "/search",
                    "results": search_result.get("results", []),
                    "total_found": search_result.get("total_found", 0),
                    "time_ms": search_result.get("time_ms", 0.0),
                    "error": search_result.get("error"),
                    "query": query,
                    "topic": topic,
                    "date_from": date_from,
                    "date_to": date_to,
                    "mood": mood,
                    "tags": tags,
                    "people": people,
                    "project": project,
                    "location": location,
                    "weather": "",
                    "has_active_filters": has_active_filters,
                    "llm_available": provider is not None,
                    "dual_pipeline": search_result.get("dual_pipeline"),
                },
            )
        return request.app.state.templates.TemplateResponse(
            request,
            "partials/search_results.html",
            {
                "request": request,
                "current_page": "/search",
                "results": [],
                "total_found": 0,
                "time_ms": 0.0,
                "error": None,
                "query": query,
                "topic": topic,
                "date_from": date_from,
                "date_to": date_to,
                "mood": mood,
                "tags": tags,
                "people": people,
                "project": project,
                "location": location,
                "weather": "",
                "has_active_filters": has_active_filters,
                "llm_available": provider is not None,
                "dual_pipeline": None,
            },
        )

    # Full page render
    return request.app.state.templates.TemplateResponse(
        request,
        "search.html",
        {
            "request": request,
            "current_page": "/search",
            "active_tab": tab,
            "ai_query": ai_query,
            "results": search_result.get("results", []) if search_result else [],
            "total_found": search_result.get("total_found", 0) if search_result else 0,
            "time_ms": search_result.get("time_ms", 0.0) if search_result else 0.0,
            "error": search_result.get("error") if search_result else None,
            "query": query,
            "topic": topic,
            "date_from": date_from,
            "date_to": date_to,
            "mood": mood,
            "tags": tags,
            "people": people,
            "project": project,
            "location": location,
            "has_active_filters": has_active_filters,
            "llm_available": provider is not None,
            "projects": projects,
            "locations": locations,
            "drilldown_links": _drilldown_links(),
            "dual_pipeline": search_result.get("dual_pipeline")
            if search_result
            else None,
        },
    )


@router.post("/api/search/ai", response_class=HTMLResponse)
async def ai_search(request: Request):
    """Handle AI-powered natural language search."""
    form = await request.form()
    user_query = str(form.get("query", "")).strip()

    if not user_query:
        return HTMLResponse(
            '<article class="rounded-2xl p-6 sm:p-7" style="background: rgba(255, 113, 108, 0.08); box-shadow: 0 0 0 1px rgba(255, 113, 108, 0.2); color: var(--color-error);">查询不能为空</article>',
            status_code=400,
        )

    provider = await get_provider()
    if provider is None:
        return HTMLResponse(
            '<article class="rounded-2xl p-6 sm:p-7" style="background: rgba(255, 113, 108, 0.08); box-shadow: 0 0 0 1px rgba(255, 113, 108, 0.2); color: var(--color-error);">AI 不可用，请先在设置页配置 LLM API</article>',
            status_code=400,
        )

    # 使用 LLM 统一提取查询计划（日期 + 关键词）
    search_plan = await _derive_search_plan(provider, user_query)
    date_from = search_plan.get("date_from")
    date_to = search_plan.get("date_to")
    derived_queries = search_plan.get("queries", [])

    ai_search_result = await search_ai_journals_web(
        user_query=user_query,
        derived_queries=[
            *list(_behavioral_query_expansions(user_query)),
            *list(derived_queries),
        ],
        date_from=date_from,
        date_to=date_to,
        provider=provider,
        limit=15,
    )

    results = list(ai_search_result.get("results", []))
    total = int(ai_search_result.get("total_found", len(results)))

    ai_summary_state = dict(ai_search_result.get("ai_summary") or {})
    summary = ai_summary_state.get("summary")
    insights = ai_summary_state.get("insights", [])
    suggestions = ai_summary_state.get("suggestions", [])

    if not summary and results:
        summary = f"找到了 {total} 篇相关日志，但没有生成 AI 摘要。"

    # 构建结构化摘要HTML
    summary_html = ""
    if summary:
        summary_html = f'<div class="mb-5 text-sm leading-7" style="color: var(--color-on-surface);">{escape(summary)}</div>'

    # 核心洞察部分
    insights_html = ""
    if insights:
        for insight in insights[:5]:
            if isinstance(insight, dict):
                theme = escape(str(insight.get("theme", "")))
                quote = escape(str(insight.get("quote", "")))
                date = escape(str(insight.get("date", "")))
                insight_text = escape(str(insight.get("insight", "")))
                insights_html += (
                    f'<div class="mb-4 pb-4" style="border-bottom: 1px solid rgba(255,255,255,0.05);">'
                    f'<p class="font-medium text-sm mb-2" style="color: var(--color-primary);">{theme}</p>'
                    f'<p class="text-sm mb-2" style="color: var(--color-on-surface-variant); font-style: italic;">{quote}'
                )
                if date:
                    insights_html += f' <span style="opacity: 0.6;">— {date}</span>'
                insights_html += "</p>"
                if insight_text:
                    insights_html += f'<p class="text-sm" style="color: var(--color-on-surface);">{insight_text}</p>'
                insights_html += "</div>"

    # 建议部分
    suggestions_html = ""
    if suggestions:
        suggestions_html = '<div class="mt-5 pt-5" style="border-top: 1px solid rgba(255,255,255,0.08);">'
        for suggestion in suggestions[:3]:
            suggestions_html += f'<p class="text-sm mb-2" style="color: var(--color-on-surface-variant);">· {escape(str(suggestion))}</p>'
        suggestions_html += "</div>"

    # 相关日志链接
    result_lookup: dict[tuple[str, str], dict[str, Any]] = {}
    for item in results:
        result_lookup[
            (
                _normalize_result_title(str(item.get("title") or "")),
                str(item.get("date") or "").strip(),
            )
        ] = item

    items_html = ""
    for item in results[:5]:
        title = str(item.get("title", "无标题"))
        date = str(item.get("date", ""))
        route_path = item.get("journal_route_path", "")
        href = f"/journal/{route_path}" if route_path else "#"
        items_html += (
            f'<li><a href="{escape(href)}" class="text-sm hover:underline" style="color: var(--color-primary);">{escape(title)}</a>'
            f'<span class="text-xs ml-2" style="color: var(--color-on-surface-variant);">{escape(date)}</span></li>'
        )

    filters_html = "".join(
        f'<span class="rounded-full px-3 py-1 text-xs" style="background: rgba(255,255,255,0.06); color: var(--color-on-surface-variant);">{escape(str(k))}: {escape(str(v))}</span>'
        for k, v in {
            "query": user_query,
            "date_from": date_from,
            "date_to": date_to,
            "derived": ", ".join((ai_search_result.get("derived_queries") or [])[:3]),
        }.items()
        if v
    )

    html = (
        '<article class="rounded-2xl p-6 sm:p-7" style="background: rgba(18, 22, 30, 0.82); box-shadow: 0 20px 40px rgba(0, 0, 0, 0.28), 0 0 0 1px rgba(255, 255, 255, 0.05);">'
        '<div class="flex items-start gap-4 mb-5">'
        '<div class="w-10 h-10 rounded-xl flex items-center justify-center" style="background: linear-gradient(135deg, rgba(255, 231, 146, 0.15), rgba(133, 255, 242, 0.1));">'
        '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="color: var(--color-primary);"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>'
        "</div>"
        "<div>"
        '<h3 class="font-display text-xl font-medium" style="color: var(--color-on-surface);">AI 回答</h3>'
        f'<p class="text-sm" style="color: var(--color-on-surface-variant);">基于搜索到的 {total} 篇相关日志</p>'
        "</div></div>"
        f'<div class="flex flex-wrap gap-2 mb-5">{filters_html}</div>'
        f"{summary_html}"
        f"{insights_html}"
        f"{suggestions_html}"
        + (
            '<div class="mt-6 pt-6" style="border-top: 1px solid rgba(68, 72, 79, 0.15);">'
            '<h4 class="text-sm font-medium mb-3" style="color: var(--color-on-surface);">相关日志</h4>'
            f'<ul class="space-y-2">{items_html}</ul>'
            "</div>"
            if items_html
            else ""
        )
        + "</article>"
    )

    return HTMLResponse(html)
