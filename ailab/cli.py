from __future__ import annotations

import argparse
import json
from pathlib import Path

from .embeddings import HashingEmbedder
from .rag import RAGService
from .store import SQLiteHybridStore
from .text import chunk_document, load_documents


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AI Infrastructure Lab")
    parser.add_argument("--db", type=Path, default=Path("data/lab.db"))
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("reset")
    ingest = commands.add_parser("ingest")
    ingest.add_argument("path", type=Path)
    ingest.add_argument("--chunk-size", type=int, default=120)
    ingest.add_argument("--overlap", type=int, default=24)
    ask = commands.add_parser("ask")
    ask.add_argument("query")
    ask.add_argument("--provider", choices=["offline", "ollama"], default="offline")
    ask.add_argument("--top-k", type=int, default=4)
    commands.add_parser("status")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    store = SQLiteHybridStore(args.db, HashingEmbedder())
    try:
        if args.command == "reset":
            store.reset()
            print(f"Reset {args.db}")
        elif args.command == "ingest":
            documents = load_documents(args.path)
            chunks = [chunk for document in documents for chunk in chunk_document(document, args.chunk_size, args.overlap)]
            print(json.dumps({"documents": len(documents), "chunks_upserted": store.upsert(chunks), "index_size": store.count()}))
        elif args.command == "ask":
            answer = RAGService(store).answer(args.query, args.top_k, args.provider)
            print(json.dumps(answer.to_dict(), indent=2))
        elif args.command == "status":
            print(json.dumps({"database": str(args.db), "indexed_chunks": store.count()}))
        return 0
    finally:
        store.close()


if __name__ == "__main__":
    raise SystemExit(main())

