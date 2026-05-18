from __future__ import annotations

import uuid

from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models

from app.core.config import get_settings
from app.services.embedding import embed_text, embed_texts


def _point_id(doc_id: str, chunk_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"bou-kb:{doc_id}:{chunk_id}"))


def _metadata_filter(status_filter: str = "published", category: str = "") -> models.Filter:
    conditions: list[models.FieldCondition] = []
    if status_filter != "all":
        conditions.append(
            models.FieldCondition(
                key="status",
                match=models.MatchValue(value=status_filter),
            )
        )
    if category:
        conditions.append(
            models.FieldCondition(
                key="category",
                match=models.MatchValue(value=category),
            )
        )
    return models.Filter(must=conditions)


class VectorStore:
    def __init__(self) -> None:
        settings = get_settings()
        self.collection = settings.QDRANT_COLLECTION
        self.client = AsyncQdrantClient(url=settings.QDRANT_URL)

    async def ensure_collection(self, vector_size: int) -> None:
        exists = await self.client.collection_exists(self.collection)
        if exists:
            return
        await self.client.create_collection(
            collection_name=self.collection,
            vectors_config=models.VectorParams(
                size=vector_size,
                distance=models.Distance.COSINE,
            ),
        )

    async def delete_document(self, doc_id: str) -> None:
        if not doc_id or not await self.client.collection_exists(self.collection):
            return
        await self.client.delete(
            collection_name=self.collection,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="doc_id",
                            match=models.MatchValue(value=doc_id),
                        )
                    ]
                )
            ),
            wait=True,
        )

    async def upsert_document(self, doc: dict) -> dict:
        chunks = doc.get("chunks") or []
        if not chunks:
            await self.delete_document(doc.get("doc_id", ""))
            return {"upserted": 0, "deleted_old": True}

        texts = [chunk.get("content", "") for chunk in chunks]
        vectors = await embed_texts(texts)
        await self.ensure_collection(len(vectors[0]))
        await self.delete_document(doc.get("doc_id", ""))

        doc_meta = doc.get("metadata") or {}
        points = []
        for chunk, vector in zip(chunks, vectors, strict=False):
            payload = {
                "doc_id": doc.get("doc_id"),
                "chunk_id": chunk.get("chunk_id"),
                "chunk_index": chunk.get("index"),
                "content": chunk.get("content", ""),
                "source_file": doc.get("title") or "未知来源",
                "source_url": doc.get("source_url", ""),
                "section": chunk.get("title_path", ""),
                "document_title": doc.get("title") or "",
                "category": doc_meta.get("category", ""),
                "product_area": doc_meta.get("product_area", ""),
                "version": doc_meta.get("version", ""),
                "status": doc_meta.get("status", ""),
                "tags": doc_meta.get("tags", []),
            }
            points.append(
                models.PointStruct(
                    id=_point_id(doc.get("doc_id", ""), chunk.get("chunk_id", "")),
                    vector=vector,
                    payload=payload,
                )
            )

        await self.client.upsert(collection_name=self.collection, points=points, wait=True)
        return {"upserted": len(points), "collection": self.collection}

    async def search(self, query: str, top_k: int, status_filter: str = "published", category: str = "") -> list[dict]:
        query_vector = await embed_text(query)
        response = await self.client.query_points(
            collection_name=self.collection,
            query=query_vector,
            query_filter=_metadata_filter(status_filter, category),
            limit=top_k,
            with_payload=True,
        )
        min_score = get_settings().RAG_MIN_SCORE
        results = []
        for point in response.points:
            payload = point.payload or {}
            score = round(point.score, 4)
            if score < min_score:
                continue
            results.append(
                {
                    "doc_id": payload.get("doc_id", ""),
                    "document_title": payload.get("document_title") or payload.get("source_file", ""),
                    "source_url": payload.get("source_url", ""),
                    "chunk_id": payload.get("chunk_id", ""),
                    "chunk_index": payload.get("chunk_index"),
                    "title_path": payload.get("section", ""),
                    "content": payload.get("content", ""),
                    "score": score,
                    "scoring": {"provider": "qdrant", "min_score": min_score},
                    "metadata": {
                        "category": payload.get("category"),
                        "status": payload.get("status"),
                        "version": payload.get("version"),
                        "tags": payload.get("tags", []),
                    },
                }
            )
        return results


async def publish_document_to_vector_store(doc: dict) -> dict:
    return await VectorStore().upsert_document(doc)


async def delete_document_from_vector_store(doc_id: str) -> None:
    await VectorStore().delete_document(doc_id)


async def search_vector_store(query: str, top_k: int, status_filter: str = "published", category: str = "") -> list[dict]:
    return await VectorStore().search(query, top_k, status_filter, category)
