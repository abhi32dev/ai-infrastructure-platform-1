# AI Infrastructure Lab

A local-first, production-minded learning lab for Staff/Principal AI Infrastructure interviews. The repository builds one cohesive platform in vertical slices, with explicit mappings in [ROADMAP.md](ROADMAP.md) and cross-cutting controls in [docs/staff-level-controls.md](docs/staff-level-controls.md).

## Implemented projects

- Project 1 foundation: compact RAG system with durable local storage, hybrid retrieval, routing, evaluation, and citations. See [docs/milestone-1.md](docs/milestone-1.md).
- Project 2: durable agent runtime with typed tools, policy gates, human approval, bounded retry, idempotent resume, event history, and dead letters. See [docs/project-2-agent-runtime.md](docs/project-2-agent-runtime.md).

All 13 projects meet the repository completion definition. Optional live integrations that require model downloads or heavyweight ML frameworks remain explicitly identified in the roadmap.

## Design principles

- Runs locally before requiring cloud accounts or paid APIs
- Makes state, metrics, costs, retries, and failures visible
- Keeps provider and storage boundaries replaceable
- Uses deterministic components in tests
- Documents what changes at production scale

## Quick start

```bash
python3 -m ailab.cli reset
python3 -m ailab.cli ingest examples/knowledge
python3 -m ailab.cli ask "How does checkpointed recovery work?"
python3 -m pytest
python3 scripts/verify.py
python3 scripts/verify_agent_runtime.py
```

The verification command runs happy-path, positive, negative, persistence, and failure-recovery scenarios. It writes reviewable evidence to `artifacts/verification/latest.json` and `latest.txt`.

The commands above are active and verified; see [COMMANDS.md](COMMANDS.md) for every project environment and exercise.
