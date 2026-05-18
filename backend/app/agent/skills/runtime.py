from __future__ import annotations

import json

from langchain_core.callbacks.manager import adispatch_custom_event
from langchain_core.messages import AIMessage, HumanMessage

from app.agent.json_output import ainvoke_json
from app.agent.skills.registry import get_default_skill_id, get_skill
from app.agent.state import AgentState
from app.llm import get_llm
from app.mcp.client import MCPClientError, call_mcp_tool
from app.message_utils import build_multimodal_prompt, get_message_image_urls, get_message_text
from pydantic import BaseModel, Field

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

CHAT_QUALITY_CONFIRM_WORDS = {"确认", "可以", "提交", "对", "是", "没错", "好的", "好", "嗯", "ok", "OK"}
CHAT_QUALITY_HIGH_PRIORITY_TYPES = {"chain_of_thought_leak", "system_or_code_leak"}


class ChatQualitySlots(BaseModel):
    issue_type: str = Field(description="聊天质量问题类型枚举")
    occurrence_time: str | None = Field(default="", description="问题发生时间")
    affected_character: str | None = Field(default="", description="涉及角色名")
    evidence_summary: str = Field(description="异常表现摘要")
    user_expected_behavior: str | None = Field(default="", description="用户期待的正常表现")
    needs_clarification: bool = Field(description="是否缺少发生时间或有效证据")
    clarify_question: str = Field(default="", description="需要追问用户的一个简短问题")


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
        resolved_tool_name = "user_order_search"
        params = {"user_id": user_id}
        if memory.get("assets_type") in {"vip_monthly", "vip_weekly", "coin"}:
            params["asset_type"] = memory["assets_type"]

    elif tool_name == "asset_details_list":
        resolved_tool_name = "assets_flow_search"
        params = {"user_id": user_id}
        if memory.get("assets_type"):
            params["asset_type"] = memory["assets_type"]

    elif tool_name == "word_order_submission":
        resolved_tool_name = "word_order_submission"
        params = {
            "user_id": user_id,
            "issue_type": ISSUE_TYPE_BY_ASSET.get(memory.get("assets_type"), "虚拟资产未到账"),
            "work_order_type": "bug",
            "category": "bug提工单",
            "description": memory.get("user_query", "用户反馈购买后未到账"),
            "order_id": memory.get("order_id", ""),
        }

    elif tool_name == "chat_quality_work_order":
        resolved_tool_name = "word_order_submission"
        params = {
            "user_id": user_id,
            "issue_type": "聊天质量反馈",
            "intent": "chat_quality_feedback",
            "work_order_type": "content_quality",
            "category": "内容回复质量问题",
            "description": memory.get("feedback_content") or memory.get("evidence_summary") or memory.get("user_query", ""),
            "occurrence_time": memory.get("occurrence_time", ""),
            "attachments": memory.get("attachments", []),
            "priority": memory.get("priority", "normal"),
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


def _is_chat_quality_confirmation(text: str) -> bool:
    normalized = "".join(
        ch for ch in text.strip().lower()
        if ch not in " \t\r\n，,。.!！?？~～"
    )
    if not normalized or normalized.startswith(("不", "别", "先别", "不用")):
        return False
    confirm_prefixes = ("对", "是", "是的", "是这样", "没错", "可以", "确认", "提交", "好的", "好", "嗯", "ok")
    return (
        normalized in {word.lower() for word in CHAT_QUALITY_CONFIRM_WORDS}
        or normalized.startswith(confirm_prefixes)
        or any(word in normalized for word in ("确认提交", "帮我提交", "可以提交"))
    )


def _chat_quality_priority(issue_type: str, query: str) -> str:
    if issue_type in CHAT_QUALITY_HIGH_PRIORITY_TYPES:
        return "high"
    if any(keyword in query for keyword in ("思维链", "prompt", "系统", "代码", "json", "JSON", "工具调用", "底层")):
        return "high"
    return "normal"


def _chat_quality_confirmation_message(memory: dict) -> str:
    character = memory.get("affected_character") or "未提到"
    occurrence_time = memory.get("occurrence_time") or "未提供"
    return (
        "我先帮你整理一下这次聊天质量反馈：\n"
        f"- 问题类型：{memory.get('issue_type_label') or memory.get('issue_type') or '聊天质量异常'}\n"
        f"- 发生时间：{occurrence_time}\n"
        f"- 涉及角色：{character}\n"
        f"- 异常表现：{memory.get('evidence_summary') or memory.get('user_query', '')}\n\n"
        "你确认后，我就帮你提交给相关同学处理。"
    )


async def _extract_chat_quality_slots(query: str, state: AgentState, memory: dict) -> ChatQualitySlots:
    prompt = f"""你是 BOU 客服的聊天质量反馈信息整理助手。
请根据用户输入和可能的图片，提取聊天质量反馈工单需要的信息。

问题类型只能输出以下枚举之一：
- repeated_reply：回复重复、循环、连续复读
- truncated_reply：回复被截断、没说完、半句话结束
- chain_of_thought_leak：暴露思考过程、推理过程、分析步骤、隐藏思维链
- system_or_code_leak：暴露 prompt、系统消息、JSON、代码、工具调用、底层实现
- subject_confusion：主语错乱、角色和用户身份混淆、说话人混乱
- memory_issue：遗忘上下文、记忆丢失、与前文矛盾
- persona_drift：人设偏移、不符合角色设定或语气
- other_model_anomaly：其他大模型输出异常

如果缺少发生时间或有效证据，needs_clarification 为 true，并只给一个简短具体的问题。
如果用户文字或图片已经足够说明异常，不要强行要求截图。

已有槽位：
{memory}

用户输入：
{query}

只输出 JSON，字段为：
issue_type, occurrence_time, affected_character, evidence_summary, user_expected_behavior, needs_clarification, clarify_question
"""
    return await ainvoke_json(get_llm(), [build_multimodal_prompt(prompt, state["messages"][-1])], ChatQualitySlots)


async def _run_chat_quality_feedback_skill(state: AgentState) -> dict:
    query = state.get("rewrite_query") or get_message_text(state["messages"][-1])
    user_id = state.get("user_id", "demo_user_001")
    memory = state.get("dialog_state", {}).copy()
    memory["_skill_id"] = "chat_quality_feedback"
    memory.setdefault("user_query", query)

    if memory.get("_awaiting_chat_quality_confirmation"):
        if not _is_chat_quality_confirmation(query):
            memory["_awaiting_chat_quality_confirmation"] = False
        else:
            api_result = await _call_api("chat_quality_work_order", memory, user_id)
            ticket_id = api_result.get("ticket_id") or (api_result.get("work_order") or {}).get("ticket_id", "")
            memory["ticket_id"] = ticket_id
            memory["_awaiting_chat_quality_confirmation"] = False
            await adispatch_custom_event(
                "tool_call",
                {
                    "node": "skills",
                    "skill_id": "chat_quality_feedback",
                    "task_id": "submit",
                    "task_purpose": "提交内容回复质量问题工单",
                    "tool_name": "word_order_submission",
                    "logical_tool_name": "chat_quality_work_order",
                    "arguments": _build_tool_call("chat_quality_work_order", memory, user_id)[1],
                    "result": api_result,
                    "success": not bool(api_result.get("error")),
                },
            )
            if api_result.get("error"):
                final_reply = (
                    "抱歉，我这边暂时没能把反馈提交到后台工单系统。"
                    "你的问题信息我已经整理好了，但现在不能算提交成功，需要后台工单接口恢复或补齐配置后再提交。"
                )
            else:
                suffix = f"工单号是 {ticket_id}。" if ticket_id else "已经提交给相关同学了。"
                final_reply = (
                    f"抱歉让你遇到这种出戏的体验，我已经帮你反馈了，{suffix}"
                    "谢谢你把这个问题告诉我们，这类 badcase 对后续优化很有帮助。"
                )
            return {
                "dialog_state": memory,
                "messages": [AIMessage(content=final_reply)],
                "intent": "chat_quality_feedback",
                "confidence": state.get("confidence", 0.0),
                "route": "skills",
                "rag_results": [],
                "needs_clarification": False,
                "clarify_question": "",
            }

    try:
        slots = await _extract_chat_quality_slots(query, state, memory)
    except RuntimeError as exc:
        error_text = str(exc)
        if "429" in error_text or "SetLimitExceeded" in error_text or "TooManyRequests" in error_text:
            return _todo_response(
                state,
                memory,
                (
                    "抱歉，这次没有提交成功：当前模型服务触发了额度限制，"
                    "我没法继续整理这条聊天质量反馈。请稍后再试，或让管理员调整模型额度/关闭安全体验限制后再提交。"
                ),
            )
        raise
    memory.update({
        "issue_type": slots.issue_type,
        "issue_type_label": {
            "repeated_reply": "回复重复",
            "truncated_reply": "回复截断",
            "chain_of_thought_leak": "思维链泄露",
            "system_or_code_leak": "prompt/代码/系统信息泄露",
            "subject_confusion": "主语错乱",
            "memory_issue": "记忆丢失",
            "persona_drift": "人设偏移",
            "other_model_anomaly": "其他大模型异常",
        }.get(slots.issue_type, "聊天质量异常"),
        "occurrence_time": slots.occurrence_time or "",
        "affected_character": slots.affected_character or "",
        "evidence_summary": slots.evidence_summary,
        "user_expected_behavior": slots.user_expected_behavior or "",
        "attachments": get_message_image_urls(state["messages"][-1]),
        "priority": _chat_quality_priority(slots.issue_type, query),
    })
    memory["feedback_content"] = (
        f"用户反馈聊天质量问题：{memory['issue_type_label']}。"
        f"发生时间：{memory.get('occurrence_time') or '未提供'}。"
        f"涉及角色：{memory.get('affected_character') or '未提到'}。"
        f"异常表现：{memory.get('evidence_summary') or query}"
    )

    if slots.needs_clarification and slots.clarify_question:
        memory["_current_task"] = "collect_chat_quality_info"
        final_reply = slots.clarify_question
        needs_clarification = True
    else:
        memory["_awaiting_chat_quality_confirmation"] = True
        final_reply = _chat_quality_confirmation_message(memory)
        needs_clarification = True

    return {
        "dialog_state": memory,
        "messages": [AIMessage(content=final_reply)],
        "intent": "chat_quality_feedback",
        "confidence": state.get("confidence", 0.0),
        "route": "skills",
        "rag_results": [],
        "needs_clarification": needs_clarification,
        "clarify_question": final_reply,
    }


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

    asset = api_result.get("asset")
    if isinstance(asset, dict):
        status = asset.get("status")
        balance = asset.get("balance")
        if status in {"abnormal", "not_delivered"}:
            return "not_found", ""
        if balance is not None and balance > 0:
            return "normal_delivery", str(balance)

    details = api_result.get("details")
    if isinstance(details, list) and details:
        total_granted = sum(
            item.get("amount", 0)
            for item in details
            if isinstance(item, dict) and item.get("change_type") == "grant"
        )
        return "normal_delivery", str(total_granted) if total_granted else str(len(details))

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
    if skill_id == "chat_quality_feedback":
        return await _run_chat_quality_feedback_skill(state)

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

            elif tool_name == "word_order_submission":
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
