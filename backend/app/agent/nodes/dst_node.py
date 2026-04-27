"""
节点: DST (对话状态追踪)
紧接在 classify 之后，更新 dialog_state 并判断是否缺少关键槽位。
"""

from pydantic import BaseModel, Field
from app.agent.state import AgentState
from app.llm import get_llm
from app.message_utils import build_multimodal_prompt, get_message_text
from app.prompts.dst import DST_PROMPT


class DSTResult(BaseModel):
    slots: dict = Field(description="已收集到的所有槽位及其值")
    missing_slots: list[str] = Field(description="当前意图下必须但缺失的槽位列表")


async def dst_node(state: AgentState) -> dict:
    if state.get("needs_clarification"):
        return {}
        
    intent = state.get("intent", "unknown")
    latest_message = state["messages"][-1]
    query = state.get("rewritten_query") or get_message_text(latest_message)
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
