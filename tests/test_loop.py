from kara.agent.loop import clean_answer_text, needs_page_or_current_data, run_agent
from kara.llm.base import ChatReply, LLMProvider, ToolCall

from fakes import FakeProvider, FakeStreamProvider


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

    async def chat(self, messages, tools=None, reasoning_effort=None):
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


async def test_stage_labels_never_rewind_and_narration_becomes_a_step():
    provider = FakeStreamProvider(
        [
            ChatReply(
                content="need the page first",
                tool_calls=[ToolCall(id="c1", name="yada_scrape", arguments={"url": "https://example.com"})],
            ),
            ChatReply(content="Composed answer [1]."),
        ]
    )
    events: list[dict] = []

    async def on_event(payload):
        events.append(payload)

    await run_agent(
        "Summarize https://example.com",
        provider=provider,
        runner=FakeRunner(),
        max_sources=5,
        max_steps=3,
        on_event=on_event,
    )

    types = [event["type"] for event in events]
    assert "stream_reset" not in types
    assert "token" in types

    researching = [event for event in events if event["type"] == "stage" and event["stage"] == "researching"]
    assert len(researching) == 1

    steps = [event["text"] for event in events if event["type"] == "step"]
    assert steps == ["need the page first"]

    stages = [event["stage"] for event in events if event["type"] == "stage"]
    assert stages[0] == "researching"
    assert "fetching" in stages
    assert "composing" in stages
    assert "initializing" not in stages


async def test_summarize_replaces_scraped_text_with_digest():
    provider = FakeStreamProvider(
        [
            ChatReply(
                tool_calls=[ToolCall(id="c1", name="yada_scrape", arguments={"url": "https://example.com"})]
            ),
            ChatReply(content="DIGESTED PAGE TEXT with facts"),
            ChatReply(content="Composed answer [1]."),
        ]
    )

    class LongRunner(FakeRunner):
        async def execute(self, name, args):
            name, response = await super().execute(name, args)
            if name == "yada_scrape":
                response["text"] = "word " * 2000
            return name, response

    result = await run_agent(
        "Summarize https://example.com",
        provider=provider,
        runner=LongRunner(),
        max_sources=5,
        summarize=True,
    )

    assert result["answer"] == "Composed answer [1]."
    assert result["sources"][0]["text"] == "DIGESTED PAGE TEXT with facts"


async def test_summarize_passes_short_pages_through_free():
    provider = FakeStreamProvider(
        [
            ChatReply(
                tool_calls=[ToolCall(id="c1", name="yada_scrape", arguments={"url": "https://example.com"})]
            ),
            ChatReply(content="Composed answer [1]."),
        ]
    )

    result = await run_agent(
        "Summarize https://example.com",
        provider=provider,
        runner=FakeRunner(),
        max_sources=5,
        summarize=True,
    )

    assert result["answer"] == "Composed answer [1]."
    assert result["sources"][0]["text"] == "useful page text"


async def test_summarize_digests_failed_scrape_shell():
    provider = FakeStreamProvider(
        [
            ChatReply(
                tool_calls=[ToolCall(id="c1", name="yada_scrape", arguments={"url": "https://flaky.dev"})]
            ),
            ChatReply(content="DIGESTED FAILED SHELL"),
            ChatReply(content="Composed answer [1]."),
        ]
    )

    class FailedShellRunner(FakeRunner):
        async def execute(self, name, args):
            name, response = await super().execute(name, args)
            if name == "yada_scrape":
                response["ok"] = False
                response["text"] = "partial shell " * 1000
            return name, response

    result = await run_agent(
        "Summarize https://flaky.dev",
        provider=provider,
        runner=FailedShellRunner(),
        max_sources=5,
        summarize=True,
    )

    assert result["answer"] == "Composed answer [1]."
    tool_messages = [
        m for m in provider.calls[-1]
        if m.get("role") == "tool" and "DIGESTED FAILED SHELL" in m.get("content", "")
    ]
    assert tool_messages


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


async def test_source_cap_stops_scraping_and_reports_limit():
    provider = FakeProvider(
        [
            ChatReply(tool_calls=[ToolCall(id="c1", name="yada_scrape", arguments={"url": "https://a.dev"})]),
            ChatReply(tool_calls=[ToolCall(id="c2", name="yada_scrape", arguments={"url": "https://b.dev"})]),
            ChatReply(tool_calls=[ToolCall(id="c3", name="yada_scrape", arguments={"url": "https://c.dev"})]),
            ChatReply(content="Composed answer [1][2]."),
        ]
    )
    runner = FakeRunner()

    result = await run_agent("compare a b c", provider=provider, runner=runner, max_sources=2)

    assert len(result["sources"]) == 2
    fetched = [args.get("url") for _, args in runner.calls]
    assert "https://c.dev" not in fetched
    refused = [
        m for m in provider.calls[-1]
        if m.get("role") == "tool" and "Source limit reached" in m.get("content", "")
    ]
    assert refused


async def test_successful_url_is_locked_and_not_refetched():
    provider = FakeProvider(
        [
            ChatReply(tool_calls=[ToolCall(id="c1", name="yada_scrape", arguments={"url": "https://a.dev"})]),
            ChatReply(tool_calls=[ToolCall(id="c2", name="yada_scrape", arguments={"url": "https://a.dev"})]),
            ChatReply(content="Composed answer [1]."),
        ]
    )
    runner = FakeRunner()

    result = await run_agent("summarize a", provider=provider, runner=runner, max_sources=5)

    assert len(runner.calls) == 1
    assert len(result["sources"]) == 1
    locked = [
        m for m in provider.calls[-1]
        if m.get("role") == "tool" and "Already scraped" in m.get("content", "")
    ]
    assert locked


async def test_failing_url_gets_three_attempts_then_stops():
    class FailRunner(FakeRunner):
        async def execute(self, name, args):
            self.calls.append((name, args))
            return name, {"ok": False, "url": args.get("url"), "text": "", "error": "boom"}

    provider = FakeProvider(
        [
            ChatReply(tool_calls=[ToolCall(id="c1", name="yada_scrape", arguments={"url": "https://flaky.dev"})]),
            ChatReply(tool_calls=[ToolCall(id="c2", name="yada_scrape", arguments={"url": "https://flaky.dev"})]),
            ChatReply(tool_calls=[ToolCall(id="c3", name="yada_scrape", arguments={"url": "https://flaky.dev"})]),
            ChatReply(tool_calls=[ToolCall(id="c4", name="yada_scrape", arguments={"url": "https://flaky.dev"})]),
            ChatReply(content="Could not fetch it."),
        ]
    )
    runner = FailRunner()

    await run_agent("fetch flaky", provider=provider, runner=runner, max_sources=5)

    assert len(runner.calls) == 3
    refused = [
        m for m in provider.calls[-1]
        if m.get("role") == "tool" and "failed three times" in m.get("content", "")
    ]
    assert refused


async def test_scrape_many_prefilters_already_scraped_urls():
    class MixedRunner(FakeRunner):
        async def execute(self, name, args):
            self.calls.append((name, args))
            if name == "yada_scrape_many":
                results = []
                for url in args.get("urls", []):
                    ok = "bad" not in url
                    results.append(
                        {"ok": ok, "title": url, "url": url, "text": "text" if ok else "", "layer": "fake", "error": "" if ok else "boom"}
                    )
                return name, {"ok": any(r["ok"] for r in results), "results": results}
            return await super().execute(name, args)

    provider = FakeProvider(
        [
            ChatReply(tool_calls=[ToolCall(id="c1", name="yada_scrape_many", arguments={"urls": ["https://good.dev", "https://bad.dev"]})]),
            ChatReply(tool_calls=[ToolCall(id="c2", name="yada_scrape_many", arguments={"urls": ["https://good.dev", "https://bad.dev"]})]),
            ChatReply(content="Composed answer [1]."),
        ]
    )
    runner = MixedRunner()

    await run_agent("compare good and bad", provider=provider, runner=runner, max_sources=10)

    many_calls = [args for name, args in runner.calls if name == "yada_scrape_many"]
    assert many_calls[0]["urls"] == ["https://good.dev", "https://bad.dev"]
    assert many_calls[1]["urls"] == ["https://bad.dev"]


async def test_run_agent_passes_reasoning_effort_to_provider():
    provider = FakeStreamProvider([ChatReply(content="Answer [1].")])

    await run_agent("hi", provider=provider, runner=FakeRunner(), reasoning_effort="high")

    assert provider.efforts == ["high"]


async def test_max_effort_falls_back_to_high_on_timeout():
    from kara.llm.base import LLMError

    provider = FakeStreamProvider(
        [
            LLMError("nim: network error: timed out", retriable=True),
            ChatReply(content="Answer after fallback [1]."),
        ]
    )

    result = await run_agent("hi", provider=provider, runner=FakeRunner(), reasoning_effort="max")

    assert result["answer"] == "Answer after fallback [1]."
    assert provider.efforts == ["max", "high"]


async def test_max_effort_falls_back_to_high_on_504():
    from kara.llm.base import LLMError

    provider = FakeStreamProvider(
        [
            LLMError("nim: HTTP 504", status_code=504, retriable=True),
            ChatReply(content="Answer after fallback [1]."),
        ]
    )

    await run_agent("hi", provider=provider, runner=FakeRunner(), reasoning_effort="max")

    assert provider.efforts == ["max", "high"]


async def test_lower_effort_timeout_raises_without_fallback():
    import pytest
    from kara.llm.base import LLMError

    provider = FakeStreamProvider([LLMError("nim: network error: timed out", retriable=True)])

    with pytest.raises(LLMError):
        await run_agent("hi", provider=provider, runner=FakeRunner(), reasoning_effort="low")

    assert provider.efforts == ["low"]
