"""
节点3c: 闲聊 / 意图澄清 / 兜底回复

适用意图: chat, unknown，以及需要澄清的情况
"""

from langchain_core.messages import AIMessage, SystemMessage
from app.agent.state import AgentState
from app.llm import get_llm

CHAT_SYSTEM_PROMPT = """你是 BOU 的 AI 助手「BOU Intelligence」，性格友好、活泼，有亲和力。

你服务于一个社交娱乐类 App。用户正在和你闲聊或提了一个超出产品范围的问题。
- 友好回应，可以简单聊几句
- 如果能引导回产品相关话题，自然地引导
- 不要假装自己是人类，可以说「我是 BOU 的 AI 助手」
- 回复简洁，2-4句话即可"""

CLARIFY_SYSTEM_PROMPT = """你是 BOU 的 AI 客服助手。

用户的问题不够清晰，请礼貌地向用户确认：
- 他具体遇到了什么问题
- 或者他想了解什么功能

用一个简短的反问句，帮助澄清意图。不超过2句话。"""


async def chat_node(state: AgentState) -> dict:
    needs_clarification = state.get("needs_clarification", False)
    system_prompt = CLARIFY_SYSTEM_PROMPT if needs_clarification else CHAT_SYSTEM_PROMPT

    llm = get_llm(streaming=True)
    response = await llm.ainvoke([
        SystemMessage(content=system_prompt),
        *state["messages"],
    ])

    return {"messages": [AIMessage(content=response.content)]}
