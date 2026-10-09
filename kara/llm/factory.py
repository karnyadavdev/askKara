from kara.config import Settings
from kara.llm.base import ChatReply, LLMError, LLMProvider


class ResilientProvider(LLMProvider):
    name = "resilient"

    def __init__(self, providers: list[LLMProvider]):
        if not providers:
            raise LLMError("No LLM providers are configured")
        self._providers = providers

    @property
    def chain(self) -> list[str]:
        return [p.name for p in self._providers]

    @property
    def last_used(self) -> str | None:
        return getattr(self, "_last_used", None)

    async def chat(self, messages: list[dict], tools: list[dict] | None = None) -> ChatReply:
        last_error: LLMError | None = None
        for provider in self._providers:
            try:
                reply = await provider.chat(messages, tools=tools)
                self._last_used = provider.name
                return reply
            except LLMError as exc:
                if not exc.retriable:
                    raise
                last_error = exc
        raise last_error or LLMError("All LLM providers failed", retriable=True)


def build_provider(settings: Settings) -> ResilientProvider:
    from kara.llm.groq import GroqProvider, OpenAIProvider

    makers = {
        "groq": lambda: GroqProvider(settings.groq_api_key, settings.groq_model, settings.llm_timeout),
        "openai": lambda: OpenAIProvider(settings.openai_api_key, settings.openai_model, settings.llm_timeout),
    }
    available_keys = {
        "groq": settings.groq_api_key,
        "openai": settings.openai_api_key,
    }

    providers: list[LLMProvider] = []
    for name in settings.llm_chain:
        if not available_keys.get(name, "").strip():
            continue
        maker = makers.get(name)
        if maker is None:
            continue
        providers.append(maker())

    return ResilientProvider(providers)
