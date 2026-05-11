from __future__ import annotations

from typing import Any


def _input_schema(tool: dict[str, Any]) -> dict[str, Any]:
    schema = tool.get("inputSchema") or tool.get("input_schema") or {}
    if isinstance(schema, dict) and schema:
        return schema
    return {"type": "object", "properties": {}}


def convert_mcp_tools_to_openai_tools(mcp_tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert MCP tools/list output to Chat Completions function tools."""

    provider_tools: list[dict[str, Any]] = []
    for tool in mcp_tools:
        name = tool.get("name")
        if not name:
            continue
        provider_tools.append({
            "type": "function",
            "function": {
                "name": name,
                "description": tool.get("description") or "",
                "parameters": _input_schema(tool),
            },
        })
    return provider_tools


def convert_openai_tools_to_responses_tools(openai_tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert Chat Completions function tools to Responses API function tools."""

    responses_tools: list[dict[str, Any]] = []
    for tool in openai_tools:
        function = tool.get("function") if isinstance(tool, dict) else None
        if not isinstance(function, dict) or not function.get("name"):
            continue
        responses_tools.append({
            "type": "function",
            "name": function["name"],
            "description": function.get("description") or "",
            "parameters": function.get("parameters") or {"type": "object", "properties": {}},
            "strict": False,
        })
    return responses_tools
