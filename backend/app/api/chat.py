"""
Chat API

POST /api/chat/stream   — SSE 流式对话（前端主要用这个）
GET  /api/chat/history  — 获取对话历史
DELETE /api/chat/history — 清空对话历史
"""

from __future__ import annotations

import json
import uuid
from fastapi import APIRouter, Query, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, AIMessage

from app.agent.graph import agent_graph
from app.agent.state import AgentState
from app.agent.memory import compress_history, trigger_ltm_update
from app.db.mongo import get_history, append_messages, clear_history, clear_all_history
from app.message_utils import make_user_message
import asyncio
from app.api.auth import get_current_user

router = APIRouter(prefix="/chat", tags=["chat"])


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
        "rewritten_query": "",
        "intent": "unknown",
        "confidence": 0.0,
        "needs_clarification": False,
        "dialog_state": dialog_state,
        "missing_slots": [],
        "rag_results": [],
        "api_response": "",
        "react_steps": [],
    }

    async def event_generator():
        # 发送 session_id（前端首次对话需要保存）
        yield f"data: {json.dumps({'type': 'session', 'session_id': session_id})}\n\n"

        collected_tokens: list[str] = []
        intent_sent = False
        # 记录哪些节点产生了 token，用于过滤 ReAct 中间 LLM 调用的 token
        # （只有最终回复节点的 token 才推给前端）
        final_answer_nodes = {
            "rag",
            "api_call",
            "skills",
            "chat_respond",
            "clarify",
            "unrecognized",
            "web_search",
            "react",
        }

        # 收集最后一个状态的 dialog_state
        final_dialog_state = None
        
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
                    # ReAct 节点内部会多次调用 LLM；只有最后一次（无 tool_calls）才是
                    # 最终回复。我们用一个简单标记：收到 token 时先缓存，done 时判断。
                    # 实际上 LangGraph streaming 里 ReAct 中间步骤不会产生纯文本 token，
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
                elif hasattr(output, "intent"):
                    intent = output.intent
                else:
                    intent = ""
                if intent:
                    intent_sent = True
                    yield f"data: {json.dumps({'type': 'intent', 'intent': intent})}\n\n"

            # ── 查询改写结果 ──
            elif event_type == "on_chain_end" and node_name == "rewrite":
                output = event["data"].get("output", {})
                if isinstance(output, dict):
                    rewritten_query = output.get("rewritten_query", "")
                else:
                    rewritten_query = ""
                if rewritten_query:
                    yield f"data: {json.dumps({'type': 'rewrite', 'rewritten_query': rewritten_query})}\n\n"

            # ── 思考步骤（RAG / web_search / react 节点发出的自定义事件）──
            elif event_type == "on_custom_event" and event.get("name") == "thinking_step":
                step_data = event["data"]
                yield f"data: {json.dumps({'type': 'thinking_step', **step_data})}\n\n"

            # ── RAG 调试元信息 ──
            elif event_type == "on_custom_event" and event.get("name") == "rag_meta":
                meta_data = event["data"]
                yield f"data: {json.dumps({'type': 'rag_meta', **meta_data})}\n\n"

            # ── RAG 检索结果明细 ──
            elif event_type == "on_custom_event" and event.get("name") == "rag_results":
                rag_data = event["data"]
                yield f"data: {json.dumps({'type': 'rag_results', **rag_data})}\n\n"

            # ── 节点结束时兜底处理：如果节点没有流式输出 token（比如 ReAct 节点使用的是非流式调用），
            # 就在节点结束时把最终结果一次性推给前端。
            elif event_type == "on_chain_end" and node_name in final_answer_nodes:
                output = event["data"].get("output", {})
                if isinstance(output, dict) and "messages" in output:
                    messages_list = output["messages"]
                    if messages_list:
                        last_msg = messages_list[-1]
                        if hasattr(last_msg, "content") and last_msg.content and not collected_tokens:
                            collected_tokens.append(last_msg.content)
                            yield f"data: {json.dumps({'type': 'token', 'content': last_msg.content})}\n\n"

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
            
            # 后台异步更新长期记忆（脚手架）
            if final_dialog_state:
                asyncio.create_task(trigger_ltm_update(user_id, session_id, final_dialog_state))
                
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
