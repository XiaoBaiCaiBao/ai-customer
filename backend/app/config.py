from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    # LLM — 改这里切换任意 OpenAI 兼容模型
    LLM_MODEL: str = "gpt-4o"
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = ""  # 留空则使用 OpenAI 官方地址

    EMBEDDING_MODEL: str = "doubao-embedding-vision-251215"
    # multimodal embedding 专用端点（与 LLM_BASE_URL 独立）
    EMBEDDING_BASE_URL: str = "https://ark.cn-beijing.volces.com/api/v3/embeddings/multimodal"

    # RAG provider
    RAG_PROVIDER: str = "qdrant"  # qdrant | volcengine_kb

    # Qdrant
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_COLLECTION: str = "knowledge_base"

    # Volcengine Knowledge Base
    VOLC_KB_SCHEME: str = "https"
    VOLC_KB_HOST: str = "api-knowledgebase.mlp.cn-beijing.volces.com"
    VOLC_KB_REGION: str = "cn-north-1"
    VOLC_KB_SERVICE: str = "air"
    VOLC_KB_AK: str = ""
    VOLC_KB_SK: str = ""
    VOLC_KB_ACCOUNT_ID: str = ""
    VOLC_KB_PROJECT: str = "default"
    VOLC_KB_COLLECTION_NAME: str = ""
    VOLC_KB_RESOURCE_ID: str = ""
    VOLC_KB_LIMIT: int = 5
    VOLC_KB_RETRIEVE_COUNT: int = 10
    VOLC_KB_DENSE_WEIGHT: float = 0.5
    VOLC_KB_RERANK_SWITCH: bool = True
    VOLC_KB_CHUNK_GROUP: bool = True
    VOLC_KB_RERANK_ONLY_CHUNK: bool = False
    VOLC_KB_CHUNK_DIFFUSION_COUNT: int = 0
    VOLC_KB_TIMEOUT_SECONDS: int = 30

    # MongoDB
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB: str = "ai_customer"

    # 产研通知接口
    NOTIFY_API_URL: str = ""
    NOTIFY_API_KEY: str = ""

    # MCP Server 鉴权（可选，配置后调用方需传入 auth_token）
    MCP_SERVER_TOKEN: str = ""

    # CORS
    CORS_ORIGINS: str = "http://localhost:5173"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]

    @property
    def llm_base_url(self) -> str | None:
        return self.LLM_BASE_URL or None


@lru_cache
def get_settings() -> Settings:
    return Settings()
