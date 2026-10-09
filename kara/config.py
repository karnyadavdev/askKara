import os
import secrets
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent

load_dotenv(ROOT / ".env", override=True)


def _truthy(name: str, default: str = "1") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    database_url: str = "sqlite+aiosqlite:///./kara.db"
    auto_create_tables: bool = True

    auth_required: bool = False
    jwt_secret: str = ""
    jwt_ttl_seconds: int = 86400

    llm_chain: tuple[str, ...] = ("groq", "openai")
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    llm_timeout: float = 90.0

    yada_mode: str = "import"
    yada_root: str = ""
    yada_api_url: str = ""
    yada_api_key: str = ""
    scrape_timeout: float = 100.0
    youtube_extract: bool = True

    search_enabled: bool = True
    max_steps: int = 8
    max_sources_cap: int = 10

    host: str = "127.0.0.1"
    port: int = 4177

    extra: dict = field(default_factory=dict, compare=False)

    @property
    def llm_ready(self) -> bool:
        keys = {
            "groq": self.groq_api_key,
            "openai": self.openai_api_key,
        }
        return any(keys.get(name, "").strip() for name in self.llm_chain)

    @property
    def yada_ready(self) -> bool:
        if self.yada_mode == "off":
            return False
        if self.yada_mode == "http":
            return bool(self.yada_api_url.strip())
        return bool(self.yada_root.strip())


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    jwt_secret = os.getenv("KARA_JWT_SECRET", "").strip()
    if not jwt_secret:
        jwt_secret = secrets.token_hex(32)

    chain_raw = os.getenv("KARA_LLM_CHAIN", "groq,openai")
    chain = tuple(p.strip().lower() for p in chain_raw.split(",") if p.strip())

    return Settings(
        database_url=os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./kara.db").strip(),
        auto_create_tables=_truthy("KARA_AUTO_CREATE_TABLES"),
        auth_required=_truthy("KARA_AUTH_REQUIRED", "0"),
        jwt_secret=jwt_secret,
        jwt_ttl_seconds=int(os.getenv("KARA_JWT_TTL", "86400")),
        llm_chain=chain or ("groq", "openai"),
        groq_api_key=os.getenv("GROQ_API_KEY", "").strip(),
        groq_model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b").strip(),
        openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip(),
        llm_timeout=float(os.getenv("KARA_LLM_TIMEOUT", "90")),
        yada_mode=os.getenv("YADA_MODE", "import").strip().lower(),
        yada_root=os.getenv("YADA_ROOT", "").strip(),
        yada_api_url=os.getenv("YADA_API_URL", "").strip(),
        yada_api_key=os.getenv("YADA_API_KEY", "").strip(),
        scrape_timeout=float(os.getenv("KARA_SCRAPE_TIMEOUT", "100")),
        youtube_extract=_truthy("KARA_YOUTUBE_EXTRACT"),
        search_enabled=_truthy("KARA_SEARCH_ENABLED"),
        max_steps=int(os.getenv("KARA_MAX_STEPS", "8")),
        max_sources_cap=int(os.getenv("KARA_MAX_SOURCES_CAP", "10")),
        host=os.getenv("KARA_HOST", "127.0.0.1").strip(),
        port=int(os.getenv("KARA_PORT", "4177")),
    )
