"""
Chat API

POST /api/chat/stream   — SSE 流式对话（前端主要用这个）
GET  /api/chat/history  — 获取对话历史
DELETE /api/chat/history — 清空对话历史
"""

import json
import uuid
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, AIMessage

from app.agent.graph import agent_graph
from app.agent.state import AgentState
from app.db.mongo import get_history, append_messages, clear_history

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    user_id: str = "anonymous"


@router.post("/stream")
async def chat_stream(req: ChatRequest):
    """流式对话，使用 SSE 协议返回 token"""
    session_id = req.session_id or str(uuid.uuid4())

    # 加载历史对话
    history = await get_history(session_id)
    history_messages = [
        HumanMessage(content=m["content"]) if m["role"] == "user"
        else AIMessage(content=m["content"])
        for m in history
    ]

    initial_state: AgentState = {
        "messages": history_messages + [HumanMessage(content=req.message)],
        "user_id": req.user_id,
        "session_id": session_id,
        "rewritten_query": "",
        "intent": "unknown",
        "confidence": 0.0,
        "needs_clarification": False,
        "rag_results": [],
        "api_response": "",
    }

    async def event_generator():
        # 发送 session_id（前端首次对话需要保存）
        yield f"data: {json.dumps({'type': 'session', 'session_id': session_id})}\n\n"

        collected_tokens: list[str] = []
        intent_sent = False

        async for event in agent_graph.astream_events(initial_state, version="v2"):
            event_type = event["event"]

            # 流式输出 token
            if event_type == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                if chunk.content:
                    collected_tokens.append(chunk.content)
                    yield f"data: {json.dumps({'type': 'token', 'content': chunk.content})}\n\n"

            # 意图识别完成后，推送意图信息给前端
            elif (
                event_type == "on_chain_end"
                and event.get("metadata", {}).get("langgraph_node") == "classify"
                and not intent_sent
            ):
                output = event["data"].get("output", {})
                # output 可能是 dict（节点返回值）或 Pydantic model（中间调用结果）
                if isinstance(output, dict):
                    intent = output.get("intent", "")
                elif hasattr(output, "intent"):
                    intent = output.intent
                else:
                    intent = ""
                if intent:
                    intent_sent = True
                    yield f"data: {json.dumps({'type': 'intent', 'intent': intent})}\n\n"

        # 保存本轮对话到 MongoDB
        full_response = "".join(collected_tokens)
        if full_response:
            await append_messages(session_id, req.user_id, [
                {"role": "user", "content": req.message},
                {"role": "assistant", "content": full_response},
            ])

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
async def get_chat_history(session_id: str = Query(...)):
    messages = await get_history(session_id)
    return {"session_id": session_id, "messages": messages}


@router.delete("/history")
async def delete_chat_history(session_id: str = Query(...)):
    await clear_history(session_id)
    return {"message": "ok"}
