from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class Document:
    id: str
    text: str
    source: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Chunk:
    id: str
    document_id: str
    text: str
    source: str
    position: int
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SearchResult:
    chunk: Chunk
    dense_score: float
    lexical_score: float
    combined_score: float


@dataclass(frozen=True)
class RouteDecision:
    model: str
    provider: str
    reason: str
    estimated_input_tokens: int
    complexity_score: int


@dataclass(frozen=True)
class Citation:
    number: int
    chunk_id: str
    source: str


@dataclass(frozen=True)
class Answer:
    query: str
    text: str
    citations: list[Citation]
    route: RouteDecision
    retrieved: list[SearchResult]
    usage: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

