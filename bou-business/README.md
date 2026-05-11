# bou-business

`bou-business` simulates the independent BOU business system. It exposes normal REST APIs and wraps the same capabilities as MCP tools through a Streamable HTTP JSON-RPC endpoint.

## Run

```bash
cd bou-business
npm run dev
```

Default base URL:

```text
http://127.0.0.1:8011
```

## REST APIs

- `GET /health`
- `GET /api/users/{user_id}/orders?limit=5&asset_type=vip_monthly&start=2026-05-01T00:00:00%2B08:00&end=2026-05-09T23:59:59%2B08:00`
- `GET /api/users/{user_id}/assets`
- `GET /api/users/{user_id}/assets/{asset_type}/details`
- `POST /api/work-orders`

## MCP Endpoint

```text
POST /mcp
```

Tools:

- `get_user_recent_orders`
- `get_user_details`
- `get_asset_details`
- `submit_work_order`

Optional auth:

```bash
BOU_BUSINESS_TOKEN=dev-token npm run dev
```

The agent backend should then set:

```env
MCP_AUTH_TOKEN=dev-token
```
