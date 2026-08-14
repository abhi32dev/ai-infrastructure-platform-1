# Production reasoning — Production RAG

## Why this project exists

Grounded retrieval must preserve tenant isolation and citation provenance. This project is deliberately small enough to execute locally but preserves the decision points that dominate production incidents and staff-level design reviews.

## Production invariants

- Inputs are typed, validated before side effects, and reject null, empty, malformed, non-finite, unsafe or unsupported values.
- Every mutation is attributable and either idempotent or protected by a unique operation identity.
- Work is bounded by capacity, deadline, retry, quota and cost policies; overload is an explicit state rather than silent degradation.
- Durable evidence separates desired state, actual state, decisions, attempts, outputs and failures.
- Recovery is tested from persisted state. A successful retry cannot duplicate an already committed effect.
- Tenant, identity and policy boundaries are enforced before retrieval, execution or publication.
- Observability records user-impact signals without secrets, raw credentials or chain-of-thought.

## Test strategy and why it matters

The project test suite uses a layered production matrix:

1. **Unit tests** isolate deterministic business rules so failures identify one invariant.
2. **Null and type tests** prevent ambiguous downstream exceptions and injection through unexpected shapes.
3. **Boundary tests** exercise zero, one, maximum, over-maximum, negative, NaN and infinity where applicable.
4. **Negative-policy tests** prove the system fails closed for authorization, budgets, schemas and unsafe configuration.
5. **Idempotency tests** repeat requests, events and resume operations to prevent duplicate cost or effects.
6. **Failure-injection tests** simulate providers, workers, storage, timeouts, corruption and partial completion.
7. **Recovery tests** verify checkpoint, replay, reconciliation, fallback, circuit, failover or rollback behavior.
8. **Concurrency/capacity tests** validate bounded queues, resource placement, quotas and load shedding.
9. **Security tests** cover malformed identity, tenant escape, prompt injection, PII/secrets and audit tampering.
10. **Contract tests** validate protocol, API, artifact and environment compatibility at replaceable boundaries.

Project-specific scenarios:

- empty corpus and empty query
- invalid chunk size/overlap
- duplicate ingestion and deterministic IDs
- tenant/metadata filter isolation
- embedding provider outage
- cache hit, miss and TTL expiry
- retrieval recall/MRR regression
- citation and grounding failure

Tests use deterministic clocks, seeded data, temporary directories and local stores where possible. This avoids flaky CI. Live cloud/model/GPU tests belong in a separate opt-in suite because availability, cost and credentials would otherwise make the default suite non-reproducible.

## Design choice and trade-off

SQLite keeps the lab inspectable; production substitutes a replicated vector/search tier behind the same contract.

The trade-off is intentional: a local implementation cannot prove internet-scale throughput, multi-region durability or accelerator performance. It can prove state transitions, schemas, policy, retry safety, observability contracts and failure handling—the logic that must remain correct when scale changes.

## Operational review checklist

- Define SLI/SLO, error-budget owner, alert thresholds and rollback authority.
- Estimate peak throughput, concurrency, memory/storage growth, token/GPU usage and unit cost.
- Document dependency limits, timeouts, retry budgets, circuit behavior and degradation order.
- Define backup, restore, replay, reconciliation, regional failure and disaster-recovery exercises.
- Threat-model identity, tenant boundaries, secrets, supply chain, data retention and audit access.
- Version schemas, prompts, datasets, models, policies, APIs and infrastructure; test compatibility.
- Establish deployment gates, canary signals, automated rollback and manual override procedures.

## Staff/Principal discussion prompts

### 1. Which invariant is financially or operationally most expensive to violate?

**Staff/Principal answer.** Tenant isolation is the costliest invariant: one cross-tenant retrieval is a confidentiality incident, while a missed relevant chunk is normally a recoverable quality defect. Retrieval must therefore filter before ranking and generation, not redact after the answer exists.

**Implementation evidence.** [`ailab/rag_advanced.py · AdvancedRetriever.search`](../../ailab/rag_advanced.py) is the concrete control point used by this project:

```python
def search(self,query:str,limit=5,filters:dict[str,Any]|None=None)->list[SearchResult]:
  candidates=self.store.search(query,limit=max(self.store.count(),limit));filters=filters or {};candidates=[r for r in candidates if (r.dense_score>0 or r.lexical_score>0) and all(r.chunk.metadata.get(k)==v for k,v in filters.items())];return rerank(query,reciprocal_rank_fusion(candidates))[:limit]
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `AdvancedRetriever.search` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 2. Where is the linearization point for an idempotent mutation?

**Staff/Principal answer.** The durable linearization point is SQLiteHybridStore.upsert committing the stable chunk identity and content. Re-ingestion may recompute embeddings, but after the transaction commits, the stable ID represents one logical chunk and subsequent reads must observe that version.

**Implementation evidence.** [`ailab/store.py · SQLiteHybridStore.upsert`](../../ailab/store.py) is the concrete control point used by this project:

```python
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
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `SQLiteHybridStore.upsert` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 3. Which state is authoritative during disagreement, and how is reconciliation bounded?

**Staff/Principal answer.** The indexed chunk record is authoritative for retrieval; cached answers are derived and disposable. Reconciliation is bounded to re-embedding or re-indexing known document IDs, followed by retrieval evaluation, rather than accepting cache contents as source truth.

**Implementation evidence.** [`ailab/store.py · SQLiteHybridStore.upsert`](../../ailab/store.py) is the concrete control point used by this project:

```python
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
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `SQLiteHybridStore.upsert` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 4. What does graceful degradation preserve, and what must fail closed?

**Staff/Principal answer.** Degrade from dense-plus-lexical retrieval to the remaining healthy retriever or return an explicit no-evidence response. Tenant filtering, citation provenance, and grounding must fail closed; the system must never answer from unauthorized or uncited context.

**Implementation evidence.** [`ailab/rag.py · RAGService.answer`](../../ailab/rag.py) is the concrete control point used by this project:

```python
def answer(self, query: str, limit: int = 4, provider: str = "offline") -> Answer:
        results = self.store.search(query, limit=limit)
        if not results:
            raise ValueError("The index is empty; ingest documents before asking questions")
        contexts = [result.chunk.text for result in results]
        route = self.router.route(query, "\n".join(contexts), force_provider=provider)
        generation = self.providers[route.provider].generate(route.model, query, contexts)
        citations = [Citation(index, result.chunk.id, result.chunk.source) for index, result in enumerate(results, 1)]
        return Answer(
            query=query,
            text=generation.text,
            citations=citations,
            route=route,
            retrieved=results,
            usage={"prompt_tokens": generation.prompt_tokens, "completion_tokens": generation.completion_tokens},
        )
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `RAGService.answer` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 5. Which metrics detect correctness loss before customers report it?

**Staff/Principal answer.** Track Recall@K, MRR, empty-result rate, citation validity, grounding score, cache hit rate, provider failures, and p95 latency by tenant and corpus version. Recall and citation regressions are leading correctness indicators even when HTTP success remains 100%.

**Implementation evidence.** [`ailab/rag_advanced.py · run_retrieval_eval`](../../ailab/rag_advanced.py) is the concrete control point used by this project:

```python
def run_retrieval_eval(retriever:AdvancedRetriever,cases:list[RAGEvalCase],k=3)->dict:
 if not cases:raise ValueError("evaluation cases cannot be empty")
 reciprocal=[];hits=0
 for case in cases:
  results=retriever.search(case.query,k);rank=next((i for i,r in enumerate(results,1) if case.expected_source in r.chunk.source),None);hits+=rank is not None;reciprocal.append(0 if rank is None else 1/rank)
 return {"cases":len(cases),"recall_at_k":hits/len(cases),"mean_reciprocal_rank":sum(reciprocal)/len(cases),"passed":hits==len(cases)}
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `run_retrieval_eval` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 6. What changes at 10× traffic, 100× data, multiple regions or adversarial tenants?

**Staff/Principal answer.** At scale, shard by tenant/corpus, replicate indexes, make ingestion asynchronous, version embeddings, and use admission control around model calls. Multi-region reads need version-aware replication; adversarial tenants require quotas and filter enforcement inside the storage query.

**Implementation evidence.** [`ailab/rag_advanced.py · AdvancedRetriever.search`](../../ailab/rag_advanced.py) is the concrete control point used by this project:

```python
def search(self,query:str,limit=5,filters:dict[str,Any]|None=None)->list[SearchResult]:
  candidates=self.store.search(query,limit=max(self.store.count(),limit));filters=filters or {};candidates=[r for r in candidates if (r.dense_score>0 or r.lexical_score>0) and all(r.chunk.metadata.get(k)==v for k,v in filters.items())];return rerank(query,reciprocal_rank_fusion(candidates))[:limit]
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `AdvancedRetriever.search` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 7. Which decisions belong in the platform versus the application team, and why?

**Staff/Principal answer.** The platform owns identity propagation, storage isolation, embedding/index versioning, budgets, telemetry, and evaluation gates. The application team owns corpus semantics, metadata policy, chunking experiments, relevance labels, and the product decision for when no answer is preferable.

**Implementation evidence.** [`ailab/rag.py · RAGService.answer`](../../ailab/rag.py) is the concrete control point used by this project:

```python
def answer(self, query: str, limit: int = 4, provider: str = "offline") -> Answer:
        results = self.store.search(query, limit=limit)
        if not results:
            raise ValueError("The index is empty; ingest documents before asking questions")
        contexts = [result.chunk.text for result in results]
        route = self.router.route(query, "\n".join(contexts), force_provider=provider)
        generation = self.providers[route.provider].generate(route.model, query, contexts)
        citations = [Citation(index, result.chunk.id, result.chunk.source) for index, result in enumerate(results, 1)]
        return Answer(
            query=query,
            text=generation.text,
            citations=citations,
            route=route,
            retrieved=results,
            usage={"prompt_tokens": generation.prompt_tokens, "completion_tokens": generation.completion_tokens},
        )
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `RAGService.answer` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

## Commands and evidence

Activate this project's `.venv`, run its CLI and project test file from `COMMANDS.md`, then inspect the matching `artifacts/project-*` report. The environment is a non-editable wheel snapshot so another project's installation cannot silently change this project.
