from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost:5432/axiom"
    DATABASE_URL_SYNC: str = "postgresql://user:password@localhost:5432/axiom"

    GROQ_API_KEY: str = ""
    GROQ_MODEL_STRONG: str = "llama-3.3-70b-versatile"
    GROQ_MODEL_FAST: str = "llama-3.1-8b-instant"
    GROQ_MODEL_VISION: str = "llama-3.2-11b-vision-preview"

    PRISMTRACE_HOST: str = "https://prism-api-prod.up.railway.app"
    PRISMTRACE_PROJECT_ID: str = ""
    PRISMTRACE_API_KEY: str = ""

    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
