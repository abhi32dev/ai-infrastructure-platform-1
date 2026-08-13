# Build Progress

## 2026-08-13 - Milestone 1 foundation

Completed and verified:

- Saved the complete 12-project portfolio and resume mapping in `ROADMAP.md`
- Implemented a dependency-free local RAG vertical slice
- Added persistent SQLite storage using WAL mode
- Added deterministic local dense vectors and BM25-style lexical retrieval
- Added normalized hybrid score fusion
- Added cited offline generation and an Ollama provider adapter
- Added a simple complexity-aware model-routing policy
- Added retrieval-hit, citation-validity, and grounding evaluation
- Added durable workflow checkpoints, bounded retries, resume, and idempotent step completion
- Added 3 learning documents, architecture notes, exercises, interview questions, and production substitutions
- Added 6 automated tests

Acceptance result:

```text
6 passed
3 documents ingested
6 chunks indexed
Natural checkpoint/idempotency question retrieves the reliability source first
```

Next increment:

- Replace the test embedding option with a real Ollama embedding adapter
- Add reciprocal-rank fusion and reranking
- Add a versioned evaluation dataset runner
- Add model budgets, fallback rules, and a usage ledger
- Expose ingestion/query/evaluation through FastAPI

