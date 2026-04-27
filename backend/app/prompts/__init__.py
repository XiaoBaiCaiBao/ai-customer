"""提示词按节点拆分为独立模块，便于单独维护。此处聚合导出以保持兼容。"""

from app.prompts.api import AFTERSALES_SYSTEM_PROMPT, COMPLAINT_SYSTEM_PROMPT
from app.prompts.chat import CHAT_SYSTEM_PROMPT, CLARIFY_SYSTEM_PROMPT
from app.prompts.classify import CLASSIFY_PROMPT
from app.prompts.dst import DST_PROMPT
from app.prompts.rag import RAG_SYSTEM_PROMPT
from app.prompts.rewrite import REWRITE_PROMPT
from app.prompts.skills import AFTERSALES_SKILL
from app.prompts.stm_compress import STM_COMPRESS_PROMPT
from app.prompts.web_search import (
    WEB_SEARCH_DEFAULT_PROMPT,
    WEB_SEARCH_EXTRACT_PROMPT,
    WEB_SEARCH_FORMAT_ERROR_PROMPT,
    WEB_SEARCH_FORMAT_WEATHER_PROMPT,
)

__all__ = [
    "AFTERSALES_SYSTEM_PROMPT",
    "CHAT_SYSTEM_PROMPT",
    "CLASSIFY_PROMPT",
    "CLARIFY_SYSTEM_PROMPT",
    "COMPLAINT_SYSTEM_PROMPT",
    "DST_PROMPT",
    "RAG_SYSTEM_PROMPT",
    "REWRITE_PROMPT",
    "AFTERSALES_SKILL",
    "STM_COMPRESS_PROMPT",
    "WEB_SEARCH_DEFAULT_PROMPT",
    "WEB_SEARCH_EXTRACT_PROMPT",
    "WEB_SEARCH_FORMAT_ERROR_PROMPT",
    "WEB_SEARCH_FORMAT_WEATHER_PROMPT",
]
