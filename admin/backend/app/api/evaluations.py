from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.api.kb import score_chunk
from app.core.db import mongo_client
from app.evaluations.runners import build_authoring_todo_result

router = APIRouter(prefix="/evaluations", tags=["evaluations"])

CaseStatus = Literal["active", "disabled"]
EvaluationType = Literal["rewrite", "intent", "rag_recall", "rag_answer", "mcp_tool", "skills", "end_to_end"]
RouteType = Literal["RAG", "MCP", "Skills", "工单", "产品反馈", "其他"]


class EvaluationCaseCreate(BaseModel):
    question: str
    expected_answer: str = ""
    expected_intent: str = ""
    expected_doc_id: str = ""
    expected_chunk_ids: list[str] = Field(default_factory=list)
    evaluation_type: EvaluationType = "rag_recall"
    route_type: RouteType = "RAG"
    expected_payload: dict = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    status: CaseStatus = "active"


class EvaluationCaseUpdate(BaseModel):
    question: str | None = None
    expected_answer: str | None = None
    expected_intent: str | None = None
    expected_doc_id: str | None = None
    expected_chunk_ids: list[str] | None = None
    evaluation_type: EvaluationType | None = None
    route_type: RouteType | None = None
    expected_payload: dict | None = None
    tags: list[str] | None = None
    status: CaseStatus | None = None


class RunEvaluationRequest(BaseModel):
    case_ids: list[str] = Field(default_factory=list)
    top_k: int = Field(default=5, ge=1, le=20)
    status_filter: Literal["published", "reviewing", "draft", "all"] = "published"
    category: str = ""


def now() -> datetime:
    return datetime.now(timezone.utc)


async def ensure_seed_cases(collection) -> None:
    if await collection.count_documents({}) > 0:
        return
    timestamp = now()
    await collection.insert_many(
        [
            {
                "case_id": "EVAL_1001",
                "question": "聊天里出现红色感叹号是怎么回事？",
                "expected_answer": "红色感叹号通常表示消息发送失败、网络异常或内容触发安全策略，需要引导用户重试或反馈。",
                "expected_intent": "content_safety_consult",
                "expected_doc_id": "",
                "expected_chunk_ids": [],
                "evaluation_type": "rag_recall",
                "route_type": "RAG",
                "expected_payload": {
                    "expected_documents": ["FAQ-内容安全策略", "星能返还规则"],
                    "expected_answer_points": ["安全策略拦截", "星能不消耗或返还", "继续聊天即可"],
                    "expected_keywords": ["红色感叹号", "敏感策略", "星能返还"],
                    "expected_chunk_snippets": ["男主回复超出敏感策略程度则消息无法返回"],
                },
                "tags": ["高频问题", "红色感叹号"],
                "status": "active",
                "created_at": timestamp,
                "updated_at": timestamp,
            },
            {
                "case_id": "EVAL_1002",
                "question": "月卡 VIP 有哪些权益？",
                "expected_answer": "应召回会员权益或订阅规则相关知识。",
                "expected_intent": "pre_sales_consult",
                "expected_doc_id": "",
                "expected_chunk_ids": [],
                "evaluation_type": "rag_recall",
                "route_type": "RAG",
                "expected_payload": {
                    "expected_documents": ["会员权益说明", "星能规则"],
                    "expected_answer_points": ["会员权益", "赠送星能", "生效时间"],
                    "expected_keywords": ["月卡", "会员", "星能"],
                },
                "tags": ["会员权益"],
                "status": "active",
                "created_at": timestamp,
                "updated_at": timestamp,
            },
        ]
    )


async def recall_candidates(db, query: str, top_k: int, status_filter: str, category: str) -> list[dict]:
    filters = {}
    if status_filter != "all":
        filters["metadata.status"] = status_filter
    if category:
        filters["metadata.category"] = category

    results = []
    cursor = db.knowledge_documents.find(filters).sort("updated_at", -1).limit(300)
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
    return results[:top_k]


def judge_case(case: dict, hits: list[dict]) -> dict:
    expected_doc_id = case.get("expected_doc_id") or ""
    expected_chunk_ids = set(case.get("expected_chunk_ids") or [])
    expected_payload = case.get("expected_payload") or {}
    expected_documents = set(expected_payload.get("expected_documents") or [])
    expected_keywords = set(expected_payload.get("expected_keywords") or [])
    expected_snippets = expected_payload.get("expected_chunk_snippets") or []
    hit_rank = None
    hit_reason = "未配置标准文档/chunk，按是否有召回结果判定为辅助评测"

    if expected_chunk_ids:
        for index, hit in enumerate(hits, start=1):
            if hit.get("chunk_id") in expected_chunk_ids:
                hit_rank = index
                hit_reason = "命中标准 chunk"
                break
    elif expected_doc_id:
        for index, hit in enumerate(hits, start=1):
            if hit.get("doc_id") == expected_doc_id:
                hit_rank = index
                hit_reason = "命中标准文档"
                break
    elif expected_documents or expected_keywords or expected_snippets:
        for index, hit in enumerate(hits, start=1):
            title = hit.get("document_title") or ""
            content = hit.get("content") or ""
            doc_hit = any(doc in title for doc in expected_documents)
            keyword_hit = expected_keywords and all(keyword in content for keyword in expected_keywords)
            snippet_hit = any(snippet and snippet in content for snippet in expected_snippets)
            if doc_hit or keyword_hit or snippet_hit:
                hit_rank = index
                hit_reason = "命中期望文档/关键词/片段"
                break
    elif hits:
        hit_rank = 1

    passed = hit_rank is not None
    return {
        "passed": passed,
        "rank": hit_rank,
        "mrr": round(1 / hit_rank, 4) if hit_rank else 0,
        "top_score": hits[0]["score"] if hits else 0,
        "hit_reason": hit_reason if passed else "未召回标准知识",
        "badcase_type": None if passed else "recall_miss",
    }


@router.get("/cases")
async def list_cases():
    client, db_name = mongo_client()
    try:
        collection = client[db_name].evaluation_cases
        await ensure_seed_cases(collection)
        cases = []
        cursor = collection.find({}).sort("updated_at", -1).limit(200)
        async for case in cursor:
            case["_id"] = str(case["_id"])
            cases.append(case)
        return {"cases": cases}
    finally:
        client.close()


@router.post("/cases")
async def create_case(req: EvaluationCaseCreate):
    client, db_name = mongo_client()
    try:
        case_id = f"EVAL_{uuid.uuid4().hex[:8]}"
        timestamp = now()
        doc = {
            "case_id": case_id,
            **req.model_dump(),
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        await client[db_name].evaluation_cases.insert_one(doc)
        return {"case_id": case_id}
    finally:
        client.close()


@router.patch("/cases/{case_id}")
async def update_case(case_id: str, req: EvaluationCaseUpdate):
    client, db_name = mongo_client()
    try:
        update = {key: value for key, value in req.model_dump().items() if value is not None}
        if not update:
            return {"updated": False}
        update["updated_at"] = now()
        result = await client[db_name].evaluation_cases.update_one({"case_id": case_id}, {"$set": update})
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="评测用例不存在")
        return {"updated": True}
    finally:
        client.close()


@router.post("/runs")
async def run_evaluation(req: RunEvaluationRequest):
    client, db_name = mongo_client()
    try:
        db = client[db_name]
        await ensure_seed_cases(db.evaluation_cases)
        filters = {"status": "active"}
        if req.case_ids:
            filters["case_id"] = {"$in": req.case_ids}

        cases = []
        cursor = db.evaluation_cases.find(filters).sort("updated_at", -1).limit(500)
        async for case in cursor:
            cases.append(case)
        if not cases:
            raise HTTPException(status_code=400, detail="没有可运行的评测用例")

        results = []
        for case in cases:
            if case.get("evaluation_type") != "rag_recall":
                results.append(build_authoring_todo_result(case))
                continue

            hits = await recall_candidates(
                db=db,
                query=case.get("question", ""),
                top_k=req.top_k,
                status_filter=req.status_filter,
                category=req.category,
            )
            judgement = judge_case(case, hits)
            results.append(
                {
                    "case_id": case.get("case_id"),
                    "question": case.get("question"),
                    "expected_intent": case.get("expected_intent", ""),
                    "evaluation_type": case.get("evaluation_type", "rag_recall"),
                    "passed": judgement["passed"],
                    "rank": judgement["rank"],
                    "mrr": judgement["mrr"],
                    "top_score": judgement["top_score"],
                    "hit_reason": judgement["hit_reason"],
                    "badcase_type": judgement["badcase_type"],
                    "hits": hits,
                }
            )

        total = len(results)
        passed_count = sum(1 for item in results if item["passed"])
        metrics = {
            "case_count": total,
            "passed_count": passed_count,
            "badcase_count": total - passed_count,
            "needs_implementation_count": sum(1 for item in results if item.get("needs_implementation")),
            "recall_at_k": round(passed_count / total, 4) if total else 0,
            "mrr": round(sum(item["mrr"] for item in results) / total, 4) if total else 0,
            "avg_top_score": round(sum(item["top_score"] for item in results) / total, 4) if total else 0,
        }

        run_id = f"RUN_{uuid.uuid4().hex[:10]}"
        timestamp = now()
        run_doc = {
            "run_id": run_id,
            "request": req.model_dump(),
            "metrics": metrics,
            "results": results,
            "created_at": timestamp,
        }
        await db.evaluation_runs.insert_one(run_doc)
        return {"run_id": run_id, "metrics": metrics, "results": results}
    finally:
        client.close()


@router.get("/runs")
async def list_runs():
    client, db_name = mongo_client()
    try:
        runs = []
        cursor = client[db_name].evaluation_runs.find({}, {"results": 0}).sort("created_at", -1).limit(50)
        async for run in cursor:
            run["_id"] = str(run["_id"])
            runs.append(run)
        return {"runs": runs}
    finally:
        client.close()


@router.get("/runs/{run_id}")
async def get_run(run_id: str):
    client, db_name = mongo_client()
    try:
        run = await client[db_name].evaluation_runs.find_one({"run_id": run_id})
        if not run:
            raise HTTPException(status_code=404, detail="评测运行不存在")
        run["_id"] = str(run["_id"])
        return run
    finally:
        client.close()
