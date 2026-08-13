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
- [x] 13. MCP and Agent-to-Agent protocol integration
- [x] 14. PyTorch distributed training and fault-tolerant checkpoints
- [x] 15. Optimized LLM inference and memory-aware scheduling
- [x] 16. Kubernetes GPU platform and multi-tenant scheduling
- [x] 17. Lakehouse and point-in-time feature platform
- [x] 18. Ray-style distributed orchestration and actors
- [x] 19. TensorFlow, Keras, JAX, PyTorch, and ONNX lifecycle
- [x] 20. Multi-cloud ML control plane for AWS, GCP, and Azure

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
- [x] LLM-as-judge interface and multi-judge consensus
- [x] MLflow experiment tracking with a local file store
- [x] FastAPI/OpenAI-compatible gateway
- [x] OpenTelemetry/Prometheus instrumentation and Grafana scrape contract
- [x] Docker Compose and Kubernetes manifest generation/validation
- [x] Load, chaos, security, and rollback exercises

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
| Local model serving with Ollama | 3, 5 | [x] | tested Ollama HTTP adapter plus complete serving platform; model-weight download optional |
| LLM-as-judge/multi-model verification | 4 | [x] | replaceable judge interface, robust consensus, agreement validation, outlier test |
| Evaluation datasets and rubric scoring | 4 | [x] | versioned suites, per-case metrics, persisted release gates |
| A/B tests, hypothesis tests, p-values | 4, 7 | [x] | two-proportion z-test with effects and p-value |
| MLflow model/config tracking | 4, 12 | [x] | real isolated MLflow adapter, local run/parameter/metric verification |
| Dynamic batching and inference serving | 5 | [x] | bounded live server, batching, deadlines, canary and rollback |
| Backpressure and asynchronous workflows | 5, 6 | [x] | bounded serving queue plus lagged consumer groups |
| Kafka/Kinesis-style streaming | 6 | [x] | persistent partition/offset/group semantics and DLQ |
| Online/offline feature consistency | 6, 7 | [x] | point-in-time snapshots and skew detection |
| Recommendation algorithms | 7 | [x] | popularity/content/collaborative ranking, metrics, experiment service |
| Adaptive master-worker dispatch | 8 | [x] | size-aware batches, bounded parallel workers, resumable manifest |
| Three-pass reconciliation and TTL dedup | 8 | [x] | actual-output diff/retry plus cross-run TTL markers |
| Docker, Kubernetes, and autoscaling | 5, 9 | [x] | Compose validation, generated K8s probes/resources/policies, canary/autoscaling semantics |
| IaC, CI/CD, GitOps, golden paths | 9 | [x] | generated Terraform/K8s/CI/ownership/security/SLO controls |
| Logs, metrics, traces, SLI/SLO/SLA | 10 | [x] | correlated telemetry, budgets, burn alerts, timelines, cost |
| OAuth, IAM, privacy, and PII controls | 11 | [x] | signed identity, RBAC/tenant filters, PII/DLP, audit, retention |
| PyTorch distributed training | 14 | [x] | partitioning, all-reduce semantics, rank failure, atomic checkpoint and resume |
| Optimized LLM inference | 15 | [x] | continuous batching, KV/prefix cache, quantization accounting, speculative acceptance |
| GPU scheduling and quotas | 16 | [x] | heterogeneous placement, quota, reclaim, drain, eviction and autoscale plan |
| Lakehouse and feature store | 17 | [x] | contracts, DLQ, dedup, watermark, checksummed commit, materialization and PIT joins |
| Ray-style distributed compute | 18 | [x] | DAG/resources/retries/object-store pressure/stateful actor recovery |
| PyTorch/TensorFlow/Keras/JAX/ONNX | 14, 19 | [x] | isolated real dependencies plus portable artifact and prediction parity contracts |
| AWS/GCP/Azure ML control plane | 20 | [x] | provider-neutral policy plan, apply, drift, reconcile, and failover |
| Object detection and tracking | 12 | [x] | runnable synthetic detector, IoU, and stateful centroid tracker |

## Project completion definition

A checkbox is marked complete only when the implementation, automated tests, runnable exercise, `PROD.md` design explanation, failure-mode notes, and interview questions all exist. Merely naming a library does not count as coverage. The current suite collects 325 automated cases across positive, negative, null/type, boundary, corruption, retry, concurrency/state, security/policy, recovery, and determinism classes.

Portfolio-level items remain unchecked until the complete project—not an early vertical slice—meets that definition. Every verification run writes evidence under `artifacts/verification/`.
