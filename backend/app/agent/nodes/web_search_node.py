"""
节点: 联网查询节点

适用意图: web_search
使用 wttr.in 免费 API 查询天气等实时信息，并通过
adispatch_custom_event 向前端流式推送思考步骤。

思考流程:
  Thought  → 分析用户意图，提取关键词
  Action   → 调用实时查询 API
  Observation → 解析返回数据
  Final    → 组织自然语言回复
"""

import json
import httpx
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.callbacks.manager import adispatch_custom_event
from app.agent.state import AgentState
from app.llm import get_llm

# 用 LLM 从用户问题中提取查询关键词（城市名、搜索词等）
EXTRACT_PROMPT = """从以下用户问题中，提取需要查询的关键信息。
只返回 JSON，格式：{{"type": "weather", "location": "城市名"}} 或 {{"type": "other", "query": "搜索词"}}

用户问题：{query}"""

# 格式化天气数据为自然语言
FORMAT_WEATHER_PROMPT = """你是 BOU 的 AI 助手，请根据以下天气数据，用友好自然的语气回复用户。
回复 2-3 句话，包含温度、天气状况、简单建议。

城市: {city}
天气数据: {data}

用户原始问题: {query}"""

FORMAT_ERROR_PROMPT = """你是 BOU 的 AI 助手。
用户想查询实时信息，但查询失败了。请友好地告知用户暂时无法获取该信息，并建议替代方案。
用户问题: {query}"""


async def _extract_query_info(query: str) -> dict:
    """用 LLM 提取查询意图和关键词"""
    llm = get_llm()
    structured_llm = llm.with_structured_output(
        {"type": "object", "properties": {"type": {"type": "string"}, "location": {"type": "string"}, "query": {"type": "string"}}}
    )
    try:
        prompt = EXTRACT_PROMPT.format(query=query)
        result = await llm.ainvoke([HumanMessage(content=prompt)])
        # 解析 JSON
        content = result.content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        return json.loads(content.strip())
    except Exception:
        return {"type": "other", "query": query}


async def _fetch_weather(city: str) -> dict:
    """调用 wttr.in API 获取天气数据"""
    url = f"https://wttr.in/{city}?format=j1&lang=zh"
    async with httpx.AsyncClient(timeout=8.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json()


def _parse_weather(data: dict, city: str) -> str:
    """提取关键天气字段"""
    try:
        current = data["current_condition"][0]
        temp_c = current["temp_C"]
        feels_like = current["FeelsLikeC"]
        desc = current.get("lang_zh", [{}])[0].get("value", current.get("weatherDesc", [{}])[0].get("value", "未知"))
        humidity = current["humidity"]
        # 今日预报
        today = data["weather"][0]
        max_t = today["maxtempC"]
        min_t = today["mintempC"]
        return (
            f"温度 {temp_c}°C（体感 {feels_like}°C），{desc}，"
            f"湿度 {humidity}%，今日 {min_t}~{max_t}°C"
        )
    except Exception:
        return str(data)[:300]


async def web_search_node(state: AgentState) -> dict:
    query = state.get("rewritten_query") or state["messages"][-1].content

    # ── Step 1: Thought ──
    await adispatch_custom_event(
        "thinking_step",
        {
            "step_type": "thought",
            "step_num": 1,
            "content": f"用户想查询实时信息，我需要先理解具体查什么、查哪里。分析中：「{query}」",
        },
    )

    query_info = await _extract_query_info(query)
    search_type = query_info.get("type", "other")
    location = query_info.get("location", "")
    search_query = query_info.get("query", query)

    # ── Step 2: Action ──
    if search_type == "weather" and location:
        await adispatch_custom_event(
            "thinking_step",
            {
                "step_type": "action",
                "step_num": 2,
                "content": f"调用 WeatherAPI.get_weather(city=\"{location}\")",
            },
        )
        # 执行查询
        try:
            raw_data = await _fetch_weather(location)
            weather_summary = _parse_weather(raw_data, location)

            # ── Step 3: Observation ──
            await adispatch_custom_event(
                "thinking_step",
                {
                    "step_type": "observation",
                    "step_num": 3,
                    "content": f"查询成功 → {location}: {weather_summary}",
                },
            )

            # ── Step 4: Final ──
            await adispatch_custom_event(
                "thinking_step",
                {
                    "step_type": "final",
                    "step_num": 4,
                    "content": "已获取实时天气数据，正在组织自然语言回复…",
                },
            )

            llm = get_llm(streaming=True)
            response = await llm.ainvoke([
                SystemMessage(content=FORMAT_WEATHER_PROMPT.format(
                    city=location, data=weather_summary, query=query
                )),
            ])

        except Exception as e:
            await adispatch_custom_event(
                "thinking_step",
                {
                    "step_type": "observation",
                    "step_num": 3,
                    "content": f"查询失败: {type(e).__name__}，将告知用户并建议替代方案",
                },
            )
            llm = get_llm(streaming=True)
            response = await llm.ainvoke([
                SystemMessage(content=FORMAT_ERROR_PROMPT.format(query=query)),
            ])
    else:
        # 非天气类实时查询，暂时说明暂不支持
        await adispatch_custom_event(
            "thinking_step",
            {
                "step_type": "action",
                "step_num": 2,
                "content": f"分析到查询类型为 {search_type!r}，当前支持天气查询，正在用大模型回答…",
            },
        )
        await adispatch_custom_event(
            "thinking_step",
            {
                "step_type": "final",
                "step_num": 3,
                "content": "使用模型知识回复，提示用户实时搜索局限性…",
            },
        )
        llm = get_llm(streaming=True)
        response = await llm.ainvoke([
            SystemMessage(content="你是 BOU 的 AI 助手。用户想查询实时信息，请如实回答（如果是天气，说明需要提供城市名）。"),
            HumanMessage(content=query),
        ])

    return {"messages": [AIMessage(content=response.content)]}
