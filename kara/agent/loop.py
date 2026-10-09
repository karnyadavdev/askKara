import re

from kara.agent.tools import TOOL_SCHEMAS, ToolRunner, dumps, urls_in_text
from kara.llm.base import LLMError, LLMProvider
from kara.prompts import build_system_prompt


def clean_answer_text(text: str) -> str:
    text = (text or "").strip()
    text = text.replace("\u2011", "-").replace("\u202f", " ").replace("\xa0", " ")
    if not text:
        return text

    lines = text.splitlines()
    cut_at = None
    for i, line in enumerate(lines):
        clean = line.strip().strip("*_:- ").lower()
        if clean in {"source", "sources", "references", "reference"}:
            cut_at = i
            break
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
) -> dict:
    system = build_system_prompt(max_sources=max_sources)
    messages: list[dict] = [{"role": "system", "content": system}, {"role": "user", "content": question}]
    used_sources: list[dict] = []
    tool_trace: list[dict] = []

    async def emit(payload: dict):
        if on_event:
            await on_event(payload)

    for _ in range(max_steps):
        await emit({"type": "stage", "stage": "initializing", "message": "Initializing research..."})
        try:
            reply = await provider.chat(messages, tools=TOOL_SCHEMAS)
        except LLMError:
            raise

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
                            "Decide whether this question needs web/page data. If it does, call google_search "
                            "or yada_scrape_many. If it is general knowledge, answer directly."
                        ),
                    }
                )
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
            if call.name == "google_search":
                await emit({"type": "stage", "stage": "searching", "message": "Searching for sources..."})
            elif call.name == "yada_scrape":
                await emit({"type": "stage", "stage": "fetching", "message": "Fetching source page..."})
            elif call.name == "yada_scrape_many":
                await emit({"type": "stage", "stage": "fetching", "message": "Fetching source pages..."})

            name, response = await runner.execute(call.name, call.arguments)
            tool_trace.append({"tool": name, "args": call.arguments, "ok": response.get("ok", True)})

            if name == "yada_scrape" and response.get("ok"):
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

        await emit({"type": "stage", "stage": "composing", "message": "Composing answer..."})

    return {
        "answer": "I hit the research step limit before producing a final answer.",
        "sources": used_sources[:max_sources],
        "tool_trace": tool_trace,
        "provider": provider.name,
    }
