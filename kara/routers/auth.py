import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kara.config import Settings, get_settings
from kara.db import get_session
from kara.deps import client_ip, get_current_user
from kara.limiter import SlidingWindowLimiter
from kara.models import User
from kara.schemas import LoginIn, RegisterIn, TokenOut, UserOut
from kara.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])

_auth_limiter = SlidingWindowLimiter(max_hits=10, window_seconds=300.0)


def reset_auth_limiter() -> None:
    _auth_limiter.reset()


def _token_for(user: User, settings: Settings) -> TokenOut:
    token = create_access_token(user.id, settings.jwt_secret, settings.jwt_ttl_seconds)
    return TokenOut(access_token=token, user=UserOut(id=user.id, email=user.email))


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
    return UserOut(id=user.id, email=user.email)
