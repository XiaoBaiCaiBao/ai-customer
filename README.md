# AI Customer Service — BOU 智能客服

基于 LangGraph + RAG 的 AI 客服系统，支持意图识别、查询改写、RAG 知识库检索、流式回复。

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | Vue3 + TailwindCSS + Pinia |
| 后端 | Python 3.11+ · FastAPI · SSE 流式输出 |
| Agent | LangGraph |
| LLM | OpenAI 兼容接口（可切换任意模型） |
| 向量库 | Qdrant（外部独立服务，可选） |
| 对话历史 | 内存（开发） / MongoDB（生产） |

## Agent 意图路由

```
用户输入
  → 查询改写 (rewrite)       # 结合多轮历史，消除代词歧义
  → 意图分类 (classify)
      ├─ product_info / usage_issue / event  → RAG 检索 → 生成回复
      ├─ complaint / aftersales              → 安抚回复 + 通知产研 API
      └─ chat / unknown                      → 直接回复
```

## 快速启动

### 1. 后端

**Python 需要 3.11 或以上版本。**

```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# 编辑 .env，至少填写 LLM_MODEL / LLM_API_KEY / LLM_BASE_URL
# USE_MEMORY=true 时无需任何数据库，直接启动

uvicorn main:app --reload --port 8000
```

### 2. 前端

```bash
cd frontend
npm install
npm run dev
```

打开 http://localhost:5173

### 3. 基础设施（可选，生产或需要知识库时）

```bash
docker compose up -d   # 启动 Qdrant (6333) + MongoDB (27017)
```

在 `.env` 中将 `USE_MEMORY=false` 并配置 `MONGODB_URL`。  
知识库由外部服务写入 Qdrant，本项目只负责检索。

## 切换 LLM 模型

修改 `backend/.env` 即可，无需改代码：

```bash
# 火山引擎·豆包
LLM_MODEL=doubao-seed-1-8-251228
LLM_API_KEY=your-key
LLM_BASE_URL=https://ark.cn-beijing.volces.com/api/v3

# DeepSeek
LLM_MODEL=deepseek-chat
LLM_API_KEY=your-key
LLM_BASE_URL=https://api.deepseek.com

# 通义千问
LLM_MODEL=qwen-max
LLM_API_KEY=your-key
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

# OpenAI
LLM_MODEL=gpt-4o
LLM_API_KEY=sk-xxx
LLM_BASE_URL=   # 留空

# 本地 Ollama
LLM_MODEL=qwen2.5:7b
LLM_API_KEY=ollama
LLM_BASE_URL=http://localhost:11434/v1
```

## API 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/chat/stream` | SSE 流式对话 |
| GET | `/api/chat/history?session_id=xxx` | 获取对话历史 |
| DELETE | `/api/chat/history?session_id=xxx` | 清空对话历史 |
| GET | `/health` | 健康检查 |

## 项目结构

```
backend/
├── app/
│   ├── agent/
│   │   ├── graph.py          # LangGraph 图定义
│   │   ├── state.py          # 对话状态
│   │   └── nodes/
│   │       ├── rewrite.py    # 查询改写
│   │       ├── classify.py   # 意图分类
│   │       ├── rag_node.py   # RAG 检索 + 生成
│   │       ├── api_node.py   # 通知产研 + 安抚回复
│   │       └── chat_node.py  # 闲聊 / 澄清
│   ├── api/chat.py           # FastAPI 路由（SSE）
│   ├── rag/retriever.py      # Qdrant 检索
│   ├── db/mongo.py           # 对话历史存储
│   ├── llm.py                # LLM 工厂
│   └── config.py             # 配置
frontend/
├── src/
│   ├── views/ChatView.vue    # 主页面
│   ├── components/MessageBubble.vue
│   └── stores/chat.js        # 状态管理 + SSE 对接
docker-compose.yml            # Qdrant + MongoDB
```
