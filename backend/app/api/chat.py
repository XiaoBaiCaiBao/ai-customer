"""
Chat API

POST /api/chat/stream   — SSE 流式对话（前端主要用这个）
GET  /api/chat/history  — 获取对话历史
DELETE /api/chat/history — 清空对话历史
"""

from __future__ import annotations

import json
import logging
import uuid
from fastapi import APIRouter, Query, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, AIMessage

from app.agent.graph import agent_graph
from app.agent.state import AgentState
from app.agent.memory import compress_history
from app.db.mongo import get_history, append_messages, clear_history, clear_all_history
from app.message_utils import make_user_message
import asyncio
from app.api.auth import get_current_user

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    images: list[str] = []

@router.post("/stream")
async def chat_stream(req: ChatRequest, current_user: dict = Depends(get_current_user)):
    """流式对话，使用 SSE 协议返回 token"""
    user_id = current_user["user_id"]
    session_id = req.session_id or str(uuid.uuid4())

    # 加载历史对话
    history, dialog_state = await get_history(session_id, user_id)
    history_messages = [
        make_user_message(m.get("content", ""), m.get("images", [])) if m["role"] == "user"
        else AIMessage(content=m["content"])
        for m in history
    ]

    initial_state: AgentState = {
        "messages": history_messages + [make_user_message(req.message, req.images)],
        "user_id": user_id,
        "session_id": session_id,
        "rewrite_query": "",
        "rewrite_analysis": "",
        "intent": "unknown_respond",
        "confidence": 0.0,
        "slots": {},
        "task": {"action": "none"},
        "route": "chat_respond",
        "needs_clarification": False,
        "clarify_question": "",
        "active_task": dialog_state.get("active_task"),
        "dialog_state": dialog_state,
        "rag_results": [],
    }

    async def event_generator():
        # 发送 session_id（前端首次对话需要保存）
        yield f"data: {json.dumps({'type': 'session', 'session_id': session_id})}\n\n"

        collected_tokens: list[str] = []
        intent_sent = False
        # 记录哪些节点产生了 token，用于过滤中间 LLM 调用的 token
        # （只有最终回复节点的 token 才推给前端）
        final_answer_nodes = {
            "rag",
            "mcp_tool",
            "skills",
            "chat_respond",
            "clarify",
        }

        # 收集最后一个状态的 dialog_state
        final_dialog_state = None
        
        try:
            async for event in agent_graph.astream_events(initial_state, version="v2"):
                event_type = event["event"]
                node_name = event.get("metadata", {}).get("langgraph_node", "")
            
                # 保存最后一次遇到的完整 dialog_state
                if "state" in event.get("data", {}):
                    state_data = event["data"]["state"]
                    if isinstance(state_data, dict) and "dialog_state" in state_data:
                        final_dialog_state = state_data["dialog_state"]
                # 有时 state 在 output 里
                elif "output" in event.get("data", {}):
                    output_data = event["data"]["output"]
                    if isinstance(output_data, dict) and "dialog_state" in output_data:
                        final_dialog_state = output_data["dialog_state"]

                # ── 流式 token（只推送来自最终回复节点的 token）──
                if event_type == "on_chat_model_stream" and node_name in final_answer_nodes:
                    chunk = event["data"]["chunk"]
                    if chunk.content:
                        # 工具/SOP 节点内部可能会多次调用 LLM；只有最终回复才是
                        # 最终回复。我们用一个简单标记：收到 token 时先缓存，done 时判断。
                        # 实际上 LangGraph streaming 里中间步骤不会产生纯文本 token，
                        # 只有最终回复才会，所以直接推送是安全的。
                        collected_tokens.append(chunk.content)
                        yield f"data: {json.dumps({'type': 'token', 'content': chunk.content})}\n\n"

                # ── 意图识别完成后推送意图 ──
                elif (
                    event_type == "on_chain_end"
                    and node_name == "classify"
                    and not intent_sent
                ):
                    output = event["data"].get("output", {})
                    if isinstance(output, dict):
                        intent = output.get("intent", "")
                        confidence = output.get("confidence")
                        route = output.get("route")
                    elif hasattr(output, "intent"):
                        intent = output.intent
                        confidence = getattr(output, "confidence", None)
                        route = getattr(output, "route", None)
                    else:
                        intent = ""
                        confidence = None
                        route = None
                    if intent:
                        intent_sent = True
                        payload = {"type": "intent", "intent": intent}
                        if confidence is not None:
                            payload["confidence"] = confidence
                        if route:
                            payload["route"] = route
                        yield f"data: {json.dumps(payload)}\n\n"

                # ── 查询改写结果 ──
                elif event_type == "on_chain_end" and node_name == "rewrite":
                    output = event["data"].get("output", {})
                    if isinstance(output, dict):
                        rewrite_query = output.get("rewrite_query", "")
                        rewrite_analysis = output.get("rewrite_analysis", "")
                    else:
                        rewrite_query = ""
                        rewrite_analysis = ""
                    if rewrite_query:
                        yield f"data: {json.dumps({'type': 'rewrite', 'input_query': req.message, 'rewrite_query': rewrite_query, 'rewrite_analysis': rewrite_analysis})}\n\n"

                # ── 思考步骤（RAG / MCP / skills 节点发出的自定义事件）──
                elif event_type == "on_custom_event" and event.get("name") == "thinking_step":
                    step_data = event["data"]
                    yield f"data: {json.dumps({'type': 'thinking_step', **step_data})}\n\n"

                elif event_type == "on_custom_event" and event.get("name") == "classification_debug":
                    debug_data = event["data"]
                    if (
                        not intent_sent
                        and debug_data.get("intent")
                    ):
                        intent_sent = True
                        payload = {"type": "intent", "intent": debug_data["intent"]}
                        if debug_data.get("confidence") is not None:
                            payload["confidence"] = debug_data["confidence"]
                        if debug_data.get("route"):
                            payload["route"] = debug_data["route"]
                        yield f"data: {json.dumps(payload)}\n\n"
                    yield f"data: {json.dumps({'type': 'classification_debug', **debug_data})}\n\n"

                elif event_type == "on_custom_event" and event.get("name") == "tool_call":
                    tool_data = event["data"]
                    yield f"data: {json.dumps({'type': 'tool_call', **tool_data})}\n\n"

                # ── RAG 调试元信息 ──
                elif event_type == "on_custom_event" and event.get("name") == "rag_meta":
                    meta_data = event["data"]
                    yield f"data: {json.dumps({'type': 'rag_meta', **meta_data})}\n\n"

                # ── RAG 检索结果明细 ──
                elif event_type == "on_custom_event" and event.get("name") == "rag_results":
                    rag_data = event["data"]
                    yield f"data: {json.dumps({'type': 'rag_results', **rag_data})}\n\n"

                # ── 节点结束时兜底处理：如果节点没有流式输出 token（比如 SOP 节点使用的是非流式调用），
                # 就在节点结束时把最终结果一次性推给前端。
                elif event_type == "on_chain_end" and node_name in final_answer_nodes:
                    output = event["data"].get("output", {})
                    if isinstance(output, dict) and output.get("rag_results"):
                        results = output.get("rag_results", [])
                        query = results[0].get("query", "") if results else ""
                        yield f"data: {json.dumps({'type': 'rag_results', 'query': query, 'results': output.get('rag_results', [])})}\n\n"
                    if isinstance(output, dict) and "messages" in output:
                        messages_list = output["messages"]
                        if messages_list:
                            last_msg = messages_list[-1]
                            if hasattr(last_msg, "content") and last_msg.content and not collected_tokens:
                                collected_tokens.append(last_msg.content)
                                yield f"data: {json.dumps({'type': 'token', 'content': last_msg.content})}\n\n"
        except Exception as exc:
            logger.exception("chat stream failed: session_id=%s user_id=%s", session_id, user_id)
            error_text = str(exc)
            if "429" in error_text or "SetLimitExceeded" in error_text or "TooManyRequests" in error_text:
                fallback = (
                    "抱歉，这次处理失败是因为当前模型服务触发了额度限制，暂时无法继续响应。"
                    "请稍后再试，或让管理员调整模型额度/关闭安全体验限制。"
                )
            else:
                fallback = "抱歉，这次处理时后端出现异常，我已经停止本轮执行了。请稍后再试一次。"
            collected_tokens.append(fallback)
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)[:300]})}\n\n"
            yield f"data: {json.dumps({'type': 'token', 'content': fallback})}\n\n"

        # 保存本轮对话到 MongoDB
        full_response = "".join(collected_tokens)
        if full_response:
            await append_messages(
                session_id, 
                user_id, 
                [
                    {"role": "user", "content": req.message, "images": req.images},
                    {"role": "assistant", "content": full_response},
                ],
                dialog_state=final_dialog_state
            )
            
            # 后台异步执行短期记忆压缩
            asyncio.create_task(compress_history(session_id, user_id))
            
        yield f"data: {json.dumps({'type': 'done', 'session_id': session_id})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # 禁止 Nginx 缓冲，确保实时流式
        },
    )


@router.get("/history")
async def get_chat_history(
    session_id: str = Query(...),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]
    messages, _ = await get_history(session_id, user_id)
    return {"session_id": session_id, "messages": messages}

@router.delete("/history")
async def delete_chat_history(
    session_id: str = Query(...),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]
    await clear_history(session_id, user_id)
    return {"message": "会话已重启"}


@router.delete("/reset")
async def reset_chat(
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]
    deleted_count = await clear_all_history(user_id)
    return {
        "message": "聊天已重置",
        "deleted_count": deleted_count,
    }
