import asyncio

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kara.avatars import (
    ALLOWED_CONTENT_TYPES,
    MAX_UPLOAD_BYTES,
    AvatarError,
    AvatarStore,
    get_avatar_store,
    process_avatar,
)
from kara.config import Settings, get_settings
from kara.db import get_session
from kara.deps import client_ip, get_current_user, user_from_token
from kara.limiter import SlidingWindowLimiter
from kara.models import User
from kara.schemas import LoginIn, ProfileIn, RegisterIn, TokenIn, TokenOut, UserOut
from kara.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])

_auth_limiter = SlidingWindowLimiter(max_hits=10, window_seconds=300.0)


def reset_auth_limiter() -> None:
    _auth_limiter.reset()


def _user_out(user: User) -> UserOut:
    avatar_url = f"/api/avatars/{user.id}" if user.avatar_key else None
    return UserOut(id=user.id, email=user.email, name=user.display_name, avatar_url=avatar_url)


def _token_for(user: User, settings: Settings) -> TokenOut:
    token = create_access_token(user.id, settings.jwt_secret, settings.jwt_ttl_seconds)
    return TokenOut(access_token=token, user=_user_out(user))


def _check_auth_rate(request: Request) -> None:
    allowed, retry_after = _auth_limiter.check(client_ip(request))
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts",
            headers={"Retry-After": str(int(retry_after) + 1)},
        )


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> TokenOut:
    _check_auth_rate(request)
    email = payload.email.strip().lower()
    existing = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    password_hash = await asyncio.to_thread(hash_password, payload.password)
    user = User(email=email, password_hash=password_hash)
    session.add(user)
    try:
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    await session.refresh(user)
    return _token_for(user, settings)


@router.post("/login", response_model=TokenOut)
async def login(
    payload: LoginIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> TokenOut:
    _check_auth_rate(request)
    email = payload.email.strip().lower()
    user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is None or not await asyncio.to_thread(verify_password, payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    return _token_for(user, settings)


@router.get("/me", response_model=UserOut)
async def me(user: User | None = Depends(get_current_user)) -> UserOut:
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return _user_out(user)


@router.post("/me", response_model=UserOut)
async def me_from_body(
    payload: TokenIn,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> UserOut:
    user = await user_from_token(payload.token, session, settings)
    return _user_out(user)


@router.patch("/me", response_model=UserOut)
async def update_profile(
    payload: ProfileIn,
    user: User | None = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> UserOut:
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    user.display_name = payload.name
    await session.commit()
    return _user_out(user)


@router.post("/avatar", response_model=UserOut)
async def upload_avatar(
    file: UploadFile = File(...),
    user: User | None = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    store: AvatarStore | None = Depends(get_avatar_store),
) -> UserOut:
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    if store is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Avatars not configured")
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Use a JPG, PNG, or WebP image")

    raw = bytearray()
    while chunk := await file.read(64 * 1024):
        raw.extend(chunk)
        if len(raw) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Image is over 2 MB")
    if not raw:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file")

    try:
        jpeg = await asyncio.to_thread(process_avatar, bytes(raw))
    except AvatarError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    key = f"avatars/{user.id}.jpg"
    await store.upload(key, jpeg, "image/jpeg")
    user.avatar_key = key
    await session.commit()
    return _user_out(user)
