"""
查询改写节点。

这个节点只做“把当前用户输入变成后续节点容易处理的查询”，不负责回答、
分类或抽取业务槽位。它会综合三类上下文：
- 当前用户输入：本轮用户刚发送的原文。
- 当前图片：如果用户本轮发送了图片，图片内容也是本轮输入的一部分。
- 最近 N 条历史对话：用于承接上一轮主题、消解代词和省略表达。
- 短期记忆 dialog_state：用于读取已经确认的用户事实和当前会话主题。

输出字段说明：
- rewrite_query：真正交给后续执行链路的单个标准查询；需要澄清时为空。
"""

import json
from datetime import datetime

from pydantic import BaseModel, Field
from openai import APIStatusError

from app.agent.state import AgentState
from app.agent.prompts.rewrite import get_rewrite_prompt
from app.agent.json_output import ainvoke_json
from app.llm import get_llm
from app.message_utils import build_multimodal_prompt, get_message_image_urls, get_message_text


# query改写这里的问题
# 是否要保留“需要澄清”的分支？但如何判断问题不清晰，这不还是跟意图有关系吗？
# 综上，改写和意图识别是否真的能完全分开？如果不能，是不是就没必要非要分成两个节点了？


MAX_HISTORY_MESSAGES = 6
DEFAULT_CLARIFY_QUESTION = "我还需要再确认一下，你指的是哪个问题或对象？"
LLM_CONFIG_ERROR_QUESTION = "当前大模型配置不可用，请检查模型名称、Endpoint 或权限后重试。"


REWRITE_PROMPT = """# Role
你是客服对话系统里的查询改写节点。你的任务不是回答用户，也不是判断业务意图，
而是把用户当前输入改写成脱离上下文也能理解的标准查询。

# Input
- 当前系统时间：{current_time}
- 当前用户输入：{user_input}
- 当前图片：{image_context}
- 最近历史对话：
{history_text}
- 短期记忆：
{short_memory}

# Responsibilities
1. 口语清洗与规范化
   去掉无业务意义的口头语、语气词、客套话，把表达整理成清楚、直接的自然语言查询。

2. 指代消解与上下文补全
   结合最近历史对话和短期记忆，补全“这个、那个、它、刚才的、什么时候、怎么弄”等省略表达。
   如果历史和短期记忆里有明确对象，要把对象写进改写结果。
   如果用户本轮发送了图片，图片内容也是当前输入。当前文本很短（如“咋回事”“这个怎么弄”）
   但图片中有明确产品界面或异常状态时，要结合图片补全查询，不要仅因为文本短就澄清。

3. 单问题改写
   用户输入按本轮完整问题处理，把它整理成一个清晰、连贯的问题。

4. 指代不明阻断
   如果当前输入依赖上下文，并且当前图片、历史对话和短期记忆都无法唯一确定指代对象，不要猜。
   此时 needs_clarification 必须为 true，query 必须为空，并给出一句面向用户的澄清问题。

# Rules
- 不要回答用户问题。
- 不要编造历史对话和短期记忆中不存在的事实。
- 不要输出第三人称总结，例如“用户想查询...”。输出应是直接查询，例如“月卡VIP用户有哪些权益？”。
- 相对时间要结合当前系统时间转成明确日期；不涉及时间时不要强行补时间。
- 如果当前输入本身已经清楚，也仍然要输出规范化后的 query，不要跳过改写。
- 保留本轮输入的完整含义，整理为一个综合查询。
- 如果图片内容足以确定用户在问的对象，可以输出基于图片的查询；如果图片内容也无法判断，再澄清。

# Output
你必须只输出一个合法 JSON 对象，不要包含 Markdown。字段固定如下：
{{
  "analysis": "说明如何判断指代关系、是否使用历史/短期记忆、是否需要澄清。",
  "used_history": true,
  "used_short_memory": false,
  "needs_clarification": false,
  "clarification_question": null,
  "query": "标准且独立的自然语言查询"
}}

# Few-shots

## Example 1: 依赖历史对话补全省略主语
Input:
- 当前用户输入：那我有什么权益？
- 最近历史对话：
用户: 我是月卡VIP
- 短期记忆：暂无

Output:
{{
  "analysis": "当前输入中的“我”需要结合上一轮用户自述补全为“月卡VIP用户”。输出一个标准查询。",
  "used_history": true,
  "used_short_memory": false,
  "needs_clarification": false,
  "clarification_question": null,
  "query": "月卡VIP用户有哪些权益？"
}}

## Example 2: 输入过短且无明确承接对象
Input:
- 当前用户输入：啥？
- 最近历史对话：暂无
- 短期记忆：暂无

Output:
{{
  "analysis": "当前输入只有反问词，没有明确问题对象；历史对话和短期记忆也没有可承接的信息，无法安全改写。",
  "used_history": false,
  "used_short_memory": false,
  "needs_clarification": true,
  "clarification_question": "你是想问哪件事？可以再补充一下具体问题吗？",
  "query": null
}}

## Example 3: 多点输入仍作为一个问题处理
Input:
- 当前用户输入：深夜模式在哪儿开？年龄怎么调啊
- 最近历史对话：暂无
- 短期记忆：暂无

Output:
{{
  "analysis": "当前输入提到了深夜模式入口和年龄修改方式；不依赖历史对话或短期记忆。按单问题链路保留为一个综合查询。",
  "used_history": false,
  "used_short_memory": false,
  "needs_clarification": false,
  "clarification_question": null,
  "query": "深夜模式在哪里开启，以及年龄怎么修改？"
}}

## Example 4: 结合图片补全短问句
Input:
- 当前用户输入：咋回事？
- 当前图片：用户发送了 1 张截图，截图中聊天消息旁出现红色感叹号。
- 最近历史对话：暂无
- 短期记忆：暂无

Output:
{{
  "analysis": "当前文本很短，但图片中有明确的聊天红色感叹号异常状态，可以结合图片补全为内容安全相关问题，不需要澄清。",
  "used_history": false,
  "used_short_memory": false,
  "needs_clarification": false,
  "clarification_question": null,
  "query": "聊天消息为什么出现红色感叹号？"
}}
"""


class QueryRewriteResult(BaseModel):
    """LLM 结构化输出。保持扁平字段，方便日志、调试和状态传递。"""

    analysis: str = Field(description="改写分析：指代、上下文依赖和澄清判断。")
    used_history: bool = Field(description="是否使用最近历史对话完成改写。")
    used_short_memory: bool = Field(description="是否使用短期记忆完成改写。")
    needs_clarification: bool = Field(description="是否因指代严重不明而需要向用户澄清。")
    clarification_question: str | None = Field(default=None, description="需要澄清时面向用户的问题。")
    query: str | None = Field(default=None, description="改写后的单个标准查询；需要澄清时为空。")


def _format_recent_history(state: AgentState) -> str:
    """把最近 N 条历史消息整理成 prompt 中稳定可读的对话文本。"""

    history_msgs = state["messages"][:-1][-MAX_HISTORY_MESSAGES:]
    if not history_msgs:
        return "暂无"

    lines = []
    for message in history_msgs:
        role = "用户" if message.type == "human" else "AI"
        text = get_message_text(message)
        if text:
            lines.append(f"{role}: {text}")
    return "\n".join(lines) if lines else "暂无"


def _format_short_memory(state: AgentState) -> str:
    """短期记忆目前来自 dialog_state，后续可以替换成固定 schema 的摘要。"""

    dialog_state = state.get("dialog_state", {})
    return str(dialog_state) if dialog_state else "暂无"


def _format_image_context(state: AgentState) -> str:
    """说明当前消息是否包含图片；图片本体会随 prompt 一起传给多模态模型。"""

    image_count = len(get_message_image_urls(state["messages"][-1]))
    if not image_count:
        return "无"
    return f"用户本轮发送了 {image_count} 张图片，请把图片内容视为当前输入的一部分。"


def _clean_query(query: str | None) -> str:
    """清理空白，避免下游处理空问题。"""

    return query.strip() if query and query.strip() else ""


async def rewrite_node(state: AgentState) -> dict:
    messages = state["messages"]
    if not messages:
        return {
            "rewrite_query": "",
            "rewrite_analysis": "",
            "rewrite_used_history": False,
            "rewrite_used_short_memory": False,
            "needs_clarification": False,
            "clarify_question": "",
        }

    latest_message = messages[-1]
    current_query = get_message_text(latest_message)
    history_text = _format_recent_history(state)
    short_memory = _format_short_memory(state)
    image_context = _format_image_context(state)

    prompt = get_rewrite_prompt(REWRITE_PROMPT).format(
        current_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        user_input=current_query,
        image_context=image_context,
        history_text=history_text,
        short_memory=short_memory,
    )

    llm = get_llm()
    try:
        result: QueryRewriteResult = await ainvoke_json(llm, [
            build_multimodal_prompt(prompt, latest_message)
        ], QueryRewriteResult)
    except APIStatusError as e:
        message = str(e)
        if e.status_code == 404 or "InvalidEndpointOrModel" in message:
            clarify_question = LLM_CONFIG_ERROR_QUESTION
        else:
            clarify_question = "当前大模型服务暂时不可用，请稍后再试。"
        return {
            "rewrite_query": "",
            "rewrite_analysis": message,
            "rewrite_used_history": False,
            "rewrite_used_short_memory": False,
            "needs_clarification": True,
            "clarify_question": clarify_question,
        }
    except RuntimeError as e:
        message = str(e)
        if "LLM HTTP 401" in message:
            clarify_question = "当前大模型鉴权失败，请检查 Ark API Key 后重试。"
        elif "LLM HTTP 429" in message:
            clarify_question = "当前大模型请求被限流或额度不足，请稍后再试。"
        else:
            clarify_question = "当前大模型服务暂时不可用，请稍后再试。"
        return {
            "rewrite_query": "",
            "rewrite_analysis": message,
            "rewrite_used_history": False,
            "rewrite_used_short_memory": False,
            "needs_clarification": True,
            "clarify_question": clarify_question,
        }
    except (json.JSONDecodeError, ValueError) as e:
        return {
            "rewrite_query": "",
            "rewrite_analysis": f"LLM JSON parse failed: {e}",
            "rewrite_used_history": False,
            "rewrite_used_short_memory": False,
            "needs_clarification": True,
            "clarify_question": "当前大模型输出格式异常，请稍后再试。",
        }

    if result.needs_clarification:
        clarify_question = result.clarification_question or DEFAULT_CLARIFY_QUESTION
        return {
            "rewrite_query": "",
            "rewrite_analysis": result.analysis,
            "rewrite_used_history": result.used_history,
            "rewrite_used_short_memory": result.used_short_memory,
            "needs_clarification": True,
            "clarify_question": clarify_question,
        }

    rewrite_query = _clean_query(result.query)
    if not rewrite_query:
        clarify_question = result.clarification_question or DEFAULT_CLARIFY_QUESTION
        return {
            "rewrite_query": "",
            "rewrite_analysis": result.analysis,
            "rewrite_used_history": result.used_history,
            "rewrite_used_short_memory": result.used_short_memory,
            "needs_clarification": True,
            "clarify_question": clarify_question,
        }

    return {
        "rewrite_query": rewrite_query,
        "rewrite_analysis": result.analysis,
        "rewrite_used_history": result.used_history,
        "rewrite_used_short_memory": result.used_short_memory,
        "needs_clarification": False,
        "clarify_question": "",
    }
