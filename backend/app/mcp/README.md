# MCP Server (ai-customer)

## 运行方式

1. 安装依赖：

```bash
pip install -r backend/requirements.txt
```

2. 可选配置 `.env`：

```env
MCP_SERVER_TOKEN=your_token_here
```

3. 启动 MCP Server（stdio）：

```bash
python -m app.mcp.server
```

## 已暴露工具

- `get_user_recent_orders(user_id, auth_token?)`
- `check_user_assets(user_id, auth_token?)`
- `submit_work_order(user_id, issue_type, description, order_id?, auth_token?)`

## 治理策略

- 参数校验：`user_id`、`issue_type`、`description` 在工具层校验。
- 幂等保障：`submit_work_order` 基于关键字段生成幂等键，重复提交返回同一工单号。
- 权限控制：若配置 `MCP_SERVER_TOKEN`，调用方必须传 `auth_token`。
- 审计日志：记录工具名、调用耗时、调用结果状态。

