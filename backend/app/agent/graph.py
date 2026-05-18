"""
LangGraph Agent 图定义

流程:
  START
    │
    ▼
  rewrite (查询改写)
    │
    ▼
  classify (意图识别 / 轻量 DST / 路由)
    ├─ rag
    ├─ mcp_tool
    ├─ skills
    ├─ chat_respond
    └─ clarify
    │
    ▼
  END
"""

from langgraph.graph import StateGraph, START, END
from app.agent.state import AgentState
from app.agent.nodes.rewrite import rewrite_node
from app.agent.nodes.classify import classify_node
from app.agent.nodes.rag_node import rag_node
from app.agent.nodes.mcp_tool_node import mcp_tool_node
from app.agent.nodes.skills_node import skills_node
from app.agent.nodes.chat_node import chat_node, clarify_node


def build_graph():
    builder = StateGraph(AgentState)

    # 注册节点
    builder.add_node("rewrite", rewrite_node)
    builder.add_node(
        "classify",
        classify_node,
        destinations=("rag", "mcp_tool", "skills", "chat_respond", "clarify"),
    )
    builder.add_node("rag", rag_node)
    builder.add_node("mcp_tool", mcp_tool_node)
    builder.add_node("skills", skills_node)
    builder.add_node("chat_respond", chat_node)
    builder.add_node("clarify", clarify_node)

    # 主干边
    builder.add_edge(START, "rewrite")
    builder.add_edge("rewrite", "classify")

    # 终点
    builder.add_edge("rag", END)
    builder.add_edge("mcp_tool", END)
    builder.add_edge("skills", END)
    builder.add_edge("chat_respond", END)
    builder.add_edge("clarify", END)

    return builder.compile()


# 全局单例
agent_graph = build_graph()
