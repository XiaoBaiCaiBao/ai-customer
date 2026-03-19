from functools import lru_cache
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from app.config import get_settings


def get_llm(streaming: bool = False) -> ChatOpenAI:
    """
    统一 LLM 工厂。切换模型只需改 .env 里的 LLM_MODEL / LLM_BASE_URL：
      - OpenAI:    LLM_MODEL=gpt-4o, LLM_BASE_URL=（留空）
      - DeepSeek:  LLM_MODEL=deepseek-chat, LLM_BASE_URL=https://api.deepseek.com
      - 通义千问:  LLM_MODEL=qwen-max, LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
      - Ollama:    LLM_MODEL=qwen2.5:7b, LLM_BASE_URL=http://localhost:11434/v1
    """
    s = get_settings()
    return ChatOpenAI(
        model=s.LLM_MODEL,
        api_key=s.LLM_API_KEY,
        base_url=s.llm_base_url,
        streaming=streaming,
        temperature=0,
    )


@lru_cache
def get_embeddings() -> OpenAIEmbeddings:
    s = get_settings()
    return OpenAIEmbeddings(
        model=s.EMBEDDING_MODEL,
        api_key=s.LLM_API_KEY,
        base_url=s.llm_base_url,
    )
