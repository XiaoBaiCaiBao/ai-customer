# MCP Client (ai-customer)

`ai-customer` 后端是 MCP Host，并在 `app/mcp/client.py` 里使用官方 Python SDK 实现一个很薄的 Streamable HTTP MCP client。

MCP Server 已迁移到独立业务系统 `bou-business`，避免把业务接口和 Agent 混在同一个边界里。

## 调用链路

```text
FastAPI / LangGraph Host
  -> app.mcp.client.list_tools()
  -> 将 MCP tools 转成模型供应商 tools 参数
  -> LLM 返回 tool_calls
  -> app.mcp.client.call_mcp_tool(...)
  -> bou-business /mcp
  -> bou-business REST/service/mock data
```

## 后端配置

```env
MCP_SERVER_URL=http://localhost:8011/mcp
MCP_AUTH_TOKEN=
MCP_TIMEOUT_SECONDS=8
```

## 当前使用的工具

- `user_account_search(user_id)`：用户账户查询。
- `user_order_search(user_id, asset_type?, datetime_range?, limit?)`：用户订单查询。
- `assets_flow_search(user_id, asset_type, datetime_range?)`：虚拟资产流水查询。
- `word_order_submission(user_id, issue_type, description, work_order_type?, category?, order_id?, occurrence_time?, attachments?, priority?)`：工单提交。

## 边界

- `mcp_tool` 节点：需要业务工具的意图，使用模型原生 tools/tool_calls 选择工具和参数，再调用 MCP tool。
- `skills_node`：复杂 SOP，不是 MCP tool；它可以在步骤里调用 MCP tools。
- `bou-business`：业务系统边界，负责 REST API、mock data、MCP Server。
