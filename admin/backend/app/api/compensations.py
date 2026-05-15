from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.db import mongo_client

router = APIRouter(prefix="/compensations", tags=["compensations"])


class CompensationRequest(BaseModel):
    user_id: str
    asset_type: Literal["star_energy", "echo_shell", "vip_days"]
    amount: int = Field(..., gt=0, le=100000)
    reason: str
    related_ticket_id: str | None = None


def now() -> datetime:
    return datetime.now(timezone.utc)


@router.post("")
async def create_compensation(req: CompensationRequest):
    client, db_name = mongo_client()
    try:
        record_id = f"CMP_{uuid.uuid4().hex[:10]}"
        record = {
            "record_id": record_id,
            "user_id": req.user_id,
            "asset_type": req.asset_type,
            "amount": req.amount,
            "reason": req.reason,
            "related_ticket_id": req.related_ticket_id,
            "status": "mock_submitted",
            "operator": "admin",
            "created_at": now(),
        }
        await client[db_name].compensation_records.insert_one(record)
        return {"record_id": record_id, "status": "mock_submitted"}
    finally:
        client.close()


@router.get("")
async def list_compensations():
    client, db_name = mongo_client()
    try:
        records = []
        cursor = client[db_name].compensation_records.find({}).sort("created_at", -1).limit(50)
        async for record in cursor:
            record["_id"] = str(record["_id"])
            records.append(record)
        return {"records": records}
    finally:
        client.close()
