from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, Field

router = APIRouter(prefix="/auth", tags=["auth"])

SECRET_KEY = "my_super_secret_key_for_demo_only"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days
ALLOWED_USER_ID = "helloworld666"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

_MAX_NICKNAME = 64


class LoginRequest(BaseModel):
    """任意非空字符串作为会话用户标识（写入 JWT sub，用于对话隔离）。"""

    nickname: str = Field(..., max_length=_MAX_NICKNAME, description="昵称或任意标识")


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        sub = payload.get("sub")
        if not sub:
            raise HTTPException(status_code=401, detail="Invalid token")
        if sub != ALLOWED_USER_ID:
            raise HTTPException(status_code=403, detail="无权访问")
        return {"user_id": sub}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


@router.post("/login")
async def login(req: LoginRequest):
    nickname = req.nickname.strip()
    if not nickname:
        raise HTTPException(status_code=400, detail="请输入内容后再进入")
    if nickname != ALLOWED_USER_ID:
        raise HTTPException(status_code=403, detail="用户名不正确")

    access_token = create_access_token(data={"sub": nickname})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": nickname,
    }
