from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kara.config import Settings, get_settings
from kara.db import get_session
from kara.deps import get_current_user
from kara.models import User
from kara.schemas import LoginIn, RegisterIn, TokenOut, UserOut
from kara.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _token_for(user: User, settings: Settings) -> TokenOut:
    token = create_access_token(user.id, settings.jwt_secret, settings.jwt_ttl_seconds)
    return TokenOut(access_token=token, user=UserOut(id=user.id, email=user.email))


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterIn,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> TokenOut:
    email = payload.email.strip().lower()
    existing = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    user = User(email=email, password_hash=hash_password(payload.password))
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return _token_for(user, settings)


@router.post("/login", response_model=TokenOut)
async def login(
    payload: LoginIn,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> TokenOut:
    email = payload.email.strip().lower()
    user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    return _token_for(user, settings)


@router.get("/me", response_model=UserOut)
async def me(user: User | None = Depends(get_current_user)) -> UserOut:
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return UserOut(id=user.id, email=user.email)
