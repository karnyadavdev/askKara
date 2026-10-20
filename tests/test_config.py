from kara.config import Settings


def test_defaults():
    settings = Settings()
    assert settings.database_url.startswith("sqlite")
    assert settings.llm_chain == ("groq",)
    assert settings.max_sources_cap == 10
    assert settings.auth_required is False


def test_llm_ready_requires_a_chain_key():
    assert Settings(groq_api_key="k").llm_ready is True
    assert Settings(llm_chain=("groq", "openai"), openai_api_key="k").llm_ready is True
    assert Settings().llm_ready is False


def test_yada_ready_modes():
    assert Settings(yada_mode="off").yada_ready is False
    assert Settings(yada_mode="http", yada_api_url="http://yada:8000").yada_ready is True
    assert Settings(yada_mode="http").yada_ready is False
    assert Settings(yada_mode="import", yada_root="/tmp/yada").yada_ready is True
    assert Settings(yada_mode="import").yada_ready is False
