from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kara.agent.tools import ToolRunner
from kara.config import Settings, get_settings
from kara.db import get_session
from kara.llm.factory import ResilientProvider, build_provider
from kara.models import User
from kara.scraper.yada import YadaClient
from kara.security import TokenError, decode_access_token

_bearer = HTTPBearer(auto_error=False)

_provider: ResilientProvider | None = None
_yada: YadaClient | None = None


def get_provider() -> ResilientProvider:
    global _provider
    if _provider is None:
        _provider = build_provider(get_settings())
    return _provider


def get_yada() -> YadaClient:
    global _yada
    if _yada is None:
        _yada = YadaClient(get_settings())
    return _yada


def reset_runtime_state() -> None:
    global _provider, _yada
    _provider = None
    _yada = None


def get_runner(
    yada: YadaClient = Depends(get_yada),
    settings: Settings = Depends(get_settings),
) -> ToolRunner:
    return ToolRunner(yada, max_sources=settings.max_sources_cap, search_enabled=settings.search_enabled)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> User | None:
    if credentials is None:
        return None
    try:
        user_id = decode_access_token(credentials.credentials, settings.jwt_secret)
    except TokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown user")
    return user


async def require_user(
    user: User | None = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> User | None:
    if settings.auth_required and user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return user


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"
