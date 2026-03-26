import asyncio
from datetime import datetime, timezone
from langchain_core.messages import HumanMessage
from app.llm import get_llm
from app.db.mongo import _client
from app.prompts.stm_compress import STM_COMPRESS_PROMPT


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


async def trigger_ltm_update(user_id: str, session_id: str, new_dialog_state: dict) -> None:
    """
    【长期记忆 LTM 异步更新脚手架】
    当对话发生关键信息更新时，或在对话结束时调用此方法。
    可以在这里将 dialog_state 或对话摘要抽取成 Fact，写入向量数据库或用户画像库。
    """
    print(f"[LTM] 触发长期记忆更新 - 用户: {user_id}, Session: {session_id}")
    # 示例逻辑：
    # 1. 检查 new_dialog_state 中是否包含用户的偏好信息（如手机型号、充值习惯等）
    # 2. 调用 LLM 提取 Fact
    # 3. 存入 LTM (Milvus/Qdrant 或 MongoDB 用户集合)
    
    # 模拟异步延迟
    await asyncio.sleep(0.1)
    pass
