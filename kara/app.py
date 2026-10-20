from contextlib import asynccontextmanager

from fastapi import FastAPI

from kara.config import get_settings
from kara.db import create_all_tables
from kara.routers import ask, auth, health, history


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
    app.include_router(history.router)

    return app


app = create_app()
