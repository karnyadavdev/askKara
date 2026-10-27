from kara.agent.summarize import SUMMARIZE_INPUT_LIMIT, summarize_texts
from kara.llm.base import ChatReply, LLMError, LLMProvider
from kara.prompts import SUMMARIZE_CHAR_LIMIT, build_summarize_prompt
from kara.texttrim import CUT_MARKER, TRUNCATED_MARKER

QUESTION = "What are the rate limits?"
LONG_TEXT = "word " * 2000


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


async def test_short_page_passes_through_free():
    provider = ScriptedSummarizer([])

    result = await summarize_texts(provider, QUESTION, ["small page text"])

    assert result == ["small page text"]
    assert provider.calls == []


async def test_exact_cap_page_passes_through_free():
    provider = ScriptedSummarizer([])

    result = await summarize_texts(provider, QUESTION, ["x" * SUMMARIZE_CHAR_LIMIT])

    assert result == ["x" * SUMMARIZE_CHAR_LIMIT]
    assert provider.calls == []


async def test_summary_uses_low_effort_and_caps_length():
    provider = ScriptedSummarizer([ChatReply(content="x" * 9000)])

    result = await summarize_texts(provider, QUESTION, [LONG_TEXT])

    assert len(result[0]) == SUMMARIZE_CHAR_LIMIT
    assert result[0].endswith(CUT_MARKER)
    assert provider.calls[0]["reasoning_effort"] == "low"
    assert QUESTION in provider.calls[0]["messages"][0]["content"]


async def test_summary_cuts_at_word_boundary():
    provider = ScriptedSummarizer([ChatReply(content="rate limit " * 900)])

    result = await summarize_texts(provider, QUESTION, [LONG_TEXT])

    assert len(result[0]) <= SUMMARIZE_CHAR_LIMIT
    assert result[0].endswith(CUT_MARKER)
    body = result[0][: -len(CUT_MARKER)]
    assert body.endswith("limit")


async def test_short_summary_replaces_long_page():
    provider = ScriptedSummarizer([ChatReply(content="short digest")])

    result = await summarize_texts(provider, QUESTION, [LONG_TEXT])

    assert result == ["short digest"]


async def test_input_is_trimmed_before_prompting():
    long_text = "HEAD" + "y" * 80_000 + "TAIL"
    provider = ScriptedSummarizer([ChatReply(content="digest")])

    await summarize_texts(provider, QUESTION, [long_text])

    prompt = provider.calls[0]["messages"][0]["content"]
    assert TRUNCATED_MARKER in prompt
    assert "HEAD" in prompt
    assert "TAIL" in prompt
    assert len(prompt) - len(build_summarize_prompt(QUESTION, "")) <= SUMMARIZE_INPUT_LIMIT


async def test_llm_error_falls_back_to_trimmed_text_within_budget():
    long_text = "MIDDLE" + "y" * 40_000
    provider = ScriptedSummarizer([LLMError("boom", status_code=503, retriable=True)])

    result = await summarize_texts(provider, QUESTION, [long_text])

    assert len(result[0]) <= SUMMARIZE_CHAR_LIMIT
    assert TRUNCATED_MARKER in result[0]


async def test_empty_summary_falls_back_to_trimmed_text():
    long_text = "y" * 20_000
    provider = ScriptedSummarizer([ChatReply(content="  ")])

    result = await summarize_texts(provider, QUESTION, [long_text])

    assert len(result[0]) <= SUMMARIZE_CHAR_LIMIT


async def test_empty_text_stays_empty_without_llm_call():
    provider = ScriptedSummarizer([])

    result = await summarize_texts(provider, QUESTION, [""])

    assert result == [""]
    assert provider.calls == []


async def test_batch_preserves_order_and_mixes_free_and_digested():
    provider = ScriptedSummarizer([ChatReply(content="DIGESTED")])

    result = await summarize_texts(provider, QUESTION, ["a", LONG_TEXT, "c"])

    assert result == ["a", "DIGESTED", "c"]
    assert len(provider.calls) == 1


def test_digest_prompt_never_asks_for_rejection():
    prompt = build_summarize_prompt(QUESTION, "some page text")

    assert "INSUFFICIENT" not in prompt
    assert "insufficient" in prompt
    assert "6000" in prompt
    assert "[TRUNCATED]" in prompt
