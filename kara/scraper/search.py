import asyncio
import os

import httpx

TAVILY_URL = "https://api.tavily.com/search"
SERPER_URL = "https://google.serper.dev/search"
BRAVE_URL = "https://api.search.brave.com/res/v1/web/search"


def _ddgs_search_sync(query: str, max_results: int) -> list[dict]:
    from ddgs import DDGS

    results = DDGS().text(query, max_results=max_results)
    return [{"title": r.get("title", ""), "url": r.get("href", "")} for r in results]


async def _ddgs_search(query: str, max_results: int) -> list[dict]:
    return await asyncio.wait_for(asyncio.to_thread(_ddgs_search_sync, query, max_results), timeout=20)


async def _tavily_search(query: str, max_results: int, api_key: str) -> list[dict]:
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            TAVILY_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json={"query": query, "max_results": max_results, "search_depth": "basic"},
        )
        response.raise_for_status()
        payload = response.json()
    return [{"title": r.get("title", ""), "url": r.get("url", "")} for r in payload.get("results", [])]


async def _serper_search(query: str, max_results: int, api_key: str) -> list[dict]:
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            SERPER_URL,
            headers={"X-API-KEY": api_key},
            json={"q": query, "num": max_results},
        )
        response.raise_for_status()
        payload = response.json()
    return [{"title": r.get("title", ""), "url": r.get("link", "")} for r in payload.get("organic", [])]


async def _brave_search(query: str, max_results: int, api_key: str) -> list[dict]:
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(
            BRAVE_URL,
            headers={"X-Subscription-Token": api_key, "Accept": "application/json"},
            params={"q": query, "count": max_results},
        )
        response.raise_for_status()
        payload = response.json()
    web = payload.get("web") or {}
    return [{"title": r.get("title", ""), "url": r.get("url", "")} for r in web.get("results", [])]


async def search_web(
    query: str,
    max_results: int = 5,
    provider: str = "ddgs",
    api_key: str = "",
) -> dict:
    provider = (provider or "ddgs").strip().lower()
    query = (query or "").strip()
    if not query:
        return {"ok": False, "sources": [], "error": "Empty search query"}
    if provider not in {"tavily", "serper", "brave", "ddgs"}:
        return {"ok": False, "sources": [], "error": f"Unknown search provider: {provider}"}

    try:
        if provider in {"tavily", "serper", "brave"}:
            env_names = {"tavily": "TAVILY_API_KEY", "serper": "SERPER_API_KEY", "brave": "BRAVE_API_KEY"}
            if not api_key.strip():
                return {
                    "ok": False,
                    "sources": [],
                    "error": f"Search misconfigured: {env_names[provider]} is not set",
                }
            if provider == "tavily":
                raw = await _tavily_search(query, max_results, api_key.strip())
            elif provider == "serper":
                raw = await _serper_search(query, max_results, api_key.strip())
            else:
                raw = await _brave_search(query, max_results, api_key.strip())
        else:
            raw = await _ddgs_search(query, max_results)
    except httpx.HTTPStatusError as exc:
        return {
            "ok": False,
            "sources": [],
            "error": f"{provider}_http_{exc.response.status_code}",
        }
    except Exception as exc:
        return {"ok": False, "sources": [], "error": f"{provider}_failed: {type(exc).__name__}"}

    sources = [item for item in raw if str(item.get("url", "")).startswith(("http://", "https://"))]
    return {"ok": True, "sources": sources[:max_results], "error": ""}
