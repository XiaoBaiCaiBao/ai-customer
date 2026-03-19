"""
对话历史存储

USE_MEMORY=true  → 内存存储（默认，无需任何数据库，重启清空）
USE_MEMORY=false → MongoDB 持久化存储
"""

from app.config import get_settings

# 内存存储：{ session_id: [{"role": ..., "content": ...}, ...] }
_store: dict[str, list[dict]] = {}


def _use_memory() -> bool:
    return get_settings().USE_MEMORY


async def get_history(session_id: str) -> list[dict]:
    if _use_memory():
        return _store.get(session_id, [])[-20:]

    from datetime import datetime, timezone
    from motor.motor_asyncio import AsyncIOMotorClient
    s = get_settings()
    client = AsyncIOMotorClient(s.MONGODB_URL)
    doc = await client[s.MONGODB_DB].conversations.find_one({"session_id": session_id})
    client.close()
    if not doc:
        return []
    return doc.get("messages", [])[-20:]


async def append_messages(session_id: str, user_id: str, new_messages: list[dict]) -> None:
    if _use_memory():
        if session_id not in _store:
            _store[session_id] = []
        _store[session_id].extend(new_messages)
        return

    from datetime import datetime, timezone
    from motor.motor_asyncio import AsyncIOMotorClient
    s = get_settings()
    client = AsyncIOMotorClient(s.MONGODB_URL)
    now = datetime.now(timezone.utc)
    await client[s.MONGODB_DB].conversations.update_one(
        {"session_id": session_id},
        {
            "$set": {"user_id": user_id, "updated_at": now},
            "$setOnInsert": {"created_at": now},
            "$push": {"messages": {"$each": new_messages}},
        },
        upsert=True,
    )
    client.close()


async def clear_history(session_id: str) -> None:
    if _use_memory():
        _store.pop(session_id, None)
        return

    from motor.motor_asyncio import AsyncIOMotorClient
    s = get_settings()
    client = AsyncIOMotorClient(s.MONGODB_URL)
    await client[s.MONGODB_DB].conversations.delete_one({"session_id": session_id})
    client.close()
