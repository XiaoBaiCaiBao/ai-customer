from __future__ import annotations

import logging
import time
from typing import Any

from mcp.server.fastmcp import FastMCP  # pyright: ignore[reportMissingImports]

from app.agent.tools import (
    check_user_assets_service,
    get_user_recent_orders_service,
    submit_work_order_service,
)
from app.config import get_settings

logger = logging.getLogger("app.mcp")
mcp = FastMCP("ai-customer-mcp")


def _assert_auth(token: str | None) -> None:
    settings = get_settings()
    expected = settings.MCP_SERVER_TOKEN
    if not expected:
        return
    if token != expected:
        raise ValueError("UNAUTHORIZED: token 不正确")


def _audit(tool_name: str, request: dict[str, Any], response: dict[str, Any], elapsed_ms: int) -> None:
    logger.info(
        "mcp_tool_called",
        extra={
            "tool": tool_name,
            "request": request,
            "response_ok": response.get("success", False),
            "error_code": (response.get("error") or {}).get("code"),
            "elapsed_ms": elapsed_ms,
        },
    )


@mcp.tool()
def get_user_recent_orders(user_id: str, auth_token: str | None = None) -> dict[str, Any]:
    """查询用户最近订单（读操作）。"""
    _assert_auth(auth_token)
    start = time.perf_counter()
    result = get_user_recent_orders_service(user_id=user_id)
    _audit("get_user_recent_orders", {"user_id": user_id}, result, int((time.perf_counter() - start) * 1000))
    return result


@mcp.tool()
def check_user_assets(user_id: str, auth_token: str | None = None) -> dict[str, Any]:
    """查询用户资产状态（读操作）。"""
    _assert_auth(auth_token)
    start = time.perf_counter()
    result = check_user_assets_service(user_id=user_id)
    _audit("check_user_assets", {"user_id": user_id}, result, int((time.perf_counter() - start) * 1000))
    return result


@mcp.tool()
def submit_work_order(
    user_id: str,
    issue_type: str,
    description: str,
    order_id: str = "",
    auth_token: str | None = None,
) -> dict[str, Any]:
    """提交售后工单（写操作，带幂等）。"""
    _assert_auth(auth_token)
    start = time.perf_counter()
    result = submit_work_order_service(
        user_id=user_id,
        issue_type=issue_type,
        description=description,
        order_id=order_id,
        caller_role="service",
    )
    _audit(
        "submit_work_order",
        {"user_id": user_id, "issue_type": issue_type, "order_id": order_id},
        result,
        int((time.perf_counter() - start) * 1000),
    )
    return result


def run() -> None:
    mcp.run()


if __name__ == "__main__":
    run()

