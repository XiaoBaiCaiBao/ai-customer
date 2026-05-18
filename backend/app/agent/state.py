from typing import Annotated, Any, Literal, TypedDict
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


IntentType = Literal[
    "usage_guide",                  # 1. 使用指南
    "account_issue_consult",        # 2. 账号问题咨询
    "feature_play_consult",         # 3. 功能玩法咨询
    "privacy_permission_consult",   # 4. 隐私权限咨询
    "activity_consult",             # 5. 线上、线下活动咨询
    "content_safety_consult",       # 6. 内容安全策略咨询
    "chat_quality_feedback",        # 7. 聊天质量反馈
    "fault_feedback",               # 8. 故障反馈
    "data_search",                  # 9. 实时数据查询
    "pre_sales_consult",            # 10. 售前咨询
    "after_sales_issue",            # 11. 售后问题
    "product_suggestion",           # 12. 产品建议
    "product_complaint",            # 13. 产品吐槽
    "chat_respond",                 # 14. 其他/闲聊
    "unknown_respond",              # 无法识别
]


RouteType = Literal[
    "rag",
    "mcp_tool",
    "skills",
    "clarify",
    "chat_respond",
]


TaskStage = Literal[
    "collecting",
    "confirming",
    "executing",
    "done",
]


TaskHandler = Literal[
    "rag",
    "mcp",
    "skills",
    "chat",
]


TaskAction = Literal[
    "none",
    "start",
    "update",
    "confirm",
    "cancel",
    "complete",
]


class PendingAction(TypedDict, total=False):
    type: str
    tool: str
    params: dict[str, Any]


class TaskUpdate(TypedDict, total=False):
    action: TaskAction
    task_type: IntentType | None
    stage: TaskStage | None
    slots: dict[str, Any]
    missing_slots: list[str]
    pending_action: PendingAction | None


class ActiveTask(TypedDict, total=False):
    task_type: IntentType
    handler: TaskHandler
    stage: TaskStage
    slots: dict[str, Any]
    missing_slots: list[str]
    pending_action: PendingAction | None


class DialogState(TypedDict, total=False):
    active_task: ActiveTask | None


class AgentState(TypedDict):
    # 对话历史，使用 add_messages reducer 自动追加
    messages: Annotated[list[BaseMessage], add_messages]

    # 请求元信息
    user_id: str
    session_id: str

    # 查询改写后的结果：后续链路真正处理的单个问题。
    rewrite_query: str
    rewrite_analysis: str

    # 意图识别结果
    intent: IntentType
    confidence: float
    slots: dict[str, Any]
    task: TaskUpdate
    needs_clarification: bool
    clarify_question: str
    route: RouteType

    # RAG 检索结果
    rag_results: list[dict]

    # 对话状态追踪，存储多轮中提取到的关键槽位。如果遇到用户澄清的情况，意图识别看到TaskStage是confirming，就知道是继续之前的任务了。
    active_task: ActiveTask | None

    # 存储到数据库中，供重启流程恢复用
    dialog_state: DialogState
