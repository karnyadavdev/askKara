import re

from kara.agent.summarize import summarize_texts
from kara.agent.tools import TOOL_SCHEMAS, ToolRunner, dumps, urls_in_text
from kara.llm.base import LLMError, LLMProvider
from kara.prompts import build_system_prompt


_CITATION_RE = re.compile(r"^\s*(?:\d+[.)]|[-*•]|\[\d+\])\s*\S|^https?://\S", re.IGNORECASE)


def _is_citation_line(line: str) -> bool:
    return bool(_CITATION_RE.match(line))


def clean_answer_text(text: str) -> str:
    text = (text or "").strip()
    text = text.replace("\u2011", "-").replace("\u202f", " ").replace("\xa0", " ")
    if not text:
        return text

    lines = text.splitlines()
    cut_at = None
    for i, line in enumerate(lines):
        clean = line.strip().strip("*_:- ").lower()
        if clean not in {"source", "sources", "references", "reference"}:
            continue
        rest = [ln for ln in lines[i + 1:] if ln.strip()]
        if rest and all(_is_citation_line(ln) for ln in rest):
            cut_at = i
    if cut_at is not None:
        text = "\n".join(lines[:cut_at]).strip()

    return text


def needs_page_or_current_data(text: str) -> bool:
    q = text.lower()
    return bool(
        urls_in_text(text)
        or re.search(r"\b(latest|current|today|now|as of|price|followers|comments?|post|page|website|source|news)\b", q)
    )


async def run_agent(
    question: str,
    *,
    provider: LLMProvider,
    runner: ToolRunner,
    max_sources: int = 8,
    max_steps: int = 8,
    on_event=None,
    summarize: bool = False,
    history: list[dict] | None = None,
) -> dict:
    system = build_system_prompt(max_sources=max_sources)
    messages: list[dict] = [{"role": "system", "content": system}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": question})
    used_sources: list[dict] = []
    scraped_urls: set[str] = set()
    tool_trace: list[dict] = []
    round_text: list[str] = []

    async def emit(payload: dict):
        if on_event:
            await on_event(payload)

    async def on_token(text: str) -> None:
        round_text.append(text)

    async def flush_step() -> None:
        text = "".join(round_text).strip()
        round_text.clear()
        if text:
            await emit({"type": "step", "text": text})

    await emit({"type": "stage", "stage": "researching", "message": "Researching..."})

    for i in range(max_steps):
        round_text.clear()
        if i > 0:
            await emit({"type": "stage", "stage": "composing", "message": "Composing answer..."})
        try:
            reply = await provider.chat_stream(messages, tools=TOOL_SCHEMAS, on_text=on_token)
        except LLMError:
            raise

        if reply.tool_calls:
            await flush_step()

        if not reply.tool_calls:
            answer = clean_answer_text(reply.content or "")
            if not used_sources:
                if answer and not tool_trace and not needs_page_or_current_data(question):
                    return {"answer": answer, "sources": [], "tool_trace": tool_trace, "provider": provider.name}
                if tool_trace:
                    return {
                        "answer": answer or "I could not produce an answer from the available tool results.",
                        "sources": [],
                        "tool_trace": tool_trace,
                        "provider": provider.name,
                    }
                messages.append({"role": "assistant", "content": reply.content})
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "Decide whether this question needs web/page data. If it does, call web_search "
                            "or yada_scrape_many. If it is general knowledge, answer directly."
                        ),
                    }
                )
                await flush_step()
                continue
            return {
                "answer": answer or "No final answer was returned.",
                "sources": used_sources[:max_sources],
                "tool_trace": tool_trace,
                "provider": provider.name,
            }

        messages.append(
            {
                "role": "assistant",
                "content": reply.content,
                "tool_calls": [
                    {"id": call.id, "name": call.name, "arguments": call.arguments} for call in reply.tool_calls
                ],
            }
        )

        for call in reply.tool_calls:
            if call.name == "web_search":
                await emit({"type": "stage", "stage": "searching", "message": "Searching for sources..."})
            elif call.name == "yada_scrape":
                await emit({"type": "stage", "stage": "fetching", "message": "Fetching source page..."})
            elif call.name == "yada_scrape_many":
                await emit({"type": "stage", "stage": "fetching", "message": "Fetching source pages..."})

            if call.name == "yada_scrape":
                url = str(call.arguments.get("url") or "").strip()
                if url in scraped_urls:
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call.id,
                            "name": call.name,
                            "content": dumps({"ok": True, "already_scraped": True, "url": url, "text": "Already scraped. Use the data from the earlier tool result. Do not scrape this URL again."}),
                        }
                    )
                    tool_trace.append({"tool": call.name, "args": call.arguments, "ok": True, "skipped": True})
                    continue

            name, response = await runner.execute(call.name, call.arguments)
            tool_trace.append({"tool": name, "args": call.arguments, "ok": response.get("ok", True)})

            if summarize and name in {"yada_scrape", "yada_scrape_many"}:
                await emit({"type": "stage", "stage": "digesting", "message": "Digesting sources..."})
                if name == "yada_scrape":
                    response["text"] = (await summarize_texts(provider, question, [response.get("text") or ""]))[0]
                else:
                    results = response.get("results") or []
                    summaries = await summarize_texts(
                        provider, question, [item.get("text") or "" for item in results]
                    )
                    for item, summary in zip(results, summaries):
                        item["text"] = summary

            if name == "yada_scrape" and response.get("ok"):
                url = response.get("url") or ""
                scraped_urls.add(url)
                used_sources.append(
                    {
                        "title": response.get("title") or response.get("url"),
                        "url": response.get("url"),
                        "text": response.get("text") or "",
                        "layer": response.get("layer") or "none",
                    }
                )
            elif name == "yada_scrape_many" and response.get("ok"):
                for source in response.get("results", []):
                    if not source.get("ok"):
                        continue
                    url = source.get("url") or ""
                    if url in scraped_urls:
                        continue
                    scraped_urls.add(url)
                    used_sources.append(
                        {
                            "title": source.get("title") or source.get("url"),
                            "url": source.get("url"),
                            "text": source.get("text") or "",
                            "layer": source.get("layer") or "none",
                        }
                    )

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "name": name,
                    "content": dumps(response),
                }
            )

    return {
        "answer": "I hit the research step limit before producing a final answer.",
        "sources": used_sources[:max_sources],
        "tool_trace": tool_trace,
        "provider": provider.name,
    }
