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
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.callbacks.manager import adispatch_custom_event
from app.agent.state import AgentState
from app.llm import get_llm
from app.message_utils import get_message_text
from app.prompts.skills import (
    SKILL_REGISTRY,
    AFTERSALES_DEFAULT_SKILL,
    REPLY_NOT_FOUND_MSG,
)
from app.agent.tools import TOOLS_MAP

MAX_TASKS = 6  # 单次对话最多执行的 Task 数，防止死循环


# ─── 工具调用适配层 ────────────────────────────────────────────────────────────

async def _call_api(tool_name: str, memory: dict, user_id: str) -> dict:
    """
    根据 tool_name 组装参数并调用对应工具。
    各工具的参数从 memory 中读取，缺省值用 user_id 兜底。
    """
    params: dict = {}
    resolved_tool_name = tool_name

    if tool_name == "order_search":
        # 复用 get_user_recent_orders 作为 order_search
        resolved_tool_name = "get_user_recent_orders"
        params = {"user_id": user_id}

    elif tool_name == "asset_details_list":
        # 复用 check_user_assets（后续可替换为真实接口）
        resolved_tool_name = "check_user_assets"
        params = {"user_id": user_id}

    elif tool_name == "submit_work_order":
        resolved_tool_name = "submit_work_order"
        params = {
            "user_id": user_id,
            "issue_type": memory.get("assets_type", "虚拟资产未到账"),
            "description": memory.get("user_query", "用户反馈购买后未到账"),
            "order_id": memory.get("order_id", ""),
        }

    else:
        params = {"user_id": user_id}

    fn = TOOLS_MAP.get(resolved_tool_name)
    if not fn:
        return {"error": f"未知工具: {tool_name}"}

    try:
        raw = await fn.ainvoke(params)
        return json.loads(raw) if isinstance(raw, str) else raw
    except Exception as e:
        return {"error": str(e)}


# ─── 分支判断：根据 API 返回决定走哪个 branch ────────────────────────────────

def _branch_order_search(api_result: dict) -> tuple[str, str]:
    """返回 (branch_key, order_id_or_empty)"""
    orders = api_result.get("orders", [])
    if not orders:
        return "no_orders", ""

    unpaid = [o for o in orders if o.get("status") not in ("Success", "Paid")]
    paid = [o for o in orders if o.get("status") in ("Success", "Paid")]

    if unpaid:
        return "has_unpaid", ""
    if len(paid) > 1:
        return "paid_need_confirm", ""
    return "single_paid", paid[0].get("order_id", "")


def _branch_asset_details(api_result: dict) -> tuple[str, str]:
    """返回 (branch_key, assets_amount_or_empty)"""
    if api_result.get("error"):
        return "not_found", ""
    # delivery_callback_failed 表示权益未下发
    if api_result.get("diagnosis") == "delivery_callback_failed":
        return "not_found", ""
    # 有 stamina_current 说明正常发放
    stamina = api_result.get("stamina_current")
    if stamina is not None and stamina > 0:
        return "normal_delivery", str(stamina)
    return "not_found", ""


# ─── 主节点 ─────────────────────────────────────────────────────────────────

async def skills_node(state: AgentState) -> dict:
    query = state.get("rewritten_query") or get_message_text(state["messages"][-1])
    user_id = state.get("user_id", "demo_user_001")
    memory = state.get("dialog_state", {}).copy()
    memory.setdefault("user_query", query)

    # 确定本次使用的 Skill（当前只有 asset_recharge_issue；后续可按子意图扩展）
    skill_id = memory.get("_skill_id", AFTERSALES_DEFAULT_SKILL)
    sop = SKILL_REGISTRY.get(skill_id)
    if not sop:
        return {"messages": [AIMessage(content="暂不支持该类型的售后处理，请联系人工客服。")]}

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
            api_result = await _call_api(tool_name, memory, user_id)

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
                ticket_id = api_result.get("ticket_id", "")
                memory["ticket_id"] = ticket_id
                obs = f"工单提交：{ticket_id}"
                next_task_id = branches.get("ok", "T6")

            else:
                obs = f"API 调用：{json.dumps(api_result, ensure_ascii=False)[:200]}"
                next_task_id = list(branches.values())[0] if branches else None

            observations.append(f"[{current_task_id}] {obs}")

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
        "skills_result": {"observations": observations, "reply": final_reply},
        "messages": [AIMessage(content=final_reply)],
    }
