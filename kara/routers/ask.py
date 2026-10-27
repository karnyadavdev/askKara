import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kara.agent.loop import run_agent
from kara.config import Settings, get_settings
from kara.db import get_session
from kara.deps import build_runner, client_ip, get_provider, get_yada, require_user
from kara.limiter import SlidingWindowLimiter
from kara.llm.base import LLMError, LLMProvider
from kara.models import Conversation, QueryRecord, User, utcnow
from kara.schemas import AskRequest
from kara.scraper.yada import YadaClient

router = APIRouter(tags=["ask"])

_rate_limiter = SlidingWindowLimiter(max_hits=15, window_seconds=300.0)
_deep_limiter = SlidingWindowLimiter(max_hits=3, window_seconds=300.0)

CONTEXT_TURNS = 10
CONTEXT_QUESTION_CHARS = 2000
CONTEXT_ANSWER_CHARS = 2000


def reset_rate_limiter() -> None:
    _rate_limiter.reset()
    _deep_limiter.reset()


def _line(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False) + "\n"


@router.post("/api/ask/stream")
async def ask_stream(
    payload: AskRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    provider: LLMProvider = Depends(get_provider),
    yada: YadaClient = Depends(get_yada),
    user: User | None = Depends(require_user),
):
    question = (payload.question or "").strip()
    if not question:
        raise HTTPException(status_code=422, detail="question is required")
    if len(question) > 4000:
        raise HTTPException(status_code=422, detail="question too long")

    limiter = _deep_limiter if payload.deep else _rate_limiter
    allowed, retry_after = limiter.check(client_ip(request))
    if not allowed:
        return JSONResponse(
            {"detail": "Rate limit exceeded"},
            status_code=429,
            headers={"Retry-After": str(int(retry_after) + 1)},
        )

    conversation: Conversation | None = None
    if payload.conversation_id is not None:
        conversation = await session.get(Conversation, payload.conversation_id)
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        if user is not None and conversation.user_id != user.id:
            raise HTTPException(status_code=404, detail="Conversation not found")
        if user is None and conversation.user_id is not None:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        title = " ".join(question.split())[:60] or "Untitled"
        conversation = Conversation(user_id=user.id if user is not None else None, title=title)
        session.add(conversation)
        await session.flush()

    prior = (
        await session.execute(
            select(QueryRecord)
            .where(QueryRecord.conversation_id == conversation.id)
            .order_by(QueryRecord.id.desc())
            .limit(CONTEXT_TURNS)
        )
    ).scalars().all()
    history: list[dict] = []
    for record in reversed(prior):
        history.append({"role": "user", "content": (record.question or "")[:CONTEXT_QUESTION_CHARS]})
        if record.answer:
            history.append({"role": "assistant", "content": record.answer[:CONTEXT_ANSWER_CHARS]})

    summarize = payload.deep and settings.summarize_sources
    runner = build_runner(settings, yada, deep=payload.deep, summarize=summarize)
    if payload.deep:
        max_sources = max(1, min(int(payload.max_sources or settings.deep_max_sources), settings.deep_max_sources))
        max_steps = settings.deep_max_steps
    else:
        max_sources = max(1, min(int(payload.max_sources or 10), settings.max_sources_cap))
        max_steps = settings.max_steps
    effort = settings.deep_reasoning_effort if payload.deep else settings.normal_reasoning_effort
    user_id = user.id if user is not None else None

    async def events():
        yield _line({"type": "conversation", "id": conversation.id})
        queue: asyncio.Queue[dict] = asyncio.Queue()

        async def on_event(event_payload: dict) -> None:
            await queue.put(event_payload)

        task = asyncio.create_task(
            run_agent(
                question,
                provider=provider,
                runner=runner,
                max_sources=max_sources,
                max_steps=max_steps,
                on_event=on_event,
                summarize=summarize,
                history=history,
                reasoning_effort=effort,
            )
        )

        try:
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
                    session.add(
                        QueryRecord(
                            user_id=user_id,
                            conversation_id=conversation.id,
                            question=question,
                            answer=(result.get("answer") or "")[:20000],
                            sources_json=json.dumps(sources, ensure_ascii=False),
                            provider=result.get("provider") or "",
                        )
                    )
                    conversation.updated_at = utcnow()
                    try:
                        await session.commit()
                    except Exception:
                        await session.rollback()
                        yield _line({"type": "error", "message": "save_failed", "retryable": False})
                        return
                    yield _line({"type": "sources", "sources": sources})
                    yield _line(
                        {
                            "type": "done",
                            "answer": result.get("answer") or "",
                            "sources": sources,
                            "provider": result.get("provider") or "",
                        }
                    )
                    return

                try:
                    event = await asyncio.wait_for(queue.get(), timeout=0.25)
                except asyncio.TimeoutError:
                    continue
                if event.get("type") in {"stage", "token", "step"}:
                    yield _line(event)
        finally:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    return StreamingResponse(
        events(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )
