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

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        reasoning_effort: str | None = None,
    ) -> ChatReply:
        last_error: LLMError | None = None
        for provider in self._providers:
            try:
                reply = await provider.chat(messages, tools=tools, reasoning_effort=reasoning_effort)
                self._last_used = provider.name
                return reply
            except LLMError as exc:
                if not exc.retriable:
                    raise
                last_error = exc
        raise last_error or LLMError("All LLM providers failed", retriable=True)

    async def chat_stream(
        self, messages: list[dict], tools: list[dict] | None = None, on_text=None, reasoning_effort: str | None = None
    ) -> ChatReply:
        last_error: LLMError | None = None
        for provider in self._providers:
            emitted = False

            async def forward(text: str) -> None:
                nonlocal emitted
                emitted = True
                if on_text:
                    await on_text(text)

            try:
                reply = await provider.chat_stream(messages, tools=tools, on_text=forward, reasoning_effort=reasoning_effort)
                self._last_used = provider.name
                return reply
            except LLMError as exc:
                if emitted or not exc.retriable:
                    raise
                last_error = exc
        raise last_error or LLMError("All LLM providers failed", retriable=True)


def build_provider(settings: Settings) -> ResilientProvider:
    from kara.llm.providers import NIMProvider, OpenAICompatibleProvider

    configs: dict[str, tuple[str, str, str]] = {
        "groq": (settings.groq_api_key, settings.groq_model, "https://api.groq.com/openai/v1"),
        "openai": (settings.openai_api_key, settings.openai_model, "https://api.openai.com/v1"),
        "openrouter": (settings.openrouter_api_key, settings.openrouter_model, "https://openrouter.ai/api/v1"),
        "mistral": (settings.mistral_api_key, settings.mistral_model, "https://api.mistral.ai/v1"),
        "nim": (settings.nim_api_key, settings.nim_model, "https://integrate.api.nvidia.com/v1"),
    }

    providers: list[LLMProvider] = []
    for name in settings.llm_chain:
        entry = configs.get(name)
        if entry is None:
            continue
        api_key, model, base_url = entry
        if not api_key.strip():
            continue
        if name == "nim":
            providers.append(NIMProvider(api_key, model, settings.llm_timeout))
        else:
            providers.append(OpenAICompatibleProvider(name, api_key, model, base_url, settings.llm_timeout))

    return ResilientProvider(providers)
