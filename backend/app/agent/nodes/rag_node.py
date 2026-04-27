"""
节点3a: RAG 检索 + 生成回答

适用意图: product_info, usage_issue, event
通过 adispatch_custom_event 向前端推送检索思考步骤。
"""

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.callbacks.manager import adispatch_custom_event
from app.agent.state import AgentState
from app.config import get_settings
from app.rag.retriever import retrieve
from app.llm import get_llm
from app.message_utils import build_multimodal_prompt, get_message_text

from app.prompts.rag import RAG_SYSTEM_PROMPT


async def rag_node(state: AgentState) -> dict:
    latest_message = state["messages"][-1]
    query = state.get("rewritten_query") or get_message_text(latest_message)
    settings = get_settings()

    # ── Thought ──
    await adispatch_custom_event(
        "thinking_step",
        {
            "step_type": "thought",
            "step_num": 1,
            "content": f"用户在咨询产品相关问题，我需要在知识库中检索相关内容来回答。",
        },
    )

    # ── Action ──
    await adispatch_custom_event(
        "thinking_step",
        {
            "step_type": "action",
            "step_num": 2,
            "content": f'KnowledgeBase.search(query="{query}")',
        },
    )

    results = await retrieve(query)
    state_update: dict = {"rag_results": results}

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

    llm = get_llm(streaming=True)
    response = await llm.ainvoke([
        SystemMessage(content=RAG_SYSTEM_PROMPT.format(context=context)),
        build_multimodal_prompt(query, latest_message),
    ])

    state_update["messages"] = [AIMessage(content=response.content)]
    return state_update
