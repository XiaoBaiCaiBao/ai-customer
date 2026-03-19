"""
RAG 检索层 — 只读，知识库由外部独立服务写入

调用方式:
  results = await retrieve("星能是什么？")

返回格式:
  [{"content": "...", "source": "产品手册.pdf", "score": 0.87}, ...]
"""

import asyncio
from qdrant_client import QdrantClient, AsyncQdrantClient
from qdrant_client.models import ScoredPoint
from app.config import get_settings
from app.llm import get_embeddings

_async_client: AsyncQdrantClient | None = None


def _get_async_client() -> AsyncQdrantClient:
    global _async_client
    if _async_client is None:
        _async_client = AsyncQdrantClient(url=get_settings().QDRANT_URL)
    return _async_client


async def retrieve(query: str, top_k: int = 5) -> list[dict]:
    """
    检索知识库，返回最相关的 top_k 个文档片段。
    如果知识库为空或 Qdrant 不可达，优雅降级返回空列表。
    """
    s = get_settings()
    try:
        embeddings = get_embeddings()
        query_vector = await asyncio.to_thread(embeddings.embed_query, query)

        client = _get_async_client()
        results: list[ScoredPoint] = await client.search(
            collection_name=s.QDRANT_COLLECTION,
            query_vector=query_vector,
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
            for r in results
            if r.score > 0.5  # 过滤低相关性结果
        ]
    except Exception as e:
        # 知识库服务不可用时不影响 Agent 运行
        print(f"[RAG] 检索失败，降级处理: {e}")
        return []
