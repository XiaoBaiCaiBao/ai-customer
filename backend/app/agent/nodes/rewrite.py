"""
节点1: 查询改写

将用户的最新消息结合对话历史，改写成一个语义完整、独立的查询。
解决「代词指代」「省略主语」等多轮对话中的歧义问题。

例:
  历史: "我是月卡VIP"
  用户: "那我有什么权益？"
  改写: "月卡VIP用户有哪些权益？"
"""

from datetime import datetime
from pydantic import BaseModel, Field
from app.agent.state import AgentState
from app.llm import get_llm
from app.message_utils import (
    build_multimodal_prompt,
    get_message_image_urls,
    get_message_text,
)

from app.prompts.rewrite import REWRITE_PROMPT

class ThoughtProcess(BaseModel):
    step1_analysis: str = Field(description="分析指代关系、是否多意图、是否需要安全阻断。")
    step2_rewrite: str = Field(description="说明口语清洗、上下文补全及时间对齐的具体过程。")

class Telemetry(BaseModel):
    is_multi_turn_context: bool = Field(description="是否依赖了历史记忆（memory_data）来完成补全或消解")
    has_noise_cleaned: bool = Field(description="是否对用户的原始输入进行了口语去噪和清洗")

class RewriteResult(BaseModel):
    thought_process: ThoughtProcess
    telemetry: Telemetry
    rewritten_queries: list[str] = Field(description="生成的标准且独立的自然语言查询语句")
    need_clarification: bool = Field(description="如果指代严重不明导致无法安全改写，设为 true，并清空 rewritten_queries 数组。")

async def rewrite_node(state: AgentState) -> dict:
    messages = state["messages"]
    if not messages:
        return {"rewritten_query": ""}

    # 最后一条是用户当前消息
    latest_message = messages[-1]
    current_query = get_message_text(latest_message)

    # 取最近 6 条历史（不含当前）作为上下文
    history_msgs = messages[:-1][-6:]
    history_text = "\n".join(
        f"{'用户' if m.type == 'human' else 'AI'}: {get_message_text(m)}"
        for m in history_msgs
    )

    # 提取短期记忆（如有）
    dialog_state = state.get("dialog_state", {})
    dialog_state_text = str(dialog_state) if dialog_state else "暂无"

    # 无历史且无图片时直接跳过改写，节省 LLM 调用
    if not history_text.strip() and not get_message_image_urls(latest_message):
        return {"rewritten_query": current_query}

    llm = get_llm()
    structured_llm = llm.with_structured_output(RewriteResult)
    
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    memory_data_text = f"对话记录：\n{history_text}\n短期记忆(槽位等)：\n{dialog_state_text}"
    
    prompt = REWRITE_PROMPT.format(
        current_time=current_time,
        user_input=current_query,
        memory_data=memory_data_text
    )
    result: RewriteResult = await structured_llm.ainvoke([
        build_multimodal_prompt(prompt, latest_message)
    ])
    
    if result.need_clarification or not result.rewritten_queries:
        # 如果严重阻断，这里可以直接将阻断标识传递给后续，但为了简化，直接用原 query 往下走
        # 实际可以在 state 中加一个 need_clarification 字段在下一步直接拦截
        rewritten = current_query
    else:
        # 把多个独立改写结果用逗号拼接，或者直接传第一个（视下游能够处理多意图情况而定，这里默认拼接）
        rewritten = "，".join(result.rewritten_queries).strip()

    return {"rewritten_query": rewritten or current_query}
