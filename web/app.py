"""FastAPI application factory."""

from contextlib import asynccontextmanager
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from tools.lib.config import ATTACHMENTS_DIR, resolve_user_data_dir
from web.config import STATIC_DIR, TEMPLATES_DIR
from web.context_processors import global_context
from web.runtime import get_runtime_info
from web.routes.api import router as api_router
from web.routes.dashboard import router as dashboard_router
from web.routes.edit import router as edit_router
from web.routes.journal import router as journal_router
from web.routes.search import router as search_router
from web.routes.settings import router as settings_router
from web.routes.write import router as write_router


def _get_version() -> str:
    try:
        from importlib.metadata import version

        return version("life-index")
    except Exception:
        return "dev"


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        user_data_dir = resolve_user_data_dir()
        runtime = get_runtime_info()
        if not user_data_dir.exists():
            print(
                "Life Index Web GUI warning: "
                f"USER_DATA_DIR does not exist yet ({user_data_dir})"
            )
        print(
            "Life Index Web GUI runtime: "
            f"user_data_dir={runtime['user_data_dir']} | "
            f"journals_dir={runtime['journals_dir']} | "
            f"override={runtime['life_index_data_dir_override']} | "
            f"readonly_simulation={runtime['readonly_simulation']}"
        )
        yield

    app = FastAPI(
        title="Life Index Web GUI",
        version=_get_version(),
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    if ATTACHMENTS_DIR.exists():
        app.mount(
            "/attachments",
            StaticFiles(directory=str(ATTACHMENTS_DIR)),
            name="attachments",
        )

    app.state.templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    app.state.templates.env.globals.update(global_context())

    app.include_router(dashboard_router)
    app.include_router(api_router)
    app.include_router(edit_router)
    app.include_router(journal_router)
    app.include_router(search_router)
    app.include_router(settings_router)
    app.include_router(write_router)

    @app.get("/api/health")
    async def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "version": app.version,
            "runtime": get_runtime_info(),
        }

    @app.get("/api/runtime")
    async def runtime() -> dict[str, Any]:
        return get_runtime_info()

    return app
