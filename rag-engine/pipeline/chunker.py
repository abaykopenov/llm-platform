"""
Chunker — Split text into chunks using various strategies.
Strategies: fixed, paragraph, semantic, sliding_window.
"""

import re
from typing import List, Dict


def chunk_text(
    text: str,
    chunk_size: int = 800,
    chunk_overlap: int = 100,
    strategy: str = "sliding_window",
) -> List[Dict]:
    """
    Split text into overlapping chunks.
    Returns list of dicts: [{"text": str, "index": int}, ...]
    """
    if not text or not text.strip():
        return []

    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    if strategy == "fixed":
        return _fixed_chunks(text, chunk_size, chunk_overlap)
    elif strategy == "paragraph":
        return _paragraph_chunks(text, chunk_size, chunk_overlap)
    elif strategy == "semantic":
        return _semantic_chunks(text, chunk_size, chunk_overlap)
    else:  # sliding_window (default)
        return _sliding_window_chunks(text, chunk_size, chunk_overlap)


def _fixed_chunks(text: str, size: int, overlap: int) -> List[Dict]:
    """Simple fixed-size chunking."""
    chunks = []
    start = 0
    idx = 0
    while start < len(text):
        end = start + size
        chunk = text[start:end].strip()
        if chunk:
            chunks.append({"text": chunk, "index": idx})
            idx += 1
        start = end - overlap
    return chunks


def _paragraph_chunks(text: str, max_size: int, overlap: int) -> List[Dict]:
    """Chunk by paragraphs, merging small ones."""
    paragraphs = text.split("\n\n")
    chunks = []
    current = ""
    idx = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        if current and len(current) + len(para) + 2 > max_size:
            chunks.append({"text": current.strip(), "index": idx})
            idx += 1
            # Overlap: keep tail of previous chunk
            if overlap > 0 and len(current) > overlap:
                current = current[-overlap:].lstrip()
                # Find word boundary
                space = current.find(" ")
                if space > 0:
                    current = current[space + 1:]
                current = current + "\n\n" + para
            else:
                current = para
        else:
            current = (current + "\n\n" + para) if current else para

    if current.strip():
        chunks.append({"text": current.strip(), "index": idx})

    return chunks


def _semantic_chunks(text: str, max_size: int, overlap: int) -> List[Dict]:
    """
    Recursive splitting using hierarchy of separators.
    Approximates semantic chunking without requiring embeddings.
    """
    separators = ["\n\n", "\n", ". ", "! ", "? ", "; ", ", ", " "]
    raw_chunks = _recursive_split(text, separators, max_size)

    # Apply overlap
    chunks = []
    for i, chunk_text in enumerate(raw_chunks):
        if i > 0 and overlap > 0:
            prev = raw_chunks[i - 1]
            overlap_text = prev[-overlap:] if len(prev) > overlap else prev
            space = overlap_text.find(" ")
            if space > 0:
                overlap_text = overlap_text[space + 1:]
            chunk_text = overlap_text + " " + chunk_text

        text_stripped = chunk_text.strip()
        if text_stripped:
            chunks.append({"text": text_stripped, "index": i})

    return chunks


def _sliding_window_chunks(text: str, size: int, overlap: int) -> List[Dict]:
    """Sliding window with word-boundary awareness."""
    words = text.split()
    if not words:
        return []

    # Estimate chars per word
    avg_word_len = len(text) / len(words) if words else 5
    words_per_chunk = max(1, int(size / avg_word_len))
    words_overlap = max(0, int(overlap / avg_word_len))

    chunks = []
    idx = 0
    start = 0

    while start < len(words):
        end = min(start + words_per_chunk, len(words))
        chunk = " ".join(words[start:end]).strip()
        if chunk:
            chunks.append({"text": chunk, "index": idx})
            idx += 1
        start = end - words_overlap
        if start >= len(words) or end == len(words):
            break

    return chunks


def _recursive_split(text: str, separators: list, chunk_size: int) -> List[str]:
    """Recursively split text using a hierarchy of separators."""
    if len(text) <= chunk_size:
        return [text]

    sep = separators[0] if separators else " "
    remaining_seps = separators[1:] if len(separators) > 1 else []

    parts = text.split(sep)
    chunks = []
    current = ""

    for part in parts:
        candidate = (current + sep + part) if current else part
        if len(candidate) <= chunk_size:
            current = candidate
        else:
            if current:
                chunks.append(current)
            if len(part) > chunk_size and remaining_seps:
                sub_chunks = _recursive_split(part, remaining_seps, chunk_size)
                chunks.extend(sub_chunks)
            else:
                current = part

    if current:
        chunks.append(current)

    return chunks
