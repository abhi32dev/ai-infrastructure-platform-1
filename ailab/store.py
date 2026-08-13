from __future__ import annotations

import json
import math
import sqlite3
from collections import Counter
from pathlib import Path

from .embeddings import HashingEmbedder, cosine_similarity
from .models import Chunk, SearchResult
from .text import content_tokens


class SQLiteHybridStore:
    def __init__(self, path: Path, embedder: HashingEmbedder) -> None:
        self.path = path
        self.embedder = embedder
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute(
            """CREATE TABLE IF NOT EXISTS chunks (
                id TEXT PRIMARY KEY, document_id TEXT NOT NULL, text TEXT NOT NULL,
                source TEXT NOT NULL, position INTEGER NOT NULL,
                metadata TEXT NOT NULL, embedding TEXT NOT NULL, terms TEXT NOT NULL
            )"""
        )
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def reset(self) -> None:
        self.connection.execute("DELETE FROM chunks")
        self.connection.commit()

    def upsert(self, chunks: list[Chunk]) -> int:
        rows = []
        for chunk in chunks:
            terms = content_tokens(chunk.text)
            rows.append(
                (
                    chunk.id,
                    chunk.document_id,
                    chunk.text,
                    chunk.source,
                    chunk.position,
                    json.dumps(chunk.metadata, sort_keys=True),
                    json.dumps(self.embedder.embed(chunk.text)),
                    json.dumps(terms),
                )
            )
        self.connection.executemany(
            """INSERT INTO chunks VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET text=excluded.text, source=excluded.source,
            metadata=excluded.metadata, embedding=excluded.embedding, terms=excluded.terms""",
            rows,
        )
        self.connection.commit()
        return len(rows)

    def count(self) -> int:
        return int(self.connection.execute("SELECT COUNT(*) FROM chunks").fetchone()[0])

    def search(self, query: str, limit: int = 5, dense_weight: float = 0.55) -> list[SearchResult]:
        if not 0 <= dense_weight <= 1:
            raise ValueError("dense_weight must be between 0 and 1")
        rows = self.connection.execute("SELECT * FROM chunks").fetchall()
        if not rows:
            return []
        query_terms = content_tokens(query)
        query_vector = self.embedder.embed(query)
        documents = [json.loads(row["terms"]) for row in rows]
        document_frequency = Counter(term for terms in documents for term in set(terms))
        avg_length = sum(map(len, documents)) / len(documents)
        raw: list[tuple[sqlite3.Row, float, float]] = []
        for row, terms in zip(rows, documents):
            dense = max(0.0, cosine_similarity(query_vector, json.loads(row["embedding"])))
            frequencies = Counter(terms)
            lexical = 0.0
            for term in query_terms:
                tf = frequencies[term]
                if not tf:
                    continue
                idf = math.log(1 + (len(rows) - document_frequency[term] + 0.5) / (document_frequency[term] + 0.5))
                denominator = tf + 1.5 * (1 - 0.75 + 0.75 * len(terms) / max(avg_length, 1))
                lexical += idf * (tf * 2.5) / denominator
            raw.append((row, dense, lexical))
        max_lexical = max((item[2] for item in raw), default=1.0) or 1.0
        results = []
        for row, dense, lexical in raw:
            normalized_lexical = lexical / max_lexical
            chunk = Chunk(
                id=row["id"], document_id=row["document_id"], text=row["text"],
                source=row["source"], position=row["position"], metadata=json.loads(row["metadata"]),
            )
            combined = dense_weight * dense + (1 - dense_weight) * normalized_lexical
            results.append(SearchResult(chunk, dense, normalized_lexical, combined))
        return sorted(results, key=lambda item: (-item.combined_score, item.chunk.id))[:limit]
