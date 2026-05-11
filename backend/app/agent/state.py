from typing import Annotated, Literal, TypedDict
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


IntentType = Literal[
    "usage_guide",                  # 使用指南
    "account_issue_consult",        # 账号问题咨询
    "feature_play_consult",         # 功能玩法咨询
    "privacy_permission_consult",   # 隐私权限咨询
    "activity_consult",             # 线上、线下活动咨询
    "data_search",                  # 实时数据查询
    "content_safety_consult",       # 内容安全策略咨询
    "chat_quality_feedback",        # 聊天质量反馈
    "pre_sales_consult",            # 售前咨询
    "after_sales_issue",            # 售后问题
    "product_suggestion",           # 产品建议
    "product_complaint",            # 产品吐槽
    "fault_feedback",               # 故障反馈
    "chat_respond",                 # 闲聊
    "unknown_respond",              # 命中敏感词/未识别
]


class AgentState(TypedDict):
    # 对话历史，使用 add_messages reducer 自动追加
    messages: Annotated[list[BaseMessage], add_messages]

    # 请求元信息
    user_id: str
    session_id: str

    # 查询改写后的结果：后续链路真正处理的单个问题。
    rewrite_query: str
    rewrite_analysis: str
    rewrite_used_history: bool
    rewrite_used_short_memory: bool

    # 意图识别结果
    intent: IntentType
    confidence: float
    route: str

    # RAG 检索结果
    rag_results: list[dict]

    # 对话状态追踪，存储多轮中提取到的关键槽位
    dialog_state: dict
    needs_clarification: bool
    clarify_question: str
