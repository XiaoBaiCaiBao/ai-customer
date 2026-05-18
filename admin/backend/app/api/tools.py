from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.db import mongo_client

router = APIRouter(prefix="/tools", tags=["tools"])

ToolStatus = Literal["active", "disabled"]


class ToolDefinition(BaseModel):
    tool_id: str
    name: str
    description: str = ""
    applicable_intents: list[str] = Field(default_factory=list)
    input_schema: dict = Field(default_factory=dict)
    output_schema: dict = Field(default_factory=dict)
    mock_response: dict = Field(default_factory=dict)
    failure_strategy: str = "失败后澄清用户或转人工"
    owner: str = "产品/研发"
    status: ToolStatus = "active"


def now() -> datetime:
    return datetime.now(timezone.utc)


async def ensure_seed_tools(collection) -> None:
    if await collection.count_documents({}) > 0:
        return
    timestamp = now()
    await collection.insert_many(
        [
            {
                "tool_id": "get_user_spending_summary",
                "name": "查询用户消费汇总",
                "description": "查询用户在指定时间范围内的消费金额或星能消耗汇总。",
                "applicable_intents": ["账单查询", "虚拟资产消耗相关疑问"],
                "input_schema": {
                    "user_id": "string",
                    "start_time": "datetime",
                    "end_time": "datetime",
                    "asset_type": "star_energy | echo_shell | money",
                },
                "output_schema": {
                    "total_amount": "number",
                    "currency": "string",
                    "summary": "string",
                },
                "mock_response": {
                    "total_amount": 128,
                    "currency": "CNY",
                    "summary": "最近30天共消费128元，主要用于月卡和回声贝。",
                },
                "failure_strategy": "缺少时间范围时先澄清；接口失败时转人工工单。",
                "owner": "商业化/后端",
                "status": "active",
                "created_at": timestamp,
                "updated_at": timestamp,
            },
            {
                "tool_id": "get_user_asset_transactions",
                "name": "查询用户虚拟资产流水",
                "description": "查询星能、回声贝等虚拟资产的获得和消耗流水。",
                "applicable_intents": ["虚拟资产消耗相关疑问", "售后 / 到账异常"],
                "input_schema": {
                    "user_id": "string",
                    "asset_type": "star_energy | echo_shell",
                    "start_time": "datetime",
                    "end_time": "datetime",
                },
                "output_schema": {
                    "income": "number",
                    "expense": "number",
                    "transactions": "array",
                },
                "mock_response": {
                    "income": 2000,
                    "expense": 860,
                    "transactions": [
                        {"time": "2026-05-01", "type": "chat", "amount": -20},
                        {"time": "2026-05-02", "type": "daily_bonus", "amount": 100},
                    ],
                },
                "failure_strategy": "权限不足或用户身份缺失时要求登录；流水异常时提交工单。",
                "owner": "资产/后端",
                "status": "active",
                "created_at": timestamp,
                "updated_at": timestamp,
            },
            {
                "tool_id": "submit_feedback_ticket",
                "name": "提交用户反馈工单",
                "description": "把聊天质量、故障、产品建议等问题提交给后台处理。",
                "applicable_intents": ["聊天质量反馈", "故障反馈", "产品建议"],
                "input_schema": {
                    "user_id": "string",
                    "issue_type": "string",
                    "description": "string",
                    "attachments": "array",
                    "priority": "low | medium | high",
                },
                "output_schema": {
                    "ticket_id": "string",
                    "status": "string",
                },
                "mock_response": {
                    "ticket_id": "TCK_123456",
                    "status": "pending",
                },
                "failure_strategy": "提交失败时保留摘要并提示用户稍后重试或人工跟进。",
                "owner": "客服/运营",
                "status": "active",
                "created_at": timestamp,
                "updated_at": timestamp,
            },
        ]
    )


@router.get("")
async def list_tools():
    client, db_name = mongo_client()
    try:
        collection = client[db_name].tool_registry
        await ensure_seed_tools(collection)
        tools = []
        cursor = collection.find({}).sort("updated_at", -1).limit(100)
        async for tool in cursor:
            tool["_id"] = str(tool["_id"])
            tools.append(tool)
        return {"tools": tools}
    finally:
        client.close()


@router.post("")
async def upsert_tool(req: ToolDefinition):
    client, db_name = mongo_client()
    try:
        timestamp = now()
        doc = {
            **req.model_dump(),
            "updated_at": timestamp,
        }
        result = await client[db_name].tool_registry.update_one(
            {"tool_id": req.tool_id},
            {
                "$set": doc,
                "$setOnInsert": {"created_at": timestamp},
            },
            upsert=True,
        )
        return {"tool_id": req.tool_id, "mode": "updated" if result.matched_count else "created"}
    finally:
        client.close()


@router.patch("/{tool_id}/status")
async def update_tool_status(tool_id: str, payload: dict):
    status = payload.get("status")
    if status not in {"active", "disabled"}:
        raise HTTPException(status_code=400, detail="状态只能是 active 或 disabled")

    client, db_name = mongo_client()
    try:
        result = await client[db_name].tool_registry.update_one(
            {"tool_id": tool_id},
            {"$set": {"status": status, "updated_at": now()}},
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="工具不存在")
        return {"updated": True}
    finally:
        client.close()
