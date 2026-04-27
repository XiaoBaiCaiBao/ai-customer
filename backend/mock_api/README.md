# Mock Business API

这是给 MVP 使用的业务 mock API 服务，模拟真实后端系统能力：

- 查询用户资产
- 查询用户订单
- 查询资产明细
- 提交售后工单

## 启动

在仓库根目录执行：

```bash
cd backend
uvicorn mock_api.main:app --reload --port 8010
```

如果没有激活虚拟环境，也可以直接使用项目里的 venv：

```bash
cd backend
./venv/bin/uvicorn mock_api.main:app --reload --port 8010
```

打开接口文档：

```text
http://localhost:8010/docs
```

## 测试用户

- `user_1001`：月卡订单支付成功但权益未到账，适合测试售后链路。
- `user_1002`：周卡和资产正常，适合测试正常查询链路。

## 接口

### 健康检查

```http
GET /health
```

### 查询用户资产

```http
GET /api/users/{user_id}/assets
```

### 查询用户订单

```http
GET /api/users/{user_id}/orders?limit=5
```

### 查询资产明细

```http
GET /api/users/{user_id}/assets/{asset_id}/details
```

### 提交售后工单

```http
POST /api/work-orders
Content-Type: application/json

{
  "user_id": "user_1001",
  "issue_type": "月卡未到账",
  "description": "用户反馈购买月卡后体力和月卡权益未到账",
  "order_id": "ORD_20260423_1001",
  "priority": "normal"
}
```

## 和 MCP 的关系

这个服务可以作为 MCP tool 的下游业务 API。后续 MCP 层只需要把模型调用参数转换成这些 HTTP 请求，再把返回结果整理成模型容易理解的 observation。
