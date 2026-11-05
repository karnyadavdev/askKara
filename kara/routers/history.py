import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kara.config import Settings, get_settings
from kara.db import get_session
from kara.deps import get_current_user, user_from_token
from kara.models import Conversation, QueryRecord, User
from kara.schemas import TokenIn

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


async def _conversations_for(user: User, session: AsyncSession) -> dict:
    rows = (
        (
            await session.execute(
                select(Conversation)
                .where(Conversation.user_id == user.id)
                .order_by(Conversation.updated_at.desc())
                .limit(50)
            )
        )
        .scalars()
        .all()
    )

    return {
        "items": [
            {
                "id": conversation.id,
                "title": conversation.title,
                "updated_at": conversation.updated_at.isoformat() if conversation.updated_at else "",
            }
            for conversation in rows
        ]
    }


async def _turns_for(user: User, conversation_id: int, session: AsyncSession) -> dict:
    conversation = await session.get(Conversation, conversation_id)
    if conversation is None or conversation.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    records = (
        (
            await session.execute(
                select(QueryRecord)
                .where(QueryRecord.conversation_id == conversation.id)
                .order_by(QueryRecord.id.asc())
            )
        )
        .scalars()
        .all()
    )

    return {
        "items": [
            {
                "id": record.id,
                "question": record.question,
                "answer": record.answer,
                "sources": json.loads(record.sources_json or "[]"),
                "provider": record.provider,
                "created_at": record.created_at.isoformat() if record.created_at else "",
            }
            for record in records
        ]
    }


@router.get("")
async def conversations(
    session: AsyncSession = Depends(get_session),
    user: User | None = Depends(get_current_user),
) -> dict:
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return await _conversations_for(user, session)


@router.post("")
async def conversations_from_body(
    payload: TokenIn,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    user = await user_from_token(payload.token, session, settings)
    return await _conversations_for(user, session)


@router.get("/{conversation_id}")
async def conversation_turns(
    conversation_id: int,
    session: AsyncSession = Depends(get_session),
    user: User | None = Depends(get_current_user),
) -> dict:
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return await _turns_for(user, conversation_id, session)


@router.post("/{conversation_id}")
async def conversation_turns_from_body(
    conversation_id: int,
    payload: TokenIn,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    user = await user_from_token(payload.token, session, settings)
    return await _turns_for(user, conversation_id, session)
