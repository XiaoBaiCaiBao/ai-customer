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
| 对话历史 | MongoDB（按 `user_id` + `session_id` 隔离） |

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
# 对话历史依赖 MongoDB：可先执行下方 docker compose 启动 Mongo，或自备实例并配置 MONGODB_URL

uvicorn main:app --reload --port 8000
```

### 2. 前端

```bash
cd frontend
npm install
npm run dev
```

打开 http://localhost:5173

### 3. 基础设施（本地开发）

```bash
docker compose -f docker-compose.dev.yml up -d   # Qdrant (6333) + MongoDB (27017)
```

`.env` 中配置 `MONGODB_URL=mongodb://localhost:27017`（与 dev compose 一致）。  
知识库由外部服务写入 Qdrant，本项目只负责检索。

---

## 服务器部署（生产环境）

### 1. 购买云服务器

推荐规格：**2 核 4 GB 内存**（阿里云 / 腾讯云 / 火山引擎轻量应用服务器，约 ¥60-100/月）  
系统：Ubuntu 22.04 LTS

### 2. 服务器初始化

```bash
# 安装 Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker

# 安装 Docker Compose plugin（通常随 Docker 一起安装，验证一下）
docker compose version
```

### 3. 拉取代码 & 配置环境变量

```bash
git clone https://github.com/你的账号/ai-customer.git
cd ai-customer

cp backend/.env.example backend/.env
# 编辑 .env，填写 API Key、模型名等
vi backend/.env
```

关键配置项（生产环境）：

```bash
LLM_MODEL=doubao-seed-1-8-251228
LLM_API_KEY=your-key
LLM_BASE_URL=https://ark.cn-beijing.volces.com/api/v3

EMBEDDING_MODEL=doubao-embedding-vision-251215
EMBEDDING_BASE_URL=https://ark.cn-beijing.volces.com/api/v3/embeddings/multimodal

# 以下由 docker-compose.yml 自动覆盖，保持默认即可
QDRANT_URL=http://qdrant:6333
MONGODB_URL=mongodb://mongodb:27017
```

### 4. 启动全栈服务

```bash
docker compose up -d --build
```

首次会拉取镜像并构建，约需 3-5 分钟。启动后通过服务器 IP 访问：`http://<服务器IP>`

查看服务状态：

```bash
docker compose ps
docker compose logs -f backend   # 实时查看后端日志
```

### 5. 导入知识库（可选）

知识库数据需要在服务器上单独运行一次导入脚本：

```bash
# 将 PDF 文件上传到服务器 data/ 目录后执行
cd scripts
pip install -r requirements.txt
python ingest_pdf.py ../data/你的文档.pdf
```

### 6. 绑定域名（可选）

如果有域名，解析 A 记录到服务器 IP，再配置 SSL 证书（推荐使用 Certbot + Let's Encrypt）：

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

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
| GET | `/api/chat/history?session_id=xxx&user_id=xxx` | 获取对话历史（须与创建会话时 user_id 一致） |
| DELETE | `/api/chat/history?session_id=xxx&user_id=xxx` | 清空对话历史 |
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
docker-compose.yml            # 生产全栈（nginx + backend + qdrant + mongodb）
docker-compose.dev.yml        # 本地开发（仅 qdrant + mongodb）
```
