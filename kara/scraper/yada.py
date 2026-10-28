import asyncio
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from kara.config import Settings
from kara.scraper.pageclean import page_to_text
from kara.texttrim import trim_head_tail


def html_to_text(html: str, base_url: str | None = None) -> str:
    return page_to_text(html, base_url=base_url)


_META_KEYS = {
    "published": (
        "article:published_time",
        "og:article:published_time",
        "datepublished",
        "date",
        "pubdate",
        "publishdate",
    ),
    "updated": (
        "article:modified_time",
        "og:updated_time",
        "datemodified",
        "last-modified",
    ),
    "author": (
        "author",
        "article:author",
        "citation_author",
        "parsely-author",
        "sailthru.author",
        "byl",
    ),
}
_META_VALUE_LIMIT = 120
_ARTICLE_TYPES = {
    "article",
    "newsarticle",
    "blogposting",
    "report",
    "techarticle",
    "scholarlyarticle",
    "opinionnewsarticle",
    "analysisnewsarticle",
    "reviewnewsarticle",
}


def _collapse_meta(text: str) -> str:
    return re.sub(r"\s+", " ", str(text)).strip()[:_META_VALUE_LIMIT]


def _author_name(value) -> str:
    if isinstance(value, str):
        return _collapse_meta(value)
    if isinstance(value, dict):
        return _author_name(value.get("name"))
    if isinstance(value, list):
        names = [_author_name(item) for item in value]
        return _collapse_meta(", ".join(name for name in names if name))
    return ""


def _jsonld_nodes(data):
    if isinstance(data, list):
        for item in data:
            yield from _jsonld_nodes(item)
    elif isinstance(data, dict):
        yield data
        graph = data.get("@graph")
        if isinstance(graph, list):
            for item in graph:
                yield from _jsonld_nodes(item)


def _jsonld_type(node: dict) -> set[str]:
    value = node.get("@type")
    items = value if isinstance(value, list) else [value]
    return {str(item).casefold() for item in items if item}


def _jsonld_url(node: dict) -> str:
    for key in ("url", "@id", "mainEntityOfPage"):
        value = node.get(key)
        if isinstance(value, dict):
            value = value.get("@id") or value.get("url")
        if isinstance(value, str):
            return value
    return ""


def _jsonld_meta(soup: BeautifulSoup, base_url: str = "") -> dict[str, str]:
    found: dict[str, str] = {}
    nodes: list[dict] = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            continue
        nodes.extend(node for node in _jsonld_nodes(data) if isinstance(node, dict))
    page = base_url.rstrip("/") if base_url else ""

    def matches_page(node: dict) -> bool:
        if not page:
            return False
        value = _jsonld_url(node).rstrip("/")
        return value == page or value.startswith((page + "/", page + "?"))

    def score(node: dict) -> int:
        is_article = _jsonld_type(node) & _ARTICLE_TYPES
        return (2 if is_article else 0) + (1 if matches_page(node) else 0)

    for node in sorted(nodes, key=score, reverse=True):
        for key in ("datePublished", "dateModified"):
            value = node.get(key)
            if isinstance(value, str) and value.strip():
                found.setdefault(key.casefold(), _collapse_meta(value))
        author = _author_name(node.get("author"))
        if author:
            found.setdefault("author", author)
    return found


def _meta_tags(soup: BeautifulSoup) -> dict[str, str]:
    found: dict[str, str] = {}
    for tag in soup.find_all("meta"):
        key = tag.get("property") or tag.get("name") or tag.get("itemprop")
        value = tag.get("content")
        if key and value:
            found.setdefault(str(key).strip().casefold(), _collapse_meta(value))
    return found


def _page_meta(soup: BeautifulSoup, base_url: str = "") -> str:
    jsonld = _jsonld_meta(soup, base_url)
    tags = _meta_tags(soup)

    def pick(field: str) -> str:
        if field == "published":
            value = jsonld.get("datepublished")
        elif field == "updated":
            value = jsonld.get("datemodified")
        else:
            value = jsonld.get("author")
        if value:
            return value
        for key in _META_KEYS[field]:
            value = tags.get(key)
            if value:
                return value
        return ""

    published = pick("published")
    updated = pick("updated")
    author = pick("author")
    if not published:
        for time_tag in soup.find_all("time"):
            value = time_tag.get("datetime") or time_tag.get_text(" ", strip=True)
            if value:
                published = _collapse_meta(value)
                break
    fields = []
    if published:
        fields.append(f"published {published}")
    if updated and updated != published:
        fields.append(f"updated {updated}")
    if author:
        fields.append(f"author {author}")
    if not fields:
        return ""
    return "[page info: " + " | ".join(fields) + "]"


def extract_payload(result: dict, base_url: str | None = None) -> tuple[str, str]:
    content = result.get("content") or {}
    html = ""
    fallback = ""
    if isinstance(content, dict):
        html = content.get("html") or ""
        for key in ("text", "markdown", "clean_text", "content"):
            value = content.get(key)
            if isinstance(value, str) and len(value) > len(fallback):
                fallback = value
    elif isinstance(content, str):
        html = content
    title = ""
    if html:
        soup = BeautifulSoup(html, "lxml")
        if soup.title and soup.title.string:
            title = soup.title.string.strip()
        base = base_url or str(result.get("url") or "")
        text = page_to_text(html, base_url=base or None)
        meta = _page_meta(soup, base)
        if meta:
            text = f"{meta}\n\n{text}".strip()
        return title, text
    return title, re.sub(r"\s+", " ", fallback).strip()


def yada_reason(data: dict) -> str:
    attempt = data.get("best_attempt")
    if isinstance(attempt, dict) and attempt.get("reason"):
        return str(attempt["reason"])
    return str(data.get("diagnosis") or "")


class YadaClient:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._engine = None
        self._import_failed: str | None = None

    def _load_engine(self):
        if self._engine is not None:
            return self._engine
        if self._import_failed:
            return None
        root = self._settings.yada_root.strip()
        if not root or not Path(root).exists():
            self._import_failed = f"YADA_ROOT not found: {root or '(unset)'}"
            return None
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        try:
            from scraper import ScraperEngine

            self._engine = ScraperEngine()
        except Exception as exc:
            self._import_failed = str(exc)
            return None
        return self._engine

    async def scrape(self, url: str) -> dict:
        mode = self._settings.yada_mode
        if mode == "off":
            return self._failure(url, "YADA disabled (YADA_MODE=off)")

        if mode == "http":
            return await self._scrape_http(url)

        return await self._scrape_import(url)

    async def _scrape_import(self, url: str) -> dict:
        engine = self._load_engine()
        if engine is None:
            return self._failure(url, f"YADA import unavailable: {self._import_failed}")

        try:
            result = await asyncio.wait_for(
                engine.scrape(url, mode="auto", allow_browser=False),
                timeout=self._settings.scrape_timeout,
            )
            data = result.to_dict()
            title, text = extract_payload(data, base_url=url)
            return self._build_result(url, data, title, text)
        except Exception as exc:
            return self._failure(url, str(exc))

    async def _scrape_http(self, url: str) -> dict:
        base = self._settings.yada_api_url.rstrip("/")
        headers = {}
        if self._settings.yada_api_key:
            headers["X-API-Key"] = self._settings.yada_api_key
        try:
            async with httpx.AsyncClient(timeout=self._settings.scrape_timeout) as client:
                resp = await client.post(
                    f"{base}/scrape",
                    json={"url": url, "mode": "auto", "allow_browser": False},
                    headers=headers,
                )
            if resp.status_code >= 400:
                return self._failure(url, f"YADA HTTP {resp.status_code}")
            data = resp.json()
        except Exception as exc:
            return self._failure(url, str(exc))

        title, text = extract_payload(data, base_url=url)
        return self._build_result(url, data, title, text)

    def _build_result(self, url: str, data: dict, title: str, text: str) -> dict:
        text = trim_head_tail(text, 100_000)
        ok = bool(data.get("success")) and bool(text.strip())
        if not ok and data.get("success"):
            return {
                "ok": False,
                "title": title or url,
                "url": url,
                "text": "",
                "layer": data.get("layer_used") or "none",
                "error": "no text content extracted from page",
                "reason": "YADA returned success but page yielded 0 characters of text",
            }
        return {
            "ok": ok,
            "title": title or url,
            "url": url,
            "text": text,
            "layer": data.get("layer_used") or "none",
            "error": data.get("error", ""),
            "reason": yada_reason(data),
        }

    @staticmethod
    def _failure(url: str, error: str) -> dict:
        return {
            "ok": False,
            "title": urlparse(url).netloc or url,
            "url": url,
            "text": "",
            "layer": "none",
            "error": error,
            "reason": error,
        }
