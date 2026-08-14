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

### 1. Why keep retrieval evaluation separate from generation evaluation?

**Answer.** Retrieval and generation have different failure domains. Recall@K/MRR determine whether evidence reached the model; grounding/citation/answer metrics determine whether the model used that evidence correctly. A single answer score cannot distinguish a missing chunk from hallucination, so it produces the wrong remediation. `run_retrieval_eval` evaluates source ranking independently; `evaluate` scores the generated answer.

```python
# ailab/rag_advanced.py
return {"cases": len(cases), "recall_at_k": hits / len(cases),
        "mean_reciprocal_rank": sum(reciprocal) / len(cases),
        "passed": hits == len(cases)}
```

### 2. How do BM25 and dense-vector retrieval fail differently?

**Answer.** BM25 fails on vocabulary mismatch but excels at rare exact identifiers; dense retrieval captures semantic similarity but may blur exact facts, domains, or tenants. Hybrid retrieval reduces correlated error, but both must share authorization filters. The store calculates lexical and cosine signals separately before fusion.

```python
# ailab/store.py · SQLiteHybridStore.search
dense = max(0.0, cosine_similarity(query_vector, json.loads(row["embedding"])))
lexical += idf * (tf * 2.5) / denominator
```

### 3. Why must hybrid scores be normalized or fused by rank?

**Answer.** BM25 and cosine values have unrelated scales and distributions; raw addition allows one retriever's numeric range to dominate without meaningfully higher relevance. Normalize calibrated scores or use reciprocal-rank fusion, which depends on ordering rather than score magnitude. This project uses RRF and then an inspectable reranker.

```python
# ailab/rag_advanced.py · reciprocal_rank_fusion
scores[result.chunk.id] = scores.get(result.chunk.id, 0.0) + 1 / (k + rank)
```

### 4. When does chunk overlap help, and when does it waste context?

**Answer.** Overlap helps when an answer-bearing concept crosses a chunk boundary. Too much overlap duplicates tokens, retrieval candidates, embedding cost, and model context, reducing evidence diversity. Treat overlap as a measured corpus parameter, enforce `0 <= overlap < chunk_size`, and evaluate recall plus context duplication.

```python
# ailab/text.py · chunk_document
if size <= 0 or overlap < 0 or overlap >= size:
    raise ValueError("Require size > 0 and 0 <= overlap < size")
```

### 5. Why is a checkpoint insufficient without idempotent side effects?

**Answer.** A process can commit an external mutation and crash before checkpointing completion. Replay then repeats the mutation. The practical design combines a stable operation key, remote deduplication, a durable effect record, and reconciliation; a local checkpoint alone cannot make two systems atomic.

```python
# ailab/agent_runtime.py · DurableAgentRuntime._execute
cached = self.connection.execute(
    "SELECT output FROM tool_effects WHERE idempotency_key=?", (key,)
).fetchone()
if cached:
    return json.loads(cached["output"])
```

### 6. What information must be journaled for deterministic replay?

**Answer.** Persist run/step identity, plan and policy versions, resolved inputs or immutable references, tool/version, attempt/error, approval actor/decision, idempotency key, effect/output hash, checkpoint state, timestamps, and final transition. Record new correction events instead of rewriting history; exclude secrets and chain-of-thought.

```python
# ailab/agent_runtime.py · DurableAgentRuntime._event
self.connection.execute(
    "INSERT INTO events(run_id, event_type, payload, created_at) VALUES (?, ?, ?, ?)",
    (run_id, event_type, json.dumps(payload, sort_keys=True), time.time()))
```

### 7. What signals should a cost-aware model router use?

**Answer.** Use tenant/privacy policy, task complexity, context size, quality requirement, deadline, model health, predicted input/output tokens, unit price, remaining request/tenant budget, and observed quality/latency feedback. Policy constraints filter candidates first; cost only ranks the remaining eligible set.

```python
# ailab/model_gateway.py · ModelGateway._route
candidates = [model for model in self.models.values()
    if model.max_context >= tokens
    and (request.privacy != "local" or model.provider == "local")
    and self._healthy(model.name)]
```

### 8. Why should a fallback chain share an end-to-end deadline?

**Answer.** Resetting a full timeout for every model multiplies tail latency and performs work after the caller's useful window. Reserve one deadline across queueing and every fallback; each attempt gets only remaining time. Stop when the next candidate cannot complete within the residual budget, even if it is otherwise healthy.

```text
remaining = deadline_at - monotonic_now()
if remaining <= predicted_queue_plus_inference(candidate):
    stop_fallback("end-to-end deadline exhausted")
```

### 9. How would SQLite change at high write concurrency or multi-node scale?

**Answer.** Replace the single-process database with a transactional replicated store, explicit connection pooling, partition/tenant keys, conditional writes, leases, and an outbox for asynchronous work. Keep the same uniqueness and state-transition contracts. Vector retrieval, event history, and artifacts may move to specialized stores, but one component must remain authoritative for each mutation.

```python
# Current local atomic boundary retained by the production replacement
self.connection.executemany("""INSERT INTO chunks VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(id) DO UPDATE SET text=excluded.text, source=excluded.source,
    metadata=excluded.metadata, embedding=excluded.embedding, terms=excluded.terms""", rows)
self.connection.commit()
```

### 10. Which evaluation components must stay deterministic in CI?

**Answer.** Dataset/version selection, preprocessing, required/forbidden-term checks, citation validation, metric formulas, thresholds, statistical calculations, seeds, and release-decision logic must be deterministic. Probabilistic model judges can be additive, but pin model/prompt/config and calibrate them against human labels; never make a flaky remote judge the only safety gate.

```python
# ailab/eval_platform.py · EvaluationPlatform.gate
reasons = []
if summary["quality"] < thresholds.minimum_quality:
    reasons.append("quality_below_threshold")
if summary["safety"] < thresholds.minimum_safety:
    reasons.append("safety_below_threshold")
decision = "promote" if not reasons else "block"
return {"run_id": run_id, "decision": decision,
        "reasons": reasons, "summary": summary}
```

The complete production architecture review for Project 1 is in [`projects/project-01-rag/PROD.md`](../projects/project-01-rag/PROD.md).

## Production-scale substitutions

| Local component | Production option | New concern introduced |
|---|---|---|
| SQLite | PostgreSQL/pgvector or Qdrant | concurrency, replication, index maintenance |
| Hashing embedder | hosted/local embedding model | batching, GPU use, model/version drift |
| Python process | Kubernetes service | scheduling, rollout, network partitions |
| Direct provider call | model gateway | quotas, deadlines, health and fallbacks |
| Local journal | Temporal/PostgreSQL workflow state | leases, split-brain and retention |

## Completed production-RAG extensions

- Real Ollama `/api/embed` provider contract with explicit availability failures
- Reciprocal-rank fusion of dense and lexical rankings
- Second-stage deterministic reranking by query coverage and ordered terms
- Metadata/tenant filtering before results are returned
- TTL semantic response cache
- LangChain Document and LlamaIndex Node conversion adapters
- Versioned retrieval evaluation dataset with Recall@K and mean reciprocal rank

The deterministic reranker is intentionally inspectable; it is not described as a neural cross-encoder. A neural reranker, pgvector, or Qdrant can replace the same boundaries without changing the learning exercises.
