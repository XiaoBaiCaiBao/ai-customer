from fastapi import APIRouter, Depends
from app.api.auth import get_current_user
from app.db.mongo import _client

router = APIRouter(prefix="/admin", tags=["admin"])

@router.get("/users")
async def list_users(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin":
        return {"error": "权限不足"}
    
    # 查找有过对话的用户
    client, db_name = _client()
    try:
        users = await client[db_name].conversations.distinct("user_id")
        return {"users": users}
    finally:
        client.close()

@router.delete("/history/user")
async def delete_user_history(target_user_id: str, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin":
        return {"error": "权限不足"}
    
    client, db_name = _client()
    try:
        res = await client[db_name].conversations.delete_many({"user_id": target_user_id})
        return {"message": f"Deleted {res.deleted_count} conversations for {target_user_id}"}
    finally:
        client.close()

@router.delete("/history/all")
async def delete_all_history(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin":
        return {"error": "权限不足"}
    
    client, db_name = _client()
    try:
        res = await client[db_name].conversations.delete_many({})
        return {"message": f"Deleted all {res.deleted_count} conversations"}
    finally:
        client.close()
