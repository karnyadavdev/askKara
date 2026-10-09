from kara.llm.base import ChatReply, LLMError, LLMProvider, ToolCall


class FakeProvider(LLMProvider):
    name = "fake"

    def __init__(self, replies):
        self._replies = list(replies)
        self.calls = []

    async def chat(self, messages, tools=None):
        self.calls.append([dict(message) for message in messages])
        if not self._replies:
            return ChatReply(content="fallback answer")
        reply = self._replies.pop(0)
        if isinstance(reply, LLMError):
            raise reply
        return reply


class FakeYada:
    def __init__(self):
        self.calls = []

    async def scrape(self, url, objective=""):
        self.calls.append(url)
        return {
            "ok": True,
            "title": f"Title for {url}",
            "url": url,
            "text": "page text " * 100,
            "layer": "fake",
            "error": "",
        }


__all__ = ["ChatReply", "FakeProvider", "FakeYada", "LLMError", "ToolCall"]
