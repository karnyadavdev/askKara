import asyncio

from kara.llm.base import LLMError, LLMProvider
from kara.prompts import SUMMARIZE_CHAR_LIMIT, build_summarize_prompt
from kara.texttrim import trim_head_tail

FALLBACK_CHAR_LIMIT = 15_000
CONCURRENCY = 6


async def _summarize_one(
    provider: LLMProvider,
    question: str,
    text: str,
    semaphore: asyncio.Semaphore,
) -> str:
    if not text:
        return text
    async with semaphore:
        try:
            reply = await provider.chat(
                [{"role": "user", "content": build_summarize_prompt(question, text)}],
                reasoning_effort="low",
            )
        except LLMError:
            return trim_head_tail(text, FALLBACK_CHAR_LIMIT)
    summary = (reply.content or "").strip()
    if not summary:
        return trim_head_tail(text, FALLBACK_CHAR_LIMIT)
    return summary[:SUMMARIZE_CHAR_LIMIT]


async def summarize_texts(provider: LLMProvider, question: str, texts: list[str]) -> list[str]:
    semaphore = asyncio.Semaphore(CONCURRENCY)
    return list(
        await asyncio.gather(
            *(_summarize_one(provider, question, text, semaphore) for text in texts)
        )
    )
