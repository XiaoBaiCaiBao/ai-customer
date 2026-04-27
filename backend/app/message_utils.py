from __future__ import annotations

from typing import Any

from langchain_core.messages import BaseMessage, HumanMessage


def _as_content(value: BaseMessage | Any) -> Any:
    return value.content if hasattr(value, "content") else value


def get_message_image_urls(value: BaseMessage | Any) -> list[str]:
    content = _as_content(value)
    if not isinstance(content, list):
        return []

    image_urls: list[str] = []
    for part in content:
        if not isinstance(part, dict) or part.get("type") != "image_url":
            continue
        image_url = part.get("image_url")
        if isinstance(image_url, dict):
            url = str(image_url.get("url", "")).strip()
        else:
            url = str(image_url or "").strip()
        if url:
            image_urls.append(url)
    return image_urls


def get_message_text(value: BaseMessage | Any, include_image_hint: bool = True) -> str:
    content = _as_content(value)

    if isinstance(content, str):
        text = content.strip()
    elif isinstance(content, list):
        text_parts: list[str] = []
        for part in content:
            if not isinstance(part, dict) or part.get("type") != "text":
                continue
            piece = str(part.get("text", "")).strip()
            if piece:
                text_parts.append(piece)
        text = "\n".join(text_parts).strip()
    else:
        text = str(content or "").strip()

    image_count = len(get_message_image_urls(content))
    if include_image_hint and image_count:
        hint = f"[用户发送了 {image_count} 张图片]"
        return f"{text}\n{hint}".strip() if text else hint

    return text


def make_user_message(text: str, image_urls: list[str] | None = None) -> HumanMessage:
    clean_text = text.strip()
    clean_images = [url for url in (image_urls or []) if url]

    if not clean_images:
        return HumanMessage(content=clean_text)

    content: list[dict] = [
        {
            "type": "text",
            "text": clean_text or "请结合我发送的图片进行分析和回答。",
        }
    ]
    content.extend(
        {"type": "image_url", "image_url": {"url": url}}
        for url in clean_images
    )
    return HumanMessage(content=content)


def build_multimodal_prompt(prompt_text: str, source_message: BaseMessage | Any) -> HumanMessage:
    image_urls = get_message_image_urls(source_message)
    if not image_urls:
        return HumanMessage(content=prompt_text)

    content: list[dict] = [{"type": "text", "text": prompt_text}]
    content.extend(
        {"type": "image_url", "image_url": {"url": url}}
        for url in image_urls
    )
    return HumanMessage(content=content)
