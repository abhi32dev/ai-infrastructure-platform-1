from __future__ import annotations

import hashlib
import re
from pathlib import Path

from .models import Chunk, Document

TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_./+-]*")
STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "both", "by", "do", "does",
    "for", "from", "how", "in", "is", "it", "of", "on", "or", "the", "to",
    "was", "what", "when", "where", "which", "why", "with", "needed",
}


def tokenize(text: str) -> list[str]:
    return [match.group(0).lower() for match in TOKEN_RE.finditer(text)]


def content_tokens(text: str) -> list[str]:
    terms = [term for term in tokenize(text) if term not in STOP_WORDS and len(term) > 1]
    return [term[:-1] if len(term) > 4 and term.endswith("s") and not term.endswith("ss") else term for term in terms]


def stable_id(*parts: str, length: int = 16) -> str:
    payload = "\x1f".join(parts).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:length]


def load_documents(path: Path) -> list[Document]:
    supported = {".md", ".txt"}
    files = [path] if path.is_file() else sorted(p for p in path.rglob("*") if p.suffix.lower() in supported)
    documents: list[Document] = []
    for file_path in files:
        text = file_path.read_text(encoding="utf-8").strip()
        if not text:
            continue
        source = str(file_path)
        documents.append(Document(id=stable_id(source, text), text=text, source=source))
    return documents


def chunk_document(document: Document, size: int = 120, overlap: int = 24) -> list[Chunk]:
    if size <= 0 or overlap < 0 or overlap >= size:
        raise ValueError("Require size > 0 and 0 <= overlap < size")
    words = document.text.split()
    chunks: list[Chunk] = []
    step = size - overlap
    for position, start in enumerate(range(0, len(words), step)):
        text = " ".join(words[start : start + size]).strip()
        if not text:
            break
        chunks.append(
            Chunk(
                id=stable_id(document.id, str(position), text),
                document_id=document.id,
                text=text,
                source=document.source,
                position=position,
                metadata={**document.metadata, "word_start": start},
            )
        )
        if start + size >= len(words):
            break
    return chunks
