"""闲聊、澄清和未识别处理路径。"""

from langchain_core.messages import AIMessage, SystemMessage
from app.agent.state import AgentState
from app.llm import get_llm

CHAT_SYSTEM_PROMPT = """你是 BOU 的 AI 助手「BOU Intelligence」，性格友好、活泼，有亲和力。

你服务于一个社交娱乐类 App。用户正在和你闲聊或提了一个超出产品范围的问题。
- 友好回应，可以简单聊几句
- 如果能引导回产品相关话题，自然地引导
- 不要假装自己是人类，可以说「我是 BOU 的 AI 助手」
- 回复简洁，2-4句话即可"""


async def chat_node(state: AgentState) -> dict:
    llm = get_llm()
    response = await llm.ainvoke([
        SystemMessage(content=CHAT_SYSTEM_PROMPT),
        *state["messages"],
    ])
    return {
        "messages": [AIMessage(content=response.content)],
        "intent": state.get("intent", "chat_respond"),
        "confidence": state.get("confidence", 0.0),
        "route": "chat_respond",
        "rag_results": [],
        "dialog_state": state.get("dialog_state", {}),
        "needs_clarification": False,
        "clarify_question": "",
    }


async def clarify_node(state: AgentState) -> dict:
    content = (
        state.get("clarify_question")
        or state.get("rewrite_query")
        or "我好像没完全明白您的意思，您可以再具体描述一下吗？"
    )
    return {
        "messages": [AIMessage(content=content)],
        "intent": state.get("intent", "unknown_respond"),
        "confidence": state.get("confidence", 0.0),
        "route": "clarify",
        "rag_results": [],
        "dialog_state": state.get("dialog_state", {}),
        "needs_clarification": True,
        "clarify_question": content,
    }


async def unrecognized_node(state: AgentState) -> dict:
    content = "这个问题我还没识别清楚，可以换个问法吗？"
    return {
        "messages": [AIMessage(content=content)],
        "intent": "unknown_respond",
        "confidence": state.get("confidence", 0.0),
        "route": "unrecognized",
        "rag_results": [],
        "dialog_state": state.get("dialog_state", {}),
        "needs_clarification": False,
        "clarify_question": "",
    }
