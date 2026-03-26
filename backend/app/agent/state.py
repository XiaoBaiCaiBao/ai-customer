from typing import Annotated, Literal, TypedDict
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


IntentType = Literal[
    "product_info",   # 产品功能咨询
    "usage_issue",    # 使用遇到问题
    "complaint",      # 吐槽/产品建议
    "aftersales",     # 售后/账单问题
    "event",          # 运营活动
    "web_search",     # 联网查询
    "chat",           # 闲聊
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

    # 路由目标（> 0.85 置信度下，Router 节点得出的后续节点）
    route_destination: str

    # RAG 检索结果
    rag_results: list[dict]

    # 外部 API 调用结果
    api_response: str

    # 对话状态追踪 (DST)，存储多轮中提取到的关键槽位
    dialog_state: dict
    missing_slots: list[str]

    # ReAct 推理步骤（用于 UI 展示思考过程）
    react_steps: list[dict]
