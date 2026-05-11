"""Helpers for model JSON text output without provider-specific JSON schema mode."""

import json
import re
from typing import TypeVar

import httpx
from pydantic import BaseModel

ModelT = TypeVar("ModelT", bound=BaseModel)


def _extract_json_object(text: str) -> str:
    content = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", content, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        content = fenced.group(1).strip()

    if content.startswith("{") and content.endswith("}"):
        return content

    start = content.find("{")
    end = content.rfind("}")
    if start != -1 and end != -1 and end > start:
        return content[start:end + 1]

    return content


async def ainvoke_json(llm, messages: list, model: type[ModelT]) -> ModelT:
    """Ask a chat model for plain JSON text and validate it with Pydantic.

    Some providers or lightweight models do not support OpenAI's
    response_format.type=json_schema. This keeps structured outputs portable by
    relying only on normal chat completion text.
    """

    try:
        response = await llm.ainvoke(messages)
    except httpx.HTTPStatusError as e:
        body = ""
        try:
            body = e.response.text
        except Exception:
            body = str(e)
        raise RuntimeError(
            f"LLM HTTP {e.response.status_code}: {body[:500]}"
        ) from e
    content = response.content
    if isinstance(content, list):
        content = "".join(
            item.get("text", "") if isinstance(item, dict) else str(item)
            for item in content
        )
    json_text = _extract_json_object(str(content))
    return model.model_validate(json.loads(json_text))
