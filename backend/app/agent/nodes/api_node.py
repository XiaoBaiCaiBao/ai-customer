"""
节点3b: API 调用 + 生成回答

适用意图:
  - complaint:  安抚用户 + 调接口通知产研团队
  - aftersales: 收集信息 + 调接口通知产研团队

外部 API 地址由 .env 的 NOTIFY_API_URL 配置。
"""

import httpx
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from app.agent.state import AgentState
from app.config import get_settings
from app.llm import get_llm

from app.prompts.api import AFTERSALES_SYSTEM_PROMPT, COMPLAINT_SYSTEM_PROMPT


async def _notify_product_team(intent: str, user_id: str, content: str) -> bool:
    """调用管理后台接口，通知产研团队"""
    s = get_settings()
    if not s.NOTIFY_API_URL:
        print("[API] NOTIFY_API_URL 未配置，跳过通知")
        return False

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                s.NOTIFY_API_URL,
                json={"intent": intent, "user_id": user_id, "content": content},
                headers={"Authorization": f"Bearer {s.NOTIFY_API_KEY}"},
            )
            return resp.status_code == 200
    except Exception as e:
        print(f"[API] 通知失败: {e}")
        return False


async def api_node(state: AgentState) -> dict:
    intent = state.get("intent", "complaint")
    query = state.get("rewritten_query") or state["messages"][-1].content
    user_id = state.get("user_id", "anonymous")

    # 异步通知产研（不等待结果，不阻塞用户回复）
    await _notify_product_team(intent, user_id, query)

    # 根据意图选择回复策略
    if intent == "complaint":
        system_prompt = COMPLAINT_SYSTEM_PROMPT.format(query=query)
    else:
        system_prompt = AFTERSALES_SYSTEM_PROMPT.format(query=query)

    llm = get_llm(streaming=True)
    response = await llm.ainvoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=query),
    ])

    return {
        "api_response": "notified",
        "messages": [AIMessage(content=response.content)],
    }
