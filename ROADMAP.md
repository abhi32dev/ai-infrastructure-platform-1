# AI Infrastructure Lab - Project Roadmap

This repository is a hands-on companion to the Staff/Principal AI Infrastructure resumes. It favors observable, failure-aware implementations over scale theater: every distributed-systems property is demonstrated locally, measured, and documented with its production-scale implications.

## Portfolio roadmap

- [x] 1. Production RAG platform
- [x] 2. Durable agent runtime and orchestrator
- [x] 3. LLM gateway, model router, and cost controller
- [x] 4. LLM evaluation and release-gating platform
- [x] 5. High-availability inference serving platform
- [x] 6. Streaming feature and online-inference pipeline
- [x] 7. Recommendation system with experimentation
- [x] 8. Self-healing distributed batch platform
- [x] 9. Multi-tenant AI platform golden path
- [x] 10. AI observability, SLO, and incident lab
- [x] 11. AI security, privacy, and governance gateway
- [x] 12. Classical ML and computer-vision lifecycle

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

- [x] Inspectable second-stage reranking and replaceable vector-store boundary
- [x] Semantic cache and tenant-aware filters
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
| LangChain/LlamaIndex integration patterns | 1 | [x] | tested Document/Node adapters into core document contract |
| Embeddings and vector retrieval | 1 | [x] | deterministic embedder and persistent SQLite vectors |
| Semantic/hybrid search and reranking | 1 | [x] | Ollama embeddings, BM25+dense RRF, second-stage reranker |
| Grounding and citations | 1, 4 | [x] | cited offline/Ollama prompts and citation-validity gate |
| Agent orchestration and tool calling | 2 | [x] | typed plans, dependency validation, and tool registry |
| Checkpoints, retry, replay, idempotency | 2, 8 | [x] | durable steps/effects, bounded retry, resume, and dead letters |
| Human-in-the-loop and least privilege | 2, 11 | [x] | durable approval/denial and per-runtime tool allowlist |
| Model routing and token-cost controls | 3 | [x] | constraint router, cost caps, tenant budgets, usage/decision ledgers |
| Local model serving with Ollama | 3, 5 | [~] | Ollama HTTP adapter done; serving platform planned |
| LLM-as-judge/multi-model verification | 4 | [~] | replaceable judge interface and deterministic judge; live model judge optional |
| Evaluation datasets and rubric scoring | 4 | [x] | versioned suites, per-case metrics, persisted release gates |
| A/B tests, hypothesis tests, p-values | 4, 7 | [x] | two-proportion z-test with effects and p-value |
| MLflow model/config tracking | 4, 12 | [ ] | LLMOps milestone |
| Dynamic batching and inference serving | 5 | [x] | bounded live server, batching, deadlines, canary and rollback |
| Backpressure and asynchronous workflows | 5, 6 | [x] | bounded serving queue plus lagged consumer groups |
| Kafka/Kinesis-style streaming | 6 | [x] | persistent partition/offset/group semantics and DLQ |
| Online/offline feature consistency | 6, 7 | [x] | point-in-time snapshots and skew detection |
| Recommendation algorithms | 7 | [x] | popularity/content/collaborative ranking, metrics, experiment service |
| Adaptive master-worker dispatch | 8 | [x] | size-aware batches, bounded parallel workers, resumable manifest |
| Three-pass reconciliation and TTL dedup | 8 | [x] | actual-output diff/retry plus cross-run TTL markers |
| Docker, Kubernetes, and autoscaling | 5, 9 | [~] | serving semantics and generated K8s resources; live kind optional |
| IaC, CI/CD, GitOps, golden paths | 9 | [x] | generated Terraform/K8s/CI/ownership/security/SLO controls |
| Logs, metrics, traces, SLI/SLO/SLA | 10 | [x] | correlated telemetry, budgets, burn alerts, timelines, cost |
| OAuth, IAM, privacy, and PII controls | 11 | [x] | signed identity, RBAC/tenant filters, PII/DLP, audit, retention |
| PyTorch/TensorFlow ML lifecycle | 7, 12 | [~] | full framework-neutral lifecycle; live PyTorch/TensorFlow adapter optional |
| Object detection and tracking | 12 | [x] | runnable synthetic detector, IoU, and stateful centroid tracker |

## Project completion definition

A checkbox is marked complete only when the implementation, automated tests, runnable exercise, design explanation, failure-mode notes, and interview questions all exist. Merely naming a library does not count as coverage.

Portfolio-level items remain unchecked until the complete project—not an early vertical slice—meets that definition. Every verification run writes evidence under `artifacts/verification/`.
