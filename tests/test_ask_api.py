import json

from kara.deps import get_provider
from kara.llm.base import LLMError, ToolCall

from fakes import ChatReply, FakeProvider


def parse_ndjson(text):
    return [json.loads(line) for line in text.splitlines() if line.strip()]


async def ask(client, question, max_sources=5):
    return await client.post("/api/ask/stream", json={"question": question, "max_sources": max_sources})


async def test_stream_direct_answer(client):
    client.app.dependency_overrides[get_provider] = lambda: FakeProvider([ChatReply(content="Paris [1].")])

    resp = await ask(client, "What is the capital of France?")

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/x-ndjson")
    events = parse_ndjson(resp.text)
    assert events[-1]["type"] == "done"
    assert events[-1]["answer"] == "Paris [1]."
    assert any(event["type"] in {"stage", "sources"} for event in events)


async def test_stream_with_tool_calls_returns_sources(client):
    client.app.dependency_overrides[get_provider] = lambda: FakeProvider(
        [
            ChatReply(
                tool_calls=[ToolCall(id="c1", name="yada_scrape", arguments={"url": "https://example.com"})]
            ),
            ChatReply(content="Composed answer [1]."),
        ]
    )

    resp = await ask(client, "Summarize https://example.com")

    events = parse_ndjson(resp.text)
    done = events[-1]
    assert done["type"] == "done"
    assert done["answer"] == "Composed answer [1]."
    assert done["sources"][0]["url"] == "https://example.com"
    assert any(event["type"] == "sources" for event in events)


async def test_empty_question_is_rejected(client):
    resp = await ask(client, "   ")
    assert resp.status_code == 422


async def test_max_sources_is_clamped_to_cap(client):
    from kara.config import get_settings

    cap = get_settings().max_sources_cap
    client.app.dependency_overrides[get_provider] = lambda: FakeProvider(
        [
            ChatReply(
                tool_calls=[ToolCall(id="c1", name="yada_scrape", arguments={"url": "https://example.com"})]
            )
        ]
        * 1
        + [ChatReply(content="Done [1].")]
    )

    resp = await ask(client, "Summarize https://example.com", max_sources=999)

    assert resp.status_code == 200
    done = parse_ndjson(resp.text)[-1]
    assert len(done["sources"]) <= cap


async def test_rate_limit_returns_429(client):
    from fakes import ChatReply

    client.app.dependency_overrides[get_provider] = lambda: FakeProvider([ChatReply(content="ok")] * 20)

    responses = [await ask(client, f"question {i}") for i in range(17)]
    statuses = [response.status_code for response in responses]

    assert statuses[:15] == [200] * 15
    assert statuses.count(429) == 2
    assert responses[-1].headers["retry-after"]


async def test_provider_rate_limit_emits_error_event(client):
    client.app.dependency_overrides[get_provider] = lambda: FakeProvider(
        [
            LLMError("groq: HTTP 429", status_code=429, retriable=True),
            LLMError("openai: HTTP 429", status_code=429, retriable=True),
        ]
    )

    resp = await ask(client, "Summarize https://example.com")

    assert resp.status_code == 200
    events = parse_ndjson(resp.text)
    assert events[-1]["type"] == "error"
    assert events[-1]["message"] == "rate_limited"


async def test_provider_auth_failure_emits_error_event(client):
    client.app.dependency_overrides[get_provider] = lambda: FakeProvider(
        [LLMError("openai: authentication failed (check API key)", status_code=401)]
    )

    resp = await ask(client, "Summarize https://example.com")

    assert resp.status_code == 200
    last = parse_ndjson(resp.text)[-1]
    assert last["type"] == "error"
    assert "authentication" in last["message"]


async def test_guest_history_is_saved(client):
    from fakes import ChatReply

    client.app.dependency_overrides[get_provider] = lambda: FakeProvider([ChatReply(content="Answer.")])

    await ask(client, "What is 2+2?")

    from sqlalchemy import select

    from kara.db import get_session_factory
    from kara.models import QueryRecord

    factory = get_session_factory()
    async with factory() as session:
        rows = (await session.execute(select(QueryRecord))).scalars().all()
    assert len(rows) == 1
    assert rows[0].user_id is None


async def test_health_endpoint(client):
    resp = await client.get("/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["llm_chain"] == ["groq", "openai"]
    assert body["auth_required"] is False


async def test_index_is_served(client):
    resp = await client.get("/")

    assert resp.status_code == 200
    assert "askKara" in resp.text.lower() or "<html" in resp.text.lower()
