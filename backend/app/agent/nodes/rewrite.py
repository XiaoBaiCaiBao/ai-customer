"""
节点1: 查询改写

将用户的最新消息结合对话历史，改写成一个语义完整、独立的查询。
解决「代词指代」「省略主语」等多轮对话中的歧义问题。

例:
  历史: "我是月卡VIP"
  用户: "那我有什么权益？"
  改写: "月卡VIP用户有哪些权益？"
"""

from langchain_core.messages import HumanMessage
from app.agent.state import AgentState
from app.llm import get_llm

REWRITE_PROMPT = """你是一个查询改写助手。根据对话历史，将用户最新的问题改写成一个完整、独立、清晰的查询语句。

要求：
- 补全代词指代（把"它"、"这个"、"那个"替换为具体名词）
- 补全省略的主语或宾语
- 保持用户的原意，不要添加额外假设
- 如果问题已经足够清晰，直接返回原文
- 只输出改写后的查询，不要解释

对话历史：
{history}

用户最新问题：{query}

改写后的查询："""


async def rewrite_node(state: AgentState) -> dict:
    messages = state["messages"]
    if not messages:
        return {"rewritten_query": ""}

    # 最后一条是用户当前消息
    current_query = messages[-1].content

    # 取最近 6 条历史（不含当前）作为上下文
    history_msgs = messages[:-1][-6:]
    history_text = "\n".join(
        f"{'用户' if m.type == 'human' else 'AI'}: {m.content}"
        for m in history_msgs
    )

    # 无历史时直接跳过改写，节省 LLM 调用
    if not history_text.strip():
        return {"rewritten_query": current_query}

    llm = get_llm()
    prompt = REWRITE_PROMPT.format(history=history_text, query=current_query)
    response = await llm.ainvoke([HumanMessage(content=prompt)])
    rewritten = response.content.strip()

    return {"rewritten_query": rewritten or current_query}
