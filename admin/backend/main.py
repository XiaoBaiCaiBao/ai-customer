from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.compensations import router as compensations_router
from app.api.evaluations import router as evaluations_router
from app.api.kb import router as kb_router
from app.api.tickets import router as tickets_router
from app.api.tools import router as tools_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title="BOU Admin Console",
    description="BOU 智能客服管理后台：知识库、工单、补偿",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(kb_router, prefix="/api")
app.include_router(tickets_router, prefix="/api")
app.include_router(compensations_router, prefix="/api")
app.include_router(evaluations_router, prefix="/api")
app.include_router(tools_router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok"}
