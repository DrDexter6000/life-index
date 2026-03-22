"""Dashboard route."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from web.services.stats import compute_dashboard_stats

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request) -> HTMLResponse:
    stats = compute_dashboard_stats()
    return request.app.state.templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "request": request,
            "stats": stats,
        },
    )
