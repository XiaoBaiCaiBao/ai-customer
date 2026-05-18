"""RAG 处理路径：知识库检索 + 生成回答。"""

from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.callbacks.manager import adispatch_custom_event
from app.agent.state import AgentState
from app.agent.prompts.rag import get_rag_system_prompt
from app.config import get_settings
from app.rag.retriever import retrieve
from app.llm import get_llm
from app.message_utils import build_multimodal_prompt, get_message_text

RAG_SYSTEM_PROMPT = """你是 BOU 的 AI 客服助手，友好、专业、简洁。

请根据下方「知识库内容」回答用户的问题。
- 如果知识库中有明确答案，直接回答，可以适当用 emoji 让回复更友好
- 如果知识库内容不足，诚实告知「我暂时没有找到相关信息，建议您联系人工客服」
- 如果知识库内容与当前问题不匹配，不要借用其他主题的内容回答
- 不要编造不在知识库中的信息

知识库内容：
{context}"""


async def rag_node(state: AgentState) -> dict:
    latest_message = state["messages"][-1]
    query = state.get("rewrite_query") or get_message_text(latest_message)
    settings = get_settings()
    
    await adispatch_custom_event(
        "thinking_step",
        {
            "step_type": "action",
            "step_num": 2,
            "content": f'KnowledgeBase.search(query="{query}")',
        },
    )

    results = await retrieve(query)

    await adispatch_custom_event(
        "rag_meta",
        {
            "provider": settings.RAG_PROVIDER,
            "query": query,
            "result_count": len(results),
        },
    )

    if results:
        await adispatch_custom_event(
            "rag_results",
            {
                "query": query,
                "results": results,
            },
        )

    # ── Observation ──
    if results:
        sources = [r.get("source", "未知来源") for r in results]
        obs = f"检索到 {len(results)} 条相关内容，来源：{', '.join(set(sources))}"
    else:
        obs = "知识库中未找到相关内容，将诚实告知用户"

    await adispatch_custom_event(
        "thinking_step",
        {
            "step_type": "observation",
            "step_num": 3,
            "content": obs,
        },
    )

    # 构建上下文
    if results:
        context = "\n\n---\n\n".join(
            f"【来源: {r['source']}】\n{r['content']}" for r in results
        )
    else:
        context = "（知识库中暂无相关内容）"

    await adispatch_custom_event(
        "thinking_step",
        {
            "step_type": "final",
            "step_num": 4,
            "content": "已整理知识库内容，正在生成回复…",
        },
    )

    if results:
        llm = get_llm(streaming=True)
        response = await llm.ainvoke([
            SystemMessage(content=get_rag_system_prompt(RAG_SYSTEM_PROMPT).format(context=context)),
            build_multimodal_prompt(query, latest_message),
        ])
        answer = response.content
    else:
        answer = "我暂时没有找到相关信息，建议您联系人工客服"

    rag_results = [{**r, "query": query} for r in results]
    return {
        "messages": [AIMessage(content=answer)],
        "intent": state.get("intent", "unknown_respond"),
        "confidence": state.get("confidence", 0.0),
        "route": "rag",
        "rag_results": rag_results,
        "dialog_state": state.get("dialog_state", {}),
        "needs_clarification": False,
        "clarify_question": "",
    }
