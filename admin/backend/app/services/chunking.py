from __future__ import annotations

import hashlib
import re
from typing import Literal

from pydantic import BaseModel, Field


KnowledgeStatus = Literal["draft", "reviewing", "published", "archived"]
ChunkMethod = Literal["heading", "fixed", "semantic"]


class KnowledgeMetadata(BaseModel):
    category: str = "产品功能"
    product_area: str = "BOU App"
    owner: str = "产品运营"
    version: str = "v1.0"
    status: KnowledgeStatus = "draft"
    visibility: str = "客服Agent"
    effective_at: str = ""
    expire_at: str = ""
    update_frequency: str = "按需更新"
    tags: list[str] = Field(default_factory=list)


class ChunkStrategy(BaseModel):
    method: ChunkMethod = "heading"
    chunk_size: int = Field(default=700, ge=120, le=3000)
    overlap: int = Field(default=100, ge=0, le=800)
    preserve_tables: bool = True
    add_parent_title: bool = True


class KnowledgeChunk(BaseModel):
    chunk_id: str
    index: int
    title_path: str = ""
    content: str
    token_estimate: int
    metadata: dict = Field(default_factory=dict)


def token_estimate(text: str) -> int:
    return max(1, len(text.strip()) // 2)


def extract_title(markdown: str, fallback: str = "未命名文档") -> str:
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped.lstrip("#").strip() or fallback
    return fallback


def normalize_fetched_doc(raw: str) -> tuple[str, str]:
    lines = []
    for line in raw.splitlines():
        if line.startswith("Total output lines:"):
            continue
        lines.append(line.rstrip())
    content = "\n".join(lines).strip()
    return extract_title(content), content


def stable_chunk_id(title: str, index: int, content: str) -> str:
    digest = hashlib.sha1(f"{title}:{index}:{content[:200]}".encode("utf-8")).hexdigest()[:12]
    return f"chk_{digest}"


def split_fixed(text: str, chunk_size: int, overlap: int) -> list[str]:
    normalized = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not normalized:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(len(normalized), start + chunk_size)
        candidate = normalized[start:end]
        if end < len(normalized):
            break_at = max(candidate.rfind("\n\n"), candidate.rfind("。"), candidate.rfind("."), candidate.rfind("\n"))
            if break_at > chunk_size * 0.45:
                end = start + break_at + 1
                candidate = normalized[start:end]
        chunks.append(candidate.strip())
        if end >= len(normalized):
            break
        start = max(0, end - overlap) if overlap else end
        if start >= end:
            start = end
    return [chunk for chunk in chunks if chunk]


def split_heading(text: str, chunk_size: int, overlap: int) -> list[tuple[str, str]]:
    sections: list[tuple[str, list[str]]] = []
    current_title = "正文"
    current_lines: list[str] = []

    for line in text.splitlines():
        if re.match(r"^#{1,6}\s+\S", line.strip()):
            if current_lines:
                sections.append((current_title, current_lines))
            current_title = line.strip().lstrip("#").strip()
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_lines:
        sections.append((current_title, current_lines))

    output: list[tuple[str, str]] = []
    for title, lines in sections:
        section_text = "\n".join(lines).strip()
        if len(section_text) <= chunk_size:
            output.append((title, section_text))
            continue
        output.extend((title, part) for part in split_fixed(section_text, chunk_size, overlap))
    return output


def split_semantic(text: str, chunk_size: int, overlap: int) -> list[str]:
    blocks = [block.strip() for block in re.split(r"\n\s*\n", text) if block.strip()]
    chunks: list[str] = []
    buffer: list[str] = []
    length = 0
    for block in blocks:
        if buffer and length + len(block) > chunk_size:
            chunks.append("\n\n".join(buffer).strip())
            if overlap:
                tail = "\n\n".join(buffer)[-overlap:]
                buffer = [tail] if tail.strip() else []
                length = len(tail)
            else:
                buffer = []
                length = 0
        buffer.append(block)
        length += len(block)
    if buffer:
        chunks.append("\n\n".join(buffer).strip())
    return chunks


def build_chunks(title: str, content: str, metadata: KnowledgeMetadata, strategy: ChunkStrategy) -> list[KnowledgeChunk]:
    if strategy.method == "heading":
        raw_chunks = split_heading(content, strategy.chunk_size, strategy.overlap)
    elif strategy.method == "semantic":
        raw_chunks = [("", chunk) for chunk in split_semantic(content, strategy.chunk_size, strategy.overlap)]
    else:
        raw_chunks = [("", chunk) for chunk in split_fixed(content, strategy.chunk_size, strategy.overlap)]

    chunks: list[KnowledgeChunk] = []
    for index, (title_path, chunk_content) in enumerate(raw_chunks):
        enriched = chunk_content
        if strategy.add_parent_title and title_path and title_path not in chunk_content[:120]:
            enriched = f"【所属章节】{title_path}\n\n{chunk_content}"
        chunks.append(
            KnowledgeChunk(
                chunk_id=stable_chunk_id(title, index, enriched),
                index=index,
                title_path=title_path,
                content=enriched,
                token_estimate=token_estimate(enriched),
                metadata={
                    "document_title": title,
                    "category": metadata.category,
                    "product_area": metadata.product_area,
                    "version": metadata.version,
                    "status": metadata.status,
                    "tags": metadata.tags,
                },
            )
        )
    return chunks
