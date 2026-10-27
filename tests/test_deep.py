async def test_deep_request_raises_caps_and_steps(client, monkeypatch):
    import kara.routers.ask as ask_module

    captured = {}
    real = ask_module.run_agent

    async def spy(question, **kwargs):
        captured.update(kwargs)
        return await real(question, **kwargs)

    monkeypatch.setattr(ask_module, "run_agent", spy)
    resp = await client.post(
        "/api/ask/stream",
        json={"question": "deep question", "max_sources": 99, "deep": True},
    )
    assert resp.status_code == 200
    assert captured["max_sources"] == 50
    assert captured["max_steps"] == 30
    assert captured["summarize"] is False


async def test_normal_request_keeps_small_caps(client, monkeypatch):
    import kara.routers.ask as ask_module

    captured = {}
    real = ask_module.run_agent

    async def spy(question, **kwargs):
        captured.update(kwargs)
        return await real(question, **kwargs)

    monkeypatch.setattr(ask_module, "run_agent", spy)
    resp = await client.post(
        "/api/ask/stream",
        json={"question": "normal question", "max_sources": 99},
    )
    assert resp.status_code == 200
    assert captured["max_sources"] == 10
    assert captured["max_steps"] == 12
    assert captured["summarize"] is False


async def test_deep_rate_limit_is_separate(client):
    for _ in range(3):
        resp = await client.post("/api/ask/stream", json={"question": "deep q", "deep": True})
        assert resp.status_code == 200

    blocked = await client.post("/api/ask/stream", json={"question": "deep q", "deep": True})
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers

    normal = await client.post("/api/ask/stream", json={"question": "normal q"})
    assert normal.status_code == 200


async def test_deep_batch_cap_allows_larger_scrape_batches():
    from fakes import FakeYada
    from kara.agent.tools import ToolRunner

    yada = FakeYada()
    runner = ToolRunner(yada, max_sources=50, batch_cap=25)
    urls = [f"https://s{i}.dev" for i in range(30)]
    name, response = await runner.execute("yada_scrape_many", {"urls": urls})
    assert response["requested"] == 25
    assert len(yada.calls) == 25


async def test_omitted_max_sources_uses_mode_default(client, monkeypatch):
    import kara.routers.ask as ask_module

    captured = {}
    real = ask_module.run_agent

    async def spy(question, **kwargs):
        captured.update(kwargs)
        return await real(question, **kwargs)

    monkeypatch.setattr(ask_module, "run_agent", spy)

    await client.post("/api/ask/stream", json={"question": "normal q"})
    assert captured["max_sources"] == 10

    captured.clear()
    await client.post("/api/ask/stream", json={"question": "deep q", "deep": True})
    assert captured["max_sources"] == 50


def test_budget_invariant_is_cap_times_per_page():
    from kara.config import Settings
    from kara.deps import build_runner

    settings = Settings()

    normal = build_runner(settings, None, deep=False)
    assert normal.budget.max_sources == 10
    assert normal.budget.total_chars == 10 * 10_000

    deep = build_runner(settings, None, deep=True)
    assert deep.budget.max_sources == 50
    assert deep.budget.total_chars == 50 * 6_000
