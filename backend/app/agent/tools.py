import hashlib
import json
import random
import re
import string
from typing import Any
from langchain_core.tools import tool  # pyright: ignore[reportMissingImports]

_USER_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_\-]{3,64}$")
_ALLOWED_ISSUE_TYPES = {"月卡未到账", "周卡未到账", "回声贝未到账", "虚拟资产未到账", "体力异常"}
_WORK_ORDER_IDEMPOTENCY_CACHE: dict[str, str] = {}


def _ok(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _error(code: str, message: str, details: dict[str, Any] | None = None) -> str:
    return json.dumps(
        {
            "success": False,
            "error": {
                "code": code,
                "message": message,
                "details": details or {},
            },
        },
        ensure_ascii=False,
    )


def _validate_user_id(user_id: str) -> str | None:
    if not user_id:
        return "user_id 不能为空"
    if not _USER_ID_PATTERN.match(user_id):
        return "user_id 仅支持 3-64 位字母、数字、下划线和短横线"
    return None


def get_user_recent_orders_service(user_id: str) -> dict[str, Any]:
    invalid = _validate_user_id(user_id)
    if invalid:
        return json.loads(_error("INVALID_ARGUMENT", invalid, {"field": "user_id"}))

    return {
        "success": True,
        "user_id": user_id,
        "orders": [
            {
                "order_id": "ORD_2024_10892",
                "type": "monthly_card",
                "product": "BOU月卡（30天体力+150）",
                "amount": 30.00,
                "status": "Success",
                "paid_at": "2024-01-15 14:32:07",
                "delivery_status": "pending_callback",
            }
        ],
    }


def check_user_assets_service(user_id: str) -> dict[str, Any]:
    invalid = _validate_user_id(user_id)
    if invalid:
        return json.loads(_error("INVALID_ARGUMENT", invalid, {"field": "user_id"}))

    return {
        "success": True,
        "user_id": user_id,
        "stamina_current": 0,
        "stamina_max": 150,
        "monthly_card_active": False,
        "monthly_card_expire": None,
        "diagnosis": "delivery_callback_failed",
        "note": "订单 ORD_2024_10892 扣款成功但发货回调超时，权益未下发",
    }


def submit_work_order_service(
    user_id: str,
    issue_type: str,
    description: str,
    order_id: str = "",
    caller_role: str = "trusted_agent",
) -> dict[str, Any]:
    invalid = _validate_user_id(user_id)
    if invalid:
        return json.loads(_error("INVALID_ARGUMENT", invalid, {"field": "user_id"}))

    if caller_role not in {"trusted_agent", "service"}:
        return json.loads(_error("PERMISSION_DENIED", "当前调用方无权限提交工单"))
    if issue_type not in _ALLOWED_ISSUE_TYPES:
        return json.loads(
            _error(
                "INVALID_ARGUMENT",
                f"issue_type 不合法，可选值：{sorted(_ALLOWED_ISSUE_TYPES)}",
                {"field": "issue_type"},
            )
        )
    if not description or len(description.strip()) < 6:
        return json.loads(_error("INVALID_ARGUMENT", "description 至少 6 个字符", {"field": "description"}))

    idempotency_basis = f"{user_id}|{issue_type}|{order_id.strip()}|{description.strip()[:120]}"
    idempotency_key = hashlib.sha256(idempotency_basis.encode("utf-8")).hexdigest()
    existing = _WORK_ORDER_IDEMPOTENCY_CACHE.get(idempotency_key)
    if existing:
        return {
            "success": True,
            "ticket_id": existing,
            "user_id": user_id,
            "issue_type": issue_type,
            "idempotent": True,
            "message": f"工单已存在，无需重复提交。工单号: {existing}",
        }

    ticket_id = "TICKET_" + "".join(random.choices(string.digits, k=8))
    _WORK_ORDER_IDEMPOTENCY_CACHE[idempotency_key] = ticket_id
    return {
        "success": True,
        "ticket_id": ticket_id,
        "user_id": user_id,
        "issue_type": issue_type,
        "idempotent": False,
        "message": f"工单提交成功，产研团队将尽快核实。工单号: {ticket_id}",
    }

@tool
def get_user_recent_orders(user_id: str) -> str:
    """查询用户最近的订单列表及状态。返回最近3条订单记录。"""
    return _ok(get_user_recent_orders_service(user_id))


@tool
def check_user_assets(user_id: str) -> str:
    """查询用户当前资产状态，包括体力值、会员状态等。"""
    return _ok(check_user_assets_service(user_id))


@tool
def submit_work_order(user_id: str, issue_type: str, description: str, order_id: str = "") -> str:
    """
    提交售后工单给产研团队，适用于订单扣款成功但权益未到账等异常情况。
    参数：
    - user_id: 用户ID
    - issue_type: 问题类型（如：月卡未到账、体力异常等）
    - description: 问题的详细描述
    - order_id: 相关订单号（如果有）
    """
    result = submit_work_order_service(
        user_id=user_id,
        issue_type=issue_type,
        description=description,
        order_id=order_id,
    )
    return _ok(result)


TOOLS = [get_user_recent_orders, check_user_assets, submit_work_order]
TOOLS_MAP = {t.name: t for t in TOOLS}
