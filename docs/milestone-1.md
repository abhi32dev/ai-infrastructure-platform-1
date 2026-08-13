# Milestone 1 - Local RAG Vertical Slice

## What is runnable

The first slice implements ingestion, overlapping chunking, deterministic feature-hash embeddings, a persistent SQLite index, BM25-style lexical scoring, dense cosine scoring, hybrid score fusion, grounded answer generation, numbered citations, cost-aware routing, an Ollama adapter, a regression evaluation gate, and a durable step journal.

The hashing embedder is a learning/test double, not a claim that feature hashing matches a modern semantic embedding model. Its boundary is intentionally replaceable. This lets every reliability test run without downloads, credentials, network access, or nondeterministic model behavior.

## Run it

From the repository root:

```bash
python3 -m ailab.cli reset
python3 -m ailab.cli ingest examples/knowledge --chunk-size 90 --overlap 18
python3 -m ailab.cli status
python3 -m ailab.cli ask "Why are checkpoints and idempotency both needed?"
python3 -m pytest
```

If Ollama is installed and a model is pulled:

```bash
ollama pull qwen2.5:3b
python3 -m ailab.cli ask "Compare lexical and dense retrieval" --provider ollama
```

## Architecture

```text
Markdown/text documents
        |
  normalize + chunk
        |
 deterministic embedder
        |
 SQLite chunk/vector/term store
        |
 BM25 score + cosine score
        |
    weighted fusion
        |
 context + citation assembly
        |
 cost-aware model router
       / \
 offline  Ollama
 provider provider
        |
 evaluation gate
```

## Hands-on exercises

1. Change `--chunk-size` from 40 to 180 and compare retrieved passages.
2. Change `dense_weight` in `SQLiteHybridStore.search` and use exact identifiers versus paraphrased queries.
3. Stop Ollama and observe the explicit provider failure. Design a bounded fallback rather than hiding the error.
4. Inject a failure into a durable workflow step and inspect the `steps` table before resuming it.
5. Add a misleading document and observe why retrieval hit, grounding, and citation validity measure different defects.
6. Create a query that the router classifies as complex and inspect the recorded route reason.

## Interview questions

- Why keep retrieval evaluation separate from generation evaluation?
- How do BM25 and dense-vector retrieval fail differently?
- Why must hybrid scores be normalized or fused by rank?
- When does chunk overlap help, and when does it waste context?
- Why is a checkpoint insufficient without idempotent side effects?
- What information must be journaled for deterministic replay?
- What signals should a cost-aware model router use?
- Why should a fallback chain share an end-to-end deadline?
- How would SQLite change at high write concurrency or multi-node scale?
- Which evaluation components must stay deterministic in CI?

## Production-scale substitutions

| Local component | Production option | New concern introduced |
|---|---|---|
| SQLite | PostgreSQL/pgvector or Qdrant | concurrency, replication, index maintenance |
| Hashing embedder | hosted/local embedding model | batching, GPU use, model/version drift |
| Python process | Kubernetes service | scheduling, rollout, network partitions |
| Direct provider call | model gateway | quotas, deadlines, health and fallbacks |
| Local journal | Temporal/PostgreSQL workflow state | leases, split-brain and retention |

