from __future__ import annotations

from datetime import datetime
from typing import Any


MOCK_USERS: dict[str, dict[str, Any]] = {
    "user_1001": {
        "profile": {
            "user_id": "user_1001",
            "nickname": "小波",
            "level": 18,
            "registered_at": "2025-09-12T10:22:31+08:00",
        },
        "assets": {
            "stamina": {
                "asset_id": "asset_stamina",
                "asset_type": "stamina",
                "display_name": "体力",
                "balance": 0,
                "unit": "点",
                "status": "abnormal",
                "updated_at": "2026-04-23T09:20:10+08:00",
            },
            "monthly_card": {
                "asset_id": "asset_monthly_card",
                "asset_type": "membership",
                "display_name": "BOU月卡",
                "active": False,
                "expire_at": None,
                "status": "not_delivered",
                "updated_at": "2026-04-23T09:20:10+08:00",
            },
            "echo_beans": {
                "asset_id": "asset_echo_beans",
                "asset_type": "currency",
                "display_name": "回声贝",
                "balance": 268,
                "unit": "个",
                "status": "normal",
                "updated_at": "2026-04-22T21:02:45+08:00",
            },
        },
        "asset_details": {
            "asset_stamina": [
                {
                    "change_id": "AST_90001",
                    "change_type": "consume",
                    "amount": -20,
                    "reason": "生成图片任务",
                    "related_order_id": None,
                    "created_at": "2026-04-23T08:40:09+08:00",
                },
                {
                    "change_id": "AST_90002",
                    "change_type": "system_adjustment",
                    "amount": 0,
                    "reason": "月卡权益待下发，未增加每日体力",
                    "related_order_id": "ORD_20260423_1001",
                    "created_at": "2026-04-23T09:20:10+08:00",
                },
            ],
            "asset_monthly_card": [
                {
                    "change_id": "AST_90003",
                    "change_type": "purchase_pending",
                    "amount": 1,
                    "reason": "支付成功，发货回调超时",
                    "related_order_id": "ORD_20260423_1001",
                    "created_at": "2026-04-23T09:20:10+08:00",
                }
            ],
            "asset_echo_beans": [
                {
                    "change_id": "AST_90004",
                    "change_type": "grant",
                    "amount": 68,
                    "reason": "活动奖励",
                    "related_order_id": None,
                    "created_at": "2026-04-22T21:02:45+08:00",
                }
            ],
        },
        "orders": [
            {
                "order_id": "ORD_20260423_1001",
                "product_id": "prod_monthly_card_001",
                "product_name": "BOU月卡",
                "product_type": "monthly_card",
                "amount": 30.0,
                "currency": "CNY",
                "payment_status": "paid",
                "delivery_status": "callback_timeout",
                "paid_at": "2026-04-23T09:18:42+08:00",
                "updated_at": "2026-04-23T09:20:10+08:00",
            },
            {
                "order_id": "ORD_20260420_8842",
                "product_id": "prod_echo_beans_068",
                "product_name": "68回声贝",
                "product_type": "echo_beans",
                "amount": 6.0,
                "currency": "CNY",
                "payment_status": "paid",
                "delivery_status": "delivered",
                "paid_at": "2026-04-20T20:11:04+08:00",
                "updated_at": "2026-04-20T20:11:09+08:00",
            },
        ],
    },
    "user_1002": {
        "profile": {
            "user_id": "user_1002",
            "nickname": "阿辰",
            "level": 7,
            "registered_at": "2026-01-03T15:01:12+08:00",
        },
        "assets": {
            "stamina": {
                "asset_id": "asset_stamina",
                "asset_type": "stamina",
                "display_name": "体力",
                "balance": 120,
                "unit": "点",
                "status": "normal",
                "updated_at": "2026-04-23T07:35:12+08:00",
            },
            "weekly_card": {
                "asset_id": "asset_weekly_card",
                "asset_type": "membership",
                "display_name": "BOU周卡",
                "active": True,
                "expire_at": "2026-04-28T23:59:59+08:00",
                "status": "normal",
                "updated_at": "2026-04-21T12:06:33+08:00",
            },
        },
        "asset_details": {
            "asset_stamina": [
                {
                    "change_id": "AST_91001",
                    "change_type": "daily_grant",
                    "amount": 60,
                    "reason": "周卡每日权益",
                    "related_order_id": "ORD_20260421_7741",
                    "created_at": "2026-04-23T07:35:12+08:00",
                }
            ],
            "asset_weekly_card": [
                {
                    "change_id": "AST_91002",
                    "change_type": "activate",
                    "amount": 1,
                    "reason": "购买周卡后自动激活",
                    "related_order_id": "ORD_20260421_7741",
                    "created_at": "2026-04-21T12:06:33+08:00",
                }
            ],
        },
        "orders": [
            {
                "order_id": "ORD_20260421_7741",
                "product_id": "prod_weekly_card_001",
                "product_name": "BOU周卡",
                "product_type": "weekly_card",
                "amount": 12.0,
                "currency": "CNY",
                "payment_status": "paid",
                "delivery_status": "delivered",
                "paid_at": "2026-04-21T12:06:10+08:00",
                "updated_at": "2026-04-21T12:06:33+08:00",
            }
        ],
    },
}


WORK_ORDERS: dict[str, dict[str, Any]] = {}


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
