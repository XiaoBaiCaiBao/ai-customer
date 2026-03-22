from typing import Annotated, Literal, TypedDict
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


IntentType = Literal[
    "product_info",   # 产品功能咨询 → RAG
    "usage_issue",    # 使用遇到问题 → RAG
    "complaint",      # 吐槽/产品建议 → 安抚 + 通知产研
    "aftersales",     # 售后/账单问题 → ReAct 多步查证
    "event",          # 运营活动 → RAG
    "web_search",     # 联网查询（天气、实时信息）→ 联网 API
    "chat",           # 闲聊/其他 → 直接回复
    "unknown",        # 未识别
]


class AgentState(TypedDict):
    # 对话历史，使用 add_messages reducer 自动追加
    messages: Annotated[list[BaseMessage], add_messages]

    # 请求元信息
    user_id: str
    session_id: str

    # 查询改写后的结果
    rewritten_query: str

    # 意图识别结果
    intent: IntentType
    confidence: float
    needs_clarification: bool

    # RAG 检索结果
    rag_results: list[dict]

    # 外部 API 调用结果
    api_response: str

    # ReAct 推理步骤（用于 UI 展示思考过程）
    react_steps: list[dict]
