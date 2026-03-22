"""
对话历史存储（MongoDB）

每条会话文档含 session_id、user_id、messages；读/写/删均校验 user_id，避免串用户。
"""

from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient

from app.config import get_settings


def _client() -> tuple[AsyncIOMotorClient, str]:
    s = get_settings()
    return AsyncIOMotorClient(s.MONGODB_URL), s.MONGODB_DB


async def get_history(session_id: str, user_id: str) -> list[dict]:
    client, db_name = _client()
    try:
        doc = await client[db_name].conversations.find_one({"session_id": session_id})
        if not doc or doc.get("user_id") != user_id:
            return []
        return doc.get("messages", [])[-20:]
    finally:
        client.close()


async def append_messages(session_id: str, user_id: str, new_messages: list[dict]) -> None:
    client, db_name = _client()
    try:
        existing = await client[db_name].conversations.find_one({"session_id": session_id})
        if existing and existing.get("user_id") != user_id:
            return

        now = datetime.now(timezone.utc)
        await client[db_name].conversations.update_one(
            {"session_id": session_id},
            {
                "$set": {"user_id": user_id, "updated_at": now},
                "$setOnInsert": {"created_at": now},
                "$push": {"messages": {"$each": new_messages}},
            },
            upsert=True,
        )
    finally:
        client.close()


async def clear_history(session_id: str, user_id: str) -> None:
    client, db_name = _client()
    try:
        await client[db_name].conversations.delete_one(
            {"session_id": session_id, "user_id": user_id}
        )
    finally:
        client.close()
