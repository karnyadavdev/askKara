from kara.agent.loop import clean_answer_text, needs_page_or_current_data, run_agent
from kara.llm.base import ChatReply, LLMProvider, ToolCall

from fakes import FakeProvider


class FakeRunner:
    def __init__(self):
        self.calls = []

    async def execute(self, name, args):
        self.calls.append((name, args))
        if name == "yada_scrape":
            return name, {
                "ok": True,
                "title": "Example",
                "url": args.get("url"),
                "text": "useful page text",
                "layer": "fake",
                "error": "",
            }
        return name, {"ok": True, "sources": []}


class AlwaysToolProvider(LLMProvider):
    name = "loop"

    async def chat(self, messages, tools=None):
        call_count = sum(1 for m in messages if m.get("role") == "assistant")
        return ChatReply(
            tool_calls=[ToolCall(id=f"call_{call_count}", name="yada_scrape", arguments={"url": f"https://x.dev/{call_count}"})]
        )


async def test_direct_answer_for_general_question():
    provider = FakeProvider([ChatReply(content="Paris is the capital.")])
    events: list[dict] = []

    async def on_event(payload):
        events.append(payload)

    result = await run_agent(
        "What is the capital of France?",
        provider=provider,
        runner=FakeRunner(),
        max_sources=5,
        on_event=on_event,
    )

    assert result["answer"] == "Paris is the capital."
    assert result["sources"] == []
    assert any(event["type"] == "stage" for event in events)


async def test_tool_call_path_collects_sources_and_stages():
    provider = FakeProvider(
        [
            ChatReply(tool_calls=[ToolCall(id="c1", name="yada_scrape", arguments={"url": "https://example.com"})]),
            ChatReply(content="Composed answer [1]."),
        ]
    )
    events: list[dict] = []

    async def on_event(payload):
        events.append(payload)

    result = await run_agent(
        "Summarize https://example.com",
        provider=provider,
        runner=FakeRunner(),
        max_sources=5,
        on_event=on_event,
    )

    assert result["answer"] == "Composed answer [1]."
    assert result["sources"][0]["url"] == "https://example.com"
    stages = [event.get("stage") for event in events]
    assert "fetching" in stages and "composing" in stages


async def test_step_limit_returns_honest_answer():
    result = await run_agent(
        "keep looping",
        provider=AlwaysToolProvider(),
        runner=FakeRunner(),
        max_sources=5,
        max_steps=3,
    )

    assert result["answer"] == "I hit the research step limit before producing a final answer."
    assert len(result["sources"]) == 3


async def test_provider_error_propagates():
    from kara.llm.base import LLMError

    provider = FakeProvider([LLMError("groq: HTTP 429", status_code=429, retriable=True)])
    import pytest

    with pytest.raises(LLMError):
        await run_agent("hi", provider=provider, runner=FakeRunner())


def test_clean_answer_text_strips_sources_footer():
    text = "Real answer [1].\n\nSources:\n1. https://example.com"
    assert clean_answer_text(text) == "Real answer [1]."


def test_clean_answer_text_keeps_plain_answer():
    assert clean_answer_text("  Just an answer.  ") == "Just an answer."


def test_clean_answer_text_normalizes_exotic_hyphens():
    assert clean_answer_text("Retrieval\u2011augmented") == "Retrieval-augmented"


def test_needs_page_or_current_data():
    assert needs_page_or_current_data("What is the price today?")
    assert needs_page_or_current_data("check https://example.com")
    assert not needs_page_or_current_data("Explain quicksort")
