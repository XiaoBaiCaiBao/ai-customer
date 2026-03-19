"""
节点3a: RAG 检索 + 生成回答

适用意图: product_info, usage_issue, event
"""

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from app.agent.state import AgentState
from app.rag.retriever import retrieve
from app.llm import get_llm

RAG_SYSTEM_PROMPT = """你是 BOU 的 AI 客服助手，友好、专业、简洁。

请根据下方「知识库内容」回答用户的问题。
- 如果知识库中有明确答案，直接回答，可以适当用 emoji 让回复更友好
- 如果知识库内容不足，诚实告知「我暂时没有找到相关信息，建议您联系人工客服」
- 不要编造不在知识库中的信息

知识库内容：
{context}"""


async def rag_node(state: AgentState) -> dict:
    query = state.get("rewritten_query") or state["messages"][-1].content

    results = await retrieve(query)
    state_update: dict = {"rag_results": results}

    # 构建上下文
    if results:
        context = "\n\n---\n\n".join(
            f"【来源: {r['source']}】\n{r['content']}" for r in results
        )
    else:
        context = "（知识库中暂无相关内容）"

    llm = get_llm(streaming=True)
    response = await llm.ainvoke([
        SystemMessage(content=RAG_SYSTEM_PROMPT.format(context=context)),
        HumanMessage(content=query),
    ])

    state_update["messages"] = [AIMessage(content=response.content)]
    return state_update
