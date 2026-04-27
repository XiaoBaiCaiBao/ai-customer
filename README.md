# AI Customer Service — BOU 智能客服

基于 LangGraph + RAG 的企业级 AI 客服系统，支持意图识别、对话状态追踪 (DST)、长短期记忆管理、RAG 知识库检索、多步推理 (ReAct)、外部 API 集成及流式回复。

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | Vue3 + TailwindCSS + Pinia |
| 后端 | Python 3.11+ · FastAPI · SSE 流式输出 |
| Agent | LangGraph (StateGraph) |
| LLM | OpenAI 兼容接口（可切换任意模型） |
| 向量库 | Qdrant（外部独立服务，可选） |
| 数据存储 | MongoDB（持久化对话历史、长期记忆） |

## Agent 核心架构与流程

本项目采用模块化的多 Agent 节点设计，核心流程如下：

```mermaid
graph TD
  User[User Query] --> Init[加载历史对话与记忆]
  Init --> Rewrite[查询改写 Rewrite\n补全代词与省略信息]
  Rewrite --> Classify[意图分类 Classify\n输出意图与置信度]
  Classify --> DST[对话状态追踪 DST\n更新槽位, 判断是否缺信息]
  DST --> Router{Intent Router}
  
  Router -->|缺关键槽位| Clarify[澄清节点 Clarify\n反问用户收集槽位]
  Router -->|aftersales 售后问题| ReAct[ReAct 节点\n查单/查账/提工单]
  Router -->|product_info / usage_issue| RAG[RAG 节点\n检索知识库回答]
  Router -->|complaint 吐槽建议| API[API 节点\n安抚并通知产研]
  Router -->|web_search 实时信息| WebSearch[Web Search 节点\n请求外部接口]
  Router -->|chat / unknown| Chat[闲聊节点 Chat]
  
  ReAct <--> Tools["业务工具集\n(查订单, 查资产, 提交工单等)"]
  
  Clarify --> Out[流式输出 Response Stream]
  ReAct --> Out
  RAG --> Out
  API --> Out
  WebSearch --> Out
  Chat --> Out
  
  Out --> STM[更新短期记忆 STM]
  STM -.->|滑动窗口压缩| Comp[异步历史总结]
  Out -.->|关键信息提取| LTM[(长期记忆 LTM 异步更新)]
```

### 关键设计点 (Agent Design)

1. **查询预处理 (Query Preprocessing)**
   - **Rewrite (查询改写)**: 结合最近的历史记录，将用户的简写或代词（如“那我有什么权益”）补全为独立的查询语句（如“月卡VIP用户有哪些权益？”），提高后续意图识别和检索的准确率。
   - **Classify (意图分类)**: 使用 LLM 结构化输出（Structured Output），将用户问题分为售后、吐槽、产品咨询、闲聊、实时信息等，并给出置信度。

2. **对话状态追踪 (Dialog State Tracking, DST)**
   - 针对任务型多轮对话（如售后、吐槽），自动从用户回复中提取关键槽位（如 `issue_type`, `topic`）。
   - 如果发现关键槽位缺失，自动路由至 `Clarify` 节点向用户发起反问，收集完整信息后再进行下一步操作，避免盲目调用工具。

3. **ReAct 范式 (Reasoning and Acting)**
   - 售后场景采用 ReAct 架构，Agent 可以在内部进行多步 `Thought -> Action -> Observation` 的循环。
   - **工具箱 (Tools)**：Agent 可以调用诸如 `get_user_recent_orders`（查订单）、`check_user_assets`（查资产）、`submit_work_order`（提交售后工单）等工具，彻底查清问题后再给用户最终答复。

4. **长短期记忆管理 (Memory Management)**
   - **短期记忆 (STM)**：使用 MongoDB 存储会话级消息记录。当对话轮数超过阈值（如 6 轮）时，后台触发**异步压缩任务**，调用 LLM 将旧消息总结成简短摘要，并拼接在上下文头部，有效控制 Token 消耗并保留上下文。
   - **长期记忆 (LTM)**：预留异步更新脚手架，在特定节点或对话结束时，将 DST 收集到的用户偏好或关键 Fact 提取出来，准备存入向量数据库或用户画像系统，实现跨 Session 的记忆。

5. **提示词工程解耦 (Prompt Management)**
   - 各节点提示词按模块拆在 `app/prompts/` 下（如 `classify.py`、`react.py` 等），`__init__.py` 聚合导出；与业务代码解耦，便于单独改版式。

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

如果你想直接调用火山引擎托管知识库，而不是本地 Qdrant，可在 `backend/.env` 中额外配置：

```bash
RAG_PROVIDER=volcengine_kb
VOLC_KB_AK=your-ak
VOLC_KB_SK=your-sk
VOLC_KB_COLLECTION_NAME=你的知识库名称

# 可选
VOLC_KB_ACCOUNT_ID=
VOLC_KB_PROJECT=default
VOLC_KB_HOST=api-knowledgebase.mlp.cn-beijing.volces.com
VOLC_KB_REGION=cn-north-1
VOLC_KB_SERVICE=air
```

此时后端会直接调用火山引擎知识库检索接口，保留现有 RAG 生成链路；`Qdrant` 配置可继续保留作为本地方案。

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
│   │   ├── graph.py          # LangGraph 图定义及条件路由
│   │   ├── state.py          # 对话状态 (包含 messages, intent, dialog_state 等)
│   │   ├── memory.py         # 长短期记忆 (STM压缩, LTM脚手架)
│   │   └── nodes/
│   │       ├── rewrite.py    # 查询改写节点
│   │       ├── classify.py   # 意图分类节点
│   │       ├── dst_node.py   # 对话状态追踪节点 (提取槽位)
│   │       ├── rag_node.py   # RAG 检索节点
│   │       ├── api_node.py   # 吐槽/售后等 API 通知节点
│   │       ├── chat_node.py  # 闲聊 / 澄清节点
│   │       ├── react_node.py # ReAct 推理节点 (处理售后查账/提工单)
│   │       └── web_search_node.py # 联网查询节点 (如查天气)
│   ├── api/chat.py           # FastAPI 路由（SSE, 接收 LangGraph stream）
│   ├── prompts/              # 每节点一个提示词文件，__init__.py 聚合导出
│   │   ├── classify.py
│   │   ├── rewrite.py
│   │   ├── rag.py
│   │   ├── dst.py
│   │   ├── chat.py
│   │   ├── api.py
│   │   ├── web_search.py
│   │   ├── react.py
│   │   ├── stm_compress.py   # 短期记忆压缩（memory 模块使用）
│   │   └── __init__.py
│   ├── rag/retriever.py      # Qdrant 检索
│   ├── db/mongo.py           # MongoDB 读写 (对话记录持久化)
│   ├── llm.py                # LLM 工厂
│   └── config.py             # 全局配置
frontend/
├── src/
│   ├── views/ChatView.vue    # 主页面
│   ├── components/MessageBubble.vue
│   └── stores/chat.js        # 状态管理 + SSE 对接
docker-compose.yml            # 生产全栈（nginx + backend + qdrant + mongodb）
docker-compose.dev.yml        # 本地开发（仅 qdrant + mongodb）
```
