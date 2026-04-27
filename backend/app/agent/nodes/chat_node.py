"""
节点3c: 闲聊 / 意图澄清 / 兜底回复

适用意图: chat，以及意图澄清、未识别的代码直出兜底逻辑
"""

from langchain_core.messages import AIMessage, SystemMessage
from app.agent.state import AgentState
from app.llm import get_llm

from app.prompts.chat import CHAT_SYSTEM_PROMPT


async def chat_node(state: AgentState) -> dict:
    """正常走闲聊对话逻辑的节点"""
    llm = get_llm(streaming=True)
    response = await llm.ainvoke([
        SystemMessage(content=CHAT_SYSTEM_PROMPT),
        *state["messages"],
    ])

    return {"messages": [AIMessage(content=response.content)]}


async def clarify_node(state: AgentState) -> dict:
    """代码实现：0.6 <= 置信度 <= 0.85，下发猜您想问卡片"""
    clarify_question = state.get("clarify_question")
    if clarify_question:
        content = clarify_question
    else:
        # 实际业务中可根据当前 state["intent"] 去推荐相关问题，这里提供通用兜底示例
        content = "我好像没完全明白您的意思，您是想问以下哪个问题呢？\n1. 账号充值及资产问题\n2. 产品功能怎么用\n3. 遇到报错或异常"
        
    msg = AIMessage(
        content=content,
        additional_kwargs={"ui_type": "guess_ask_card"}
    )
    return {"messages": [msg]}


async def unrecognized_node(state: AgentState) -> dict:
    """代码实现：置信度 < 0.6，直接返回未识别兜底话术"""
    msg = AIMessage(content="不好意思，未识别到您的问题，请换个问法吧")
    return {"messages": [msg]}
