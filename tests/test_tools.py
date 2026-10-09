import pytest

from kara.agent.tools import ToolRunner, urls_in_text
from kara.scraper.search import fallback_sources

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
    response_ok = await ToolRunner(FakeYada(), search_enabled=False).execute("google_search", {"query": "x"})
    assert response_ok == ("google_search", {"ok": False, "error": "Search disabled", "sources": []})


async def test_search_enabled_uses_search_web(monkeypatch):
    async def fake_search(query, max_results=5):
        return [{"title": "T", "url": "https://a.dev"}]

    monkeypatch.setattr("kara.agent.tools.search_web", fake_search)
    name, response = await ToolRunner(FakeYada()).execute("google_search", {"query": "rag", "max_results": 1})
    assert response["ok"] is True
    assert response["sources"] == [{"title": "T", "url": "https://a.dev"}]


def test_urls_in_text_dedupes_domains():
    text = "see https://a.dev/x and https://a.dev/y plus https://b.dev"
    assert urls_in_text(text) == ["https://a.dev/x", "https://b.dev"]


def test_fallback_sources_are_never_empty():
    assert fallback_sources("rag")[0]["url"].startswith("https://")
    assert fallback_sources("anything at all")
