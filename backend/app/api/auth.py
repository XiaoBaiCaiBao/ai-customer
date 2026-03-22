from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
import jwt

router = APIRouter(prefix="/auth", tags=["auth"])

SECRET_KEY = "my_super_secret_key_for_demo_only"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

USERS = {
    "helloworld@qq.com": {"password": "helloworld", "role": "user"},
    "admin@qq.com": {"password": "yybb@bbyy", "role": "admin"},
    "test@qq.com": {"password": "test", "role": "user"},
}

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
        user_id = payload.get("sub")
        if user_id is None or user_id not in USERS:
            raise HTTPException(status_code=401, detail="Invalid user")
        user = USERS[user_id].copy()
        user["user_id"] = user_id
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

@router.post("/login")
async def login(req: LoginRequest):
    user = USERS.get(req.email)
    if not user or user["password"] != req.password:
        raise HTTPException(status_code=401, detail="邮箱或密码错误")
    
    access_token = create_access_token(data={"sub": req.email, "role": user["role"]})
    return {"access_token": access_token, "token_type": "bearer", "user_id": req.email, "role": user["role"]}
