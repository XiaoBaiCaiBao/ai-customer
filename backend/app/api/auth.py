from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
import jwt

from app.db.mongo import get_user_by_email, hash_password

router = APIRouter(prefix="/auth", tags=["auth"])

SECRET_KEY = "my_super_secret_key_for_demo_only"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

class LoginRequest(BaseModel):
    email: str
    password: str

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_email = payload.get("sub")
        if user_email is None:
            raise HTTPException(status_code=401, detail="Invalid token")
            
        user_doc = await get_user_by_email(user_email)
        if not user_doc:
            raise HTTPException(status_code=401, detail="User not found")
            
        return {
            "user_id": user_doc["email"],
            "role": user_doc.get("role", "user")
        }
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

@router.post("/login")
async def login(req: LoginRequest):
    user_doc = await get_user_by_email(req.email)
    
    # 验证用户是否存在且密码正确（密码为简单 hash）
    if not user_doc or user_doc.get("password_hash") != hash_password(req.password):
        raise HTTPException(status_code=401, detail="邮箱或密码错误")
    
    role = user_doc.get("role", "user")
    access_token = create_access_token(data={"sub": req.email, "role": role})
    
    return {
        "access_token": access_token, 
        "token_type": "bearer", 
        "user_id": req.email, 
        "role": role
    }
