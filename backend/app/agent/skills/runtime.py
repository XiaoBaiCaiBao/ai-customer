from __future__ import annotations

import json

from langchain_core.callbacks.manager import adispatch_custom_event
from langchain_core.messages import AIMessage, HumanMessage

from app.agent.skills.registry import get_default_skill_id, get_skill
from app.agent.state import AgentState
from app.llm import get_llm
from app.mcp.client import MCPClientError, call_mcp_tool
from app.message_utils import get_message_text

MAX_TASKS = 6

REPLY_NOT_FOUND_MSG = "不好意思，未查询到近3日您的订单呢，如果超过3日请提供一下大概购买时间或订单号，我再帮您查一下～"

ISSUE_TYPE_BY_ASSET = {
    "vip_monthly": "月卡未到账",
    "vip_weekly": "周卡未到账",
    "coin": "回声贝未到账",
    "回声贝": "回声贝未到账",
    "月卡": "月卡未到账",
    "周卡": "周卡未到账",
}


def _todo_response(state: AgentState, memory: dict, message: str) -> dict:
    return {
        "dialog_state": memory,
        "messages": [AIMessage(content=message)],
        "intent": state.get("intent", "unknown_respond"),
        "confidence": state.get("confidence", 0.0),
        "route": "skills",
        "rag_results": [],
        "needs_clarification": False,
        "clarify_question": "",
    }


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
    resolved_tool_name, params = _build_tool_call(tool_name, memory, user_id)
    try:
        return await call_mcp_tool(resolved_tool_name, params)
    except MCPClientError as e:
        return {"error": str(e)}


def _branch_order_search(api_result: dict) -> tuple[str, str]:
    if api_result.get("error"):
        return "no_orders", ""

    orders = api_result.get("orders", [])
    if not orders:
        return "no_orders", ""

    def is_paid(order: dict) -> bool:
        status = order.get("status") or order.get("payment_status")
        return str(status).lower() in {"success", "paid"}

    unpaid = [order for order in orders if not is_paid(order)]
    paid = [order for order in orders if is_paid(order)]

    if unpaid:
        return "has_unpaid", ""
    if len(paid) > 1:
        return "paid_need_confirm", ""
    return "single_paid", paid[0].get("order_id", "")


def _branch_asset_details(api_result: dict) -> tuple[str, str]:
    if api_result.get("error"):
        return "not_found", ""

    diagnosis = api_result.get("diagnosis")
    if isinstance(diagnosis, dict) and diagnosis.get("status") == "abnormal":
        return "not_found", ""
    if diagnosis == "delivery_callback_failed":
        return "not_found", ""

    assets = api_result.get("assets") or []
    abnormal_assets = [
        asset for asset in assets
        if asset.get("status") in {"abnormal", "not_delivered"}
    ]
    if abnormal_assets:
        return "not_found", ""

    stamina = api_result.get("stamina_current")
    if stamina is not None and stamina > 0:
        return "normal_delivery", str(stamina)

    active_asset = next((asset for asset in assets if asset.get("balance")), None)
    if active_asset:
        return "normal_delivery", str(active_asset.get("balance"))

    return "not_found", ""


async def run_skills_node(state: AgentState) -> dict:
    query = state.get("rewrite_query") or get_message_text(state["messages"][-1])
    user_id = state.get("user_id", "demo_user_001")
    memory = state.get("dialog_state", {}).copy()
    memory.setdefault("user_query", query)

    default_skill_id = get_default_skill_id(state.get("intent"))
    skill_id = memory.get("_skill_id", default_skill_id)
    skill = get_skill(skill_id)
    if not skill:
        return _todo_response(
            state,
            memory,
            f"未找到 Skill：{skill_id}。请先在 backend/app/agent/skills/registry.py 注册。",
        )

    memory["_skill_id"] = skill_id
    if skill.get("authoring_status") != "ready":
        return _todo_response(
            state,
            memory,
            skill.get("todo_message") or f"{skill_id} Skill 还没写完，请到 backend/app/agent/skills/ 下补齐。",
        )

    current_task_id = memory.pop("_current_task", skill["start_task"])
    llm = get_llm()
    task_count = 0
    final_reply: str | None = None
    observations: list[str] = []

    while current_task_id and task_count < MAX_TASKS:
        task_count += 1
        task = skill["tasks"].get(current_task_id)

        if current_task_id == "reply_not_found":
            final_reply = REPLY_NOT_FOUND_MSG
            break
        if not task:
            break

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

        if tool_type == "code":
            required = task.get("required_slots", [])
            missing = [slot for slot in required if not memory.get(slot)]
            if missing:
                final_reply = task.get("clarify_msg", "请提供更多信息。")
                memory["_current_task"] = current_task_id
                next_task_id = None
            else:
                next_task_id = branches.get("complete")

            obs = "槽位齐全" if not missing else f"缺失槽位：{missing}"
            observations.append(f"[{current_task_id}] {obs}")

        elif tool_type == "llm":
            prompt_tpl = task.get("prompt_template", "")
            prompt = prompt_tpl.format(
                **{key: memory.get(key, "") for key in memory},
                observation="\n".join(observations),
            )
            llm_response = await llm.ainvoke([HumanMessage(content=prompt)])
            llm_output = llm_response.content.strip()

            write_key = task.get("memory_write")
            if write_key:
                memory[write_key] = llm_output

            observations.append(f"[{current_task_id}] LLM 输出：{llm_output}")
            next_task_id = branches.get("unknown" if llm_output == "unknown" else "ok")

        elif tool_type == "api":
            tool_name = task.get("tool_name", "")
            mcp_tool_name, mcp_arguments = _build_tool_call(tool_name, memory, user_id)
            api_result = await _call_api(tool_name, memory, user_id)
            branch_key = ""

            if tool_name == "order_search":
                branch_key, order_id = _branch_order_search(api_result)
                if order_id:
                    memory["order_id"] = order_id
                obs = f"订单查询结果：{branch_key}，{json.dumps(api_result, ensure_ascii=False)[:200]}"
                if branch_key == "has_unpaid":
                    memory["_pending_reply_hint"] = "has_unpaid_orders"
                    next_task_id = branches.get("has_unpaid", "T6")
                elif branch_key == "paid_need_confirm":
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
                next_task_id = branches.get("ok")

            else:
                obs = f"API 调用：{json.dumps(api_result, ensure_ascii=False)[:200]}"
                next_task_id = list(branches.values())[0] if branches else None

            observations.append(f"[{current_task_id}] {obs}")
            await adispatch_custom_event(
                "tool_call",
                {
                    "node": "skills",
                    "skill_id": skill_id,
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

        elif tool_type == "reply":
            prompt_tpl = task.get("prompt_template", "请根据以下信息生成回复：{observation}")
            fill_ctx = {
                **memory,
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
            next_task_id = None

        current_task_id = next_task_id

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
