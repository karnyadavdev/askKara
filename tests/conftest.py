import os

import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("KARA_AUTH_REQUIRED", "0")
os.environ.setdefault("YADA_MODE", "off")

from kara.config import get_settings  # noqa: E402
from kara.db import create_all_tables, reset_db_state  # noqa: E402
from kara.deps import get_provider, get_yada, reset_runtime_state  # noqa: E402
from kara.routers.ask import reset_rate_limiter  # noqa: E402

from fakes import FakeProvider, FakeYada  # noqa: E402
from kara.llm.base import ChatReply  # noqa: E402


def _reset(tmp_path, monkeypatch, auth_required="0"):
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("YADA_MODE", "off")
    monkeypatch.setenv("KARA_AUTH_REQUIRED", auth_required)
    get_settings.cache_clear()
    reset_db_state()
    reset_runtime_state()
    reset_rate_limiter()


def _teardown():
    get_settings.cache_clear()
    reset_db_state()
    reset_runtime_state()
    reset_rate_limiter()


@pytest.fixture
async def client(tmp_path, monkeypatch):
    _reset(tmp_path, monkeypatch)

    from kara.app import create_app

    app = create_app()
    await create_all_tables()
    app.dependency_overrides[get_provider] = lambda: FakeProvider([ChatReply(content="default answer")])
    app.dependency_overrides[get_yada] = lambda: FakeYada()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as async_client:
        async_client.app = app
        yield async_client

    _teardown()


@pytest.fixture
async def strict_client(tmp_path, monkeypatch):
    _reset(tmp_path, monkeypatch, auth_required="1")

    from kara.app import create_app

    app = create_app()
    await create_all_tables()
    app.dependency_overrides[get_provider] = lambda: FakeProvider([ChatReply(content="default answer")])
    app.dependency_overrides[get_yada] = lambda: FakeYada()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as async_client:
        async_client.app = app
        yield async_client

    _teardown()
