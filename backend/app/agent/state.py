from typing import Annotated, Literal, TypedDict
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


IntentType = Literal[
    "app_info",        # 产品功能疑问
    "usage_issue",     # 使用遇到问题
    "user_voice",      # 吐槽/产品建议/投诉（原 app_advice）
    "aftersales",      # 售后问题（粗粒度，Planner 内细化为子类型）
    "chat_respond",    # 闲聊（原 chat）
    "unknown_respond", # 命中敏感词/未识别（原 unknown）
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

    # Planner 路由决策（route_hint: rag | mcp_single | executor_react | clarify）
    route_destination: str

    # RAG 检索结果
    rag_results: list[dict]

    # 外部 API 调用结果
    api_response: str

    # 对话状态追踪 (DST)，存储多轮中提取到的关键槽位
    dialog_state: dict
    missing_slots: list[str]
    needs_clarification: bool
    clarify_question: str

    # ReAct 推理步骤（用于 UI 展示思考过程）
    react_steps: list[dict]

    # Skills 链路执行结果
    skills_result: dict
