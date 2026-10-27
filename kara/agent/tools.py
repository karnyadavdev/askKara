import asyncio
import json
import re
from urllib.parse import urlparse

from kara.scraper.search import search_web
from kara.scraper.yada import YadaClient
from kara.texttrim import trim_head_tail

TOOL_TEXT_LIMIT = 10_000

TOOL_SCHEMAS: list[dict] = [
    {
        "name": "web_search",
        "description": (
            "Find source URLs on the open web through the configured search API. "
            "Use this when the user did not provide a direct URL or when current source discovery is needed."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query to run."},
                "max_results": {"type": "integer", "description": "Maximum number of source URLs to return."},
            },
            "required": ["query"],
        },
    },
    {
        "name": "yada_scrape",
        "description": (
            "Scrape a web page with YADA. Use this directly for URLs supplied by the user. "
            "Use this for URLs supplied by the user, URLs discovered through web_search, "
            "or authoritative URLs you can infer from the question."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The URL to scrape."},
            },
            "required": ["url"],
        },
    },
    {
        "name": "yada_scrape_many",
        "description": (
            "Scrape multiple web pages with YADA in parallel. Prefer this when the user asks "
            "for multiple sites, comparisons, lists of sources, product prices across retailers, "
            "or when web_search returns several useful URLs. It accepts 2 to 10 URLs "
            "(up to 25 in deep research mode)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "urls": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "The source URLs to scrape. Include 2 to 10 URLs.",
                },
            },
            "required": ["urls"],
        },
    },
]


class SourceBudget:
    def __init__(self, max_sources: int, total_chars: int):
        self.max_sources = max(1, max_sources)
        self.total_chars = max(1, total_chars)
        self.gathered = 0
        self.used_chars = 0

    @property
    def sources_left(self) -> int:
        return max(0, self.max_sources - self.gathered)

    @property
    def chars_left(self) -> int:
        return max(0, self.total_chars - self.used_chars)

    def add(self, chars: int) -> None:
        self.gathered += 1
        self.used_chars += max(0, chars)


class ToolRunner:
    def __init__(
        self,
        yada: YadaClient,
        max_sources: int = 8,
        search_enabled: bool = True,
        search_provider: str = "ddgs",
        search_api_key: str = "",
        batch_cap: int = 10,
        trim_text: bool = True,
        budget: SourceBudget | None = None,
    ):
        self._yada = yada
        self._max_sources = max_sources
        self._search_enabled = search_enabled
        self._search_provider = search_provider
        self._search_api_key = search_api_key
        self._batch_cap = max(2, min(batch_cap, 40))
        self._trim_text = trim_text
        self._budget = budget or SourceBudget(max_sources, max_sources * TOOL_TEXT_LIMIT)

    @property
    def budget(self) -> SourceBudget:
        return self._budget

    def _limit(self, text: str) -> str:
        if not self._trim_text:
            return text
        return trim_head_tail(text, TOOL_TEXT_LIMIT)

    async def execute(self, name: str, args: dict) -> tuple[str, dict]:
        if name == "web_search":
            return name, await self._web_search(args)

        if name == "yada_scrape":
            return name, await self._yada_scrape(args)

        if name == "yada_scrape_many":
            return name, await self._yada_scrape_many(args)

        return name, {"ok": False, "error": f"Unknown tool: {name}"}

    async def _web_search(self, args: dict) -> dict:
        if not self._search_enabled:
            return {"ok": False, "error": "Search disabled", "sources": []}
        query = str(args.get("query") or "").strip()
        max_results = int(args.get("max_results") or self._max_sources or 4)
        max_results = max(1, min(max_results, 10))
        outcome = await search_web(
            query,
            max_results=max_results,
            provider=self._search_provider,
            api_key=self._search_api_key,
        )
        if not outcome["ok"]:
            return {"ok": False, "error": outcome["error"], "sources": []}
        return {
            "summary": "Source discovery only. Call yada_scrape on relevant URLs before answering.",
            "ok": True,
            "sources": outcome["sources"],
        }

    async def _yada_scrape(self, args: dict) -> dict:
        url = str(args.get("url") or "").strip()
        if not url.startswith(("http://", "https://")):
            return {"ok": False, "error": "Invalid URL", "url": url}
        result = await self._yada.scrape(url)
        return {
            "ok": result["ok"],
            "title": result["title"],
            "url": result["url"],
            "text": self._limit(result["text"]),
            "layer": result["layer"],
            "error": result["error"],
            "reason": result.get("reason", ""),
        }

    async def _yada_scrape_many(self, args: dict) -> dict:
        raw_urls = args.get("urls") or []
        if not isinstance(raw_urls, list):
            return {"ok": False, "error": "urls must be an array", "results": []}

        urls: list[str] = []
        seen: set[str] = set()
        for raw_url in raw_urls:
            url = str(raw_url or "").strip()
            if not url.startswith(("http://", "https://")) or url in seen:
                continue
            seen.add(url)
            urls.append(url)
            if len(urls) >= self._batch_cap:
                break

        if not urls:
            return {"ok": False, "error": "No valid URLs", "results": []}

        limit = min(self._max_sources, self._batch_cap)
        sem = asyncio.Semaphore(3)

        async def guarded(single_url: str):
            async with sem:
                return await self._yada.scrape(single_url)

        scraped = await asyncio.gather(*(guarded(url) for url in urls[:limit]))
        results = [
            {
                "ok": item["ok"],
                "title": item["title"],
                "url": item["url"],
                "text": self._limit(item["text"]),
                "layer": item["layer"],
                "error": item["error"],
                "reason": item.get("reason", ""),
            }
            for item in scraped[:limit]
        ]
        any_ok = any(item["ok"] for item in results)
        return {
            "ok": any_ok,
            "requested": len(urls),
            "returned": len(results),
            "results": results,
            "error": "" if any_ok else "No usable pages were scraped",
        }


def dumps(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False)


def urls_in_text(text: str) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for match in re.finditer(r"https?://[^\s<>()\"']+", text):
        url = match.group(0).rstrip(".,;:!?]")
        domain = urlparse(url).netloc.lower()
        if not domain or domain in seen:
            continue
        seen.add(domain)
        urls.append(url)
    return urls
