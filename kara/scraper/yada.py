import asyncio
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from kara.config import Settings
from kara.scraper.youtube import maybe_youtube


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html or "", "lxml")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    return re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()


def extract_payload(result: dict) -> tuple[str, str]:
    content = result.get("content") or {}
    html = ""
    text = ""
    if isinstance(content, dict):
        html = content.get("html") or ""
        for key in ("text", "markdown", "clean_text", "content"):
            value = content.get(key)
            if isinstance(value, str) and len(value) > len(text):
                text = value
    elif isinstance(content, str):
        html = content
    if not text:
        text = html_to_text(html)
    title = ""
    if html:
        soup = BeautifulSoup(html, "lxml")
        if soup.title and soup.title.string:
            title = soup.title.string.strip()
    return title, re.sub(r"\s+", " ", text).strip()


def bad_page(title: str, text: str) -> bool:
    head = f"{title} {text[:1200]}".lower()
    return (
        "page not found" in head
        or "404" in (title or "").lower()
        or "access denied" in head
        or "robot or human" in head
        or "pardon our interruption" in head
    )


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

    async def scrape(self, url: str, objective: str = "") -> dict:
        mode = self._settings.yada_mode
        if mode == "off":
            return self._failure(url, "YADA disabled (YADA_MODE=off)")

        if mode == "http":
            return await self._scrape_http(url)

        return await self._scrape_import(url, objective)

    async def _scrape_import(self, url: str, objective: str) -> dict:
        yt = await maybe_youtube(url, objective, self._settings)
        if yt is not None:
            return {
                "ok": True,
                "title": yt.get("title") or url,
                "url": url,
                "text": yt.get("text", "")[:14000],
                "layer": yt.get("layer") or "youtube_comments_playwright",
                "error": "",
            }

        engine = self._load_engine()
        if engine is None:
            return self._failure(url, f"YADA import unavailable: {self._import_failed}")

        try:
            result = await asyncio.wait_for(
                engine.scrape(url, mode="auto", allow_browser=False),
                timeout=self._settings.scrape_timeout,
            )
            data = result.to_dict()
            title, text = extract_payload(data)
            text = text[:14000]
            ok = bool(data.get("success")) and len(text) > 350 and not bad_page(title, text)
            return {
                "ok": ok,
                "title": title or url,
                "url": url,
                "text": text,
                "layer": data.get("layer_used") or "none",
                "error": data.get("error", ""),
            }
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

        title, text = extract_payload(data)
        text = text[:14000]
        ok = bool(data.get("success")) and len(text) > 350 and not bad_page(title, text)
        return {
            "ok": ok,
            "title": title or url,
            "url": url,
            "text": text,
            "layer": data.get("layer_used") or "none",
            "error": data.get("error", ""),
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
        }
