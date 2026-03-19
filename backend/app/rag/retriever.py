"""
RAG 检索层 — 只读，知识库由外部独立服务写入

调用方式:
  results = await retrieve("星能是什么？")

返回格式:
  [{"content": "...", "source": "产品手册.pdf", "score": 0.87}, ...]
"""

import httpx
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import ScoredPoint
from app.config import get_settings

_async_client: AsyncQdrantClient | None = None


def _get_async_client() -> AsyncQdrantClient:
    global _async_client
    if _async_client is None:
        _async_client = AsyncQdrantClient(url=get_settings().QDRANT_URL)
    return _async_client


async def _embed_query(query: str) -> list[float]:
    """
    调用 doubao-embedding-vision multimodal 端点，纯文本输入。
    input 格式: [{"type": "text", "text": "..."}]
    """
    s = get_settings()
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            s.EMBEDDING_BASE_URL,
            headers={
                "Authorization": f"Bearer {s.LLM_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": s.EMBEDDING_MODEL,
                "input": [{"type": "text", "text": query}],
            },
        )
        resp.raise_for_status()
        return resp.json()["data"]["embedding"]


async def retrieve(query: str, top_k: int = 5) -> list[dict]:
    """
    检索知识库，返回最相关的 top_k 个文档片段。
    如果知识库为空或 Qdrant 不可达，优雅降级返回空列表。
    """
    s = get_settings()
    try:
        query_vector = await _embed_query(query)

        client = _get_async_client()
        response = await client.query_points(
            collection_name=s.QDRANT_COLLECTION,
            query=query_vector,
            limit=top_k,
            with_payload=True,
        )

        return [
            {
                "content": r.payload.get("content", ""),
                "source": r.payload.get("source_file", "未知来源"),
                "section": r.payload.get("section", ""),
                "score": round(r.score, 4),
            }
            for r in response.points
            if r.score > 0.4
        ]
    except Exception as e:
        print(f"[RAG] 检索失败，降级处理: {e}")
        return []
