"""
节点: DST (对话状态追踪)
紧接在 classify 之后，更新 dialog_state 并判断是否缺少关键槽位。
"""

from pydantic import BaseModel, Field
from app.agent.state import AgentState
from app.llm import get_llm
from app.message_utils import build_multimodal_prompt, get_message_text

DST_PROMPT = """你是一个对话状态追踪（DST）助手。
当前用户的意图是：{intent}。
已有状态：{dialog_state}
用户最新回复：{query}

如果意图是 aftersales（售后问题），我们需要收集：
- issue_type: 问题类型（如：充值未到账、体力没加等）

如果意图是 complaint（吐槽/投诉），我们需要收集：
- topic: 吐槽的具体功能或内容

请根据用户的最新回复，更新已有状态中的槽位。只返回 JSON，格式如下：
{{
    "slots": {{
        "issue_type": "...",
        "topic": "..."
    }},
    "missing_slots": ["...", "..."] 
}}
如果某个意图不需要某个槽位，或者槽位还未提供，对应值为 null。
如果必须的槽位缺失，将槽位名放入 missing_slots 列表中。

JSON 返回："""


class DSTResult(BaseModel):
    slots: dict = Field(description="已收集到的所有槽位及其值")
    missing_slots: list[str] = Field(description="当前意图下必须但缺失的槽位列表")


async def dst_node(state: AgentState) -> dict:
    if state.get("needs_clarification"):
        return {}
        
    intent = state.get("intent", "unknown")
    latest_message = state["messages"][-1]
    query = state.get("rewrite_query") or get_message_text(latest_message)
    dialog_state = state.get("dialog_state", {})
    
    # 只有特定的 intent 我们才需要槽位
    if intent not in ["aftersales", "complaint"]:
        return {"dialog_state": dialog_state}
    
    llm = get_llm()
    structured_llm = llm.with_structured_output(DSTResult)
    
    prompt = DST_PROMPT.format(
        intent=intent,
        dialog_state=dialog_state,
        query=query
    )
    
    try:
        result: DSTResult = await structured_llm.ainvoke([
            build_multimodal_prompt(prompt, latest_message)
        ])
        # 更新 dialog_state
        new_state = {**dialog_state}
        for k, v in result.slots.items():
            if v:
                new_state[k] = v
                
        needs_clarification = state.get("needs_clarification") or len(result.missing_slots) > 0
        
        return {
            "dialog_state": new_state,
            "missing_slots": result.missing_slots,
            "needs_clarification": needs_clarification
        }
    except Exception as e:
        print(f"[DST] 状态追踪出错: {e}")
        return {"dialog_state": dialog_state}
