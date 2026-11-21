from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kara.avatars import AvatarStore, get_avatar_store
from kara.db import get_session
from kara.models import User

router = APIRouter(prefix="/api", tags=["avatars"])


@router.get("/avatars/{user_id}")
async def get_avatar(
    user_id: int,
    session: AsyncSession = Depends(get_session),
    store: AvatarStore | None = Depends(get_avatar_store),
) -> RedirectResponse:
    user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None or not user.avatar_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No avatar")
    if store is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Avatars not configured")
    url = await store.signed_url(user.avatar_key)
    return RedirectResponse(url, status_code=status.HTTP_302_FOUND, headers={"Cache-Control": "public, max-age=3600"})
