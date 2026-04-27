"""
节点2: 意图分类

使用结构化输出识别用户意图，返回意图类型、置信度。

路由分发（置信度 + 意图 → 3条执行链路）：
  score < 0.6          → unrecognized
  0.6 <= score <= 0.85 → clarify
  score > 0.85:
    app_info / usage_issue → rag    （RAG 链路）
    user_voice             → api_call（MCP 链路）
    aftersales             → skills  （Skills 链路）
    其他                    → chat_respond
"""

from pydantic import BaseModel, Field
from app.agent.state import AgentState, IntentType
from app.llm import get_llm
from app.message_utils import build_multimodal_prompt, get_message_text

from app.prompts.classify import CLASSIFY_PROMPT


class SlotStrategy(BaseModel):
    inherit_from_memory: bool = Field(description="是否从 Memory 继承槽位")
    override: dict = Field(description="本轮用户显式覆盖的槽位字典")

class IntentResult(BaseModel):
    predicted_intent: IntentType = Field(description="识别出的最核心意图")
    confidence: float = Field(ge=0.0, le=1.0, description="对该意图的置信度评分")
    slot_strategy: SlotStrategy = Field(description="槽位继承与覆盖策略")
    clarify_question: str | None = Field(default=None, description="如果需要澄清，写具体问题")
    reasoning: str = Field(description="判断依据和推理过程")

async def classify_node(state: AgentState) -> dict:
    latest_message = state["messages"][-1]
    query = state.get("rewritten_query") or get_message_text(latest_message)
    
    # 构建 memory_state (简单提取)
    memory_state = {
        "last_intent": state.get("intent"),
        "slots": state.get("dialog_state", {})
    }

    llm = get_llm()
    structured_llm = llm.with_structured_output(IntentResult)

    prompt = CLASSIFY_PROMPT.format(query=query, memory_state=memory_state)
    result: IntentResult = await structured_llm.ainvoke([
        build_multimodal_prompt(prompt, latest_message)
    ])
    
    # 结合 slot_strategy 更新 dialog_state (可选，如果在此处就处理槽位覆盖的话)
    new_dialog_state = state.get("dialog_state", {}).copy() if result.slot_strategy.inherit_from_memory else {}
    new_dialog_state.update(result.slot_strategy.override)

    return {
        "intent": result.predicted_intent,
        "confidence": result.confidence,
        "dialog_state": new_dialog_state,
        "needs_clarification": result.clarify_question is not None,
        "clarify_question": result.clarify_question
    }


def route_after_classify(state: AgentState) -> str:
    """条件边：置信度分流后按意图直接路由到 3 条执行链路，无需额外 LLM 路由节点"""
    confidence = state.get("confidence", 0.0)

    if confidence < 0.6:
        return "unrecognized"
    elif confidence <= 0.85:
        return "clarify"

    intent = state.get("intent", "unknown_respond")
    if intent in ("app_info", "usage_issue"):
        return "rag"
    elif intent == "user_voice":
        return "api_call"
    elif intent == "aftersales":
        return "skills"
    else:
        return "chat_respond"
