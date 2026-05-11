from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import Any

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from app.config import get_settings


class MCPClientError(Exception):
    """Raised when the MCP transport, session, or tool payload fails."""

    def __init__(self, message: str, payload: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.payload = payload


class MCPToolError(MCPClientError):
    """Raised when an MCP tool returns an application-level error."""


def _dump_model(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump(by_alias=True, exclude_none=True)
    if isinstance(value, dict):
        return value
    return {
        key: getattr(value, key)
        for key in ("name", "description", "inputSchema", "input_schema", "annotations")
        if hasattr(value, key)
    }


def _normalize_tool(tool: Any) -> dict[str, Any]:
    data = _dump_model(tool)
    input_schema = data.get("inputSchema") or data.get("input_schema") or {}
    return {
        "name": data.get("name"),
        "description": data.get("description") or "",
        "inputSchema": input_schema,
        "annotations": data.get("annotations") or {},
    }


def _normalize_tool_result(result: Any) -> dict[str, Any]:
    data = _dump_model(result)
    structured = data.get("structuredContent") or data.get("structured_content")
    if isinstance(structured, dict):
        return structured

    content = data.get("content")
    if isinstance(content, list) and content:
        first = _dump_model(content[0])
        text = first.get("text")
        if text:
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                return {"success": True, "text": text}
            if isinstance(payload, dict):
                return payload

    return {"success": True, "result": data}


class StreamableHttpMCPClient:
    """Thin MCP protocol adapter for the agent host.

    Business routing, model tool selection, slot filling, and user-facing copy stay
    in the agent layer. This class only opens MCP sessions, lists tools, and calls
    tools through the official Python SDK.
    """

    def __init__(self, url: str, auth_token: str = "", timeout_seconds: float = 8.0) -> None:
        self.url = url
        self.auth_token = auth_token
        self.timeout_seconds = timeout_seconds

    def _headers(self) -> dict[str, str]:
        if not self.auth_token:
            return {}
        return {"Authorization": f"Bearer {self.auth_token}"}

    @asynccontextmanager
    async def _session(self):
        async with httpx.AsyncClient(
            headers=self._headers(),
            timeout=self.timeout_seconds,
            follow_redirects=True,
        ) as http_client:
            async with streamable_http_client(self.url, http_client=http_client) as (
                read_stream,
                write_stream,
                _,
            ):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    yield session

    async def list_tools(self) -> list[dict[str, Any]]:
        try:
            async with self._session() as session:
                result = await session.list_tools()
                return [_normalize_tool(tool) for tool in result.tools]
        except Exception as exc:
            raise MCPClientError(f"MCP list_tools failed: {exc}") from exc

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        try:
            async with self._session() as session:
                result = await session.call_tool(name, arguments=arguments)
        except Exception as exc:
            raise MCPClientError(f"MCP call_tool failed: {exc}") from exc

        payload = _normalize_tool_result(result)
        if payload.get("success") is False:
            error = payload.get("error") or {}
            raise MCPToolError(
                error.get("message") or f"MCP tool failed: {name}",
                payload=payload,
            )
        return payload


_client: StreamableHttpMCPClient | None = None


def get_mcp_client() -> StreamableHttpMCPClient:
    global _client
    settings = get_settings()
    if _client is None:
        _client = StreamableHttpMCPClient(
            url=settings.MCP_SERVER_URL,
            auth_token=settings.MCP_AUTH_TOKEN,
            timeout_seconds=settings.MCP_TIMEOUT_SECONDS,
        )
    return _client


async def call_mcp_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return await get_mcp_client().call_tool(name, arguments)
