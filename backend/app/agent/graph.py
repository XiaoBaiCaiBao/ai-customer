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
    ├─ score < 0.6 ─────────────────────→ unrecognized → END
    ├─ 0.6 <= score <= 0.85 ────────────→ clarify      → END
    └─ score > 0.85 ────────────────────→ query_router (LLM 路由决策)
                                              │
                                              ├─ rag       → END
                                              ├─ api_call  → END
                                              ├─ react     → END
                                              ├─ web_search→ END
                                              └─ chat      → END
"""

from langgraph.graph import StateGraph, START, END
from app.agent.state import AgentState
from app.agent.nodes.rewrite import rewrite_node
from app.agent.nodes.classify import classify_node, route_after_classify
from app.agent.nodes.query_router import query_router_node, route_after_query_router
from app.agent.nodes.dst_node import dst_node
from app.agent.nodes.rag_node import rag_node
from app.agent.nodes.api_node import api_node
from app.agent.nodes.chat_node import chat_node, clarify_node, unrecognized_node
from app.agent.nodes.web_search_node import web_search_node
from app.agent.nodes.react_node import react_node


def build_graph():
    builder = StateGraph(AgentState)

    # 注册节点
    builder.add_node("rewrite", rewrite_node)
    builder.add_node("classify", classify_node)
    builder.add_node("query_router", query_router_node)
    builder.add_node("dst", dst_node)
    builder.add_node("rag", rag_node)
    builder.add_node("api_call", api_node)
    builder.add_node("chat_respond", chat_node)
    builder.add_node("clarify", clarify_node)
    builder.add_node("unrecognized", unrecognized_node)
    builder.add_node("web_search", web_search_node)
    builder.add_node("react", react_node)

    # 边
    builder.add_edge(START, "rewrite")
    builder.add_edge("rewrite", "classify")
    builder.add_edge("classify", "dst")

    # 意图分流：根据置信度判定走路由 / 澄清 / 未识别
    builder.add_conditional_edges(
        "dst",
        route_after_classify,
        {
            "query_router": "query_router",
            "clarify": "clarify",
            "unrecognized": "unrecognized",
        },
    )

    # Router节点二次路由：由 LLM 决定走到哪一个具体业务处理节点
    builder.add_conditional_edges(
        "query_router",
        route_after_query_router,
        {
            "rag": "rag",
            "api_call": "api_call",
            "react": "react",
            "web_search": "web_search",
            "chat_respond": "chat_respond",
        },
    )

    # 各个终点
    builder.add_edge("rag", END)
    builder.add_edge("api_call", END)
    builder.add_edge("chat_respond", END)
    builder.add_edge("clarify", END)
    builder.add_edge("unrecognized", END)
    builder.add_edge("web_search", END)
    builder.add_edge("react", END)

    return builder.compile()


# 全局单例
agent_graph = build_graph()
