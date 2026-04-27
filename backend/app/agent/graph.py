"""
LangGraph Agent 图定义

流程:
  START
    │
    ▼
  rewrite (查询改写)
    │
    ▼
  classify (意图分类)
    │
    ▼
  dst (对话状态追踪)
    │
    ├─ score < 0.6           → unrecognized → END
    ├─ 0.6 <= score <= 0.85  → clarify      → END
    └─ score > 0.85（按意图直接路由）
         ├─ app_info / usage_issue → rag      → END  （RAG 链路）
         ├─ user_voice             → api_call → END  （MCP 链路）
         ├─ aftersales             → skills   → END  （Skills 链路）
         └─ 其他                   → chat_respond → END
"""

from langgraph.graph import StateGraph, START, END
from app.agent.state import AgentState
from app.agent.nodes.rewrite import rewrite_node
from app.agent.nodes.classify import classify_node, route_after_classify
from app.agent.nodes.dst_node import dst_node
from app.agent.nodes.rag_node import rag_node
from app.agent.nodes.api_node import api_node
from app.agent.nodes.chat_node import chat_node, clarify_node, unrecognized_node
from app.agent.nodes.skills_node import skills_node


def build_graph():
    builder = StateGraph(AgentState)

    # 注册节点
    builder.add_node("rewrite", rewrite_node)
    builder.add_node("classify", classify_node)
    builder.add_node("dst", dst_node)
    builder.add_node("rag", rag_node)
    builder.add_node("api_call", api_node)
    builder.add_node("skills", skills_node)
    builder.add_node("chat_respond", chat_node)
    builder.add_node("clarify", clarify_node)
    builder.add_node("unrecognized", unrecognized_node)

    # 主干边
    builder.add_edge(START, "rewrite")
    builder.add_edge("rewrite", "classify")
    builder.add_edge("classify", "dst")

    # 置信度 + 意图 → 3条执行链路（无需额外路由节点）
    builder.add_conditional_edges(
        "dst",
        route_after_classify,
        {
            "rag": "rag",
            "api_call": "api_call",
            "skills": "skills",
            "chat_respond": "chat_respond",
            "clarify": "clarify",
            "unrecognized": "unrecognized",
        },
    )

    # 终点
    builder.add_edge("rag", END)
    builder.add_edge("api_call", END)
    builder.add_edge("skills", END)
    builder.add_edge("chat_respond", END)
    builder.add_edge("clarify", END)
    builder.add_edge("unrecognized", END)

    return builder.compile()


# 全局单例
agent_graph = build_graph()
