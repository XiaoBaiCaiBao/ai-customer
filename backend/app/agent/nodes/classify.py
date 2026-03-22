"""
节点2: 意图分类

使用结构化输出识别用户意图，返回意图类型、置信度，
以及是否需要澄清。

路由规则：
  product_info / usage_issue / event  → rag
  complaint                           → api_call
  aftersales                          → react  (多步查证与补偿)
  web_search                          → web_search
  chat / unknown                      → chat_respond
"""

from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage
from app.agent.state import AgentState, IntentType
from app.llm import get_llm

CLASSIFY_PROMPT = """你是一个意图分类助手，服务于一个社交娱乐类 App（包含 AI 聊天、会员系统、积分、活动等功能）。

请将用户的问题分类到以下意图之一：

- product_info:  关于产品功能和使用方法（如：星能是什么？签到怎么补签？）
- usage_issue:   使用中遇到的问题（如：积分没到账、回声贝是红色感叹号）
- complaint:     对产品的吐槽和建议（如：这个设计很丑、能增加某个功能吗）
- aftersales:    与用户本身相关的售后问题，涉及订单/充值/资产异常（如：我充值了月卡没到账、体力值未到账）
- event:         运营活动、二创相关咨询
- web_search:    需要查询实时信息（如：今天天气、最新新闻、当前汇率）
- chat:          闲聊或与产品无关的对话

用户问题：{query}

请以 JSON 格式返回，不要有其他文字。"""


class IntentResult(BaseModel):
    intent: IntentType
    confidence: float = Field(ge=0.0, le=1.0)
    needs_clarification: bool
    clarification_question: str = Field(default="")


async def classify_node(state: AgentState) -> dict:
    query = state.get("rewritten_query") or state["messages"][-1].content

    llm = get_llm()
    structured_llm = llm.with_structured_output(IntentResult)

    prompt = CLASSIFY_PROMPT.format(query=query)
    result: IntentResult = await structured_llm.ainvoke([HumanMessage(content=prompt)])

    return {
        "intent": result.intent,
        "confidence": result.confidence,
        "needs_clarification": result.needs_clarification and result.confidence < 0.6,
    }


def route_after_classify(state: AgentState) -> str:
    """条件边：根据意图决定下一个节点"""
    if state.get("needs_clarification"):
        return "clarify"

    intent = state.get("intent", "chat")
    if intent in ("product_info", "usage_issue", "event"):
        return "rag"
    elif intent == "complaint":
        return "api_call"
    elif intent == "aftersales":
        return "react"
    elif intent == "web_search":
        return "web_search"
    else:
        return "chat_respond"
