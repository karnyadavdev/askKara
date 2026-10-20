import pytest

from kara.agent.summarize import FALLBACK_CHAR_LIMIT, summarize_texts
from kara.llm.base import ChatReply, LLMError, LLMProvider
from kara.texttrim import TRUNCATED_MARKER

QUESTION = "What are the rate limits?"


class ScriptedSummarizer(LLMProvider):
    name = "scripted"

    def __init__(self, outcomes):
        self._outcomes = list(outcomes)
        self.calls = []

    async def chat(self, messages, tools=None, reasoning_effort=None):
        self.calls.append({"messages": messages, "reasoning_effort": reasoning_effort})
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, LLMError):
            raise outcome
        return outcome


async def test_summary_uses_low_effort_and_caps_length():
    provider = ScriptedSummarizer([ChatReply(content="x" * 5000)])

    result = await summarize_texts(provider, QUESTION, ["page text"])

    assert result == ["x" * 1500]
    assert provider.calls[0]["reasoning_effort"] == "low"
    assert QUESTION in provider.calls[0]["messages"][0]["content"]


async def test_llm_error_falls_back_to_trimmed_text():
    long_text = "MIDDLE" + "y" * 40_000
    provider = ScriptedSummarizer([LLMError("boom", status_code=503, retriable=True)])

    result = await summarize_texts(provider, QUESTION, [long_text])

    assert len(result[0]) == FALLBACK_CHAR_LIMIT
    assert TRUNCATED_MARKER in result[0]


async def test_empty_summary_falls_back_to_trimmed_text():
    long_text = "y" * 20_000
    provider = ScriptedSummarizer([ChatReply(content="  ")])

    result = await summarize_texts(provider, QUESTION, [long_text])

    assert len(result[0]) == FALLBACK_CHAR_LIMIT


async def test_empty_text_stays_empty_without_llm_call():
    provider = ScriptedSummarizer([])

    result = await summarize_texts(provider, QUESTION, [""])

    assert result == [""]
    assert provider.calls == []


async def test_batch_preserves_order_and_count():
    provider = ScriptedSummarizer(
        [ChatReply(content="one"), ChatReply(content="two"), ChatReply(content="three")]
    )

    result = await summarize_texts(provider, QUESTION, ["a", "b", "c"])

    assert result == ["one", "two", "three"]
