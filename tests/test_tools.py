
from kara.agent.tools import TOOL_SCHEMAS, SourceBudget, ToolRunner, safe_calculate, urls_in_text

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
        async def scrape(self, url):
            return {"ok": False, "title": url, "url": url, "text": "", "layer": "none", "error": "blocked"}

    name, response = await ToolRunner(DeadYada()).execute("yada_scrape_many", {"urls": ["https://a.dev", "https://b.dev"]})
    assert response["ok"] is False
    assert response["error"] == "No usable pages were scraped"


async def test_search_disabled_rejects_lookup():
    response_ok = await ToolRunner(FakeYada(), search_enabled=False).execute("web_search", {"query": "x"})
    assert response_ok == ("web_search", {"ok": False, "error": "Search disabled", "sources": []})


async def test_search_enabled_uses_search_web(monkeypatch):
    async def fake_search(query, max_results=5, provider="ddgs", api_key="", freshness=""):
        return {"ok": True, "sources": [{"title": "T", "url": "https://a.dev"}], "error": ""}

    monkeypatch.setattr("kara.agent.tools.search_web", fake_search)
    name, response = await ToolRunner(FakeYada()).execute("web_search", {"query": "rag", "max_results": 1})
    assert response["ok"] is True
    assert response["sources"] == [{"title": "T", "url": "https://a.dev"}]


async def test_search_failure_is_reported_to_the_model(monkeypatch):
    async def fake_search(query, max_results=5, provider="ddgs", api_key="", freshness=""):
        return {"ok": False, "sources": [], "error": "tavily_http_401"}

    monkeypatch.setattr("kara.agent.tools.search_web", fake_search)
    name, response = await ToolRunner(FakeYada()).execute("web_search", {"query": "rag"})
    assert response == {"ok": False, "error": "tavily_http_401", "sources": []}


async def test_web_search_passes_freshness_through(monkeypatch):
    seen = {}

    async def fake_search(query, max_results=5, provider="ddgs", api_key="", freshness=""):
        seen["freshness"] = freshness
        return {"ok": True, "sources": [], "error": ""}

    monkeypatch.setattr("kara.agent.tools.search_web", fake_search)
    await ToolRunner(FakeYada()).execute(
        "web_search", {"query": "ignou last date", "freshness": "week"}
    )
    assert seen["freshness"] == "week"


async def test_web_search_passes_raw_freshness_for_search_layer_to_normalize(monkeypatch):
    seen = {}

    async def fake_search(query, max_results=5, provider="ddgs", api_key="", freshness=""):
        seen["freshness"] = freshness
        return {"ok": True, "sources": [], "error": ""}

    monkeypatch.setattr("kara.agent.tools.search_web", fake_search)
    await ToolRunner(FakeYada()).execute("web_search", {"query": "x", "freshness": "decade"})
    assert seen["freshness"] == "decade"


def test_urls_in_text_dedupes_domains():
    text = "see https://a.dev/x and https://a.dev/y plus https://b.dev"
    assert urls_in_text(text) == ["https://a.dev/x", "https://b.dev"]


class LongYada:
    def __init__(self):
        self.text = "H" + "m" * 40_000 + "T"

    async def scrape(self, url):
        return {"ok": True, "title": "t", "url": url, "text": self.text, "layer": "fake", "error": ""}


async def test_scrape_trims_to_ten_k_by_default():
    _, response = await ToolRunner(LongYada()).execute("yada_scrape", {"url": "https://a.dev"})
    assert len(response["text"]) == 10_000
    assert "[TRUNCATED: middle omitted]" in response["text"]


async def test_scrape_many_trims_to_ten_k_by_default():
    _, response = await ToolRunner(LongYada(), max_sources=2).execute(
        "yada_scrape_many", {"urls": ["https://a.dev", "https://b.dev"]}
    )
    assert all(len(item["text"]) == 10_000 for item in response["results"])


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


async def test_scrape_many_delivers_every_scrape_to_the_model():
    class MixedYada:
        async def scrape(self, url):
            good = "good" in url
            return {
                "ok": good,
                "title": url,
                "url": url,
                "text": "real content" if good else "thin shell",
                "layer": "fake",
                "error": "",
                "reason": "" if good else "metadata too thin",
            }

    _, response = await ToolRunner(MixedYada()).execute(
        "yada_scrape_many", {"urls": ["https://good.dev", "https://thin.dev"]}
    )

    assert response["ok"] is True
    assert [item["ok"] for item in response["results"]] == [True, False]
    assert [item["text"] for item in response["results"]] == ["real content", "thin shell"]
    assert response["results"][1]["reason"] == "metadata too thin"


async def test_scrape_many_no_longer_overfetches():
    yada = FakeYada()
    urls = [f"https://s{i}.dev" for i in range(6)]
    _, response = await ToolRunner(yada, max_sources=2).execute("yada_scrape_many", {"urls": urls})

    assert len(yada.calls) == 2
    assert len(response["results"]) == 2


def test_source_budget_tracks_sources_and_chars():
    budget = SourceBudget(2, 100)
    assert budget.sources_left == 2
    assert budget.chars_left == 100

    budget.add(60)
    budget.add(30)
    assert budget.sources_left == 0
    assert budget.chars_left == 10
    assert budget.used_chars == 90


def test_default_budget_matches_normal_mode_invariant():
    runner = ToolRunner(FakeYada(), max_sources=10)
    assert runner.budget.max_sources == 10
    assert runner.budget.total_chars == 10 * 10_000


def test_objective_parameter_is_removed_everywhere():
    from kara.prompts import build_system_prompt

    for schema in TOOL_SCHEMAS:
        assert "objective" not in schema["parameters"]["properties"]
    assert "objective" not in build_system_prompt(max_sources=50)


def test_calculator_schema_is_registered():
    names = [schema["name"] for schema in TOOL_SCHEMAS]
    assert "calculator" in names


def test_calculator_evaluates_arithmetic():
    assert safe_calculate("2 + 2") == (True, "4")
    assert safe_calculate("10 / 4") == (True, "2.5")
    assert safe_calculate("2 ** 10") == (True, "1024")
    assert safe_calculate("(1 + 2) * (3 + 4)") == (True, "21")
    assert safe_calculate("7 // 2") == (True, "3")
    assert safe_calculate("10 % 3") == (True, "1")
    assert safe_calculate("-5 + 3") == (True, "-2")


def test_calculator_rounds_floats():
    ok, result = safe_calculate("0.1 + 0.2")
    assert ok is True
    assert result == "0.3"


async def test_calculator_tool_returns_ok_payload():
    name, response = await ToolRunner(FakeYada()).execute("calculator", {"expression": "2 ** 10"})
    assert name == "calculator"
    assert response["ok"] is True
    assert response["result"] == "1024"


async def test_calculator_division_by_zero_is_friendly():
    name, response = await ToolRunner(FakeYada()).execute("calculator", {"expression": "1 / 0"})
    assert response["ok"] is False
    assert response["error"] == "Division by zero"


def test_calculator_rejects_code_injection():
    for bad in (
        "__import__('os')",
        "open('/etc/passwd')",
        "eval('1')",
        "().__class__",
        "[1,2]",
        "'string'",
        "1 if True else 2",
    ):
        ok, result = safe_calculate(bad)
        assert ok is False, bad
        assert result != ""


def test_calculator_rejects_empty_and_overlong():
    assert safe_calculate("") == (False, "Empty expression")
    assert safe_calculate("   ") == (False, "Empty expression")
    ok, result = safe_calculate("1+" * 200)
    assert ok is False
    assert "too long" in result.lower()


def test_calculator_rejects_non_arithmetic_words():
    ok, result = safe_calculate("five plus three")
    assert ok is False
