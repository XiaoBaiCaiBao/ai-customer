"""
节点: ReAct 推理节点

适用意图: aftersales（售后/账单/资产异常）

使用 ReAct（Reasoning + Acting）范式，循环执行：
  Thought → 分析当前情况，决定下一步
  Action  → 调用工具查询或操作
  Observation → 读取工具返回结果
  ... （重复直到可以给出最终答案）
  Final Answer → 拟人化安抚 + 告知结果

工具列表（MOCK，模拟真实游戏后台）:
  - get_user_recent_orders(user_id)
  - check_user_assets(user_id)
  - trigger_manual_asset_compensation(user_id, item_type)

思考步骤通过 adispatch_custom_event("thinking_step", ...) 实时推送到前端。
"""

import json
import random
import string
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.callbacks.manager import adispatch_custom_event
from langchain_core.tools import tool
from app.agent.state import AgentState
from app.llm import get_llm

# ──────────────────────────────────────────
# Mock 工具定义
# ──────────────────────────────────────────

@tool
def get_user_recent_orders(user_id: str) -> str:
    """查询用户最近的订单列表及状态。返回最近3条订单记录。"""
    mock = {
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
    return json.dumps(mock, ensure_ascii=False)


@tool
def check_user_assets(user_id: str) -> str:
    """查询用户当前资产状态，包括体力值、会员状态等。"""
    mock = {
        "user_id": user_id,
        "stamina_current": 0,
        "stamina_max": 150,
        "monthly_card_active": False,
        "monthly_card_expire": None,
        "diagnosis": "delivery_callback_failed",
        "note": "订单 ORD_2024_10892 扣款成功但发货回调超时，权益未下发",
    }
    return json.dumps(mock, ensure_ascii=False)


@tool
def trigger_manual_asset_compensation(user_id: str, item_type: str) -> str:
    """
    手动触发资产补偿，适用于订单扣款成功但权益未到账的情况。
    item_type 可选: 'monthly_card'（月卡）, 'stamina'（体力值）, 'coins'（积分）
    """
    txn_id = "TXN_" + "".join(random.choices(string.digits, k=10))
    mock = {
        "success": True,
        "transaction_id": txn_id,
        "user_id": user_id,
        "item_type": item_type,
        "items_granted": {
            "stamina": 150,
            "monthly_card_days": 30,
        },
        "message": "补发成功，权益已实时下发",
    }
    return json.dumps(mock, ensure_ascii=False)


TOOLS = [get_user_recent_orders, check_user_assets, trigger_manual_asset_compensation]
TOOLS_MAP = {t.name: t for t in TOOLS}

# ──────────────────────────────────────────
# ReAct 系统提示词
# ──────────────────────────────────────────

REACT_SYSTEM_PROMPT = """你是 BOU 的 AI 客服助手，具备查询游戏后台和执行补偿操作的权限。

你的目标是帮助用户解决售后/账单/资产异常问题。请严格按照以下步骤执行：
1. 先查询订单状态确认是否扣款成功
2. 再检查用户资产确认权益是否到账
3. 如果扣款成功但权益未到账，直接触发补偿
4. 用温暖、有同理心的语气告知用户结果，给予情绪安抚

重要原则：
- 必须先查证再操作，不能猜测
- 如果订单未扣款，不要触发补偿
- 每次工具调用后仔细分析返回结果再决策
- 最终回复要拟人化，提到具体流水号，让用户放心"""


async def react_node(state: AgentState) -> dict:
    query = state.get("rewritten_query") or state["messages"][-1].content
    user_id = state.get("user_id", "demo_user_001")

    llm = get_llm()
    llm_with_tools = llm.bind_tools(TOOLS)

    # 初始化消息链
    messages = [
        SystemMessage(content=REACT_SYSTEM_PROMPT),
        HumanMessage(content=f"用户ID: {user_id}\n用户反馈: {query}"),
    ]

    step_num = 0
    max_iterations = 6  # 防止无限循环

    for iteration in range(max_iterations):
        # 调用 LLM 决策
        response = await llm_with_tools.ainvoke(messages)
        messages.append(response)

        if response.tool_calls:
            # LLM 决定调用工具 → 提取思考文本（tool_calls 前的文字内容）
            thought_text = response.content if isinstance(response.content, str) else ""

            if thought_text.strip():
                step_num += 1
                await adispatch_custom_event(
                    "thinking_step",
                    {
                        "step_type": "thought",
                        "step_num": step_num,
                        "content": thought_text.strip(),
                    },
                )

            # 依次执行每个工具调用
            for tc in response.tool_calls:
                tool_name = tc["name"]
                tool_args = tc["args"]

                # 推送 Action 步骤
                step_num += 1
                args_str = json.dumps(tool_args, ensure_ascii=False)
                await adispatch_custom_event(
                    "thinking_step",
                    {
                        "step_type": "action",
                        "step_num": step_num,
                        "content": f"{tool_name}({args_str})",
                    },
                )

                # 执行工具
                tool_fn = TOOLS_MAP.get(tool_name)
                if tool_fn:
                    try:
                        tool_result = await tool_fn.ainvoke(tool_args)
                    except Exception as e:
                        tool_result = json.dumps({"error": str(e)}, ensure_ascii=False)
                else:
                    tool_result = json.dumps({"error": f"未知工具: {tool_name}"}, ensure_ascii=False)

                # 推送 Observation 步骤
                step_num += 1
                try:
                    parsed = json.loads(tool_result)
                    obs_text = json.dumps(parsed, ensure_ascii=False, indent=None)
                except Exception:
                    obs_text = str(tool_result)[:300]

                await adispatch_custom_event(
                    "thinking_step",
                    {
                        "step_type": "observation",
                        "step_num": step_num,
                        "content": obs_text,
                    },
                )

                # 将工具结果追加到消息链
                messages.append(
                    ToolMessage(content=tool_result, tool_call_id=tc["id"])
                )

        else:
            # 没有工具调用 → LLM 输出最终回复
            step_num += 1
            await adispatch_custom_event(
                "thinking_step",
                {
                    "step_type": "final",
                    "step_num": step_num,
                    "content": "问题已查证完毕，正在组织最终回复…",
                },
            )
            return {
                "messages": [AIMessage(content=response.content)],
                "react_steps": [],
            }

    # 超出最大迭代次数的兜底
    return {
        "messages": [AIMessage(content="非常抱歉，处理过程遇到了一些问题，请稍后再试或联系人工客服～")],
        "react_steps": [],
    }
