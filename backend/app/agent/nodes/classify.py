"""
节点2: 意图分类

使用结构化输出识别用户意图，返回意图类型、置信度。

路由分发（置信度 + 意图 → 处理路径）：
  score < 0.6 或 unknown_respond → unrecognized
  0.6 <= score <= 0.85 或需要澄清 → clarify
  RAG 咨询类 → rag
  MCP 工具类 → mcp_tool
  售后类 → skills
  其他 → chat_respond
"""

from langgraph.types import Command
from langchain_core.callbacks.manager import adispatch_custom_event
from pydantic import BaseModel, Field
from typing import get_args
from app.agent.json_output import ainvoke_json
from app.agent.state import AgentState, IntentType
from app.llm import get_llm
from app.message_utils import build_multimodal_prompt, get_message_text

CLASSIFY_PROMPT = """你是一个智能 BOU 客服问答助手，请协助完成“用户意图识别”任务。你的任务是根据用户的自然语言输入，结合历史上下文（Memory）判断用户的真实意图，并返回标准化的意图标签和置信度。

你需要综合考虑：
1. 用户当前输入的内容；
2. 会话记忆 memory_state（包含上一轮意图、已填槽位等信息）；
3. 在重复意图、槽位补全、意图切换确认等场景下，合理复用或覆盖 Memory 信息。

# 意图分类列表（业务类共13类 + 系统兜底2类）：
请只输出下列英文标签中的一个，不要输出中文意图名。

1. usage_guide：使用指南
   - iOS/安卓下载、海外 Apple ID / 切区、充值入口、支付路径。
   - 用户想知道“怎么下载安装到哪里、入口在哪里、支付怎么走”。

2. account_issue_consult：账号问题咨询
   - 预约账号、注册、登录、年龄认证、邮箱验证码、换绑邮箱、账号注销、数据恢复。
   - 用户想咨询账号流程、账号状态、认证/验证码/绑定相关问题。

3. feature_play_consult：功能玩法咨询
   - 聊天模式、深夜模式、广场玩法、羁绊值规则、记忆机制、主动发消息机制、真实世界联动、聊天记录查找、已有功能入口。
   - 用户在问产品内功能是什么、怎么玩、规则是什么、在哪里使用。

4. privacy_permission_consult：隐私权限咨询
   - 定位/城市识别、IP、剪贴板、输入法、隐私协议、权限开关、角色为什么知道现实信息。
   - 用户关注隐私、权限、数据使用、现实信息来源。

5. activity_consult：线上、线下活动咨询
   - 《心动时光册》等线上打卡活动、活动参与条件、投稿平台要求、奖励发放规则、活动截止时间、线下活动说明。
   - 用户咨询活动规则、奖励、参与方式或时间。

6. data_search：实时数据查询
   - 订单状态、月卡/星能/回声贝余额、充值记录、账号状态等需要查询实时数据的问题。
   - 用户问回声贝、星能流水明细，以及订单、充值、账号状态等需要查询实时数据的问题。

7. content_safety_consult：内容安全策略咨询
   - 发送消息触发风控弹 toast 提示、角色回复触发风控展示感叹号、分别对应的处理方式。
   - 用户问“为什么发不出去/为什么有感叹号/为什么被提示违规”等内容安全策略问题。

8. chat_quality_feedback：聊天质量反馈
   - 主语错乱、重复、输出截断、大模型胡乱回复、记忆丢失、爆 prompt、爆思维链、底层代码泄露、回复太短/太长、回复不符合角色设定。
   - 用户反馈 AI 聊天内容质量或模型输出异常。

9. pre_sales_consult：售前咨询
   - 会员类型区别、月卡/周卡权益、限时折扣、服饰礼包说明。
   - 用户购买前咨询权益、价格、优惠、套餐差异或礼包内容。

10. after_sales_issue：售后问题
   - 已充值但是星能/会员/回声贝未到账、月卡赠送星能延迟、订单异常、重复扣费。
   - 用户已经发生购买、充值、扣费或到账异常，需要查询订单或资产。

11. product_suggestion：产品建议
   - 用户提出明确功能诉求，比如“能不能出畅聊卡/撤回/重说/聊天记录查找/更换邮箱/增加字数上限/卖谷/周边”。
   - 若用户只是问“有没有这个功能/入口在哪里”，优先归入 feature_play_consult；若明确表达“希望新增/能不能做/建议支持”，归入本类。

12. product_complaint：产品吐槽
   - 用户表达不满、情绪、价格压力、流失风险，但没有明确可执行功能建议，如太贵、聊不起、星能消耗快、优惠不够、性价比低、活动不合理。
   - 用户主要是在表达对产品体验、价格、消耗、活动等的不满。

13. fault_feedback：故障反馈
   - 页面 error、登不上、卡住、转不出来、白屏/闪退、加载失败、红点消不掉、按钮点不了、充值页异常、特定角色无法回复、网络不稳定。
   - 用户反馈产品功能本身坏了、页面/按钮/网络/加载/角色响应出现异常。

14. chat_respond：闲聊或情感陪伴
   - 和 BOU 产品业务无关，但用户是在正常闲聊、寒暄、表达情绪陪伴需求。

15. unknown_respond：无法识别或不应回答
   - 无法归入上述分类，信息严重不足，或为敏感/违规/恶意/非产品业务且非明确闲聊的问题。

# 置信度（confidence）判断标准：表示你对预测意图的确定程度，范围 0～1
0.85～1.00：表达明确、强特征词/强场景指向，几乎无歧义
0.60～0.84：意图较清晰，但仍存在轻微歧义或需依赖上下文
0.40～0.59：表达模糊，需要较多推理，候选意图之间比较接近
0.00～0.39：无法稳定判断，优先归入“unknown_respond”

# 识别准则（请先牢记以下规则再开始判断）
1. 优先理解用户“最终目的”而非关键字段面含义
2. 对于表达不明确的模糊语句，结合上下文 Memory 合理推理其意图
3. 用户输入按一个完整问题处理，选择最能代表本轮诉求的意图
4. 如无法判断意图，或为非产品业务类问题且非明确闲聊，则归入“unknown_respond”
5. 当信息严重不足或意图极度模糊导致置信度很低时，标记需要澄清
6. “咨询已有规则/入口/说明”优先归入 RAG 类；“明确希望新增/改造某功能”归入 product_suggestion
7. “功能坏了/页面异常/按钮无效/加载失败”归入 fault_feedback；“AI 回复内容质量差”归入 chat_quality_feedback
8. “购买前问权益/折扣/礼包”归入 pre_sales_consult；“购买后不到账/扣费/订单异常”归入 after_sales_issue
9. 若问题同时带有咨询和反馈/售后信号，优先识别用户最需要被处理的核心诉求
10. 意图判断优先级为 after_sales_issue > fault_feedback/product_suggestion/chat_quality_feedback/product_complaint > 咨询类 > chat_respond

# 思考步骤（CoT 思维链）：
1. 首先理解用户的表达内容和上下文 memory_state 线索
2. 对照上面的意图含义，逐一排除不符合的选项
3. 推理用户背后最核心的目的或请求
4. 根据当前输入与 memory_state 决定槽位的继承与覆盖策略（slot_strategy）
5. 选择最匹配的意图分类并给出置信度评分（0～1）
6. 若需要澄清，写出具体问题

# 你的输出必须是一个 JSON 格式对象，结构如下：
{{
    "predicted_intent": "xxx",
    "confidence": 0.0,
    "slot_strategy": {{
        "inherit_from_memory": true/false,  // 是否从 Memory 继承槽位
        "override": {{ ... }}                 // 本轮用户显式覆盖的槽位
    }},
    "clarify_question": "xxx" 或 null,   // 如果需要澄清，写具体问题
    "reasoning": "简要说明判断依据和你的推理过程"
}}

# Few-shot 示例：
【示例1】
memory_state: {{
  "last_intent": "after_sales_issue",
  "slots": {{"order_id": "12345", "issue_type": "refund"}}
}}
user_input: "把那个单号换成67890试试"
输出:
{{
  "predicted_intent": "after_sales_issue",
  "confidence": 0.95,
  "slot_strategy": {{ "inherit_from_memory": true, "override": {{"order_id": "67890"}} }},
  "clarify_question": null,
  "reasoning": "用户要求更换单号，结合上下文可知其意图依然是处理之前提到的售后问题，直接沿用 Memory 中的槽位并覆盖 order_id。"
}}

【示例2】
memory_state: {{
  "last_intent": "feature_play_consult",
  "slots": {{}}
}}
user_input: "刚才那个一样的问题"
输出:
{{
  "predicted_intent": "feature_play_consult",
  "confidence": 0.90,
  "slot_strategy": {{ "inherit_from_memory": true, "override": {{}} }},
  "clarify_question": null,
  "reasoning": "用户说'跟刚才一样'，意图延续上一轮的产品咨询，直接沿用 Memory。"
}}

【示例3】
memory_state: {{}}
user_input: "查一下我的月卡是不是到账了"
输出:
{{
  "predicted_intent": "after_sales_issue",
  "confidence": 0.90,
  "slot_strategy": {{ "inherit_from_memory": false, "override": {{"item_type": "月卡"}} }},
  "clarify_question": null,
  "reasoning": "用户首轮提问，目的是确认月卡收款状态，属于售后资产类，提取出相关槽位信息。"
}}

【示例4】
memory_state: {{}}
user_input: "为什么发消息的时候弹红色风险提示？"
输出:
{{
  "predicted_intent": "content_safety_consult",
  "confidence": 0.92,
  "slot_strategy": {{ "inherit_from_memory": false, "override": {{"safety_scene": "发送消息触发风险提示"}} }},
  "clarify_question": null,
  "reasoning": "用户询问发送消息时触发风险提示的原因，属于内容安全策略咨询。"
}}

【示例5】
memory_state: {{}}
user_input: "角色一直重复上一句话，记忆也像丢了一样"
输出:
{{
  "predicted_intent": "chat_quality_feedback",
  "confidence": 0.93,
  "slot_strategy": {{ "inherit_from_memory": false, "override": {{"quality_issue": "重复回复、记忆丢失"}} }},
  "clarify_question": null,
  "reasoning": "用户反馈 AI 聊天质量问题，核心是模型输出重复和记忆异常，应归入聊天质量反馈。"
}}

【示例6】
memory_state: {{}}
user_input: "能不能加一个撤回消息的功能？"
输出:
{{
  "predicted_intent": "product_suggestion",
  "confidence": 0.91,
  "slot_strategy": {{ "inherit_from_memory": false, "override": {{"feature_request": "撤回消息"}} }},
  "clarify_question": null,
  "reasoning": "用户明确提出新增功能诉求，而不是询问已有入口，因此归入产品建议。"
}}

现在，请判断以下用户输入的意图：
当前 Memory 状态：
{memory_state}

当前用户输入：
{query}
"""


class SlotStrategy(BaseModel):
    inherit_from_memory: bool = Field(description="是否从 Memory 继承槽位")
    override: dict = Field(description="本轮用户显式覆盖的槽位字典")

class IntentResult(BaseModel):
    predicted_intent: IntentType = Field(description="识别出的最核心意图")
    confidence: float = Field(ge=0.0, le=1.0, description="对该意图的置信度评分")
    slot_strategy: SlotStrategy = Field(description="槽位继承与覆盖策略")
    clarify_question: str | None = Field(default=None, description="如果需要澄清，写具体问题")
    reasoning: str = Field(description="判断依据和推理过程")


class RawIntentResult(BaseModel):
    predicted_intent: str = Field(description="识别出的最核心意图")
    confidence: float = Field(ge=0.0, le=1.0, description="对该意图的置信度评分")
    slot_strategy: SlotStrategy = Field(description="槽位继承与覆盖策略")
    clarify_question: str | None = Field(default=None, description="如果需要澄清，写具体问题")
    reasoning: str = Field(description="判断依据和推理过程")


ALLOWED_INTENTS = set(get_args(IntentType))
INTENT_ALIASES = {
    "asset_query": "data_search",
    "asset_search": "data_search",
    "asset_detail_query": "data_search",
    "consumption_detail": "data_search",
    "consumption_query": "data_search",
    "order_query": "data_search",
    "realtime_data_query": "data_search",
}
DATA_SEARCH_KEYWORDS = (
    "查",
    "查询",
    "明细",
    "流水",
    "余额",
    "记录",
    "订单状态",
    "到账",
    "消费",
    "扣费",
)


def _normalize_intent(raw_intent: str, query: str) -> IntentType:
    intent = (raw_intent or "").strip()
    intent = INTENT_ALIASES.get(intent, intent)
    if intent in ALLOWED_INTENTS:
        return intent  # type: ignore[return-value]

    if any(keyword in query for keyword in DATA_SEARCH_KEYWORDS):
        return "data_search"
    return "unknown_respond"


async def classify_query(query: str, state: AgentState) -> IntentResult:
    latest_message = state["messages"][-1]
    memory_state = {
        "last_intent": state.get("intent"),
        "slots": state.get("dialog_state", {}),
    }

    llm = get_llm()
    prompt = CLASSIFY_PROMPT.format(query=query, memory_state=memory_state)
    raw_result = await ainvoke_json(llm, [
        build_multimodal_prompt(prompt, latest_message)
    ], RawIntentResult)
    normalized_intent = _normalize_intent(raw_result.predicted_intent, query)

    return IntentResult(
        predicted_intent=normalized_intent,
        confidence=raw_result.confidence if normalized_intent != "unknown_respond" else min(raw_result.confidence, 0.59),
        slot_strategy=raw_result.slot_strategy,
        clarify_question=raw_result.clarify_question,
        reasoning=(
            raw_result.reasoning
            if normalized_intent == raw_result.predicted_intent
            else f"{raw_result.reasoning}（原始标签 {raw_result.predicted_intent} 已规范化为 {normalized_intent}）"
        ),
    )


async def classify_node(state: AgentState) -> Command:
    query = state.get("rewrite_query") or get_message_text(state["messages"][-1])

    await adispatch_custom_event(
        "thinking_step",
        {
            "step_type": "thought",
            "step_num": 1,
            "content": f"识别问题意图：{query}",
        },
    )

    result = await classify_query(query, state)
    route = route_intent(result.predicted_intent, result.confidence, result.clarify_question)
    clarify_question = result.clarify_question or (
        "我还需要再确认一下，您可以补充具体问题或相关信息吗？"
        if route == "clarify"
        else ""
    )
    
    new_dialog_state = state.get("dialog_state", {}).copy() if result.slot_strategy.inherit_from_memory else {}
    new_dialog_state.update(result.slot_strategy.override)
    await adispatch_custom_event(
        "classification_debug",
        {
            "query": query,
            "intent": result.predicted_intent,
            "confidence": result.confidence,
            "route": route,
            "status": "classified",
            "clarify_question": clarify_question or None,
        },
    )
    await adispatch_custom_event(
        "thinking_step",
        {
            "step_type": "route",
            "step_num": 2,
            "content": (
                f"分类为 {result.predicted_intent}，"
                f"置信度 {result.confidence:.2f}，路由到 {route}"
            ),
        },
    )

    return Command(
        goto=route,
        update={
            "intent": result.predicted_intent,
            "confidence": result.confidence,
            "route": route,
            "dialog_state": new_dialog_state,
            "needs_clarification": route == "clarify",
            "clarify_question": clarify_question,
        },
    )


RAG_INTENTS = {
    "usage_guide",
    "account_issue_consult",
    "feature_play_consult",
    "privacy_permission_consult",
    "activity_consult",
    "content_safety_consult",
    "pre_sales_consult",
}

MCP_TOOL_INTENTS = {
    "chat_quality_feedback",
    "product_suggestion",
    "product_complaint",
    "fault_feedback",
    "data_search",
}


def route_intent(intent: str, confidence: float, clarify_question: str | None = None) -> str:
    if intent == "unknown_respond" or confidence < 0.6:
        return "unrecognized"
    if clarify_question or confidence <= 0.85:
        return "clarify"
    if intent in RAG_INTENTS:
        return "rag"
    if intent in MCP_TOOL_INTENTS:
        return "mcp_tool"
    if intent == "after_sales_issue":
        return "skills"
    return "chat_respond"
