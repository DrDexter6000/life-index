"""Journal route."""

import importlib

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

router = APIRouter()
get_journal = importlib.import_module("web.services.journal").get_journal


@router.get("/journal/{journal_path:path}", response_class=HTMLResponse)
async def journal_view(request: Request, journal_path: str) -> HTMLResponse:
    try:
        journal = get_journal(journal_path)
    except ValueError:
        raise HTTPException(status_code=404, detail="日志未找到")

    if journal.get("error"):
        raise HTTPException(status_code=404, detail="日志未找到")

    return request.app.state.templates.TemplateResponse(
        request,
        "journal.html",
        {
            "request": request,
            "journal": journal,
            "saved": request.query_params.get("saved") == "1",
            "warning": request.query_params.get("warning"),
        },
    )
