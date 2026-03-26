"""
节点2: 意图分类

使用结构化输出识别用户意图，返回意图类型、置信度。

路由分发（基于置信度 code 判断）：
  score < 0.6          → unrecognized (未识别兜底)
  0.6 <= score <= 0.85 → clarify (意图澄清卡片)
  score > 0.85         → query_router (LLM 决定下游业务)
"""

from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage
from app.agent.state import AgentState, IntentType
from app.llm import get_llm

from app.prompts.classify import CLASSIFY_PROMPT


class IntentResult(BaseModel):
    reasoning: str = Field(description="意图识别的思考过程（CoT）")
    intent: IntentType = Field(description="识别出的最核心意图")
    confidence: float = Field(ge=0.0, le=1.0, description="对该意图的置信度评分")


async def classify_node(state: AgentState) -> dict:
    query = state.get("rewritten_query") or state["messages"][-1].content

    llm = get_llm()
    structured_llm = llm.with_structured_output(IntentResult)

    prompt = CLASSIFY_PROMPT.format(query=query)
    result: IntentResult = await structured_llm.ainvoke([HumanMessage(content=prompt)])

    return {
        "intent": result.intent,
        "confidence": result.confidence,
    }


def route_after_classify(state: AgentState) -> str:
    """条件边：根据置信度判断是否进入 Query 路由"""
    confidence = state.get("confidence", 0.0)

    if confidence < 0.6:
        return "unrecognized"
    elif 0.6 <= confidence <= 0.85:
        return "clarify"
    else:
        return "query_router"
