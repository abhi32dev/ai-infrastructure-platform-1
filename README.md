# AI Infrastructure Lab

A local-first, production-minded learning lab for Staff/Principal AI Infrastructure interviews. The repository builds one cohesive platform in vertical slices, with explicit mappings in [ROADMAP.md](ROADMAP.md) and cross-cutting controls in [docs/staff-level-controls.md](docs/staff-level-controls.md).

**Project site:** [abhi32dev.github.io/ai-infrastructure-platform-1](https://abhi32dev.github.io/ai-infrastructure-platform-1/)

**Start with the interactive flow atlas:** [execution maps for all 20 projects](https://abhi32dev.github.io/ai-infrastructure-platform-1/flowcharts.html). It contains 120 source-linked stages with explicit continuation, rejection, retry, fallback, recovery, and durable-state paths.

## Implemented projects

| # | Project | Main concepts |
|---:|---|---|
| 1 | [Production RAG](projects/project-01-rag/README.md) | hybrid retrieval, RRF, reranking, citations, semantic cache, tenant isolation |
| 2 | [Durable agent runtime](projects/project-02-agent-runtime/README.md) | typed tools, approvals, checkpoints, retries, idempotency, DLQ |
| 3 | [Model gateway](projects/project-03-model-gateway/README.md) | OpenAI-compatible API, routing, budgets, cache, fallback, circuits, shadowing |
| 4 | [Evaluation platform](projects/project-04-evaluation/README.md) | versioned suites, multi-judge consensus, release gates, MLflow, statistics |
| 5 | [Inference serving](projects/project-05-inference-serving/README.md) | dynamic batching, backpressure, deadlines, canaries, rollback |
| 6 | [Streaming features](projects/project-06-streaming-features/README.md) | partitions, offsets, consumer groups, DLQ, late events, point-in-time features |
| 7 | [Recommendations](projects/project-07-recommendations/README.md) | collaborative/content ranking, cold start, offline metrics, A/B experiments |
| 8 | [Self-healing batch](projects/project-08-batch-platform/README.md) | adaptive dispatch, checkpoints, TTL deduplication, reconciliation |
| 9 | [Platform golden path](projects/project-09-golden-path/README.md) | service scaffolding, Docker Compose, Kubernetes, Terraform, CI and policy |
| 10 | [Observability and cost](projects/project-10-observability/README.md) | OpenTelemetry, Prometheus, SLOs, burn rates, cost attribution, rightsizing |
| 11 | [Security and guardrails](projects/project-11-security/README.md) | identity, RBAC, PII/DLP, prompt injection, quotas, tamper-evident audit |
| 12 | [ML/CV lifecycle](projects/project-12-ml-cv/README.md) | training, registry, promotion, drift, rollback, detection and tracking |
| 13 | [MCP and A2A protocols](projects/project-13-protocols/README.md) | discovery, capabilities, tools/resources/prompts, tasks, artifacts, cancellation |
| 14 | [Distributed training](projects/project-14-distributed-training/README.md) | PyTorch, data parallelism, all-reduce, failure, checkpoint and resume |
| 15 | [Optimized LLM inference](projects/project-15-optimized-inference/README.md) | continuous batching, KV/prefix cache, quantization, speculative decoding |
| 16 | [Kubernetes GPU platform](projects/project-16-gpu-platform/README.md) | heterogeneous GPUs, placement, tenant quotas, drain, eviction, autoscaling |
| 17 | [Lakehouse feature platform](projects/project-17-lakehouse-features/README.md) | contracts, DLQ, watermarks, commits, materialization, point-in-time joins |
| 18 | [Distributed orchestration](projects/project-18-distributed-orchestration/README.md) | Ray-style DAGs, resources, retries, object pressure, stateful actors |
| 19 | [Multi-framework lifecycle](projects/project-19-multi-framework/README.md) | TensorFlow, Keras, JAX, PyTorch, ONNX, artifact and prediction parity |
| 20 | [Multi-cloud control plane](projects/project-20-cloud-control-plane/README.md) | AWS, GCP, Azure, policy, budgets, drift, reconciliation and failover |

All 20 projects meet the repository completion definition. Every project contains a detailed `PROD.md`; heavyweight frameworks are installed in project-specific environments so their dependencies do not interfere.

## Design principles

- Runs locally before requiring cloud accounts or paid APIs
- Makes state, metrics, costs, retries, and failures visible
- Keeps provider and storage boundaries replaceable
- Uses deterministic components in tests
- Documents what changes at production scale

## Quick start

```bash
git clone https://github.com/abhi32dev/ai-infrastructure-platform-1.git
cd ai-infrastructure-platform-1
python3 scripts/verify_all.py
```

The portfolio command runs every project verifier, dependency-specific adapter tests, the 325-case test suite, and all 20 environment-isolation checks. The latest auditable result is stored in [artifacts/completion-audit/latest.json](artifacts/completion-audit/latest.json).

Each project owns a pinned `requirements-dev.txt`, an ignored `.venv`, a frozen dependency inventory, and a non-editable wheel manifest. See [COMMANDS.md](COMMANDS.md) for activation, demos, tests, failure exercises, and artifact inspection.

## Repository map

- `ailab/`: reusable implementations
- `projects/`: project-specific environments and learning guides
- `tests/`: unit, integration, protocol, guardrail, and failure-path tests
- `scripts/`: demos, environment bootstrap, and verification entry points
- `docs/`: architecture and staff-level reasoning guides
- `config/`: machine-readable cross-project controls
- `artifacts/`: small, committed verification evidence; generated databases and environments are ignored
