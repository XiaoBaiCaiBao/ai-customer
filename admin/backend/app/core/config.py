from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ADMIN_BACKEND_DIR = Path(__file__).resolve().parents[2]
_PATH_PARENTS = Path(__file__).resolve().parents
REPO_ROOT = _PATH_PARENTS[4] if len(_PATH_PARENTS) > 4 else ADMIN_BACKEND_DIR


class Settings(BaseSettings):
    ADMIN_MONGODB_URL: str = "mongodb://localhost:27017"
    ADMIN_MONGODB_DB: str = "ai_customer_admin"
    ADMIN_CORS_ORIGINS: str = "http://localhost:5174"

    LLM_API_KEY: str = ""
    EMBEDDING_MODEL: str = "doubao-embedding-vision-251215"
    EMBEDDING_BASE_URL: str = "https://ark.cn-beijing.volces.com/api/v3/embeddings/multimodal"
    EMBEDDING_TIMEOUT_SECONDS: float = 20.0

    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_COLLECTION: str = "knowledge_base"
    RAG_MIN_SCORE: float = 0.3

    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / "backend" / ".env", ADMIN_BACKEND_DIR / ".env"),
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.ADMIN_CORS_ORIGINS.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
