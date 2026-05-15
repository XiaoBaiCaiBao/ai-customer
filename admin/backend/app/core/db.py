from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorClient

from app.core.config import get_settings


def mongo_client() -> tuple[AsyncIOMotorClient, str]:
    settings = get_settings()
    return AsyncIOMotorClient(settings.ADMIN_MONGODB_URL), settings.ADMIN_MONGODB_DB
