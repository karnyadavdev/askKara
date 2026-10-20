import pytest

from kara.config import Settings
from kara.llm.base import ChatReply, LLMError, LLMProvider
from kara.llm.factory import ResilientProvider, build_provider


class ScriptedProvider(LLMProvider):
    def __init__(self, name, outcomes):
        self.name = name
        self._outcomes = list(outcomes)
        self.calls = 0

    async def chat(self, messages, tools=None, reasoning_effort=None):
        self.calls += 1
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, LLMError):
            raise outcome
        return outcome


async def test_falls_through_on_retriable_error():
    bad = ScriptedProvider("bad", [LLMError("too many requests", status_code=429, retriable=True)])
    good = ScriptedProvider("good", [ChatReply(content="ok")])
    resilient = ResilientProvider([bad, good])

    reply = await resilient.chat([{"role": "user", "content": "hi"}])

    assert reply.content == "ok"
    assert good.calls == 1


async def test_non_retriable_error_stops_the_chain():
    bad = ScriptedProvider("bad", [LLMError("bad key", status_code=401)])
    good = ScriptedProvider("good", [ChatReply(content="ok")])
    resilient = ResilientProvider([bad, good])

    with pytest.raises(LLMError):
        await resilient.chat([{"role": "user", "content": "hi"}])
    assert good.calls == 0


async def test_all_retriable_failures_raise_last():
    bad = ScriptedProvider("bad", [LLMError("first", status_code=503, retriable=True)])
    worse = ScriptedProvider("worse", [LLMError("second", status_code=500, retriable=True)])
    resilient = ResilientProvider([bad, worse])

    with pytest.raises(LLMError, match="second"):
        await resilient.chat([{"role": "user", "content": "hi"}])


async def test_empty_chain_raises():
    with pytest.raises(LLMError):
        ResilientProvider([])


async def test_build_provider_skips_missing_keys():
    settings = Settings(groq_api_key="k")
    provider = build_provider(settings)
    assert provider.chain == ["groq"]


async def test_build_provider_without_keys_raises():
    with pytest.raises(LLMError):
        build_provider(Settings())
