from fastapi import APIRouter, Depends

from kara.config import Settings, get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
@router.get("/api/health")
async def health(settings: Settings = Depends(get_settings)) -> dict:
    return {
        "status": "ok",
        "llm_ready": settings.llm_ready,
        "llm_chain": list(settings.llm_chain),
        "yada_ready": settings.yada_ready,
        "yada_mode": settings.yada_mode,
        "auth_required": settings.auth_required,
        "search_enabled": settings.search_enabled,
        "search_provider": settings.search_provider,
    }
