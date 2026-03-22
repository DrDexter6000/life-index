"""FastAPI application factory."""

from typing import Any

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from tools.lib.config import ATTACHMENTS_DIR
from web.config import STATIC_DIR, TEMPLATES_DIR
from web.routes.dashboard import router as dashboard_router
from web.routes.edit import router as edit_router
from web.routes.journal import router as journal_router
from web.routes.search import router as search_router
from web.routes.write import router as write_router


def _get_version() -> str:
    try:
        from importlib.metadata import version

        return version("life-index")
    except Exception:
        return "dev"


def create_app() -> FastAPI:
    app = FastAPI(
        title="Life Index Web GUI",
        version=_get_version(),
        docs_url=None,
        redoc_url=None,
    )

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    if ATTACHMENTS_DIR.exists():
        app.mount(
            "/attachments",
            StaticFiles(directory=str(ATTACHMENTS_DIR)),
            name="attachments",
        )

    app.state.templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    app.include_router(dashboard_router)
    app.include_router(edit_router)
    app.include_router(journal_router)
    app.include_router(search_router)
    app.include_router(write_router)

    @app.get("/api/health")
    async def health() -> dict[str, Any]:
        return {"status": "ok", "version": app.version}

    return app
