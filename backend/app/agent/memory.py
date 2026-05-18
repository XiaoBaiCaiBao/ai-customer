from datetime import datetime, timezone
from langchain_core.messages import HumanMessage
from app.llm import get_llm
from app.db.mongo import _client

STM_COMPRESS_PROMPT = """你是一个专业的对话总结助手。
请将以下客服对话历史总结成一段简短的摘要（不超过100字）。
摘要需要保留用户的主要诉求、已经提供的关键信息（如槽位）以及客服给出的核心答复或进度。

历史对话：
{history}

总结摘要："""


async def compress_history(session_id: str, user_id: str) -> None:
    """
    检查指定 session 的历史记录长度。
    如果超过阈值（如 10 条），则触发总结，并将总结作为第一条消息，保留最后 3-4 条。
    """
    client, db_name = _client()
    try:
        doc = await client[db_name].conversations.find_one({"session_id": session_id, "user_id": user_id})
        if not doc:
            return

        messages = doc.get("messages", [])
        
        # 阈值：超过 12 条消息（6轮）时压缩
        if len(messages) <= 12:
            return

        # 把前 len-4 条记录取出来总结
        messages_to_compress = messages[:-4]
        keep_messages = messages[-4:]

        # 拼接对话文本
        history_text = "\n".join(
            f"{'用户' if m.get('role') == 'user' else '客服'}: {m.get('content', '')}"
            for m in messages_to_compress
        )

        llm = get_llm()
        prompt = STM_COMPRESS_PROMPT.format(history=history_text)
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        summary = response.content.strip()

        # 构建新的消息列表：第一条是总结（作为系统消息或特定的 context 消息）
        new_messages = [{"role": "system", "content": f"前期对话摘要：{summary}"}] + keep_messages

        await client[db_name].conversations.update_one(
            {"session_id": session_id, "user_id": user_id},
            {"$set": {"messages": new_messages, "updated_at": datetime.now(timezone.utc)}}
        )
        print(f"[Memory] Session {session_id} 的历史记录已压缩。")

    except Exception as e:
        print(f"[Memory] 压缩历史记录失败: {e}")
    finally:
        client.close()
