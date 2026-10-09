import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


class LLMError(Exception):
    def __init__(self, message: str, status_code: int | None = None, retriable: bool = False):
        super().__init__(message)
        self.status_code = status_code
        self.retriable = retriable


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict = field(default_factory=dict)


@dataclass
class ChatReply:
    content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)


class LLMProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def chat(self, messages: list[dict], tools: list[dict] | None = None) -> ChatReply:
        raise NotImplementedError


RETRIABLE_STATUS = {429, 500, 502, 503, 504}


def parse_tool_arguments(raw) -> dict:
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {"value": parsed}
    except (json.JSONDecodeError, TypeError):
        return {"raw": str(raw)}
