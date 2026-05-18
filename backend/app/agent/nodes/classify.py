"""意图识别、轻量 DST 与路由节点。"""

from __future__ import annotations

import json
from typing import Any, get_args

from langchain_core.callbacks.manager import adispatch_custom_event
from langgraph.types import Command
from pydantic import BaseModel, Field

from app.agent.json_output import ainvoke_json
from app.agent.state import AgentState, IntentType, RouteType, TaskAction, TaskStage
from app.llm import get_llm
from app.message_utils import build_multimodal_prompt, get_message_image_urls, get_message_text


INTENT_ROUTE_TABLE: dict[IntentType, RouteType] = {
    # 1-6：知识库
    "usage_guide": "rag",
    "account_issue_consult": "rag",
    "feature_play_consult": "rag",
    "privacy_permission_consult": "rag",
    "activity_consult": "rag",
    "content_safety_consult": "rag",
    # 7：聊天质量反馈，先交给 skills；具体工单提交在 skill/runtime 中处理。
    "chat_quality_feedback": "skills",
    # 9：实时数据查询，交给 MCP/API 工具。
    "data_search": "mcp_tool",
    # 其他意图先走 LLM 兜底，后续明确 SOP 后再接入 skills / MCP / RAG+API。
    "fault_feedback": "chat_respond",
    "pre_sales_consult": "chat_respond",
    "after_sales_issue": "chat_respond",
    "product_suggestion": "chat_respond",
    "product_complaint": "chat_respond",
    "chat_respond": "chat_respond",
    "unknown_respond": "chat_respond",
}


ROUTE_HANDLER: dict[str, str] = {
    "rag": "rag",
    "mcp_tool": "mcp",
    "skills": "skills",
    "chat_respond": "chat",
    "clarify": "chat",
}


UNDERSTAND_TURN_PROMPT = """# Role
你是 BOU 客服 Agent 的意图识别与对话状态追踪节点。
你不回答用户，只输出结构化结果，供后续路由使用。

# Input
- 短期记忆 agent_state：
{agent_state}
- 当前 query：
{query}
- 当前图片列表：
{current_images}

# Intent Taxonomy
只允许输出下列英文意图之一。

1. usage_guide
   使用指南：iOS/安卓下载、海外 Apple ID/切区、充值入口、支付路径。

2. account_issue_consult
   账号问题咨询：预约账号、注册、登录、年龄认证、邮箱验证码、换绑邮箱、账号注销、数据恢复。

3. feature_play_consult
   功能玩法咨询：聊天模式、深夜模式、广场玩法、羁绊值规则、记忆机制、主动发消息机制、真实世界联动、聊天记录查找、已有功能入口。

4. privacy_permission_consult
   隐私权限咨询：定位/城市识别、IP、剪贴板、输入法、隐私协议、权限开关、角色为什么知道现实信息。

5. activity_consult
   线上/线下活动咨询：活动参与条件、投稿平台要求、奖励发放规则、活动截止时间。

6. content_safety_consult
   内容安全策略咨询：发送消息触发风控 toast、角色回复触发感叹号，以及对应处理方式。

7. chat_quality_feedback
   聊天质量反馈：主语错乱、重复、输出截断、大模型胡乱回复、记忆丢失、爆 prompt、爆思维链、底层代码泄露、回复太短/太长、回复不符合角色设定。
   典型例子：回复里爆代码了，中英文夹杂乱码了，反复重复同一句。
   相关槽位：user_id、role、occurrence_time、user_emotion、issue_type、evidence、description。

8. fault_feedback
   故障反馈：页面 error、登不上、卡住、转不出来、白屏/闪退、加载失败、红点消不掉、按钮点不了、充值页异常、特定角色无法回复、网络不稳定。

9. data_search
   实时数据查询：用户查询消费金额、虚拟资产流水、订单、账号状态等实时信息。
   相关槽位：user_id、query_type、asset_type、time_range、order_id。

10. pre_sales_consult
   售前咨询：会员类型区别、月卡/周卡权益、限时折扣、服饰礼包说明。

11. after_sales_issue
   售后问题：已充值但星能/会员/回声贝未到账、月卡赠送星能延迟、订单异常、重复扣费。

12. product_suggestion
   产品建议：明确功能诉求，如能不能出畅聊卡、撤回、重说、聊天记录查找、更换邮箱、增加字数上限、卖谷/周边。

13. product_complaint
   产品吐槽：不满、情绪、价格压力、流失风险，但没有明确可执行功能建议。

14. chat_respond
   其他/闲聊：纯情绪倾诉、日常打招呼、分享日常等非任务导向且与产品业务无关的交流。

unknown_respond
   信息严重不足，无法判断为任何意图。

# Requirements
1. 结合 agent_state 判断当前输入是否在补充未完成任务。
2. 只抽取当前可以确定的槽位，不要编造。
3. 如果必须补充信息才能继续处理，needs_clarification=true，并给出一句具体澄清问题。
4. 如果用户正在确认一个 active_task，且当前输入表达同意/提交/确认，要沿用 active_task 的意图，并把 task.stage 设为 executing。
5. 如果用户补充的是 active_task 缺失的信息，要沿用 active_task 的意图，并把 task.action 设为 update。
6. 如果用户明确取消当前任务，要把 task.action 设为 cancel。
7. 非任务类意图的 task.action 设为 none，task 其他字段用 null 或空对象。
8. 输出 JSON，不要 Markdown，不要多余文字。

# Output
{{
  "intent": "chat_quality_feedback",
  "confidence": 0.95,
  "slots": {{}},
  "needs_clarification": false,
  "clarify_question": null,
  "task": {{
    "action": "start",
    "task_type": "chat_quality_feedback",
    "stage": "executing",
    "slots": {{}},
    "missing_slots": [],
    "pending_action": null
  }}
}}
"""


class TaskUpdateModel(BaseModel):
    action: TaskAction = Field(
        default="none",
        description="任务状态动作：none/start/update/confirm/cancel/complete",
    )
    task_type: IntentType | None = Field(default=None, description="任务类型，通常等于需要执行的业务意图")
    stage: TaskStage | None = Field(default=None, description="任务阶段：collecting/confirming/executing/done")
    slots: dict[str, Any] = Field(default_factory=dict, description="任务槽位增量")
    missing_slots: list[str] = Field(default_factory=list, description="仍缺失的槽位")
    pending_action: dict[str, Any] | None = Field(default=None, description="确认后要执行的动作")


class TurnUnderstandingResult(BaseModel):
    intent: str = Field(description="本轮核心意图")
    confidence: float = Field(ge=0.0, le=1.0, description="意图置信度")
    slots: dict[str, Any] = Field(default_factory=dict, description="本轮提取槽位")
    needs_clarification: bool = Field(default=False, description="是否需要澄清")
    clarify_question: str | None = Field(default=None, description="澄清问题")
    task: TaskUpdateModel = Field(default_factory=TaskUpdateModel, description="任务状态更新")


ALLOWED_INTENTS = set(get_args(IntentType))


def _safe_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _normalize_intent(intent: str) -> IntentType:
    cleaned = (intent or "").strip()
    if cleaned in ALLOWED_INTENTS:
        return cleaned  # type: ignore[return-value]
    return "unknown_respond"


def _route_for_intent(intent: IntentType, needs_clarification: bool, clarify_question: str | None) -> RouteType:
    if needs_clarification or clarify_question:
        return "clarify"
    return INTENT_ROUTE_TABLE.get(intent, "chat_respond")  # type: ignore[return-value]


def _handler_for_route(route: RouteType) -> str:
    return ROUTE_HANDLER.get(route, "chat")


def _active_task_from_dialog_state(dialog_state: dict[str, Any]) -> dict[str, Any] | None:
    active_task = dialog_state.get("active_task")
    if isinstance(active_task, dict):
        return active_task
    return None


def _agent_state_for_prompt(state: AgentState, active_task: dict[str, Any] | None) -> dict[str, Any]:
    dialog_state = state.get("dialog_state", {}) or {}
    return {
        "user_id": state.get("user_id"),
        "session_id": state.get("session_id"),
        "active_task": active_task,
        "dialog_state": dialog_state,
        "rewrite_query": state.get("rewrite_query") or dialog_state.get("rewrite_query"),
    }


async def understand_turn(query: str, state: AgentState, active_task: dict[str, Any] | None) -> TurnUnderstandingResult:
    latest_message = state["messages"][-1]
    prompt = UNDERSTAND_TURN_PROMPT.format(
        agent_state=_safe_json(_agent_state_for_prompt(state, active_task)),
        query=query,
        current_images=_safe_json(get_message_image_urls(latest_message)),
    )
    result = await ainvoke_json(
        get_llm(),
        [build_multimodal_prompt(prompt, latest_message)],
        TurnUnderstandingResult,
    )
    intent = _normalize_intent(result.intent)
    confidence = result.confidence if intent != "unknown_respond" else min(result.confidence, 0.59)
    return TurnUnderstandingResult(
        intent=intent,
        confidence=confidence,
        slots=result.slots or {},
        needs_clarification=result.needs_clarification,
        clarify_question=result.clarify_question,
        task=result.task,
    )


def _build_active_task(
    *,
    current: dict[str, Any] | None,
    intent: IntentType,
    route: RouteType,
    slots: dict[str, Any],
    task_update: TaskUpdateModel,
) -> dict[str, Any] | None:
    action = (task_update.action or "none").strip()
    if action == "cancel":
        return None
    if route not in {"skills", "mcp_tool", "clarify"} and action == "none":
        return None

    handler = _handler_for_route(route)
    base = current or {
        "task_type": task_update.task_type or intent,
        "handler": handler,
        "slots": {},
        "missing_slots": [],
        "pending_action": None,
    }
    merged_slots = {
        **(base.get("slots") or {}),
        **slots,
        **(task_update.slots or {}),
    }

    if task_update.stage:
        stage = task_update.stage
    elif route == "clarify":
        stage = "collecting"
    elif route in {"skills", "mcp_tool"}:
        stage = "executing"
    else:
        stage = base.get("stage", "done")

    return {
        **base,
        "task_type": task_update.task_type or base.get("task_type") or intent,
        "handler": base.get("handler") or handler,
        "stage": stage,
        "slots": merged_slots,
        "missing_slots": task_update.missing_slots or base.get("missing_slots", []),
        "pending_action": task_update.pending_action if task_update.pending_action is not None else base.get("pending_action"),
    }


def _merge_dialog_state(
    dialog_state: dict[str, Any],
    *,
    active_task: dict[str, Any] | None,
) -> dict[str, Any]:
    next_state = dict(dialog_state)
    if active_task:
        next_state["active_task"] = active_task
    else:
        next_state.pop("active_task", None)
    return next_state


async def _emit_debug(
    *,
    query: str,
    intent: str,
    confidence: float,
    route: str,
    slots: dict[str, Any],
    needs_clarification: bool,
    clarify_question: str | None,
    active_task: dict[str, Any] | None,
    status: str,
) -> None:
    await adispatch_custom_event(
        "classification_debug",
        {
            "query": query,
            "intent": intent,
            "confidence": confidence,
            "route": route,
            "slots": slots,
            "needs_clarification": needs_clarification,
            "clarify_question": clarify_question,
            "active_task": active_task,
            "status": status,
        },
    )


async def classify_node(state: AgentState) -> Command:
    query = state.get("rewrite_query") or get_message_text(state["messages"][-1])
    dialog_state = state.get("dialog_state", {}) or {}
    active_task = state.get("active_task") or _active_task_from_dialog_state(dialog_state)

    await adispatch_custom_event(
        "thinking_step",
        {
            "step_type": "thought",
            "step_num": 1,
            "content": f"识别意图与对话状态：{query}",
        },
    )

    try:
        result = await understand_turn(query, state, active_task)
    except Exception as exc:
        result = TurnUnderstandingResult(
            intent="unknown_respond",
            confidence=0.0,
            slots={},
            needs_clarification=True,
            clarify_question="当前意图识别输出格式异常，请稍后再试一次。",
            task=TaskUpdateModel(),
        )
        await adispatch_custom_event(
            "thinking_step",
            {
                "step_type": "observation",
                "step_num": 2,
                "content": f"意图识别调用失败，转入澄清节点：{exc}",
            },
        )

    route = _route_for_intent(result.intent, result.needs_clarification, result.clarify_question)
    clarify_question = result.clarify_question or (
        "请澄清一下意图？"
        if route == "clarify"
        else ""
    )
    active_task = _build_active_task(
        current=active_task,
        intent=result.intent,
        route=route,
        slots=result.slots,
        task_update=result.task,
    )
    next_dialog_state = _merge_dialog_state(
        dialog_state,
        active_task=active_task,
    )

    await _emit_debug(
        query=query,
        intent=result.intent,
        confidence=result.confidence,
        route=route,
        slots=result.slots,
        needs_clarification=route == "clarify",
        clarify_question=clarify_question or None,
        active_task=active_task,
        status="classified",
    )
    await adispatch_custom_event(
        "thinking_step",
        {
            "step_type": "route",
            "step_num": 2,
            "content": f"意图 {result.intent}，置信度 {result.confidence:.2f}，路由 {route}",
        },
    )

    return Command(
        goto=route,
        update={
            "intent": result.intent,
            "confidence": result.confidence,
            "slots": result.slots,
            "task": result.task.model_dump(),
            "route": route,
            "active_task": active_task,
            "dialog_state": next_dialog_state,
            "needs_clarification": route == "clarify",
            "clarify_question": clarify_question,
        },
    )
