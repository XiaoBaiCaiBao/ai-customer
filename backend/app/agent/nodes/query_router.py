"""
节点：Query 路由

仅在置信度 > 0.85 时触发。通过大模型（结合意图与原始 Query）决定具体调用的下游业务节点。
"""

from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage
from app.agent.state import AgentState
from app.llm import get_llm
from typing import Literal

from app.prompts.query_router import QUERY_ROUTER_PROMPT


RouteDestination = Literal[
    "rag",           # 知识库检索（包含产品信息、使用故障、活动）
    "api_call",      # 直接调用客诉记录 API
    "react",         # 售后多步复杂查证（充值、订单等）
    "web_search",    # 联网搜索
    "chat_respond"   # 闲聊、兜底回复
]


class RouteResult(BaseModel):
    reasoning: str = Field(description="路由选择的思考过程（CoT）")
    destination: RouteDestination = Field(description="选定的下游业务节点")


async def query_router_node(state: AgentState) -> dict:
    query = state.get("rewritten_query") or state["messages"][-1].content
    intent = state.get("intent", "unknown")

    llm = get_llm()
    structured_llm = llm.with_structured_output(RouteResult)

    prompt = QUERY_ROUTER_PROMPT.format(query=query, intent=intent)
    result: RouteResult = await structured_llm.ainvoke([HumanMessage(content=prompt)])

    return {
        "route_destination": result.destination,
    }


def route_after_query_router(state: AgentState) -> str:
    """条件边：根据路由节点的决策，转发给对应的业务节点"""
    destination = state.get("route_destination", "chat_respond")
    return destination
