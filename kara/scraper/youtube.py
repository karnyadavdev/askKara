import asyncio
import re

from kara.config import Settings


async def youtube_comments_extract(url: str, objective: str = "") -> dict:
    try:
        from playwright.async_api import async_playwright
    except Exception as exc:
        return {"ok": False, "text": "", "error": f"Playwright unavailable for YouTube extraction: {exc}"}

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1366, "height": 900},
            )
            page = await context.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            for _ in range(8):
                await page.mouse.wheel(0, 900)
                await page.wait_for_timeout(1200)
                count = await page.locator("ytd-comment-thread-renderer #content-text").count()
                if count >= 5:
                    break

            title = ""
            try:
                title = (await page.title()).strip()
            except Exception:
                pass

            comments = await page.evaluate(
                """() => Array.from(document.querySelectorAll('ytd-comment-thread-renderer')).slice(0, 40).map((node, index) => {
                    const author = node.querySelector('#author-text, #author-text span')?.innerText?.trim() || '';
                    const text = node.querySelector('#content-text')?.innerText?.trim() || '';
                    const time = node.querySelector('.published-time-text a, #published-time-text a')?.innerText?.trim() || '';
                    const likes = node.querySelector('#vote-count-middle')?.innerText?.trim() || '';
                    return { index: index + 1, author, text, time, likes };
                }).filter(item => item.text)"""
            )
            await browser.close()

        if not comments:
            return {"ok": False, "text": "", "error": "No YouTube comments rendered after scrolling."}

        lines = [
            f"YouTube page: {title or url}",
            f"Extraction objective: {objective or 'general page summary'}",
            "Visible comments:",
        ]
        for item in comments:
            meta = " ".join(part for part in [item.get("author"), item.get("time"), item.get("likes")] if part)
            lines.append(f"{item['index']}. {meta}: {item['text']}".strip())
        return {
            "ok": True,
            "title": title or "YouTube",
            "text": "\n".join(lines),
            "layer": "youtube_comments_playwright",
            "error": "",
        }
    except Exception as exc:
        return {"ok": False, "text": "", "error": str(exc)}


def wants_youtube_comments(url: str, objective: str) -> bool:
    return "youtube.com" in url.lower() and bool(re.search(r"\b(comment|comments|first|oldest|latest)\b", objective, re.I))


async def maybe_youtube(url: str, objective: str, settings: Settings) -> dict | None:
    if not settings.youtube_extract or not wants_youtube_comments(url, objective):
        return None
    result = await youtube_comments_extract(url, objective)
    if result.get("ok"):
        return result
    return None
