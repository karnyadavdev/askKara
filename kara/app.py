from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from kara.config import get_settings
from kara.db import create_all_tables
from kara.routers import ask, auth, health

ROOT = Path(__file__).resolve().parent.parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    if settings.auto_create_tables:
        await create_all_tables()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="askKara", version="0.3.0", lifespan=lifespan)

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(ask.router)

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(ROOT / "index.html")

    @app.get("/styles.css", include_in_schema=False)
    async def styles() -> FileResponse:
        return FileResponse(ROOT / "styles.css", media_type="text/css")

    @app.get("/app.js", include_in_schema=False)
    async def app_js() -> FileResponse:
        return FileResponse(ROOT / "app.js", media_type="application/javascript")

    return app


app = create_app()
