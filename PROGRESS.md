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

## 2026-08-13 - Repeatable acceptance verification

Added `scripts/verify.py` so runnable behavior is evidenced rather than assumed. It creates isolated temporary databases and executes:

- Happy path: clean ingestion followed by a cited, grounded query
- Positive: retrieval evaluation gate
- Positive: persistent index close/reopen
- Negative: query against an empty index
- Negative: invalid chunk configuration
- Negative: unavailable Ollama provider
- Failure recovery: injected transient failure, bounded retry, checkpoint, and idempotent resume
- Full automated test suite

Latest result: **8/8 acceptance scenarios passed and 6/6 automated tests passed**. Machine-readable and human-readable evidence is stored under `artifacts/verification/`.

Truthfulness boundary: this evidence applies only to the implemented Milestone 1 vertical slice. The 12 portfolio-level projects remain unchecked until each complete project is built and independently verified.

## 2026-08-13 - Project 2 durable agent runtime

Implemented:

- Typed agent plans, steps, dependencies, arguments, and state references
- Validated tool/function registry
- Least-privilege per-runtime tool allowlist
- SQLite-backed run, step, approval, side-effect, event, and dead-letter journals
- High-risk human approval and denial transitions
- Per-tool timeouts and bounded retry
- Dead-letter isolation after retry exhaustion
- Idempotency-keyed effect reuse
- Resume without repeating completed tool calls
- Inspection CLI and complete command runbook

Verification:

```text
13/13 repository tests passed
5/5 Project 2 acceptance scenarios passed
Manual CLI start -> inspect -> approve -> resume -> repeated resume passed
```

Project 2 is marked complete. Verification evidence is stored in `artifacts/project-2-agent-runtime/`. The documentation explicitly describes the remaining atomicity gap when a real remote service does not honor the runtime's idempotency key.

## 2026-08-13 - Project 3 model gateway and environment isolation

Project 3 implemented a model registry, policy routing, privacy constraints, fallback, circuit breakers, request idempotency, tenant-isolated caching, cost caps, usage accounting, route explanations, and shadow execution.

Verification:

```text
9/9 Project 3 tests passed
6/6 Project 3 acceptance scenarios passed
22/22 repository regression tests passed
```

Added a repository-wide environment standard. Projects 1-3 now have independent `.venv` directories, exact direct dependency pins, full installed freezes, environment manifests, activation documentation, and non-editable wheel snapshots. Isolation verification runs from `/tmp` and confirms every module resolves from its own environment rather than repository source.

## 2026-08-13 - Project 4 evaluation and release gating

Implemented versioned evaluation suites, deterministic and replaceable judge scoring, safety checks, latency/cost measurement, persisted per-case results, configurable quality/safety/latency/cost gates, and two-proportion hypothesis testing. Added Project 4 commands, documentation, isolated environment definition, tests, and acceptance evidence.
