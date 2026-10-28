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

    llm_chain: tuple[str, ...] = ("groq",)
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openrouter_api_key: str = ""
    openrouter_model: str = "nvidia/nemotron-3-ultra-550b-a55b:free"
    mistral_api_key: str = ""
    mistral_model: str = "ministral-14b-latest"
    nim_api_key: str = ""
    nim_model: str = "nvidia/nemotron-3-ultra-550b-a55b"
    llm_timeout: float = 300.0

    yada_mode: str = "import"
    yada_root: str = ""
    yada_api_url: str = ""
    yada_api_key: str = ""
    scrape_timeout: float = 100.0

    search_enabled: bool = True
    search_provider: str = "ddgs"
    tavily_api_key: str = ""
    serper_api_key: str = ""
    brave_api_key: str = ""
    trust_proxy: bool = False
    max_steps: int = 12
    max_sources_cap: int = 10
    deep_max_steps: int = 20
    deep_max_sources: int = 35
    deep_batch_cap: int = 25
    deep_rate_hits: int = 3
    summarize_sources: bool = True
    normal_reasoning_effort: str = "low"
    deep_reasoning_effort: str = "high"

    host: str = "127.0.0.1"
    port: int = 4177

    extra: dict = field(default_factory=dict, compare=False)

    @property
    def llm_ready(self) -> bool:
        keys = {
            "groq": self.groq_api_key,
            "openai": self.openai_api_key,
            "openrouter": self.openrouter_api_key,
            "mistral": self.mistral_api_key,
            "nim": self.nim_api_key,
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

    chain_raw = os.getenv("KARA_LLM_CHAIN", "groq")
    chain = tuple(p.strip().lower() for p in chain_raw.split(",") if p.strip())

    return Settings(
        database_url=os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./kara.db").strip(),
        auto_create_tables=_truthy("KARA_AUTO_CREATE_TABLES"),
        auth_required=_truthy("KARA_AUTH_REQUIRED", "0"),
        jwt_secret=jwt_secret,
        jwt_ttl_seconds=int(os.getenv("KARA_JWT_TTL", "86400")),
        llm_chain=chain or ("groq",),
        groq_api_key=os.getenv("GROQ_API_KEY", "").strip(),
        groq_model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b").strip(),
        openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip(),
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY", "").strip(),
        openrouter_model=os.getenv("OPENROUTER_MODEL", "nvidia/nemotron-3-ultra-550b-a55b:free").strip(),
        mistral_api_key=os.getenv("MISTRAL_API_KEY", "").strip(),
        mistral_model=os.getenv("MISTRAL_MODEL", "ministral-14b-latest").strip(),
        nim_api_key=os.getenv("NIM_API_KEY", "").strip(),
        nim_model=os.getenv("NIM_MODEL", "nvidia/nemotron-3-ultra-550b-a55b").strip(),
        llm_timeout=float(os.getenv("KARA_LLM_TIMEOUT", "300")),
        yada_mode=os.getenv("YADA_MODE", "import").strip().lower(),
        yada_root=os.getenv("YADA_ROOT", "").strip(),
        yada_api_url=os.getenv("YADA_API_URL", "").strip(),
        yada_api_key=os.getenv("YADA_API_KEY", "").strip(),
        scrape_timeout=float(os.getenv("KARA_SCRAPE_TIMEOUT", "100")),
        search_enabled=_truthy("KARA_SEARCH_ENABLED"),
        search_provider=os.getenv("KARA_SEARCH_PROVIDER", "ddgs").strip().lower(),
        tavily_api_key=os.getenv("TAVILY_API_KEY", "").strip(),
        serper_api_key=os.getenv("SERPER_API_KEY", "").strip(),
        brave_api_key=os.getenv("BRAVE_API_KEY", "").strip(),
        trust_proxy=_truthy("KARA_TRUST_PROXY", "0"),
        max_steps=int(os.getenv("KARA_MAX_STEPS", "12")),
        max_sources_cap=int(os.getenv("KARA_MAX_SOURCES_CAP", "10")),
        deep_max_steps=int(os.getenv("KARA_DEEP_MAX_STEPS", "20")),
        deep_max_sources=int(os.getenv("KARA_DEEP_MAX_SOURCES", "35")),
        deep_batch_cap=int(os.getenv("KARA_DEEP_BATCH_CAP", "25")),
        deep_rate_hits=int(os.getenv("KARA_DEEP_RATE_HITS", "3")),
        summarize_sources=_truthy("KARA_SUMMARIZE"),
        normal_reasoning_effort=os.getenv("KARA_NORMAL_REASONING_EFFORT", "low").strip().lower(),
        deep_reasoning_effort=os.getenv("KARA_DEEP_REASONING_EFFORT", "high").strip().lower(),
        host=os.getenv("KARA_HOST", "127.0.0.1").strip(),
        port=int(os.getenv("KARA_PORT", "4177")),
    )
