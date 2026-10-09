import json

import httpx

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


class OpenAICompatibleProvider(LLMProvider):
    name = "openai-compatible"

    def __init__(self, name: str, api_key: str, model: str, base_url: str, timeout: float = 90.0):
        self.name = name
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    async def chat(self, messages: list[dict], tools: list[dict] | None = None) -> ChatReply:
        body: dict = {
            "model": self._model,
            "messages": openai_messages(messages),
            "temperature": 0.15,
        }
        if tools:
            body["tools"] = openai_tools(tools)
            body["tool_choice"] = "auto"

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    f"{self._base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json=body,
                )
        except httpx.HTTPError as exc:
            raise LLMError(f"{self.name}: network error: {exc}", retriable=True) from exc

        if resp.status_code == 401 or resp.status_code == 403:
            raise LLMError(f"{self.name}: auth failed", status_code=resp.status_code)
        if resp.status_code in RETRIABLE_STATUS:
            raise LLMError(f"{self.name}: HTTP {resp.status_code}", status_code=resp.status_code, retriable=True)
        if resp.status_code >= 400:
            raise LLMError(f"{self.name}: HTTP {resp.status_code}: {resp.text[:200]}", status_code=resp.status_code)

        return parse_openai_reply(resp.json())


class GroqProvider(OpenAICompatibleProvider):
    def __init__(self, api_key: str, model: str, timeout: float = 90.0):
        super().__init__("groq", api_key, model, "https://api.groq.com/openai/v1", timeout)


class OpenAIProvider(OpenAICompatibleProvider):
    def __init__(self, api_key: str, model: str, timeout: float = 90.0):
        super().__init__("openai", api_key, model, "https://api.openai.com/v1", timeout)
