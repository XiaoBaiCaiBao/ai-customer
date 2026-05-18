from __future__ import annotations

import asyncio
import hashlib
import math
import re
import uuid
from io import BytesIO
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from pypdf import PdfReader

from app.core.db import mongo_client
from app.services.chunking import (
    ChunkStrategy,
    KnowledgeChunk,
    KnowledgeMetadata,
    build_chunks,
    normalize_fetched_doc,
    token_estimate,
)
from app.services.vector_store import (
    delete_document_from_vector_store,
    publish_document_to_vector_store,
    search_vector_store,
)

router = APIRouter(prefix="/kb", tags=["knowledge-base"])

DocumentStatus = Literal["draft", "reviewing", "published", "archived"]
SyncFrequency = Literal["manual", "hourly", "daily", "weekly"]


class FetchFeishuRequest(BaseModel):
    url: str


class ChunkPreviewRequest(BaseModel):
    title: str = ""
    content: str
    metadata: KnowledgeMetadata = Field(default_factory=KnowledgeMetadata)
    strategy: ChunkStrategy = Field(default_factory=ChunkStrategy)


class SaveKnowledgeDocumentRequest(ChunkPreviewRequest):
    source_url: str = ""
    chunks: list[KnowledgeChunk] = Field(default_factory=list)
    sync_enabled: bool = False
    sync_frequency: SyncFrequency = "manual"
    auto_publish: bool = False


class UpdateDocumentStatusRequest(BaseModel):
    status: DocumentStatus


class UpdateSyncConfigRequest(BaseModel):
    sync_enabled: bool
    sync_frequency: SyncFrequency = "manual"
    auto_publish: bool = False


class RecallTestRequest(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=20)
    status_filter: DocumentStatus | Literal["all"] = "published"
    category: str = ""


def now() -> datetime:
    return datetime.now(timezone.utc)


def content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def extract_pdf_text(raw: bytes, filename: str) -> tuple[str, str, int]:
    try:
        reader = PdfReader(BytesIO(raw))
        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception as exc:
                raise HTTPException(status_code=400, detail="PDF 已加密，当前无法解析，请先解除加密后上传") from exc

        page_texts = []
        for index, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            if text:
                page_texts.append(f"## 第 {index} 页\n\n{text}")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail="PDF 解析失败，请确认文件未损坏") from exc

    content = "\n\n".join(page_texts).strip()
    if not content:
        raise HTTPException(status_code=400, detail="PDF 未解析出文本，可能是扫描件；当前 MVP 请先转成可复制文本或 OCR 后上传")

    title = filename.rsplit(".", 1)[0]
    return title, f"# {title}\n\n{content}", len(reader.pages)


async def fetch_feishu_content(url: str) -> tuple[str, str]:
    try:
        process = await asyncio.create_subprocess_exec(
            "lark-cli",
            "docs",
            "+fetch",
            "--doc",
            url,
            "--format",
            "pretty",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=45)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail="本机未找到 lark-cli，无法拉取飞书文档") from exc
    except asyncio.TimeoutError as exc:
        raise HTTPException(status_code=504, detail="飞书文档拉取超时") from exc

    if process.returncode != 0:
        detail = (stderr or stdout).decode("utf-8", errors="ignore")[:800]
        raise HTTPException(status_code=502, detail=f"飞书文档拉取失败：{detail}")

    raw = stdout.decode("utf-8", errors="ignore")
    return normalize_fetched_doc(raw)


def tokenize(text: str) -> set[str]:
    lowered = text.lower()
    english_words = re.findall(r"[a-z0-9_]{2,}", lowered)
    chinese_chars = re.findall(r"[\u4e00-\u9fff]", lowered)
    chinese_bigrams = [f"{chinese_chars[i]}{chinese_chars[i + 1]}" for i in range(len(chinese_chars) - 1)]
    return set(english_words + chinese_chars + chinese_bigrams)


def score_chunk(query: str, chunk_content: str, title_path: str, metadata: dict) -> tuple[float, dict]:
    query_tokens = tokenize(query)
    content_tokens = tokenize(chunk_content)
    title_tokens = tokenize(title_path)
    tag_tokens = tokenize(" ".join(metadata.get("tags") or []))

    if not query_tokens:
        return 0.0, {"keyword_hits": [], "semantic_overlap": 0.0, "title_boost": 0.0, "tag_boost": 0.0}

    content_hits = query_tokens & content_tokens
    title_hits = query_tokens & title_tokens
    tag_hits = query_tokens & tag_tokens
    semantic_overlap = len(content_hits) / max(1, len(query_tokens))
    title_boost = min(0.18, len(title_hits) * 0.06)
    tag_boost = min(0.08, len(tag_hits) * 0.04)
    length_penalty = min(0.12, math.log(max(1, len(chunk_content)) / 900 + 1) * 0.05)
    exact_bonus = 0.15 if query.strip() and query.strip() in chunk_content else 0
    score = min(1.0, semantic_overlap * 0.74 + title_boost + tag_boost + exact_bonus - length_penalty)

    return round(max(0.0, score), 4), {
        "keyword_hits": sorted(content_hits | title_hits | tag_hits)[:16],
        "semantic_overlap": round(semantic_overlap, 4),
        "title_boost": round(title_boost, 4),
        "tag_boost": round(tag_boost, 4),
        "length_penalty": round(length_penalty, 4),
        "exact_bonus": exact_bonus,
    }


@router.post("/fetch-feishu")
async def fetch_feishu_doc(req: FetchFeishuRequest):
    if "feishu.cn" not in req.url:
        raise HTTPException(status_code=400, detail="请输入飞书文档链接")

    title, content = await fetch_feishu_content(req.url)
    return {
        "title": title,
        "content": content,
        "source_url": req.url,
        "suggested_metadata": KnowledgeMetadata(
            category="产品功能",
            product_area="BOU App",
            owner="产品运营",
            tags=["飞书同步"],
        ).model_dump(),
        "stats": {
            "char_count": len(content),
            "token_estimate": token_estimate(content),
            "content_hash": content_hash(content),
        },
    }


@router.post("/upload-file")
async def upload_knowledge_file(file: UploadFile = File(...)):
    filename = file.filename or "未命名文件"
    suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    supported = {"md", "markdown", "txt", "json", "csv", "tsv", "log", "pdf"}
    if suffix not in supported:
        raise HTTPException(status_code=400, detail="当前 MVP 仅支持 md、txt、json、csv、tsv、log、pdf 文件")

    raw = await file.read()
    max_size = 10 * 1024 * 1024 if suffix == "pdf" else 2 * 1024 * 1024
    if len(raw) > max_size:
        size_mb = max_size // 1024 // 1024
        raise HTTPException(status_code=413, detail=f"文件过大，当前限制 {size_mb}MB")

    page_count = None
    if suffix == "pdf":
        title, content, page_count = extract_pdf_text(raw, filename)
    else:
        try:
            content = raw.decode("utf-8")
        except UnicodeDecodeError:
            try:
                content = raw.decode("gb18030")
            except UnicodeDecodeError as exc:
                raise HTTPException(status_code=400, detail="文件编码暂不支持，请转为 UTF-8 后上传") from exc

        if suffix in {"csv", "tsv"}:
            title = filename.rsplit(".", 1)[0]
            content = f"# {title}\n\n{content.strip()}"
        else:
            title, content = normalize_fetched_doc(content)
            if title == "未命名文档":
                title = filename.rsplit(".", 1)[0]

    stats = {
        "filename": filename,
        "char_count": len(content),
        "token_estimate": token_estimate(content),
        "content_hash": content_hash(content),
    }
    if page_count is not None:
        stats["page_count"] = page_count

    return {
        "title": title,
        "content": content.strip(),
        "source_url": f"local://{filename}",
        "suggested_metadata": KnowledgeMetadata(
            category="产品功能",
            product_area="BOU App",
            owner="产品运营",
            tags=["本地上传", suffix],
        ).model_dump(),
        "stats": stats,
    }


@router.post("/chunk-preview")
async def preview_chunks(req: ChunkPreviewRequest):
    chunks = build_chunks(req.title or "未命名文档", req.content, req.metadata, req.strategy)
    return {
        "chunks": [chunk.model_dump() for chunk in chunks],
        "summary": {
            "chunk_count": len(chunks),
            "avg_tokens": round(sum(c.token_estimate for c in chunks) / len(chunks), 1) if chunks else 0,
            "max_tokens": max((c.token_estimate for c in chunks), default=0),
            "method": req.strategy.method,
        },
    }


@router.post("/documents")
async def save_knowledge_document(req: SaveKnowledgeDocumentRequest):
    client, db_name = mongo_client()
    try:
        collection = client[db_name].knowledge_documents
        chunks = req.chunks or build_chunks(req.title or "未命名文档", req.content, req.metadata, req.strategy)
        timestamp = now()

        existing = None
        if req.source_url:
            existing = await collection.find_one({"source_url": req.source_url})

        doc_id = existing.get("doc_id") if existing else f"doc_{uuid.uuid4().hex[:12]}"
        doc_update = {
            "title": req.title or "未命名文档",
            "source_url": req.source_url,
            "source_type": "feishu" if "feishu.cn" in req.source_url else "local" if req.source_url.startswith("local://") else "manual",
            "content": req.content,
            "content_hash": content_hash(req.content),
            "metadata": req.metadata.model_dump(),
            "chunk_strategy": req.strategy.model_dump(),
            "chunks": [chunk.model_dump() for chunk in chunks],
            "chunk_count": len(chunks),
            "sync_config": {
                "sync_enabled": req.sync_enabled,
                "sync_frequency": req.sync_frequency,
                "auto_publish": req.auto_publish,
            },
            "last_sync_status": "saved",
            "updated_at": timestamp,
        }

        if existing:
            await collection.update_one(
                {"doc_id": doc_id},
                {
                    "$set": doc_update,
                    "$setOnInsert": {"created_at": timestamp, "created_by": "admin"},
                },
                upsert=True,
            )
            return {"doc_id": doc_id, "chunk_count": len(chunks), "mode": "updated"}

        doc = {
            "doc_id": doc_id,
            **doc_update,
            "created_by": "admin",
            "created_at": timestamp,
        }
        await collection.insert_one(doc)
        return {"doc_id": doc_id, "chunk_count": len(chunks), "mode": "created"}
    finally:
        client.close()


@router.get("/documents")
async def list_knowledge_documents():
    client, db_name = mongo_client()
    try:
        docs = []
        cursor = client[db_name].knowledge_documents.find({}, {"content": 0, "chunks.content": 0}).sort("updated_at", -1).limit(50)
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            docs.append(doc)
        return {"documents": docs}
    finally:
        client.close()


@router.get("/documents/{doc_id}")
async def get_knowledge_document(doc_id: str):
    client, db_name = mongo_client()
    try:
        doc = await client[db_name].knowledge_documents.find_one({"doc_id": doc_id})
        if not doc:
            raise HTTPException(status_code=404, detail="文档不存在")
        doc["_id"] = str(doc["_id"])
        return doc
    finally:
        client.close()


@router.patch("/documents/{doc_id}/status")
async def update_document_status(doc_id: str, req: UpdateDocumentStatusRequest):
    client, db_name = mongo_client()
    try:
        doc = await client[db_name].knowledge_documents.find_one({"doc_id": doc_id})
        if not doc:
            raise HTTPException(status_code=404, detail="文档不存在")

        timestamp = now()
        vector_result = None
        update = {
            "metadata.status": req.status,
            "updated_at": timestamp,
        }
        if req.status == "published":
            vector_doc = {
                **doc,
                "metadata": {
                    **(doc.get("metadata") or {}),
                    "status": "published",
                },
            }
            try:
                vector_result = await publish_document_to_vector_store(vector_doc)
            except Exception as exc:
                raise HTTPException(status_code=502, detail=f"发布到 Qdrant 失败：{exc}") from exc
            update["published_at"] = timestamp
            update["vector_status"] = "published"
            update["vector_sync_at"] = timestamp
            update["vector_result"] = vector_result
        else:
            try:
                await delete_document_from_vector_store(doc_id)
                update["vector_status"] = "deleted"
                update["vector_sync_at"] = timestamp
            except Exception as exc:
                raise HTTPException(status_code=502, detail=f"从 Qdrant 删除文档失败：{exc}") from exc
        result = await client[db_name].knowledge_documents.update_one({"doc_id": doc_id}, {"$set": update})
        return {
            "updated": bool(result.modified_count),
            "status": req.status,
            "vector_result": vector_result,
        }
    finally:
        client.close()


@router.patch("/documents/{doc_id}/sync-config")
async def update_sync_config(doc_id: str, req: UpdateSyncConfigRequest):
    client, db_name = mongo_client()
    try:
        doc = await client[db_name].knowledge_documents.find_one({"doc_id": doc_id})
        if not doc:
            raise HTTPException(status_code=404, detail="文档不存在")
        if req.sync_enabled and doc.get("source_type") != "feishu":
            raise HTTPException(status_code=400, detail="只有飞书来源文档支持自动同步")

        result = await client[db_name].knowledge_documents.update_one(
            {"doc_id": doc_id},
            {
                "$set": {
                    "sync_config": req.model_dump(),
                    "updated_at": now(),
                }
            },
        )
        return {"updated": bool(result.modified_count), "sync_config": req.model_dump()}
    finally:
        client.close()


@router.post("/documents/{doc_id}/sync-now")
async def sync_document_now(doc_id: str):
    client, db_name = mongo_client()
    try:
        collection = client[db_name].knowledge_documents
        doc = await collection.find_one({"doc_id": doc_id})
        if not doc:
            raise HTTPException(status_code=404, detail="文档不存在")
        if doc.get("source_type") != "feishu" or "feishu.cn" not in (doc.get("source_url") or ""):
            raise HTTPException(status_code=400, detail="只有飞书来源文档支持立即同步")

        title, content = await fetch_feishu_content(doc["source_url"])
        new_hash = content_hash(content)
        old_hash = doc.get("content_hash")
        timestamp = now()

        if new_hash == old_hash:
            await collection.update_one(
                {"doc_id": doc_id},
                {
                    "$set": {
                        "last_sync_at": timestamp,
                        "last_sync_status": "no_change",
                        "updated_at": timestamp,
                    }
                },
            )
            return {"changed": False, "status": "no_change", "message": "飞书内容无变化"}

        metadata = KnowledgeMetadata(**(doc.get("metadata") or {}))
        sync_config = doc.get("sync_config") or {}
        auto_publish = bool(sync_config.get("auto_publish"))
        metadata.status = "published" if auto_publish else "reviewing"
        strategy = ChunkStrategy(**(doc.get("chunk_strategy") or {}))
        chunks = build_chunks(title, content, metadata, strategy)

        updated_doc = {
            "title": title,
            "content": content,
            "content_hash": new_hash,
            "metadata": metadata.model_dump(),
            "chunks": [chunk.model_dump() for chunk in chunks],
            "chunk_count": len(chunks),
            "last_sync_at": timestamp,
            "last_sync_status": "changed_auto_published" if auto_publish else "changed_waiting_review",
            "updated_at": timestamp,
            **({"published_at": timestamp} if auto_publish else {}),
        }
        vector_result = None
        if auto_publish:
            try:
                vector_result = await publish_document_to_vector_store({**doc, **updated_doc})
                updated_doc["vector_status"] = "published"
                updated_doc["vector_sync_at"] = timestamp
                updated_doc["vector_result"] = vector_result
            except Exception as exc:
                raise HTTPException(status_code=502, detail=f"自动发布到 Qdrant 失败：{exc}") from exc

        await collection.update_one(
            {"doc_id": doc_id},
            {
                "$set": updated_doc
            },
        )
        return {
            "changed": True,
            "status": "changed_auto_published" if auto_publish else "changed_waiting_review",
            "chunk_count": len(chunks),
            "vector_result": vector_result,
            "message": "已拉取新版本并自动发布" if auto_publish else "已拉取新版本，进入待审核",
        }
    finally:
        client.close()


@router.post("/recall-test")
async def recall_test(req: RecallTestRequest):
    query = req.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="请输入测试 Query")

    client, db_name = mongo_client()
    try:
        if req.status_filter in {"published", "all"}:
            try:
                vector_results = await search_vector_store(query, req.top_k, req.status_filter, req.category)
                return {
                    "query": query,
                    "results": vector_results,
                    "summary": {
                        "candidate_count": len(vector_results),
                        "returned_count": len(vector_results),
                        "status_filter": req.status_filter,
                        "category": req.category,
                        "provider": "qdrant",
                    },
                }
            except Exception as exc:
                vector_error = str(exc)
            else:
                vector_error = ""
        else:
            vector_error = ""

        filters = {}
        if req.status_filter != "all":
            filters["metadata.status"] = req.status_filter
        if req.category:
            filters["metadata.category"] = req.category

        results = []
        cursor = client[db_name].knowledge_documents.find(filters).sort("updated_at", -1).limit(200)
        async for doc in cursor:
            doc_meta = doc.get("metadata") or {}
            for chunk in doc.get("chunks") or []:
                chunk_meta = chunk.get("metadata") or {}
                merged_meta = {**doc_meta, **chunk_meta}
                score, scoring = score_chunk(
                    query=query,
                    chunk_content=chunk.get("content", ""),
                    title_path=chunk.get("title_path", ""),
                    metadata=merged_meta,
                )
                if score <= 0:
                    continue
                results.append(
                    {
                        "doc_id": doc.get("doc_id"),
                        "document_title": doc.get("title"),
                        "source_url": doc.get("source_url", ""),
                        "chunk_id": chunk.get("chunk_id"),
                        "chunk_index": chunk.get("index"),
                        "title_path": chunk.get("title_path", ""),
                        "content": chunk.get("content", ""),
                        "score": score,
                        "scoring": scoring,
                        "metadata": {
                            "category": doc_meta.get("category"),
                            "status": doc_meta.get("status"),
                            "version": doc_meta.get("version"),
                            "tags": doc_meta.get("tags", []),
                        },
                    }
                )

        results.sort(key=lambda item: item["score"], reverse=True)
        top_results = results[: req.top_k]
        return {
            "query": query,
            "results": top_results,
            "summary": {
                "candidate_count": len(results),
                "returned_count": len(top_results),
                "status_filter": req.status_filter,
                "category": req.category,
                "provider": "local_keyword",
                "fallback_reason": vector_error,
            },
        }
    finally:
        client.close()
