import asyncio
import json

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError,
    PermissionDeniedError,
)

from kara.llm.base import (
    RETRIABLE_STATUS,
    ChatReply,
    LLMError,
    LLMProvider,
    ToolCall,
    parse_tool_arguments,
)


def openai_messages(messages: list[dict]) -> list[dict]:
    out = []
    for message in messages:
        role = message.get("role")
        if role == "system":
            out.append({"role": "system", "content": message.get("content") or ""})
        elif role == "user":
            out.append({"role": "user", "content": message.get("content") or ""})
        elif role == "assistant":
            item: dict = {"role": "assistant", "content": message.get("content")}
            calls = message.get("tool_calls") or []
            if calls:
                item["tool_calls"] = [
                    {
                        "id": call.get("id") or f"call_{i}",
                        "type": "function",
                        "function": {
                            "name": call.get("name"),
                            "arguments": json.dumps(call.get("arguments") or {}, ensure_ascii=False),
                        },
                    }
                    for i, call in enumerate(calls)
                ]
            out.append(item)
        elif role == "tool":
            out.append(
                {
                    "role": "tool",
                    "tool_call_id": message.get("tool_call_id") or "",
                    "content": message.get("content") or "",
                }
            )
    return out


def openai_tools(tools: list[dict]) -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": tool.get("parameters") or {"type": "object", "properties": {}},
            },
        }
        for tool in tools
    ]


def parse_openai_reply(data: dict) -> ChatReply:
    choices = data.get("choices") or []
    if not choices:
        return ChatReply(content=None, tool_calls=[])
    message = choices[0].get("message") or {}
    calls = []
    for i, call in enumerate(message.get("tool_calls") or []):
        fn = call.get("function") or {}
        calls.append(
            ToolCall(
                id=call.get("id") or f"call_{i}",
                name=fn.get("name") or "",
                arguments=parse_tool_arguments(fn.get("arguments")),
            )
        )
    content = message.get("content")
    return ChatReply(content=content if isinstance(content, str) else None, tool_calls=calls)


def map_openai_error(name: str, exc: Exception) -> LLMError:
    if isinstance(exc, (AuthenticationError, PermissionDeniedError)):
        return LLMError(f"{name}: auth failed", status_code=exc.status_code)
    if isinstance(exc, APIStatusError):
        if exc.status_code in RETRIABLE_STATUS:
            return LLMError(f"{name}: HTTP {exc.status_code}", status_code=exc.status_code, retriable=True)
        return LLMError(f"{name}: HTTP {exc.status_code}", status_code=exc.status_code)
    if isinstance(exc, (APIConnectionError, APITimeoutError)):
        return LLMError(f"{name}: network error: {exc}", retriable=True)
    return LLMError(f"{name}: request failed")


class OpenAICompatibleProvider(LLMProvider):
    name = "openai-compatible"

    def __init__(
        self,
        name: str,
        api_key: str,
        model: str,
        base_url: str,
        timeout: float = 90.0,
        max_retries: int = 3,
        backoff_base: float = 1.0,
    ):
        self.name = name
        self._model = model
        self._max_retries = max_retries
        self._backoff_base = backoff_base
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=timeout, max_retries=0)

    def _base_body(self, messages, tools=None, stream=False, reasoning_effort=None) -> dict:
        body: dict = {
            "model": self._model,
            "messages": openai_messages(messages),
            "temperature": 0.15,
        }
        if self._model.startswith("qwen/"):
            body["reasoning_effort"] = "low"
        if reasoning_effort:
            body["reasoning_effort"] = reasoning_effort
        if tools:
            body["tools"] = openai_tools(tools)
            body["tool_choice"] = "auto"
        if stream:
            body["stream"] = True
        return body

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        reasoning_effort: str | None = None,
    ) -> ChatReply:
        body = self._base_body(messages, tools, reasoning_effort=reasoning_effort)
        last_error: LLMError | None = None
        for attempt in range(self._max_retries):
            try:
                resp = await self._client.chat.completions.create(**body)
                return parse_openai_reply(resp.model_dump())
            except Exception as exc:
                error = map_openai_error(self.name, exc)
                if not error.retriable or attempt == self._max_retries - 1:
                    raise error from exc
                last_error = error
                await asyncio.sleep(self._backoff_base ** attempt)
        raise last_error

    async def chat_stream(
        self, messages: list[dict], tools: list[dict] | None = None, on_text=None, reasoning_effort: str | None = None
    ) -> ChatReply:
        body = self._base_body(messages, tools, stream=True, reasoning_effort=reasoning_effort)
        last_error: LLMError | None = None
        for attempt in range(self._max_retries):
            content_parts: list[str] = []
            calls: dict[int, dict] = {}
            emitted = False

            async def forward(text: str) -> None:
                nonlocal emitted
                emitted = True
                content_parts.append(text)
                if on_text:
                    await on_text(text)

            try:
                stream = await self._client.chat.completions.create(**body)
                async for chunk in stream:
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta
                    if delta.content:
                        text = delta.content if isinstance(delta.content, str) else str(delta.content)
                        await forward(text)
                    for frag in delta.tool_calls or []:
                        slot = calls.setdefault(frag.index, {"id": "", "name": "", "arguments": ""})
                        if frag.id:
                            slot["id"] = frag.id
                        if frag.function and frag.function.name:
                            slot["name"] = frag.function.name
                        if frag.function and frag.function.arguments:
                            args = frag.function.arguments
                            slot["arguments"] += args if isinstance(args, str) else str(args)
                tool_calls = [
                    ToolCall(
                        id=slot["id"] or f"call_{i}",
                        name=slot["name"],
                        arguments=parse_tool_arguments(slot["arguments"] or None),
                    )
                    for i, (_, slot) in enumerate(sorted(calls.items()))
                ]
                content = "".join(content_parts)
                return ChatReply(content=content if content else None, tool_calls=tool_calls)
            except Exception as exc:
                error = map_openai_error(self.name, exc)
                if emitted or not error.retriable or attempt == self._max_retries - 1:
                    raise error from exc
                last_error = error
                await asyncio.sleep(self._backoff_base ** attempt)
        raise last_error


class NIMProvider(OpenAICompatibleProvider):
    def __init__(self, api_key: str, model: str, timeout: float = 90.0, max_retries: int = 2, backoff_base: float = 1.5):
        super().__init__("nim", api_key, model, "https://integrate.api.nvidia.com/v1", timeout, max_retries, backoff_base)
