"""
节点：Skills Agent（SOP 执行引擎）

Skills 是预写的 SOP（标准作业流程），不是 ReAct：
- 每次 skills_node 被调用时，从当前 Task 继续执行 SOP
- 渐进式加载：每个 Task 启动时才加载自己的 prompt，不一次性塞入全部 SOP
- 流式事件（adispatch_custom_event）在每步完成时推送，前端可实时展示进度

执行循环：
  load Task → execute（code/llm/api）→ observe → branch → load next Task → …
当遇到 clarify / reply_not_found / reply Task（T6）时结束本轮，等待用户输入或输出最终回复。
"""

import json
from typing import Literal, TypedDict
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.callbacks.manager import adispatch_custom_event
from app.agent.state import AgentState
from app.llm import get_llm
from app.message_utils import get_message_text
from app.mcp.client import MCPClientError, call_mcp_tool

MAX_TASKS = 6  # 单次对话最多执行的 Task 数，防止死循环


class TaskDef(TypedDict, total=False):
    purpose: str
    tool_type: Literal["code", "llm", "api", "reply"]
    tool_name: str
    prompt_template: str
    required_slots: list[str]
    optional_slots: list[str]
    clarify_msg: str
    memory_read: list[str]
    memory_write: str
    branches: dict[str, str]


ASSET_NOT_ARRIVED_SOP: dict = {
    "skill_id": "asset_recharge_issue",
    "name": "虚拟资产购买未到账",
    "description": "处理用户购买回声贝、周卡会员、月卡会员等虚拟资产后未到账的售后问题",
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

REPLY_NOT_FOUND_MSG = "不好意思，未查询到近3日您的订单呢，如果超过3日请提供一下大概购买时间或订单号，我再帮您查一下～"

SKILL_REGISTRY: dict[str, dict] = {
    "asset_recharge_issue": ASSET_NOT_ARRIVED_SOP,
}

AFTERSALES_DEFAULT_SKILL = "asset_recharge_issue"


ISSUE_TYPE_BY_ASSET = {
    "vip_monthly": "月卡未到账",
    "vip_weekly": "周卡未到账",
    "coin": "回声贝未到账",
    "回声贝": "回声贝未到账",
    "月卡": "月卡未到账",
    "周卡": "周卡未到账",
}


# ─── MCP 工具调用适配层 ────────────────────────────────────────────────────────

def _build_tool_call(tool_name: str, memory: dict, user_id: str) -> tuple[str, dict]:
    params: dict = {}
    resolved_tool_name = tool_name

    if tool_name == "order_search":
        resolved_tool_name = "get_user_recent_orders"
        params = {"user_id": user_id}
        if memory.get("assets_type") in {"vip_monthly", "vip_weekly", "coin"}:
            params["asset_type"] = memory["assets_type"]

    elif tool_name == "asset_details_list":
        resolved_tool_name = "get_user_details"
        params = {"user_id": user_id}

    elif tool_name == "submit_work_order":
        resolved_tool_name = "submit_work_order"
        params = {
            "user_id": user_id,
            "issue_type": ISSUE_TYPE_BY_ASSET.get(memory.get("assets_type"), "虚拟资产未到账"),
            "description": memory.get("user_query", "用户反馈购买后未到账"),
            "order_id": memory.get("order_id", ""),
        }

    else:
        params = {"user_id": user_id}

    return resolved_tool_name, params


async def _call_api(tool_name: str, memory: dict, user_id: str) -> dict:
    """
    根据 tool_name 组装参数并调用对应工具。
    各工具的参数从 memory 中读取，缺省值用 user_id 兜底。
    """
    resolved_tool_name, params = _build_tool_call(tool_name, memory, user_id)
    try:
        return await call_mcp_tool(resolved_tool_name, params)
    except MCPClientError as e:
        return {"error": str(e)}


# ─── 分支判断：根据 API 返回决定走哪个 branch ────────────────────────────────

def _branch_order_search(api_result: dict) -> tuple[str, str]:
    """返回 (branch_key, order_id_or_empty)"""
    if api_result.get("error"):
        return "no_orders", ""

    orders = api_result.get("orders", [])
    if not orders:
        return "no_orders", ""

    def is_paid(order: dict) -> bool:
        status = order.get("status") or order.get("payment_status")
        return str(status).lower() in {"success", "paid"}

    unpaid = [o for o in orders if not is_paid(o)]
    paid = [o for o in orders if is_paid(o)]

    if unpaid:
        return "has_unpaid", ""
    if len(paid) > 1:
        return "paid_need_confirm", ""
    return "single_paid", paid[0].get("order_id", "")


def _branch_asset_details(api_result: dict) -> tuple[str, str]:
    """返回 (branch_key, assets_amount_or_empty)"""
    if api_result.get("error"):
        return "not_found", ""

    diagnosis = api_result.get("diagnosis")
    if isinstance(diagnosis, dict) and diagnosis.get("status") == "abnormal":
        return "not_found", ""

    # delivery_callback_failed 表示权益未下发
    if diagnosis == "delivery_callback_failed":
        return "not_found", ""

    assets = api_result.get("assets") or []
    abnormal_assets = [
        asset for asset in assets
        if asset.get("status") in {"abnormal", "not_delivered"}
    ]
    if abnormal_assets:
        return "not_found", ""

    # 有 stamina_current 说明正常发放
    stamina = api_result.get("stamina_current")
    if stamina is not None and stamina > 0:
        return "normal_delivery", str(stamina)

    active_asset = next((asset for asset in assets if asset.get("balance")), None)
    if active_asset:
        return "normal_delivery", str(active_asset.get("balance"))

    return "not_found", ""


# ─── 主节点 ─────────────────────────────────────────────────────────────────

async def skills_node(state: AgentState) -> dict:
    query = state.get("rewrite_query") or get_message_text(state["messages"][-1])
    user_id = state.get("user_id", "demo_user_001")
    memory = state.get("dialog_state", {}).copy()
    memory.setdefault("user_query", query)

    # 确定本次使用的 Skill（当前只有 asset_recharge_issue；后续可按子意图扩展）
    skill_id = memory.get("_skill_id", AFTERSALES_DEFAULT_SKILL)
    sop = SKILL_REGISTRY.get(skill_id)
    if not sop:
        final_reply = "暂不支持该类型的售后处理，请联系人工客服。"
        return {
            "messages": [AIMessage(content=final_reply)],
            "intent": state.get("intent", "after_sales_issue"),
            "confidence": state.get("confidence", 0.0),
            "route": "skills",
            "dialog_state": memory,
            "rag_results": [],
            "needs_clarification": False,
            "clarify_question": "",
        }

    # 从上次中断的 Task 继续，或从起始 Task 开始
    current_task_id = memory.pop("_current_task", sop["start_task"])
    memory["_skill_id"] = skill_id

    llm = get_llm()
    task_count = 0
    final_reply: str | None = None
    observations: list[str] = []  # 累积各 Task 的 observation，供 T6 汇总

    while current_task_id and task_count < MAX_TASKS:
        task_count += 1
        task = sop["tasks"].get(current_task_id)

        # ── 内置终止节点 ─────────────────────────────────────────────
        if current_task_id == "reply_not_found":
            final_reply = REPLY_NOT_FOUND_MSG
            break

        if not task:
            break

        # ── 渐进式加载：推送"Task 开始"事件 ─────────────────────────
        await adispatch_custom_event(
            "thinking_step",
            {
                "step_type": "action",
                "step_num": task_count,
                "content": f"[{current_task_id}] {task['purpose']}",
            },
        )

        tool_type = task.get("tool_type")
        branches = task.get("branches", {})
        next_task_id: str | None = None

        # ════════════════════════════════════════════════════════════
        # code：纯规则检查，不调用 LLM
        # ════════════════════════════════════════════════════════════
        if tool_type == "code":
            required = task.get("required_slots", [])
            missing = [s for s in required if not memory.get(s)]

            if missing:
                clarify_msg = task.get("clarify_msg", "请提供更多信息。")
                final_reply = clarify_msg
                # 记录中断位置，下一轮从 T1 重新检查槽位
                memory["_current_task"] = current_task_id
                next_task_id = None
            else:
                next_task_id = branches.get("complete")

            obs = "槽位齐全" if not missing else f"缺失槽位：{missing}"
            observations.append(f"[{current_task_id}] {obs}")

        # ════════════════════════════════════════════════════════════
        # llm：调用 LLM 做推理（渐进加载 Task 专属 prompt）
        # ════════════════════════════════════════════════════════════
        elif tool_type == "llm":
            prompt_tpl = task.get("prompt_template", "")
            prompt = prompt_tpl.format(**{k: memory.get(k, "") for k in memory} | {"observation": "\n".join(observations)})

            llm_response = await llm.ainvoke([HumanMessage(content=prompt)])
            llm_output = llm_response.content.strip()

            write_key = task.get("memory_write")
            if write_key:
                memory[write_key] = llm_output

            obs = f"LLM 输出：{llm_output}"
            observations.append(f"[{current_task_id}] {obs}")

            # 判断分支
            if llm_output == "unknown":
                next_task_id = branches.get("unknown", branches.get("ok"))
            else:
                next_task_id = branches.get("ok")

        # ════════════════════════════════════════════════════════════
        # api：调用外部工具接口
        # ════════════════════════════════════════════════════════════
        elif tool_type == "api":
            tool_name = task.get("tool_name", "")
            mcp_tool_name, mcp_arguments = _build_tool_call(tool_name, memory, user_id)
            api_result = await _call_api(tool_name, memory, user_id)
            branch_key = ""

            # 根据工具名选择对应的分支判断逻辑
            if tool_name == "order_search":
                branch_key, order_id = _branch_order_search(api_result)
                if order_id:
                    memory["order_id"] = order_id
                obs = f"订单查询结果：{branch_key}，{json.dumps(api_result, ensure_ascii=False)[:200]}"

                if branch_key == "has_unpaid":
                    # 告知用户支付状态后跳 T6
                    observations.append(f"[{current_task_id}] {obs}（有未支付订单）")
                    memory["_pending_reply_hint"] = "has_unpaid_orders"
                    next_task_id = branches.get("has_unpaid", "T6")
                elif branch_key == "paid_need_confirm":
                    # 追问哪笔订单，等待用户回复
                    final_reply = "请问您的哪笔订单未到账？请提供一下订单号或购买时间，我帮您核查～"
                    memory["_current_task"] = "T3"
                    next_task_id = None
                else:
                    next_task_id = branches.get(branch_key)

            elif tool_name == "asset_details_list":
                branch_key, assets_amount = _branch_asset_details(api_result)
                if assets_amount:
                    memory["assets_amount"] = assets_amount
                obs = f"资产流水查询：{branch_key}"
                next_task_id = branches.get(branch_key)

            elif tool_name == "submit_work_order":
                ticket_id = api_result.get("ticket_id") or (api_result.get("work_order") or {}).get("ticket_id", "")
                memory["ticket_id"] = ticket_id
                obs = f"工单提交：{ticket_id}"
                next_task_id = branches.get("ok", "T6")

            else:
                obs = f"API 调用：{json.dumps(api_result, ensure_ascii=False)[:200]}"
                next_task_id = list(branches.values())[0] if branches else None

            observations.append(f"[{current_task_id}] {obs}")

            await adispatch_custom_event(
                "tool_call",
                {
                    "node": "skills",
                    "task_id": current_task_id,
                    "task_purpose": task.get("purpose", ""),
                    "tool_name": mcp_tool_name,
                    "logical_tool_name": tool_name,
                    "arguments": mcp_arguments,
                    "result": api_result,
                    "success": not bool(api_result.get("error")),
                    "branch": branch_key,
                    "observation": obs,
                },
            )
            await adispatch_custom_event(
                "thinking_step",
                {
                    "step_type": "observation",
                    "step_num": task_count,
                    "content": obs,
                },
            )

        # ════════════════════════════════════════════════════════════
        # reply：用 LLM 生成最终回复（渐进加载 T6 专属 prompt）
        # ════════════════════════════════════════════════════════════
        elif tool_type == "reply":
            prompt_tpl = task.get("prompt_template", "请根据以下信息生成回复：{observation}")
            fill_ctx = {
                "user_query": memory.get("user_query", ""),
                "assets_type": memory.get("assets_type", ""),
                "order_id": memory.get("order_id", ""),
                "assets_amount": memory.get("assets_amount", ""),
                "ticket_id": memory.get("ticket_id", ""),
                "observation": "\n".join(observations),
            }
            prompt = prompt_tpl.format(**fill_ctx)
            llm_response = await llm.ainvoke([HumanMessage(content=prompt)])
            final_reply = llm_response.content.strip()
            next_task_id = None  # reply 任务后结束

        current_task_id = next_task_id  # type: ignore[assignment]

    if final_reply is None:
        final_reply = "已为您处理完成，如有其他问题请随时告知。"

    await adispatch_custom_event(
        "thinking_step",
        {
            "step_type": "observation",
            "step_num": task_count + 1,
            "content": f"Skills SOP 执行完毕，共 {task_count} 步",
        },
    )

    return {
        "dialog_state": memory,
        "messages": [AIMessage(content=final_reply)],
        "intent": state.get("intent", "after_sales_issue"),
        "confidence": state.get("confidence", 0.0),
        "route": "skills",
        "rag_results": [],
        "needs_clarification": "_current_task" in memory,
        "clarify_question": final_reply if "_current_task" in memory else "",
    }
