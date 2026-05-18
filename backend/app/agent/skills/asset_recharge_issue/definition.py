from __future__ import annotations

from app.agent.skills.types import SkillDef, TaskDef


SKILL: SkillDef = {
    "skill_id": "asset_recharge_issue",
    "name": "虚拟资产购买未到账",
    "description": "处理用户购买回声贝、周卡会员、月卡会员等虚拟资产后未到账的售后问题",
    "authoring_status": "ready",
    "start_task": "T1",
    "tasks": {
        "T1": TaskDef(
            purpose="检查并补全槽位",
            tool_type="code",
            required_slots=["assets_type"],
            optional_slots=["timerange"],
            clarify_msg="请问您购买的资产是：1 周卡，2 月卡，3 回声贝？回复数字即可",
            memory_read=["user_id", "user_query", "assets_type", "timerange"],
            branches={
                "complete": "T2",
                "missing": "clarify",
            },
        ),
        "T2": TaskDef(
            purpose="资产类别映射",
            tool_type="llm",
            memory_read=["assets_type"],
            memory_write="assets_type",
            prompt_template="""你是一个字段标准化助手。
用户描述的资产类型是：{assets_type}

请将其映射为以下标准枚举值之一（只输出枚举值，不要任何额外文字）：
- vip_monthly   （月卡会员）
- vip_weekly    （周卡会员）
- coin          （回声贝）

若无法匹配，输出 unknown。""",
            branches={
                "ok": "T3",
                "unknown": "T1",
            },
        ),
        "T3": TaskDef(
            purpose="订单状态查询",
            tool_type="api",
            tool_name="order_search",
            memory_read=["user_id", "timerange", "assets_type"],
            memory_write="order_id",
            branches={
                "has_unpaid": "T6",
                "paid_need_confirm": "clarify",
                "single_paid": "T4",
                "no_orders": "reply_not_found",
            },
        ),
        "T4": TaskDef(
            purpose="查询资产流水",
            tool_type="api",
            tool_name="asset_details_list",
            memory_read=["user_id", "order_id"],
            memory_write="assets_amount",
            branches={
                "normal_delivery": "T6",
                "not_found": "T5",
            },
        ),
        "T5": TaskDef(
            purpose="提交售后工单",
            tool_type="api",
            tool_name="submit_work_order",
            memory_read=["user_id", "assets_type", "order_id"],
            branches={
                "ok": "T6",
            },
        ),
        "T6": TaskDef(
            purpose="生成回复",
            tool_type="reply",
            memory_read=["assets_type", "order_id", "assets_amount"],
            prompt_template="""你是 BOU 游戏客服，请根据以下信息生成一条给用户的回复。
要求：专业、有温度、简洁，符合「听劝、陪伴」人设，不超过150字。

用户问题：{user_query}
当前资产类型：{assets_type}
关联订单：{order_id}
资产流水金额/数量：{assets_amount}
本轮处理摘要：{observation}""",
        ),
    },
}
