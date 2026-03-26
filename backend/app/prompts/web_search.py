WEB_SEARCH_EXTRACT_PROMPT = """从以下用户问题中，提取需要查询的关键信息。
只返回 JSON，格式：{{"type": "weather", "location": "城市名"}} 或 {{"type": "other", "query": "搜索词"}}

用户问题：{query}"""

WEB_SEARCH_FORMAT_WEATHER_PROMPT = """你是 BOU 的 AI 助手，请根据以下天气数据，用友好自然的语气回复用户。
回复 2-3 句话，包含温度、天气状况、简单建议。

城市: {city}
天气数据: {data}

用户原始问题: {query}"""

WEB_SEARCH_FORMAT_ERROR_PROMPT = """你是 BOU 的 AI 助手。
用户想查询实时信息，但查询失败了。请友好地告知用户暂时无法获取该信息，并建议替代方案。
用户问题: {query}"""

WEB_SEARCH_DEFAULT_PROMPT = """你是 BOU 的 AI 助手。用户想查询实时信息，请如实回答（如果是天气，说明需要提供城市名）。"""
