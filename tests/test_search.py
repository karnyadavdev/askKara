import httpx

from kara.scraper.search import BRAVE_URL, SERPER_URL, TAVILY_URL, search_web


def _stub_client(payload: dict, status_code: int = 200, url: str = TAVILY_URL):
    class StubResponse:
        def __init__(self):
            self.status_code = status_code

        def raise_for_status(self):
            if self.status_code >= 400:
                request = httpx.Request("POST", url)
                raise httpx.HTTPStatusError(
                    "error",
                    request=request,
                    response=httpx.Response(self.status_code, request=request),
                )

        def json(self):
            return payload

    class StubClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, headers=None, json=None):
            return StubResponse()

        async def get(self, url, params=None, headers=None):
            return StubResponse()

    return StubClient


async def test_tavily_success(monkeypatch):
    payload = {"results": [{"title": "T", "url": "https://a.dev", "content": "x"}]}
    monkeypatch.setattr("kara.scraper.search.httpx.AsyncClient", _stub_client(payload))
    outcome = await search_web("rag", max_results=1, provider="tavily", api_key="tvly-key")
    assert outcome == {"ok": True, "sources": [{"title": "T", "url": "https://a.dev"}], "error": ""}


async def test_tavily_requires_key():
    outcome = await search_web("rag", provider="tavily", api_key="")
    assert outcome["ok"] is False
    assert "TAVILY_API_KEY" in outcome["error"]


async def test_tavily_http_error_is_named(monkeypatch):
    monkeypatch.setattr("kara.scraper.search.httpx.AsyncClient", _stub_client({}, status_code=401))
    outcome = await search_web("rag", provider="tavily", api_key="bad")
    assert outcome == {"ok": False, "sources": [], "error": "tavily_http_401"}


async def test_ddgs_provider_is_used_when_configured(monkeypatch):
    async def fake_ddgs(query, max_results, timelimit=""):
        return [{"title": "D", "url": "https://d.dev"}]

    monkeypatch.setattr("kara.scraper.search._ddgs_search", fake_ddgs)
    outcome = await search_web("rag", provider="ddgs")
    assert outcome["sources"] == [{"title": "D", "url": "https://d.dev"}]


async def test_empty_query_is_rejected():
    outcome = await search_web("   ")
    assert outcome["ok"] is False
    assert outcome["error"] == "Empty search query"


async def test_non_http_results_are_filtered(monkeypatch):
    async def fake_ddgs(query, max_results, timelimit=""):
        return [
            {"title": "ok", "url": "https://a.dev"},
            {"title": "bad", "url": "ftp://nope"},
        ]

    monkeypatch.setattr("kara.scraper.search._ddgs_search", fake_ddgs)
    outcome = await search_web("rag")
    assert outcome["sources"] == [{"title": "ok", "url": "https://a.dev"}]


async def test_serper_success(monkeypatch):
    payload = {"organic": [{"title": "S", "link": "https://s.dev", "snippet": "x"}]}
    monkeypatch.setattr("kara.scraper.search.httpx.AsyncClient", _stub_client(payload, url=SERPER_URL))
    outcome = await search_web("rag", max_results=1, provider="serper", api_key="serper-key")
    assert outcome == {"ok": True, "sources": [{"title": "S", "url": "https://s.dev"}], "error": ""}


async def test_serper_requires_key():
    outcome = await search_web("rag", provider="serper", api_key="")
    assert outcome["ok"] is False
    assert "SERPER_API_KEY" in outcome["error"]


async def test_unknown_provider_is_rejected():
    outcome = await search_web("rag", provider="bing", api_key="x")
    assert outcome == {"ok": False, "sources": [], "error": "Unknown search provider: bing"}


async def test_brave_success(monkeypatch):
    payload = {"web": {"results": [{"title": "B", "url": "https://b.dev", "description": "x"}]}}
    monkeypatch.setattr("kara.scraper.search.httpx.AsyncClient", _stub_client(payload, url=BRAVE_URL))
    outcome = await search_web("rag", max_results=1, provider="brave", api_key="brave-key")
    assert outcome == {"ok": True, "sources": [{"title": "B", "url": "https://b.dev"}], "error": ""}


async def test_brave_requires_key():
    outcome = await search_web("rag", provider="brave", api_key="")
    assert outcome["ok"] is False
    assert "BRAVE_API_KEY" in outcome["error"]


async def test_normalize_freshness_accepts_only_the_four_windows():
    from kara.scraper.search import normalize_freshness

    assert normalize_freshness("day") == "day"
    assert normalize_freshness("  WEEK ") == "week"
    assert normalize_freshness("year") == "year"
    assert normalize_freshness("decade") == ""
    assert normalize_freshness("") == ""
    assert normalize_freshness(None) == ""


async def test_ddgs_freshness_maps_to_timelimit(monkeypatch):
    seen = {}

    async def fake_ddgs(query, max_results, timelimit=""):
        seen["timelimit"] = timelimit
        return [{"title": "D", "url": "https://d.dev"}]

    monkeypatch.setattr("kara.scraper.search._ddgs_search", fake_ddgs)
    await search_web("ignou last date", provider="ddgs", freshness="week")
    assert seen["timelimit"] == "w"


async def test_ddgs_without_freshness_sends_no_timelimit(monkeypatch):
    seen = {}

    async def fake_ddgs(query, max_results, timelimit=""):
        seen["timelimit"] = timelimit
        return [{"title": "D", "url": "https://d.dev"}]

    monkeypatch.setattr("kara.scraper.search._ddgs_search", fake_ddgs)
    await search_web("ignou last date", provider="ddgs")
    assert seen["timelimit"] == ""


async def test_tavily_freshness_maps_to_time_range(monkeypatch):
    seen = {}

    def stub_client(payload, status_code=200, url=TAVILY_URL):
        class StubResponse:
            def raise_for_status(self):
                pass

            def json(self):
                return payload

        class StubClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

            async def post(self, url, headers=None, json=None):
                seen["body"] = json
                return StubResponse()

        return StubClient

    monkeypatch.setattr(
        "kara.scraper.search.httpx.AsyncClient",
        stub_client({"results": [{"title": "T", "url": "https://a.dev"}]}),
    )
    await search_web("rag", provider="tavily", api_key="k", freshness="month")
    assert seen["body"]["time_range"] == "month"


async def test_serper_freshness_maps_to_tbs(monkeypatch):
    seen = {}

    def stub_client(payload, status_code=200, url=SERPER_URL):
        class StubResponse:
            def raise_for_status(self):
                pass

            def json(self):
                return payload

        class StubClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

            async def post(self, url, headers=None, json=None):
                seen["body"] = json
                return StubResponse()

        return StubClient

    monkeypatch.setattr(
        "kara.scraper.search.httpx.AsyncClient",
        stub_client({"organic": [{"title": "S", "url": "https://s.dev"}]}),
    )
    await search_web("rag", provider="serper", api_key="k", freshness="day")
    assert seen["body"]["tbs"] == "qdr:d"


async def test_brave_freshness_maps_to_freshness(monkeypatch):
    seen = {}

    def stub_client(payload, status_code=200, url=BRAVE_URL):
        class StubResponse:
            def raise_for_status(self):
                pass

            def json(self):
                return payload

        class StubClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

            async def get(self, url, params=None, headers=None):
                seen["params"] = params
                return StubResponse()

        return StubClient

    monkeypatch.setattr(
        "kara.scraper.search.httpx.AsyncClient",
        stub_client({"web": {"results": [{"title": "B", "url": "https://b.dev"}]}}),
    )
    await search_web("rag", provider="brave", api_key="k", freshness="year")
    assert seen["params"]["freshness"] == "py"


async def test_http_error_with_freshness_degrades_and_still_returns(monkeypatch):
    calls = []

    def stub_client(payload, status_code=200, url=TAVILY_URL):
        class StubResponse:
            def raise_for_status(self):
                if status_code >= 400:
                    request = httpx.Request("POST", url)
                    raise httpx.HTTPStatusError(
                        "error",
                        request=request,
                        response=httpx.Response(status_code, request=request),
                    )

            def json(self):
                return payload

        class StubClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

            async def post(self, url, headers=None, json=None):
                calls.append(json)
                if json and json.get("time_range"):
                    return StubResponse()
                return Stub200()

        class Stub200:
            def raise_for_status(self):
                pass

            def json(self):
                return {"results": [{"title": "T", "url": "https://a.dev"}]}

        return StubClient

    monkeypatch.setattr("kara.scraper.search.httpx.AsyncClient", stub_client({}, status_code=400))
    outcome = await search_web("rag", provider="tavily", api_key="k", freshness="day")
    assert outcome["ok"] is True
    assert len(calls) == 2
    assert "time_range" in calls[0]
    assert "time_range" not in calls[1]

