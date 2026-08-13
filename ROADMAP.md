# AI Infrastructure Lab - Project Roadmap

This repository is a hands-on companion to the Staff/Principal AI Infrastructure resumes. It favors observable, failure-aware implementations over scale theater: every distributed-systems property is demonstrated locally, measured, and documented with its production-scale implications.

## Portfolio roadmap

- [ ] 1. Production RAG platform
- [ ] 2. Durable agent runtime and orchestrator
- [ ] 3. LLM gateway, model router, and cost controller
- [ ] 4. LLM evaluation and release-gating platform
- [ ] 5. High-availability inference serving platform
- [ ] 6. Streaming feature and online-inference pipeline
- [ ] 7. Recommendation system with experimentation
- [ ] 8. Self-healing distributed batch platform
- [ ] 9. Multi-tenant AI platform golden path
- [ ] 10. AI observability, SLO, and incident lab
- [ ] 11. AI security, privacy, and governance gateway
- [ ] 12. Classical ML and computer-vision lifecycle

## Build sequence

The first capstone combines projects 1-4 because together they cover the largest interview surface: retrieval, orchestration, routing, evaluation, reliability, and cost. Each milestone leaves a runnable system.

### Milestone 1 - Local RAG vertical slice

- [x] Ingest and normalize documents
- [x] Token-aware overlapping chunking
- [x] Deterministic local embeddings
- [x] Persistent vector and lexical index
- [x] Hybrid dense/BM25 retrieval
- [x] Context assembly with citations
- [x] Complexity/cost-aware model routing
- [x] Deterministic offline provider
- [x] Ollama provider adapter
- [x] Evaluation metrics and regression gate
- [x] Durable agent checkpoints and retries
- [x] CLI demo, tests, and architecture guide

### Later capstone increments

- [ ] Cross-encoder reranking and pgvector/Qdrant adapters
- [ ] Semantic cache and tenant-aware filters
- [ ] LLM-as-judge and multi-judge consensus
- [ ] MLflow experiment tracking
- [ ] FastAPI/OpenAI-compatible gateway
- [ ] OpenTelemetry, Prometheus, and Grafana
- [ ] Docker Compose and local Kubernetes
- [ ] Load, chaos, security, and rollback exercises

## Resume coverage checklist

Statuses: `[x]` implemented and verified, `[~]` partially demonstrated, `[ ]` planned.

| Resume capability | Project(s) | Status | Evidence |
|---|---:|:---:|---|
| Seven-stage RAG pipeline | 1 | [x] | `ailab/text.py`, `embeddings.py`, `store.py`, `rag.py` |
| LangChain/LlamaIndex integration patterns | 1 | [ ] | framework adapters after core concepts |
| Embeddings and vector retrieval | 1 | [x] | deterministic embedder and persistent SQLite vectors |
| Semantic/hybrid search and reranking | 1 | [~] | BM25+dense fusion done; semantic model and reranker planned |
| Grounding and citations | 1, 4 | [x] | cited offline/Ollama prompts and citation-validity gate |
| Agent orchestration and tool calling | 2 | [ ] | durable state-machine runtime |
| Checkpoints, retry, replay, idempotency | 2, 8 | [~] | checkpoint/retry/resume journal done; tool side effects planned |
| Human-in-the-loop and least privilege | 2, 11 | [ ] | approval and tool-policy gates |
| Model routing and token-cost controls | 3 | [~] | complexity router and usage counts done; budgets/ledger planned |
| Local model serving with Ollama | 3, 5 | [~] | Ollama HTTP adapter done; serving platform planned |
| LLM-as-judge/multi-model verification | 4 | [ ] | evaluation-gate milestone |
| Evaluation datasets and rubric scoring | 4 | [~] | deterministic regression gate done; versioned suite planned |
| A/B tests, hypothesis tests, p-values | 4, 7 | [ ] | experimentation milestone |
| MLflow model/config tracking | 4, 12 | [ ] | LLMOps milestone |
| Dynamic batching and inference serving | 5 | [ ] | serving milestone |
| Backpressure and asynchronous workflows | 5, 6 | [ ] | queue saturation exercises |
| Kafka/Kinesis-style streaming | 6 | [ ] | Redpanda event pipeline |
| Online/offline feature consistency | 6, 7 | [ ] | feature pipeline tests |
| Recommendation algorithms | 7 | [ ] | ranking and experiment service |
| Adaptive master-worker dispatch | 8 | [ ] | workload scheduler |
| Three-pass reconciliation and TTL dedup | 8 | [ ] | recovery exercises |
| Docker, Kubernetes, and autoscaling | 5, 9 | [ ] | kind/k3d deployment |
| IaC, CI/CD, GitOps, golden paths | 9 | [ ] | Terraform and workflow templates |
| Logs, metrics, traces, SLI/SLO/SLA | 10 | [ ] | observability lab |
| OAuth, IAM, privacy, and PII controls | 11 | [ ] | security gateway |
| PyTorch/TensorFlow ML lifecycle | 7, 12 | [ ] | training and serving projects |
| Object detection and tracking | 12 | [ ] | computer-vision track |

## Project completion definition

A checkbox is marked complete only when the implementation, automated tests, runnable exercise, design explanation, failure-mode notes, and interview questions all exist. Merely naming a library does not count as coverage.
