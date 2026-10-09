from kara.deps import get_provider
from kara.llm.base import LLMError

from fakes import FakeProvider

VALID = {"email": "person@example.com", "password": "password-123"}


async def test_register_then_me(client):
    resp = await client.post("/api/auth/register", json=VALID)
    assert resp.status_code == 201
    token = resp.json()["access_token"]

    me = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == VALID["email"]


async def test_register_rejects_duplicate_email(client):
    first = await client.post("/api/auth/register", json=VALID)
    assert first.status_code == 201

    second = await client.post("/api/auth/register", json=VALID)
    assert second.status_code == 409


async def test_login_success_and_failure(client):
    await client.post("/api/auth/register", json=VALID)

    ok = await client.post("/api/auth/login", json=VALID)
    assert ok.status_code == 200
    assert ok.json()["token_type"] == "bearer"

    bad = await client.post("/api/auth/login", json={"email": VALID["email"], "password": "wrong-password"})
    assert bad.status_code == 401


async def test_login_rejects_unknown_email(client):
    resp = await client.post("/api/auth/login", json={"email": "ghost@example.com", "password": "password-123"})
    assert resp.status_code == 401


async def test_me_rejects_garbage_token(client):
    resp = await client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert resp.status_code == 401


async def test_me_without_token_is_401(client):
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 401


async def test_strict_mode_blocks_anonymous_ask(strict_client):
    resp = await strict_client.post("/api/ask/stream", json={"question": "hello", "max_sources": 5})
    assert resp.status_code == 401


async def test_strict_mode_allows_authed_ask(strict_client):
    register = await strict_client.post("/api/auth/register", json=VALID)
    token = register.json()["access_token"]

    resp = await strict_client.post(
        "/api/ask/stream",
        json={"question": "What is 2+2?", "max_sources": 5},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200


async def test_authed_ask_records_user(strict_client):
    register = await strict_client.post("/api/auth/register", json=VALID)
    token = register.json()["access_token"]

    resp = await strict_client.post(
        "/api/ask/stream",
        json={"question": "What is 2+2?", "max_sources": 5},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200

    from sqlalchemy import select

    from kara.db import get_session_factory
    from kara.models import QueryRecord, User

    factory = get_session_factory()
    async with factory() as session:
        user = (await session.execute(select(User).where(User.email == VALID["email"]))).scalar_one()
        record = (await session.execute(select(QueryRecord).where(QueryRecord.user_id == user.id))).scalar_one()
    assert record.question == "What is 2+2?"


async def test_ask_with_invalid_token_is_401(client):
    client.app.dependency_overrides[get_provider] = lambda: FakeProvider([LLMError("never used", status_code=500)])
    resp = await client.post(
        "/api/ask/stream",
        json={"question": "hi", "max_sources": 5},
        headers={"Authorization": "Bearer garbage"},
    )
    assert resp.status_code == 401
