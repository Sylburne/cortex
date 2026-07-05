"""Semantic-aware text chunker with heading hierarchy support."""
from app.config import settings
import re


def chunk_text(text: str, chunk_size: int = None, overlap: int = None) -> list[dict]:
    """Split text into chunks preserving semantic structure.

    Returns list of {content, metadata} dicts.
    """
    chunk_size = chunk_size or settings.chunk_size_tokens
    overlap = overlap or settings.chunk_overlap_tokens

    if not text or not text.strip():
        return []

    # Split by heading hierarchy first
    sections = _split_by_headings(text)

    chunks = []
    for section in sections:
        heading_path = section.get("heading_path", "")
        content = section["content"]
        estimated_tokens = len(content.split())  # rough token estimate

        if estimated_tokens <= chunk_size:
            chunks.append({"content": content, "metadata": {"heading_path": heading_path}})
        else:
            # Split oversized sections by paragraphs, then sentences
            sub_chunks = _split_large_section(content, chunk_size, overlap, heading_path)
            chunks.extend(sub_chunks)

    return chunks


def _split_by_headings(text: str) -> list[dict]:
    """Split text by markdown-style headings."""
    heading_pattern = re.compile(r'^(#{1,6}\s+.+|^\d+[\.\)]\s+.+)', re.MULTILINE)
    matches = list(heading_pattern.finditer(text))

    if not matches:
        return [{"content": text, "heading_path": ""}]

    sections = []
    # Content before first heading
    if matches[0].start() > 0:
        pre = text[:matches[0].start()].strip()
        if pre:
            sections.append({"content": pre, "heading_path": ""})

    for i, match in enumerate(matches):
        heading = match.group(0).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start:end].strip()
        if content:
            sections.append({"content": heading + "\n" + content, "heading_path": heading})

    return sections


def _split_large_section(content: str, chunk_size: int, overlap: int, heading_path: str) -> list[dict]:
    """Split an oversized section into overlapping chunks."""
    paragraphs = content.split("\n\n")
    chunks = []
    current = []
    current_tokens = 0

    for para in paragraphs:
        para_tokens = len(para.split())
        if current_tokens + para_tokens > chunk_size and current:
            chunk_text = "\n\n".join(current)
            chunks.append({"content": chunk_text, "metadata": {"heading_path": heading_path}})
            # Keep overlap
            overlap_paras = []
            overlap_tokens = 0
            for p in reversed(current):
                t = len(p.split())
                if overlap_tokens + t > overlap:
                    break
                overlap_paras.insert(0, p)
                overlap_tokens += t
            current = overlap_paras
            current_tokens = overlap_tokens

        current.append(para)
        current_tokens += para_tokens

    if current:
        chunks.append({"content": "\n\n".join(current), "metadata": {"heading_path": heading_path}})

    return chunks
