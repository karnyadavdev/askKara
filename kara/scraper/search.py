import asyncio

import httpx

TAVILY_URL = "https://api.tavily.com/search"
SERPER_URL = "https://google.serper.dev/search"
BRAVE_URL = "https://api.search.brave.com/res/v1/web/search"

FRESHNESS_WINDOW = ("day", "week", "month", "year")
DDGS_TIMELIMIT = {"day": "d", "week": "w", "month": "m", "year": "y"}
SERPER_TBQ = {"day": "qdr:d", "week": "qdr:w", "month": "qdr:m", "year": "qdr:y"}
BRAVE_FRESHNESS = {"day": "pd", "week": "pw", "month": "pm", "year": "py"}


def normalize_freshness(value: str) -> str:
    value = (value or "").strip().lower()
    return value if value in FRESHNESS_WINDOW else ""


def _ddgs_search_sync(query: str, max_results: int, timelimit: str = "") -> list[dict]:
    from ddgs import DDGS

    results = DDGS().text(query, max_results=max_results, timelimit=timelimit or None)
    return [{"title": r.get("title", ""), "url": r.get("href", "")} for r in results]


async def _ddgs_search(query: str, max_results: int, timelimit: str = "") -> list[dict]:
    return await asyncio.wait_for(
        asyncio.to_thread(_ddgs_search_sync, query, max_results, timelimit), timeout=20
    )


async def _tavily_search(query: str, max_results: int, api_key: str, time_range: str = "") -> list[dict]:
    payload: dict = {"query": query, "max_results": max_results, "search_depth": "basic"}
    if time_range:
        payload["time_range"] = time_range
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            TAVILY_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
    return [{"title": r.get("title", ""), "url": r.get("url", "")} for r in data.get("results", [])]


async def _serper_search(query: str, max_results: int, api_key: str, tbq: str = "") -> list[dict]:
    body: dict = {"q": query, "num": max_results}
    if tbq:
        body["tbs"] = tbq
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            SERPER_URL,
            headers={"X-API-KEY": api_key},
            json=body,
        )
        response.raise_for_status()
        payload = response.json()
    return [{"title": r.get("title", ""), "url": r.get("link", "")} for r in payload.get("organic", [])]


async def _brave_search(query: str, max_results: int, api_key: str, freshness: str = "") -> list[dict]:
    params: dict = {"q": query, "count": max_results}
    if freshness:
        params["freshness"] = freshness
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(
            BRAVE_URL,
            headers={"X-Subscription-Token": api_key, "Accept": "application/json"},
            params=params,
        )
        response.raise_for_status()
        payload = response.json()
    web = payload.get("web") or {}
    return [{"title": r.get("title", ""), "url": r.get("url", "")} for r in web.get("results", [])]


async def _run_search(
    provider: str, query: str, max_results: int, api_key: str, freshness: str
) -> list[dict]:
    if provider == "ddgs":
        return await _ddgs_search(query, max_results, DDGS_TIMELIMIT.get(freshness, ""))
    if provider == "tavily":
        return await _tavily_search(query, max_results, api_key, freshness)
    if provider == "serper":
        return await _serper_search(query, max_results, api_key, SERPER_TBQ.get(freshness, ""))
    return await _brave_search(query, max_results, api_key, BRAVE_FRESHNESS.get(freshness, ""))


async def search_web(
    query: str,
    max_results: int = 5,
    provider: str = "ddgs",
    api_key: str = "",
    freshness: str = "",
) -> dict:
    provider = (provider or "ddgs").strip().lower()
    query = (query or "").strip()
    freshness = normalize_freshness(freshness)
    if not query:
        return {"ok": False, "sources": [], "error": "Empty search query"}
    if provider not in {"tavily", "serper", "brave", "ddgs"}:
        return {"ok": False, "sources": [], "error": f"Unknown search provider: {provider}"}

    api_key = api_key.strip()
    if provider in {"tavily", "serper", "brave"}:
        env_names = {"tavily": "TAVILY_API_KEY", "serper": "SERPER_API_KEY", "brave": "BRAVE_API_KEY"}
        if not api_key:
            return {
                "ok": False,
                "sources": [],
                "error": f"Search misconfigured: {env_names[provider]} is not set",
            }

    try:
        raw = await _run_search(provider, query, max_results, api_key, freshness)
        if not raw and freshness:
            raw = await _run_search(provider, query, max_results, api_key, "")
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        if freshness:
            try:
                raw = await _run_search(provider, query, max_results, api_key, "")
            except Exception:
                return {"ok": False, "sources": [], "error": f"{provider}_http_{status}"}
        else:
            return {"ok": False, "sources": [], "error": f"{provider}_http_{status}"}
    except Exception as exc:
        return {"ok": False, "sources": [], "error": f"{provider}_failed: {type(exc).__name__}"}

    sources = [item for item in raw if str(item.get("url", "")).startswith(("http://", "https://"))]
    return {"ok": True, "sources": sources[:max_results], "error": ""}
