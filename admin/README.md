# BOU Admin Console

BOU 智能客服管理后台，独立于用户侧客服 Agent 前后端。

## 子系统边界

```text
admin/
  backend/    # 管理后台后端：飞书采集、分块预览、知识文档、工单、补偿
  frontend/   # 管理后台前端：知识库构建、工单处理、补偿操作
```

用户侧系统仍然保留在仓库根目录的 `frontend/` 和 `backend/`：

- `backend/`：客服 Agent Runtime，负责用户消息处理、RAG 检索、MCP 调用、流式回复。
- `frontend/`：用户侧聊天入口。
- `admin/backend/`：运营后台能力，负责知识库构建、工单流转、补偿留痕。
- `admin/frontend/`：运营后台界面。

## 当前 MVP 能力

### 知识库构建

- 飞书文档拉取：通过 `lark-cli docs +fetch` 获取文档正文。
- 元数据管理：分类、负责人、版本、状态、标签、适用范围。
- 分块策略：按标题结构、按段落语义、固定长度。
- Chunk 预览：展示标题路径、token 粗估、chunk 内容。
- 文档保存：保存文档正文、元数据、分块策略和 chunk 到 MongoDB。

### 工单处理

- 查看 AI 转人工工单。
- 查看用户问题、意图、AI 链路摘要和工具/RAG痕迹。
- 更新工单状态和处理结论。

### 补偿操作

- 提交星能、回声贝、VIP 天数等补偿记录。
- 当前为 mock 提交，后续可接 `bou-business` MCP 工具执行真实补偿。

## 启动

### 后端

```bash
cd admin/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8001
```

默认 MongoDB：

```bash
ADMIN_MONGODB_URL=mongodb://localhost:27017
ADMIN_MONGODB_DB=ai_customer_admin
```

### 前端

```bash
cd admin/frontend
npm install
npm run dev
```

打开 `http://localhost:5174`。

## 后续演进

- 知识库发布：草稿/审核/发布/下线状态流转。
- 向量库写入：发布后写入 Qdrant 或火山知识库。
- 召回测试：输入 query，展示召回 chunk、score、来源和命中原因。
- BadCase 回流：工单和错误回答自动生成补知识、改分块、加相似问任务。
- 补偿审批：增加审批流、操作权限和风控校验。
- 与用户侧 Agent 串联：Agent 转人工写入 `admin/backend` 工单接口；RAG 只检索已发布知识。
