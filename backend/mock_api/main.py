from __future__ import annotations

import hashlib
import re
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .data import MOCK_USERS, WORK_ORDERS, now_iso


USER_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{3,64}$")
ALLOWED_ISSUE_TYPES = {
    "月卡未到账",
    "周卡未到账",
    "回声贝未到账",
    "虚拟资产未到账",
    "体力异常",
    "订单异常",
}

app = FastAPI(
    title="AI Customer Mock Business API",
    description="用于 MVP 验证的用户资产、订单、资产明细和工单 mock 服务。",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class WorkOrderRequest(BaseModel):
    user_id: str = Field(..., min_length=3, max_length=64, examples=["user_1001"])
    issue_type: str = Field(..., examples=["月卡未到账"])
    description: str = Field(..., min_length=6, max_length=500, examples=["用户反馈购买月卡后体力和月卡权益未到账"])
    order_id: str | None = Field(default=None, examples=["ORD_20260423_1001"])
    priority: Literal["low", "normal", "high"] = "normal"


def success(data: dict[str, Any]) -> dict[str, Any]:
    return {"success": True, **data}


def fail(status_code: int, code: str, message: str, details: dict[str, Any] | None = None) -> None:
    raise HTTPException(
        status_code=status_code,
        detail={
            "success": False,
            "error": {
                "code": code,
                "message": message,
                "details": details or {},
            },
        },
    )


def get_user_or_404(user_id: str) -> dict[str, Any]:
    if not USER_ID_PATTERN.match(user_id):
        fail(
            status.HTTP_400_BAD_REQUEST,
            "INVALID_ARGUMENT",
            "user_id 仅支持 3-64 位字母、数字、下划线和短横线",
            {"field": "user_id"},
        )

    user = MOCK_USERS.get(user_id)
    if not user:
        fail(status.HTTP_404_NOT_FOUND, "USER_NOT_FOUND", "未找到该用户", {"user_id": user_id})
    return user


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/users/{user_id}/assets")
def get_user_assets(user_id: str) -> dict[str, Any]:
    """查询用户资产总览。"""
    user = get_user_or_404(user_id)
    return success(
        {
            "user_id": user_id,
            "profile": user["profile"],
            "assets": list(user["assets"].values()),
            "diagnosis": build_asset_diagnosis(user),
        }
    )


@app.get("/api/users/{user_id}/orders")
def get_user_orders(user_id: str, limit: int = Query(default=5, ge=1, le=20)) -> dict[str, Any]:
    """查询用户最近订单。"""
    user = get_user_or_404(user_id)
    return success({"user_id": user_id, "orders": user["orders"][:limit]})


@app.get("/api/users/{user_id}/assets/{asset_id}/details")
def get_asset_details(user_id: str, asset_id: str) -> dict[str, Any]:
    """查询某项资产的变动明细。"""
    user = get_user_or_404(user_id)
    asset = next((item for item in user["assets"].values() if item["asset_id"] == asset_id), None)
    if not asset:
        fail(status.HTTP_404_NOT_FOUND, "ASSET_NOT_FOUND", "未找到该资产", {"asset_id": asset_id})

    return success(
        {
            "user_id": user_id,
            "asset": asset,
            "details": user["asset_details"].get(asset_id, []),
        }
    )


@app.post("/api/work-orders", status_code=status.HTTP_201_CREATED)
def submit_work_order(req: WorkOrderRequest) -> dict[str, Any]:
    """提交售后工单，基于关键字段做简单幂等。"""
    get_user_or_404(req.user_id)

    if req.issue_type not in ALLOWED_ISSUE_TYPES:
        fail(
            status.HTTP_400_BAD_REQUEST,
            "INVALID_ARGUMENT",
            f"issue_type 不合法，可选值：{sorted(ALLOWED_ISSUE_TYPES)}",
            {"field": "issue_type"},
        )

    idempotency_basis = f"{req.user_id}|{req.issue_type}|{req.order_id or ''}|{req.description.strip()[:120]}"
    idempotency_key = hashlib.sha256(idempotency_basis.encode("utf-8")).hexdigest()
    existing = WORK_ORDERS.get(idempotency_key)
    if existing:
        return success({"work_order": {**existing, "idempotent": True}})

    ticket_id = f"WO_{len(WORK_ORDERS) + 1:06d}"
    work_order = {
        "ticket_id": ticket_id,
        "user_id": req.user_id,
        "issue_type": req.issue_type,
        "description": req.description,
        "order_id": req.order_id,
        "priority": req.priority,
        "status": "submitted",
        "created_at": now_iso(),
        "idempotent": False,
    }
    WORK_ORDERS[idempotency_key] = work_order
    return success({"work_order": work_order})


def build_asset_diagnosis(user: dict[str, Any]) -> dict[str, Any]:
    timeout_orders = [
        order
        for order in user["orders"]
        if order["payment_status"] == "paid" and order["delivery_status"] == "callback_timeout"
    ]
    abnormal_assets = [
        asset
        for asset in user["assets"].values()
        if asset.get("status") in {"abnormal", "not_delivered"}
    ]

    if timeout_orders or abnormal_assets:
        return {
            "status": "abnormal",
            "reason": "存在支付成功但权益未到账或资产异常记录",
            "related_order_ids": [order["order_id"] for order in timeout_orders],
            "related_asset_ids": [asset["asset_id"] for asset in abnormal_assets],
        }

    return {
        "status": "normal",
        "reason": "未发现明显资产异常",
        "related_order_ids": [],
        "related_asset_ids": [],
    }
