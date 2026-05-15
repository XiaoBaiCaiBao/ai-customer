from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.db import mongo_client

router = APIRouter(prefix="/tickets", tags=["tickets"])

TicketStatus = Literal["pending", "processing", "resolved", "closed"]


class TicketUpdateRequest(BaseModel):
    status: TicketStatus | None = None
    assignee: str | None = None
    resolution: str | None = None
    tags: list[str] | None = None


def now() -> datetime:
    return datetime.now(timezone.utc)


async def ensure_seed_tickets(collection) -> None:
    if await collection.count_documents({}) > 0:
        return
    timestamp = now()
    await collection.insert_many(
        [
            {
                "ticket_id": "TCK_1001",
                "user_id": "u_9271",
                "title": "聊天气泡出现红色感叹号",
                "intent": "usage_issue",
                "status": "pending",
                "priority": "medium",
                "assignee": "运营",
                "summary": "用户上传截图反馈聊天消息旁出现红色感叹号，需要确认是安全拦截还是网络失败。",
                "ai_trace": {
                    "rewrite": "聊天消息旁边出现红色感叹号是什么原因",
                    "route": "RAG",
                    "rag_confidence": 0.62,
                },
                "tags": ["RAG置信度低", "高频问题"],
                "created_at": timestamp,
                "updated_at": timestamp,
            },
            {
                "ticket_id": "TCK_1002",
                "user_id": "u_3812",
                "title": "角色回复重复且人设偏移",
                "intent": "chat_quality_feedback",
                "status": "processing",
                "priority": "high",
                "assignee": "算法",
                "summary": "用户反馈 Rafayel 连续三轮回复重复表达，并出现主体错乱，需要进入聊天质量反馈 SOP。",
                "ai_trace": {
                    "skill": "chat_quality_feedback",
                    "slots": {"role": "Rafayel", "issue_type": "重复/主体错乱"},
                },
                "tags": ["Skills", "BadCase"],
                "created_at": timestamp,
                "updated_at": timestamp,
            },
        ]
    )


@router.get("")
async def list_tickets():
    client, db_name = mongo_client()
    try:
        collection = client[db_name].support_tickets
        await ensure_seed_tickets(collection)
        tickets = []
        cursor = collection.find({}).sort("updated_at", -1).limit(100)
        async for ticket in cursor:
            ticket["_id"] = str(ticket["_id"])
            tickets.append(ticket)
        return {"tickets": tickets}
    finally:
        client.close()


@router.patch("/{ticket_id}")
async def update_ticket(ticket_id: str, req: TicketUpdateRequest):
    client, db_name = mongo_client()
    try:
        update = {key: value for key, value in req.model_dump().items() if value is not None}
        if not update:
            return {"updated": False}
        update["updated_at"] = now()
        result = await client[db_name].support_tickets.update_one({"ticket_id": ticket_id}, {"$set": update})
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="工单不存在")
        return {"updated": True}
    finally:
        client.close()


@router.post("/from-agent")
async def create_ticket_from_agent(payload: dict):
    client, db_name = mongo_client()
    try:
        ticket_id = f"TCK_{uuid.uuid4().hex[:8]}"
        timestamp = now()
        ticket = {
            "ticket_id": ticket_id,
            "user_id": payload.get("user_id", ""),
            "title": payload.get("title") or payload.get("intent") or "AI转人工工单",
            "intent": payload.get("intent", "unknown"),
            "status": "pending",
            "priority": payload.get("priority", "medium"),
            "assignee": payload.get("assignee", "运营"),
            "summary": payload.get("summary", ""),
            "ai_trace": payload.get("ai_trace", {}),
            "tags": payload.get("tags", []),
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        await client[db_name].support_tickets.insert_one(ticket)
        return {"ticket_id": ticket_id}
    finally:
        client.close()
