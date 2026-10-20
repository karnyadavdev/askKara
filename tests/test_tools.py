import pytest

from kara.agent.tools import ToolRunner, urls_in_text

from fakes import FakeYada


async def test_unknown_tool_is_rejected():
    name, response = await ToolRunner(FakeYada()).execute("bogus_tool", {})
    assert name == "bogus_tool"
    assert response["ok"] is False


async def test_scrape_rejects_non_http_url():
    name, response = await ToolRunner(FakeYada()).execute("yada_scrape", {"url": "ftp://example.com"})
    assert response["ok"] is False
    assert response["error"] == "Invalid URL"


async def test_scrape_many_dedupes_and_caps_at_ten():
    yada = FakeYada()
    urls = [f"https://s{i}.dev" for i in range(12)] + ["https://s0.dev"]
    name, response = await ToolRunner(yada, max_sources=10).execute("yada_scrape_many", {"urls": urls})

    assert response["requested"] == 10
    assert len(response["results"]) == 10
    assert len(yada.calls) == 10


async def test_scrape_many_reports_no_usable_pages():
    class DeadYada:
        async def scrape(self, url, objective=""):
            return {"ok": False, "title": url, "url": url, "text": "", "layer": "none", "error": "blocked"}

    name, response = await ToolRunner(DeadYada()).execute("yada_scrape_many", {"urls": ["https://a.dev", "https://b.dev"]})
    assert response["ok"] is False
    assert response["error"] == "No usable pages were scraped"


async def test_search_disabled_rejects_lookup():
    response_ok = await ToolRunner(FakeYada(), search_enabled=False).execute("web_search", {"query": "x"})
    assert response_ok == ("web_search", {"ok": False, "error": "Search disabled", "sources": []})


async def test_search_enabled_uses_search_web(monkeypatch):
    async def fake_search(query, max_results=5, provider="ddgs", api_key=""):
        return {"ok": True, "sources": [{"title": "T", "url": "https://a.dev"}], "error": ""}

    monkeypatch.setattr("kara.agent.tools.search_web", fake_search)
    name, response = await ToolRunner(FakeYada()).execute("web_search", {"query": "rag", "max_results": 1})
    assert response["ok"] is True
    assert response["sources"] == [{"title": "T", "url": "https://a.dev"}]


async def test_search_failure_is_reported_to_the_model(monkeypatch):
    async def fake_search(query, max_results=5, provider="ddgs", api_key=""):
        return {"ok": False, "sources": [], "error": "tavily_http_401"}

    monkeypatch.setattr("kara.agent.tools.search_web", fake_search)
    name, response = await ToolRunner(FakeYada()).execute("web_search", {"query": "rag"})
    assert response == {"ok": False, "error": "tavily_http_401", "sources": []}


def test_urls_in_text_dedupes_domains():
    text = "see https://a.dev/x and https://a.dev/y plus https://b.dev"
    assert urls_in_text(text) == ["https://a.dev/x", "https://b.dev"]


class LongYada:
    def __init__(self):
        self.text = "H" + "m" * 40_000 + "T"

    async def scrape(self, url, objective=""):
        return {"ok": True, "title": "t", "url": url, "text": self.text, "layer": "fake", "error": ""}


async def test_scrape_trims_to_fifteen_k_by_default():
    _, response = await ToolRunner(LongYada()).execute("yada_scrape", {"url": "https://a.dev"})
    assert len(response["text"]) == 15_000
    assert "[TRUNCATED: middle omitted]" in response["text"]


async def test_scrape_many_trims_to_fifteen_k_by_default():
    _, response = await ToolRunner(LongYada(), max_sources=2).execute(
        "yada_scrape_many", {"urls": ["https://a.dev", "https://b.dev"]}
    )
    assert all(len(item["text"]) == 15_000 for item in response["results"])


async def test_scrape_keeps_full_text_when_trim_disabled():
    yada = LongYada()
    _, response = await ToolRunner(yada, trim_text=False).execute("yada_scrape", {"url": "https://a.dev"})
    assert response["text"] == yada.text


async def test_scrape_many_keeps_full_text_when_trim_disabled():
    yada = LongYada()
    _, response = await ToolRunner(yada, max_sources=2, trim_text=False).execute(
        "yada_scrape_many", {"urls": ["https://a.dev", "https://b.dev"]}
    )
    assert all(item["text"] == yada.text for item in response["results"])
