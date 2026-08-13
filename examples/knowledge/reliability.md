# Durable AI Workflows

A durable agent workflow writes a checkpoint after every externally visible step. If a worker crashes, the replacement reads the last completed checkpoint and resumes rather than repeating the entire workflow. Idempotency keys prevent an operation such as sending a notification or updating a record from being applied twice during replay.

Retries must be bounded. Exponential backoff with jitter reduces synchronized retry storms, while a dead-letter queue isolates work that repeatedly fails. A timeout limits each attempt, and a circuit breaker stops calls to an unhealthy dependency. Fan-out steps need per-branch state so successful branches remain complete when one branch fails.

Deterministic replay is easiest when orchestration decisions and side effects are separated. The journal records inputs, decisions, outputs, model version, prompt version, tool version, and timestamps. Human approval should be another durable state transition rather than an in-memory pause.

