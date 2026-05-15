from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    ADMIN_MONGODB_URL: str = "mongodb://localhost:27017"
    ADMIN_MONGODB_DB: str = "ai_customer_admin"
    ADMIN_CORS_ORIGINS: str = "http://localhost:5174"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.ADMIN_CORS_ORIGINS.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
