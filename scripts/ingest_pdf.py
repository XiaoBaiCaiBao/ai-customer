"""
知识库数据入库脚本 — PDF 版

用法:
    cd scripts
    source ../backend/venv/bin/activate
    python ingest_pdf.py ../data/文档.pdf

支持多个文件:
    python ingest_pdf.py ../data/file1.pdf ../data/file2.pdf
"""

import re
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# 加载 backend/.env 里的配置
load_dotenv(Path(__file__).parent.parent / "backend" / ".env")

import httpx
import fitz  # pymupdf
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

# ── 配置（从 .env 读取）────────────────────────────────────────────────────────
QDRANT_URL        = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION_NAME   = os.getenv("QDRANT_COLLECTION", "knowledge_base")
LLM_API_KEY       = os.getenv("LLM_API_KEY", "")
EMBEDDING_MODEL   = os.getenv("EMBEDDING_MODEL", "doubao-embedding-vision-251215")
EMBEDDING_BASE_URL = os.getenv(
    "EMBEDDING_BASE_URL",
    "https://ark.cn-beijing.volces.com/api/v3/embeddings/multimodal"
)


# ── Embedding ─────────────────────────────────────────────────────────────────

def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    调用 doubao-embedding-vision multimodal 端点进行纯文本向量化。
    该接口每次调用返回一个合并向量，需每条文本单独请求。
    响应格式: {"data": {"embedding": [float, ...]}}
    """
    vectors = []
    for i, text in enumerate(texts):
        resp = httpx.post(
            EMBEDDING_BASE_URL,
            headers={
                "Authorization": f"Bearer {LLM_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": EMBEDDING_MODEL,
                "input": [{"type": "text", "text": text}],
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        vectors.append(data["data"]["embedding"])
        print(f"  向量化进度: {i + 1}/{len(texts)}")
    return vectors


# ── PDF 解析 ──────────────────────────────────────────────────────────────────

def extract_text(pdf_path: str) -> str:
    doc = fitz.open(pdf_path)
    pages = []
    for page in doc:
        pages.append(page.get_text())
    return "\n".join(pages)


def chunk_faq(text: str, source_file: str) -> list[dict]:
    """
    按编号切分 FAQ 条目。
    支持格式: "1. 标题" 或 "1、标题"
    每个 chunk 包含完整的 Q&A 内容。
    """
    # 分割页码标记
    text = re.sub(r"--\s*\d+\s*of\s*\d+\s*--", "", text)

    # 按编号切分：匹配行首的 "数字." 或 "数字、"
    parts = re.split(r"\n(?=\d+[\.、])", text)

    chunks = []
    header = parts[0].strip()  # 第一段是总说明，也作为一个 chunk

    if header:
        chunks.append({
            "content": header,
            "source_file": source_file,
            "section": "总体原则",
            "item_number": 0,
            "question": "客服总体原则",
        })

    for part in parts[1:]:
        part = part.strip()
        if not part:
            continue

        # 提取编号和内容
        m = re.match(r"^(\d+)[\.、]\s*(.*)", part, re.DOTALL)
        if not m:
            continue

        item_num = int(m.group(1))
        body = m.group(2).strip()

        # 第一行作为"问题标题"，其余是回答
        lines = body.split("\n", 1)
        question = lines[0].strip().strip('"').strip('"').strip('"')
        answer = lines[1].strip() if len(lines) > 1 else ""

        # 拼成完整 Q&A 文本（RAG 检索时语义更完整）
        full_text = f"问题：{question}\n\n回答：{answer}" if answer else f"问题：{question}"

        chunks.append({
            "content": full_text,
            "source_file": source_file,
            "section": "运营FAQ",
            "item_number": item_num,
            "question": question,
        })

    return chunks


# ── Qdrant 写入 ───────────────────────────────────────────────────────────────

def init_collection(client: QdrantClient, dim: int):
    """如果 collection 不存在则创建，已存在则跳过"""
    existing = [c.name for c in client.get_collections().collections]
    if COLLECTION_NAME not in existing:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )
        print(f"已创建 collection: {COLLECTION_NAME}")
    else:
        print(f"collection 已存在: {COLLECTION_NAME}，追加写入")


def upsert_chunks(client: QdrantClient, chunks: list[dict], vectors: list[list[float]]):
    # 获取当前最大 ID，避免覆盖已有数据
    try:
        count = client.count(COLLECTION_NAME).count
    except Exception:
        count = 0

    points = [
        PointStruct(
            id=count + i,
            vector=vec,
            payload=chunk,
        )
        for i, (chunk, vec) in enumerate(zip(chunks, vectors))
    ]
    client.upsert(collection_name=COLLECTION_NAME, points=points)
    print(f"已写入 {len(points)} 条数据（ID {count} ~ {count + len(points) - 1}）")


# ── 主流程 ────────────────────────────────────────────────────────────────────

def ingest(pdf_path: str):
    path = Path(pdf_path)
    print(f"\n{'='*50}")
    print(f"处理文件: {path.name}")

    print("1/4 解析 PDF...")
    text = extract_text(str(path))

    print("2/4 切分 FAQ 条目...")
    chunks = chunk_faq(text, path.name)
    print(f"    共切出 {len(chunks)} 个 chunk")
    for c in chunks:
        print(f"    [{c['item_number']}] {c['question'][:40]}")

    print("3/4 向量化...")
    texts = [c["content"] for c in chunks]
    vectors = embed_texts(texts)

    print("4/4 写入 Qdrant...")
    client = QdrantClient(url=QDRANT_URL)
    init_collection(client, dim=len(vectors[0]))
    upsert_chunks(client, chunks, vectors)

    print(f"✓ {path.name} 入库完成")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python ingest_pdf.py <file1.pdf> [file2.pdf ...]")
        sys.exit(1)

    for pdf in sys.argv[1:]:
        ingest(pdf)

    print("\n所有文件处理完成！")
