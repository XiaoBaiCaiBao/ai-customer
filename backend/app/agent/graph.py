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
    ├─ needs_clarification ──→ chat_respond → END
    ├─ product_info / usage_issue / event ──→ rag → END
    ├─ complaint / aftersales ──→ api_call → END
    └─ chat / unknown ──→ chat_respond → END
"""

from langgraph.graph import StateGraph, START, END
from app.agent.state import AgentState
from app.agent.nodes.rewrite import rewrite_node
from app.agent.nodes.classify import classify_node, route_after_classify
from app.agent.nodes.rag_node import rag_node
from app.agent.nodes.api_node import api_node
from app.agent.nodes.chat_node import chat_node


def build_graph():
    builder = StateGraph(AgentState)

    # 注册节点
    builder.add_node("rewrite", rewrite_node)
    builder.add_node("classify", classify_node)
    builder.add_node("rag", rag_node)
    builder.add_node("api_call", api_node)
    builder.add_node("chat_respond", chat_node)

    # 边
    builder.add_edge(START, "rewrite")
    builder.add_edge("rewrite", "classify")

    # 意图路由（条件边）
    builder.add_conditional_edges(
        "classify",
        route_after_classify,
        {
            "rag": "rag",
            "api_call": "api_call",
            "chat_respond": "chat_respond",
            "clarify": "chat_respond",
        },
    )

    builder.add_edge("rag", END)
    builder.add_edge("api_call", END)
    builder.add_edge("chat_respond", END)

    return builder.compile()


# 全局单例
agent_graph = build_graph()
