import json

from fakes import ChatReply, FakeProvider

VALID = {"email": "conv@example.com", "password": "password-123"}


def parse_ndjson(text):
    return [json.loads(line) for line in text.splitlines() if line.strip()]


async def ask(client, question, headers=None, conversation_id=None):
    body = {"question": question, "max_sources": 5}
    if conversation_id is not None:
        body["conversation_id"] = conversation_id
    return await client.post("/api/ask/stream", json=body, headers=headers or {})


async def test_conversations_require_token(client):
    resp = await client.get("/api/conversations")
    assert resp.status_code == 401


async def test_ask_creates_chat_titled_with_question(client):
    register = await client.post("/api/auth/register", json=VALID)
    token = register.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    resp = await ask(client, "What is rate limiting?", headers=headers)
    events = parse_ndjson(resp.text)
    assert events[0]["type"] == "conversation"
    assert events[0]["id"] > 0

    listing = await client.get("/api/conversations", headers=headers)
    items = listing.json()["items"]
    assert len(items) == 1
    assert items[0]["title"] == "What is rate limiting?"
    assert items[0]["id"] == events[0]["id"]


async def test_followup_continues_same_chat_and_get_turns(client):
    register = await client.post("/api/auth/register", json=VALID)
    token = register.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    first = await ask(client, "first question", headers=headers)
    conv_id = parse_ndjson(first.text)[0]["id"]

    second = await ask(client, "second question", headers=headers, conversation_id=conv_id)
    assert parse_ndjson(second.text)[0]["id"] == conv_id

    listing = await client.get("/api/conversations", headers=headers)
    assert len(listing.json()["items"]) == 1

    turns = await client.get(f"/api/conversations/{conv_id}", headers=headers)
    items = turns.json()["items"]
    assert [item["question"] for item in items] == ["first question", "second question"]


async def test_context_is_passed_to_llm_on_followup(client):
    from kara.deps import get_provider

    provider = FakeProvider([ChatReply(content="Answer one."), ChatReply(content="Answer two.")])
    client.app.dependency_overrides[get_provider] = lambda: provider

    first = await ask(client, "What is YADA?")
    conv_id = parse_ndjson(first.text)[0]["id"]
    await ask(client, "How does it search?", conversation_id=conv_id)

    assert len(provider.calls) == 2
    second_call = provider.calls[1]
    contents = [message.get("content", "") for message in second_call]
    assert second_call[0]["role"] == "system"
    assert {"role": "user", "content": "What is YADA?"} in second_call
    assert {"role": "assistant", "content": "Answer one."} in second_call
    assert contents[-1] == "How does it search?"


async def test_other_users_chat_is_404(client):
    mine = await client.post("/api/auth/register", json=VALID)
    mine_headers = {"Authorization": f"Bearer {mine.json()['access_token']}"}
    other = await client.post("/api/auth/register", json={"email": "other2@example.com", "password": "password-123"})
    other_headers = {"Authorization": f"Bearer {other.json()['access_token']}"}

    first = await ask(client, "my private chat", headers=mine_headers)
    conv_id = parse_ndjson(first.text)[0]["id"]

    resp = await client.get(f"/api/conversations/{conv_id}", headers=other_headers)
    assert resp.status_code == 404

    followup = await ask(client, "hijack attempt", headers=other_headers, conversation_id=conv_id)
    assert followup.status_code == 404


async def test_unknown_conversation_id_is_404(client):
    resp = await ask(client, "hello", conversation_id=999999)
    assert resp.status_code == 404


async def test_guests_cannot_list_chats_but_keep_in_session_continuity(client):
    first = await ask(client, "guest question one")
    conv_id = parse_ndjson(first.text)[0]["id"]
    await ask(client, "guest follow-up", conversation_id=conv_id)

    listing = await client.get("/api/conversations")
    assert listing.status_code == 401

    from sqlalchemy import select

    from kara.db import get_session_factory
    from kara.models import Conversation, QueryRecord

    factory = get_session_factory()
    async with factory() as session:
        convs = (await session.execute(select(Conversation))).scalars().all()
        rows = (await session.execute(select(QueryRecord))).scalars().all()
    assert len(convs) == 1
    assert convs[0].user_id is None
    assert len(rows) == 2
    assert all(row.conversation_id == conv_id for row in rows)
