from __future__ import annotations

import json

import httpx
from volcengine.Credentials import Credentials
from volcengine.auth.SignerV4 import SignerV4
from volcengine.base.Request import Request

from app.config import get_settings

SEARCH_KNOWLEDGE_PATH = "/api/knowledge/collection/search_knowledge"


def _build_signed_request(method: str, path: str, payload: dict) -> tuple[str, dict, str]:
    s = get_settings()
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json; charset=utf-8",
        "Host": s.VOLC_KB_HOST,
    }
    if s.VOLC_KB_ACCOUNT_ID:
        headers["V-Account-Id"] = s.VOLC_KB_ACCOUNT_ID

    req = Request()
    req.set_shema(s.VOLC_KB_SCHEME)
    req.set_method(method.upper())
    req.set_host(s.VOLC_KB_HOST)
    req.set_path(path)
    req.set_headers(headers)
    req.set_body(json.dumps(payload, ensure_ascii=False))

    credentials = Credentials(
        s.VOLC_KB_AK,
        s.VOLC_KB_SK,
        s.VOLC_KB_SERVICE,
        s.VOLC_KB_REGION,
    )
    SignerV4.sign(req, credentials)

    return f"{req.schema}://{req.host}{req.path}", req.headers, req.body


def _normalize_hit(hit: dict) -> dict:
    doc_info = hit.get("doc_info") or {}
    question = hit.get("original_question")
    answer = (hit.get("content") or "").strip()

    if question:
        content = f"问题：{question}\n\n回答：{answer}" if answer else f"问题：{question}"
    else:
        title = (hit.get("chunk_title") or "").strip()
        content = answer
        if title and title not in answer:
            content = f"标题：{title}\n\n内容：{answer}" if answer else f"标题：{title}"

    return {
        "content": content,
        "source": (
            doc_info.get("title")
            or doc_info.get("doc_name")
            or get_settings().VOLC_KB_COLLECTION_NAME
            or "火山知识库"
        ),
        "section": hit.get("chunk_title") or question or "",
        "score": round(float(hit.get("rerank_score") or hit.get("score") or 0.0), 4),
    }


async def retrieve_from_volcengine_kb(query: str, top_k: int = 5) -> list[dict]:
    s = get_settings()
    missing = [
        name
        for name, value in (
            ("VOLC_KB_AK", s.VOLC_KB_AK),
            ("VOLC_KB_SK", s.VOLC_KB_SK),
            ("VOLC_KB_COLLECTION_NAME", s.VOLC_KB_COLLECTION_NAME),
        )
        if not value
    ]
    if missing:
        print(f"[RAG] 火山知识库配置不完整，缺少: {', '.join(missing)}")
        return []

    limit = top_k if top_k > 0 else s.VOLC_KB_LIMIT
    retrieve_count = max(limit, s.VOLC_KB_RETRIEVE_COUNT)

    payload = {
        "project": s.VOLC_KB_PROJECT,
        "name": s.VOLC_KB_COLLECTION_NAME,
        "query": query,
        "limit": limit,
        "pre_processing": {
            "need_instruction": True,
            "rewrite": False,
            "return_token_usage": False,
            "messages": [
                {"role": "system", "content": ""},
                {"role": "user", "content": query},
            ],
        },
        "dense_weight": s.VOLC_KB_DENSE_WEIGHT,
        "post_processing": {
            "rerank_switch": s.VOLC_KB_RERANK_SWITCH,
            "retrieve_count": retrieve_count,
            "chunk_group": s.VOLC_KB_CHUNK_GROUP,
            "rerank_only_chunk": s.VOLC_KB_RERANK_ONLY_CHUNK,
            "chunk_diffusion_count": s.VOLC_KB_CHUNK_DIFFUSION_COUNT,
            "get_attachment_link": False,
        },
    }
    if s.VOLC_KB_RESOURCE_ID:
        payload["resource_id"] = s.VOLC_KB_RESOURCE_ID

    url, headers, body = _build_signed_request("POST", SEARCH_KNOWLEDGE_PATH, payload)

    async with httpx.AsyncClient(timeout=s.VOLC_KB_TIMEOUT_SECONDS) as client:
        resp = await client.post(url, headers=headers, content=body)
        resp.raise_for_status()
        data = resp.json()

    if data.get("code") not in (0, "0", None):
        raise RuntimeError(
            f"Volcengine KB search failed: code={data.get('code')} message={data.get('message') or data.get('msg')}"
        )

    hits = ((data.get("data") or {}).get("result_list") or [])[:limit]
    return [_normalize_hit(hit) for hit in hits if (hit.get("content") or "").strip()]
