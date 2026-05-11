from functools import lru_cache
import json
from typing import Any

import httpx
from langchain_core.messages import AIMessage, BaseMessage
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from app.agent.tools.mcp_provider_tools import convert_openai_tools_to_responses_tools
from app.config import get_settings


class VolcengineResponsesChat:
    """Minimal Ark Responses API adapter with a LangChain-like ainvoke method."""

    def __init__(
        self,
        model: str,
        api_key: str,
        base_url: str,
        timeout_seconds: float = 60.0,
    ) -> None:
        self.model = model
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    @property
    def responses_url(self) -> str:
        if self.base_url.endswith("/responses"):
            return self.base_url
        return f"{self.base_url}/responses"

    async def ainvoke(self, messages: list[BaseMessage] | list[Any], *args, **kwargs) -> AIMessage:
        tools = kwargs.get("tools")
        function_outputs = kwargs.get("function_outputs")
        previous_response_id = kwargs.get("previous_response_id")
        payload = {
            "model": self.model,
            "input": (
                self._convert_function_outputs(function_outputs)
                if function_outputs
                else [self._convert_message(message) for message in messages]
            ),
        }
        if tools:
            payload["tools"] = convert_openai_tools_to_responses_tools(tools)
            payload["tool_choice"] = kwargs.get("tool_choice", "auto")
        if previous_response_id:
            payload["previous_response_id"] = previous_response_id

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                self.responses_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        response.raise_for_status()
        data = response.json()
        tool_calls = self._extract_tool_calls(data)
        return AIMessage(
            content=self._extract_text(data),
            tool_calls=tool_calls,
            response_metadata={
                "response_id": data.get("id"),
                "raw": data,
            },
        )

    def _convert_message(self, message: BaseMessage | Any) -> dict[str, Any]:
        role = getattr(message, "type", "user")
        if role == "human":
            role = "user"
        elif role == "ai":
            role = "assistant"
        elif role not in {"user", "assistant", "system", "developer"}:
            role = "user"

        return {
            "role": role,
            "content": self._convert_content(getattr(message, "content", message)),
        }

    def _convert_content(self, content: Any) -> list[dict[str, Any]]:
        if isinstance(content, str):
            return [{"type": "input_text", "text": content}]

        if not isinstance(content, list):
            return [{"type": "input_text", "text": str(content or "")}]

        converted: list[dict[str, Any]] = []
        for part in content:
            if not isinstance(part, dict):
                converted.append({"type": "input_text", "text": str(part)})
                continue

            if part.get("type") == "text":
                converted.append({"type": "input_text", "text": str(part.get("text", ""))})
                continue

            if part.get("type") == "image_url":
                image_url = part.get("image_url")
                if isinstance(image_url, dict):
                    image_url = image_url.get("url")
                if image_url:
                    converted.append({"type": "input_image", "image_url": str(image_url)})

        return converted or [{"type": "input_text", "text": ""}]

    def _convert_function_outputs(self, outputs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        converted: list[dict[str, Any]] = []
        for output in outputs or []:
            call_id = output.get("call_id") or output.get("id")
            if not call_id:
                continue
            converted.append({
                "type": "function_call_output",
                "call_id": call_id,
                "output": str(output.get("output", "")),
            })
        return converted

    def _extract_text(self, data: dict[str, Any]) -> str:
        output_text = data.get("output_text")
        if isinstance(output_text, str):
            return output_text

        texts: list[str] = []
        for item in data.get("output", []) or []:
            if not isinstance(item, dict):
                continue
            for content in item.get("content", []) or []:
                if not isinstance(content, dict):
                    continue
                text = content.get("text") or content.get("output_text")
                if text:
                    texts.append(str(text))

        if texts:
            return "".join(texts)

        return str(data)

    def _extract_tool_calls(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        tool_calls: list[dict[str, Any]] = []
        for item in data.get("output", []) or []:
            if not isinstance(item, dict):
                continue
            item_type = item.get("type")
            if item_type not in {"function_call", "custom_tool_call"}:
                continue

            raw_args = item.get("arguments") or item.get("input") or "{}"
            try:
                args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            except json.JSONDecodeError:
                args = {}

            call_id = item.get("call_id") or item.get("id")
            tool_calls.append({
                "id": call_id,
                "name": item.get("name"),
                "args": args if isinstance(args, dict) else {},
                "type": "tool_call",
            })
        return tool_calls


def _use_volcengine_responses_api(base_url: str | None) -> bool:
    return bool(base_url and "ark.cn-beijing.volces.com/api/v3" in base_url)


def get_llm(streaming: bool = False):
    """
    统一 LLM 工厂。切换模型只需改 .env 里的 LLM_MODEL / LLM_BASE_URL：
      - OpenAI:    LLM_MODEL=gpt-4o, LLM_BASE_URL=（留空）
      - DeepSeek:  LLM_MODEL=deepseek-chat, LLM_BASE_URL=https://api.deepseek.com
      - 通义千问:  LLM_MODEL=qwen-max, LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
      - Ollama:    LLM_MODEL=qwen2.5:7b, LLM_BASE_URL=http://localhost:11434/v1
    """
    s = get_settings()
    if _use_volcengine_responses_api(s.llm_base_url):
        return VolcengineResponsesChat(
            model=s.LLM_MODEL,
            api_key=s.LLM_API_KEY,
            base_url=s.llm_base_url or "",
        )

    return ChatOpenAI(
        model=s.LLM_MODEL,
        api_key=s.LLM_API_KEY,
        base_url=s.llm_base_url,
        streaming=streaming,
        temperature=0,
    )


@lru_cache
def get_embeddings() -> OpenAIEmbeddings:
    s = get_settings()
    return OpenAIEmbeddings(
        model=s.EMBEDDING_MODEL,
        api_key=s.LLM_API_KEY,
        base_url=s.llm_base_url,
    )
