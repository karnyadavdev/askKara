from kara.llm.base import ChatReply, LLMError, LLMProvider, ToolCall


class FakeProvider(LLMProvider):
    name = "fake"

    def __init__(self, replies):
        self._replies = list(replies)
        self.calls = []
        self.efforts = []

    async def chat(self, messages, tools=None, reasoning_effort=None):
        self.calls.append([dict(message) for message in messages])
        self.efforts.append(reasoning_effort)
        if not self._replies:
            return ChatReply(content="fallback answer")
        reply = self._replies.pop(0)
        if isinstance(reply, LLMError):
            raise reply
        return reply


class FakeStreamProvider(FakeProvider):
    async def chat_stream(self, messages, tools=None, on_text=None, reasoning_effort=None):
        reply = await self.chat(messages, tools=tools, reasoning_effort=reasoning_effort)
        if reply.content and on_text:
            words = reply.content.split(" ")
            for i, word in enumerate(words):
                await on_text(word if i == 0 else f" {word}")
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


__all__ = ["ChatReply", "FakeProvider", "FakeStreamProvider", "FakeYada", "LLMError", "ToolCall"]
