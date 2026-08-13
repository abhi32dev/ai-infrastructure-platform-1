# AI Infrastructure Lab

A local-first, production-minded learning lab for Staff/Principal AI Infrastructure interviews. The repository builds one cohesive platform in vertical slices, with explicit mappings to the accompanying resumes in [ROADMAP.md](ROADMAP.md).

## Current milestone

Milestone 1 builds a compact RAG system with durable local storage, hybrid retrieval, cost-aware model routing, evaluation, and a checkpointed workflow. See [docs/milestone-1.md](docs/milestone-1.md) for the architecture and exercises.

## Design principles

- Runs locally before requiring cloud accounts or paid APIs
- Makes state, metrics, costs, retries, and failures visible
- Keeps provider and storage boundaries replaceable
- Uses deterministic components in tests
- Documents what changes at production scale

## Planned quick start

```bash
python3 -m ailab.cli reset
python3 -m ailab.cli ingest examples/knowledge
python3 -m ailab.cli ask "How does checkpointed recovery work?"
python3 -m pytest
python3 scripts/verify.py
```

The verification command runs happy-path, positive, negative, persistence, and failure-recovery scenarios. It writes reviewable evidence to `artifacts/verification/latest.json` and `latest.txt`.

The commands above will become active as Milestone 1 is implemented.
