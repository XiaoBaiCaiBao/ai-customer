from __future__ import annotations

import httpx

from app.core.config import get_settings


def _extract_embedding(payload: dict) -> list[float]:
    data = payload.get("data")
    if isinstance(data, dict) and isinstance(data.get("embedding"), list):
        return data["embedding"]
    if isinstance(data, list) and data:
        first = data[0]
        if isinstance(first, dict) and isinstance(first.get("embedding"), list):
            return first["embedding"]
    if isinstance(payload.get("embedding"), list):
        return payload["embedding"]
    raise RuntimeError("Embedding 接口返回格式不符合预期")


async def embed_text(text: str) -> list[float]:
    settings = get_settings()
    if not settings.LLM_API_KEY:
        raise RuntimeError("缺少 LLM_API_KEY，无法生成 embedding")

    async with httpx.AsyncClient(timeout=settings.EMBEDDING_TIMEOUT_SECONDS) as client:
        resp = await client.post(
            settings.EMBEDDING_BASE_URL,
            headers={
                "Authorization": f"Bearer {settings.LLM_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.EMBEDDING_MODEL,
                "input": [{"type": "text", "text": text}],
            },
        )
        resp.raise_for_status()
        return _extract_embedding(resp.json())


async def embed_texts(texts: list[str]) -> list[list[float]]:
    embeddings = []
    for text in texts:
        embeddings.append(await embed_text(text))
    return embeddings
