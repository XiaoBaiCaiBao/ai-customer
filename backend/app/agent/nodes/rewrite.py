"""
查询改写节点。

职责只限于把本轮图文输入整理成后续节点可处理的独立 query。
它不做业务意图判断，不抽取业务槽位，也不向用户澄清。

输入概念：
- 当前输入：本轮用户文本。
- 当前图片列表：本轮用户上传的图片 URL；图片内容会随 prompt 一起发给多模态模型。
- 短期记忆 agent_state：dialog_state、active_task、最近对话摘要/窗口等会话状态。

输出概念：
- rewrite_query：改写后的 query，会写入短期记忆。
- rewrite_analysis：调试分析，只通过 SSE 发给前端，不写入短期记忆。
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.agent.json_output import ainvoke_json
from app.agent.state import AgentState
from app.llm import get_llm
from app.message_utils import build_multimodal_prompt, get_message_image_urls, get_message_text


MAX_MEMORY_MESSAGES = 8


REWRITE_PROMPT = """# Role
你是 BOU 客服 Agent 的 rewrite 节点。你只负责查询改写，不回答用户、不判断业务意图、不追问澄清。

# Input
- 当前系统时间：{current_time}
- 当前用户输入：{current_input}
- 当前图片列表：{current_images}
- 短期记忆 agent_state：
{agent_state}

# Responsibilities
1. 口语清洗与规范化
   去掉无业务意义的口头语、语气词、客套话，把表达整理成清楚、直接的自然语言查询。

2. 指代消解与上下文补全
   使用短期记忆 agent_state 中的 active_task、dialog_state、最近对话，补全“这个、那个、刚才、它、一样的问题”等省略表达。

3. 单问题改写
   用户本轮输入按一个完整问题处理，整理成一个清晰、连贯的问题。不要拆成多个链路。

4. 相对时间标准化
   如果用户提到“今天、昨天、上午、刚才”等相对时间，要结合当前系统时间改写成明确日期或更清晰的时间表达。
   不涉及时间时不要强行补时间。

5. 图文混合改写
   当前图片是本轮输入的一部分。文本很短但图片中有明确异常、界面、订单、聊天内容或提示时，要把图片信息融入 query。
   如果图片无法可靠识别，只保留“用户发送了图片/截图”这个事实，不要编造图片内容。

# Rules
- 不要回答用户问题。
- 不要输出澄清问题；是否澄清由后续意图识别节点判断。
- 不要编造短期记忆或图片中不存在的事实。
- 输出应是直接查询，不要写成“用户想要...”这类第三人称总结。
- 如果当前输入严重缺信息，也要尽量保留原始语义，输出一个可供意图识别判断的 query。

# Output
你必须只输出一个合法 JSON 对象，不要包含 Markdown。字段固定如下：
{{
  "query": "改写后的单个标准查询",
  "analysis": "简要说明使用了哪些上下文、图片信息，以及为什么这样改写"
}}
"""


class QueryRewriteResult(BaseModel):
    query: str = Field(description="改写后的单个标准查询")
    analysis: str = Field(description="调试用分析，不进入短期记忆")


def _message_summary(message: Any) -> dict[str, Any]:
    role = "user" if getattr(message, "type", "") == "human" else "assistant"
    return {
        "role": role,
        "text": get_message_text(message, include_image_hint=True),
        "image_count": len(get_message_image_urls(message)),
    }


def _short_memory_state(state: AgentState) -> dict[str, Any]:
    """构造给 rewrite 使用的短期记忆视图。

    最近历史也放在这里，而不是作为 rewrite 的单独输入。
    """

    dialog_state = state.get("dialog_state", {}) or {}
    messages = state.get("messages", [])
    recent_messages = [
        _message_summary(message)
        for message in messages[:-1][-MAX_MEMORY_MESSAGES:]
    ]
    return {
        "user_id": state.get("user_id"),
        "session_id": state.get("session_id"),
        "active_task": state.get("active_task") or dialog_state.get("active_task"),
        "dialog_state": dialog_state,
        "recent_messages": recent_messages,
    }


def _safe_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _clean_query(query: str | None, fallback: str) -> str:
    cleaned = (query or "").strip()
    return cleaned or fallback.strip() or "请结合当前输入继续处理。"


async def rewrite_node(state: AgentState) -> dict:
    messages = state["messages"]
    if not messages:
        return {
            "rewrite_query": "",
            "rewrite_analysis": "本轮没有用户消息，无法改写。",
            "dialog_state": state.get("dialog_state", {}),
            "active_task": state.get("active_task"),
        }

    latest_message = messages[-1]
    current_input = get_message_text(latest_message, include_image_hint=False)
    current_images = get_message_image_urls(latest_message)
    fallback_query = get_message_text(latest_message, include_image_hint=True)
    short_memory = _short_memory_state(state)

    prompt = REWRITE_PROMPT.format(
        current_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        current_input=current_input or "（用户本轮没有文本输入）",
        current_images=_safe_json(current_images),
        agent_state=_safe_json(short_memory),
    )

    try:
        result: QueryRewriteResult = await ainvoke_json(
            get_llm(),
            [build_multimodal_prompt(prompt, latest_message)],
            QueryRewriteResult,
        )
        rewrite_query = _clean_query(result.query, fallback_query)
        rewrite_analysis = result.analysis.strip()
    except Exception as exc:
        # rewrite 不能阻断主链路。模型异常时保留用户原文，让意图识别/兜底节点继续处理。
        rewrite_query = _clean_query(None, fallback_query)
        rewrite_analysis = f"rewrite 调用失败，已回退为用户原文：{exc}"

    dialog_state = dict(state.get("dialog_state", {}) or {})
    dialog_state["rewrite_query"] = rewrite_query

    return {
        "rewrite_query": rewrite_query,
        "rewrite_analysis": rewrite_analysis,
        "dialog_state": dialog_state,
        "active_task": state.get("active_task") or dialog_state.get("active_task"),
    }
