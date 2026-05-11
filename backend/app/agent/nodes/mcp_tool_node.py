"""MCP tool node driven by the model provider's native tool calling."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.callbacks.manager import adispatch_custom_event
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage

from app.agent.state import AgentState
from app.agent.tools.mcp_provider_tools import convert_mcp_tools_to_openai_tools
from app.llm import get_llm
from app.mcp.client import MCPClientError, MCPToolError, call_mcp_tool, get_mcp_client
from app.message_utils import build_multimodal_prompt, get_message_text


MCP_TOOL_SYSTEM_PROMPT = """你是 BOU 客服 Agent 的业务工具编排助手。

你可以使用提供的工具查询 BOU 用户订单、资产、资产明细，或提交售后工单。

规则：
- 优先基于工具结果回答，不要编造订单、余额、资产状态或工单号。
- 当前用户 ID 是 {user_id}，调用工具时必须使用这个 user_id。
- 用户问余额、会员状态、到账情况时，优先查询用户详情或订单。
- 用户问流水、明细、消费记录时，调用资产明细工具，并把资产类型映射为：
  月卡/vip_monthly，周卡/vip_weekly，回声贝/coin。
- 如果用户要提交工单，但缺少问题类型或问题描述，先追问，不要随意提交。
- 回复要简洁、友好，使用客服口吻。"""


def _tool_name_set(tools: list[dict[str, Any]]) -> set[str]:
    return {str(tool.get("name")) for tool in tools if tool.get("name")}


async def _available_tools() -> list[dict[str, Any]]:
    try:
        return await get_mcp_client().list_tools()
    except MCPClientError:
        return []


def _format_error(message: str) -> AIMessage:
    return AIMessage(content=f"我这边暂时没能连接到业务工具：{message}。你可以稍后再试，或补充信息我继续帮你看。")


def _message_content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            str(item.get("text", "")) if isinstance(item, dict) else str(item)
            for item in content
        )
    return str(content or "")


def _extract_tool_calls(message: AIMessage) -> list[dict[str, Any]]:
    calls = getattr(message, "tool_calls", None) or []
    if calls:
        return [
            {
                "id": call.get("id"),
                "name": call.get("name"),
                "arguments": call.get("args") or call.get("arguments") or {},
            }
            for call in calls
            if isinstance(call, dict) and call.get("name")
        ]

    raw_calls = message.additional_kwargs.get("tool_calls") if hasattr(message, "additional_kwargs") else None
    parsed: list[dict[str, Any]] = []
    for call in raw_calls or []:
        if not isinstance(call, dict):
            continue
        function = call.get("function") or {}
        raw_args = function.get("arguments") or "{}"
        try:
            arguments = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
        except json.JSONDecodeError:
            arguments = {}
        parsed.append({
            "id": call.get("id"),
            "name": function.get("name"),
            "arguments": arguments if isinstance(arguments, dict) else {},
        })
    return [call for call in parsed if call.get("name")]


def _latest_user_message(state: AgentState):
    query = state.get("rewrite_query") or get_message_text(state["messages"][-1])
    return build_multimodal_prompt(query, state["messages"][-1])


def _build_initial_messages(state: AgentState) -> list[Any]:
    return [
        SystemMessage(content=MCP_TOOL_SYSTEM_PROMPT.format(user_id=state.get("user_id", "anonymous"))),
        _latest_user_message(state),
    ]


def _prepare_arguments(tool_call: dict[str, Any], tools: list[dict[str, Any]], state: AgentState) -> dict[str, Any]:
    arguments = dict(tool_call.get("arguments") or {})
    tool = next((item for item in tools if item.get("name") == tool_call.get("name")), {})
    schema = tool.get("inputSchema") or {}
    properties = schema.get("properties") or {}
    required = set(schema.get("required") or [])

    if ("user_id" in required or "user_id" in properties) and not arguments.get("user_id"):
        arguments["user_id"] = state.get("user_id", "anonymous")

    asset_type = arguments.get("asset_type")
    if asset_type in {"monthly_vip", "月卡", "月卡会员"}:
        arguments["asset_type"] = "vip_monthly"
    elif asset_type in {"weekly_vip", "周卡", "周卡会员"}:
        arguments["asset_type"] = "vip_weekly"
    elif asset_type in {"daibi", "代币", "回声贝", "echo"}:
        arguments["asset_type"] = "coin"

    return arguments


async def _invoke_model_with_tools(llm, messages: list[Any], provider_tools: list[dict[str, Any]]) -> AIMessage:
    if hasattr(llm, "bind_tools"):
        return await llm.bind_tools(provider_tools).ainvoke(messages)
    return await llm.ainvoke(messages, tools=provider_tools, tool_choice="auto")


async def _summarize_with_tool_results(
    llm,
    initial_messages: list[Any],
    assistant_message: AIMessage,
    tool_outputs: list[dict[str, Any]],
) -> AIMessage:
    previous_response_id = assistant_message.response_metadata.get("response_id")
    if previous_response_id and hasattr(llm, "responses_url"):
        final = await llm.ainvoke(
            [],
            previous_response_id=previous_response_id,
            function_outputs=[
                {
                    "call_id": output.get("id"),
                    "output": json.dumps(output.get("result"), ensure_ascii=False),
                }
                for output in tool_outputs
                if output.get("id")
            ],
        )
        if final.content:
            return final

    messages: list[Any] = [*initial_messages, assistant_message]
    for output in tool_outputs:
        tool_call_id = str(output.get("id") or output.get("name") or "mcp_tool_call")
        messages.append(ToolMessage(
            content=json.dumps(output.get("result"), ensure_ascii=False),
            tool_call_id=tool_call_id,
        ))
    return await llm.ainvoke(messages)


def _fallback_answer(tool_outputs: list[dict[str, Any]]) -> str:
    if not tool_outputs:
        return "我这边暂时没有拿到业务查询结果。"

    output = tool_outputs[-1]
    result = output.get("result") or {}
    if result.get("success") is False:
        error = result.get("error") or {}
        return f"我这边暂时没处理成功：{error.get('message', '业务工具返回失败')}。"

    work_order = result.get("work_order")
    if isinstance(work_order, dict) and work_order.get("ticket_id"):
        return f"我已经帮你提交售后工单，工单号是 {work_order['ticket_id']}。"

    diagnosis = result.get("diagnosis")
    if isinstance(diagnosis, dict) and diagnosis.get("reason"):
        return f"我查到你的资产状态：{diagnosis['reason']}。"

    if isinstance(result.get("orders"), list):
        orders = result["orders"]
        return f"我查到你最近有 {len(orders)} 笔相关订单。"

    details = result.get("details")
    asset = result.get("asset")
    if isinstance(details, list) and isinstance(asset, dict):
        asset_name = asset.get("name") or asset.get("type") or "该资产"
        return f"我查到 {asset_name} 共有 {len(details)} 条变动明细。"

    return "我已经查到相关业务信息了。"


async def mcp_tool_node(state: AgentState) -> dict:
    tools = await _available_tools()
    if not tools:
        answer = _format_error("当前没有可用 MCP tools")
        return {
            "messages": [answer],
            "intent": state.get("intent", "unknown_respond"),
            "confidence": state.get("confidence", 0.0),
            "route": "mcp_tool",
            "dialog_state": state.get("dialog_state", {}),
            "needs_clarification": False,
            "clarify_question": "",
            "rag_results": [],
        }

    await adispatch_custom_event(
        "thinking_step",
        {
            "step_type": "action",
            "step_num": 3,
            "content": f"Loaded {len(tools)} MCP tools; asking model to choose native tool calls",
        },
    )

    llm = get_llm()
    provider_tools = convert_mcp_tools_to_openai_tools(tools)
    initial_messages = _build_initial_messages(state)
    assistant_message = await _invoke_model_with_tools(llm, initial_messages, provider_tools)
    tool_calls = _extract_tool_calls(assistant_message)

    if not tool_calls:
        content = _message_content_text(assistant_message.content) or "我还需要您补充一点信息，才能继续处理。"
        return {
            "messages": [AIMessage(content=content)],
            "intent": state.get("intent", "unknown_respond"),
            "confidence": state.get("confidence", 0.0),
            "route": "mcp_tool",
            "dialog_state": state.get("dialog_state", {}),
            "needs_clarification": False,
            "clarify_question": "",
            "rag_results": [],
        }

    available_names = _tool_name_set(tools)
    tool_outputs: list[dict[str, Any]] = []
    dialog_state = state.get("dialog_state", {}).copy()

    for call in tool_calls:
        tool_name = call.get("name")
        arguments = _prepare_arguments(call, tools, state)
        if tool_name not in available_names:
            result = {
                "success": False,
                "error": {
                    "code": "UNKNOWN_TOOL",
                    "message": f"Selected MCP tool is not available: {tool_name}",
                },
            }
        else:
            try:
                result = await call_mcp_tool(str(tool_name), arguments)
            except MCPToolError as exc:
                result = exc.payload or {
                    "success": False,
                    "error": {"code": "MCP_TOOL_FAILED", "message": str(exc)},
                }
            except MCPClientError as exc:
                result = {
                    "success": False,
                    "error": {"code": "MCP_CALL_FAILED", "message": str(exc)},
                }

        tool_outputs.append({
            "id": call.get("id"),
            "name": tool_name,
            "arguments": arguments,
            "result": result,
        })

        await adispatch_custom_event(
            "tool_call",
            {
                "node": "mcp_tool",
                "tool_name": tool_name,
                "arguments": arguments,
                "result": result,
                "success": bool(result.get("success", True)),
                "error": result.get("error"),
            },
        )

    dialog_state["_last_tool_call"] = tool_outputs[-1] if tool_outputs else {}

    await adispatch_custom_event(
        "thinking_step",
        {
            "step_type": "observation",
            "step_num": 4,
            "content": f"Executed {len(tool_outputs)} MCP tool call(s)",
        },
    )

    try:
        final_message = await _summarize_with_tool_results(llm, initial_messages, assistant_message, tool_outputs)
        final_content = _message_content_text(final_message.content) or _fallback_answer(tool_outputs)
    except Exception:
        final_content = _fallback_answer(tool_outputs)

    return {
        "messages": [AIMessage(content=final_content)],
        "intent": state.get("intent", "unknown_respond"),
        "confidence": state.get("confidence", 0.0),
        "route": "mcp_tool",
        "dialog_state": dialog_state,
        "needs_clarification": False,
        "clarify_question": "",
        "rag_results": [],
    }
