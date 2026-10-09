import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from kara.agent.loop import run_agent
from kara.agent.tools import ToolRunner
from kara.config import Settings, get_settings
from kara.db import get_session
from kara.deps import client_ip, get_provider, get_runner, require_user
from kara.limiter import SlidingWindowLimiter
from kara.llm.base import LLMError, LLMProvider
from kara.models import QueryRecord, User
from kara.schemas import AskRequest

router = APIRouter(tags=["ask"])

_rate_limiter = SlidingWindowLimiter(max_hits=15, window_seconds=300.0)


def reset_rate_limiter() -> None:
    _rate_limiter.reset()


def _line(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False) + "\n"


@router.post("/api/ask/stream")
async def ask_stream(
    payload: AskRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    provider: LLMProvider = Depends(get_provider),
    runner: ToolRunner = Depends(get_runner),
    user: User | None = Depends(require_user),
):
    question = (payload.question or "").strip()
    if not question:
        raise HTTPException(status_code=422, detail="question is required")
    if len(question) > 4000:
        raise HTTPException(status_code=422, detail="question too long")

    allowed, retry_after = _rate_limiter.check(client_ip(request))
    if not allowed:
        return JSONResponse(
            {"detail": "Rate limit exceeded"},
            status_code=429,
            headers={"Retry-After": str(int(retry_after) + 1)},
        )

    max_sources = max(1, min(int(payload.max_sources or 8), settings.max_sources_cap))
    user_id = user.id if user is not None else None

    async def events():
        queue: asyncio.Queue[dict] = asyncio.Queue()

        async def on_event(event_payload: dict) -> None:
            await queue.put(event_payload)

        task = asyncio.create_task(
            run_agent(
                question,
                provider=provider,
                runner=runner,
                max_sources=max_sources,
                max_steps=settings.max_steps,
                on_event=on_event,
            )
        )

        while True:
            if task.done():
                while not queue.empty():
                    yield _line(queue.get_nowait())
                try:
                    result = task.result()
                except LLMError as exc:
                    if exc.status_code == 429:
                        yield _line({"type": "error", "message": "rate_limited", "retryable": True})
                    else:
                        yield _line({"type": "error", "message": str(exc)[:300], "retryable": bool(exc.retriable)})
                    return
                except Exception:
                    yield _line({"type": "error", "message": "Internal research error", "retryable": False})
                    return

                sources = [
                    {"title": source.get("title") or source.get("url"), "url": source.get("url")}
                    for source in result.get("sources", [])
                ]
                yield _line({"type": "sources", "sources": sources})
                yield _line(
                    {
                        "type": "done",
                        "answer": result.get("answer") or "",
                        "sources": sources,
                        "provider": result.get("provider") or "",
                    }
                )
                session.add(
                    QueryRecord(
                        user_id=user_id,
                        question=question,
                        answer=(result.get("answer") or "")[:20000],
                        sources_json=json.dumps(sources, ensure_ascii=False),
                        provider=result.get("provider") or "",
                    )
                )
                await session.commit()
                return

            try:
                event = await asyncio.wait_for(queue.get(), timeout=0.25)
            except asyncio.TimeoutError:
                continue
            if event.get("type") == "stage":
                yield _line(event)

    return StreamingResponse(events(), media_type="application/x-ndjson")
