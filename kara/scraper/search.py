import asyncio
from urllib.parse import quote


def fallback_sources(question: str) -> list[dict]:
    q = question.lower()
    if "retrieval augmented generation" in q or "rag" in q.split():
        return [
            {"title": "IBM: RAG", "url": "https://www.ibm.com/think/topics/retrieval-augmented-generation"},
            {"title": "AWS: RAG", "url": "https://aws.amazon.com/what-is/retrieval-augmented-generation/"},
            {"title": "NVIDIA: RAG", "url": "https://www.nvidia.com/en-us/glossary/retrieval-augmented-generation/"},
        ]
    if "web scraping" in q or "scraper" in q:
        return [
            {"title": "Wikipedia: Web scraping", "url": "https://en.wikipedia.org/wiki/Web_scraping"},
            {"title": "MDN: Fetch API", "url": "https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API"},
            {"title": "Requests docs", "url": "https://requests.readthedocs.io/en/latest/"},
        ]
    return [
        {"title": "Wikipedia", "url": f"https://en.wikipedia.org/w/index.php?search={quote(question)}"},
        {"title": "Google Patents", "url": f"https://patents.google.com/?q=({quote(question)})"},
    ]


def _search_sync(query: str, max_results: int) -> list[dict]:
    from ddgs import DDGS

    results = DDGS().text(query, max_results=max_results)
    return [{"title": r.get("title", ""), "url": r.get("href", "")} for r in results]


async def search_web(query: str, max_results: int = 5) -> list[dict]:
    try:
        raw = await asyncio.wait_for(asyncio.to_thread(_search_sync, query, max_results), timeout=20)
    except Exception:
        raw = []
    sources = [item for item in raw if item.get("url", "").startswith(("http://", "https://"))]
    if not sources:
        sources = fallback_sources(query)[:max_results]
    return sources[:max_results]
