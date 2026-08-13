#!/usr/bin/env python3
"""Generate project-specific production reasoning documents from reviewed specs."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SPECS={
"project-01-rag":("Production RAG","Grounded retrieval must preserve tenant isolation and citation provenance.",["empty corpus and empty query","invalid chunk size/overlap","duplicate ingestion and deterministic IDs","tenant/metadata filter isolation","embedding provider outage","cache hit, miss and TTL expiry","retrieval recall/MRR regression","citation and grounding failure"],"SQLite keeps the lab inspectable; production substitutes a replicated vector/search tier behind the same contract."),
"project-02-agent-runtime":("Durable agent runtime","A side effect may execute only after policy and approval, and resume must never repeat it.",["empty/invalid plans","missing or forward dependencies","tool schema mismatch","allowlist denial","approval, denial and stale resume","timeout and retry exhaustion","checkpoint crash recovery","dead-letter evidence and idempotent replay"],"SQLite transactions model durable orchestration; production uses a workflow engine and transactional outbox."),
"project-03-model-gateway":("Model gateway","Every request must be attributable, policy-routed, budgeted, isolated and safely degradable.",["empty tenant/prompt","invalid quality/privacy policy","negative, NaN and infinite cost caps","cache and request-id idempotency","tenant cache isolation","provider failure and fallback","circuit open/cooldown","shadow failure without billing"],"A local registry makes routing explainable; production adapters add provider rate limits and distributed budget counters."),
"project-04-evaluation":("Evaluation and release gates","No model or prompt change is promoted without versioned evidence and explicit thresholds.",["empty suite","invalid experiment counts","quality/safety regression","latency/cost threshold failure","invalid judge scores","low judge agreement","outlier-resistant consensus","MLflow persistence"],"Deterministic judges make CI stable; model judges are additive and require calibration against human labels."),
"project-05-inference-serving":("Inference serving","Bounded work, deadlines and rollback protect availability under overload or bad releases.",["empty/malformed requests","queue saturation","deadline expiration","dynamic batch boundaries","model output validation","canary failure and fallback","rollback","graceful drain under concurrency"],"Threads model queueing semantics cheaply; production uses async/network servers and accelerator-aware workers."),
"project-06-streaming-features":("Streaming feature platform","Offsets, schemas and event time must yield reproducible online and offline features.",["invalid partition/lateness configuration","null and non-finite events","schema-version DLQ","duplicate publication","independent consumer groups","late events and watermarks","point-in-time correctness","online/offline skew"],"SQLite models Kafka/Kinesis semantics; production swaps in a durable broker and distributed feature store."),
"project-07-recommendations":("Recommendation and experimentation","Ranking must be deterministic, explainable, measurable and safe for cold-start users.",["empty or duplicate catalog IDs","unknown items/events","empty users and invalid k","cold start","consumed-item exclusion","collaborative sparsity","sticky assignment boundaries","experiment readiness/significance"],"Compact ranking signals expose algorithms; production adds approximate candidate retrieval and learned ranking."),
"project-08-batch-platform":("Self-healing batch platform","Item-level durable state and reconciliation prevent silent loss and duplicate work.",["empty manifests","adaptive batch boundaries","transient/permanent worker failure","partial checkpoints","resume","TTL dedup expiry","missing/corrupt output","three-pass reconciliation"],"Local workers demonstrate recovery; production maps the same manifest to distributed compute and object storage."),
"project-09-golden-path":("Platform golden path","Secure defaults must be generated, validated and upgradeable without blocking legitimate escape hatches.",["invalid names and ports","existing target collision","missing generated files","root/writable container","missing limits/probes","wildcard IAM","incomplete CI gates","Compose and Kubernetes validation"],"Generation accelerates adoption; policy validation is still required because templates inevitably drift."),
"project-10-observability":("Observability and cost","Signals must connect user impact, trace context, model usage, cost and actionable SLO policy.",["no-data behavior","success/error spans","p95 boundaries","error-budget exhaustion","multi-window burn alerts","alert cooldown","tenant/model cost attribution","rightsizing at zero/low/high utilization"],"SQLite provides queryable evidence; native OTel/Prometheus adapters preserve the production export contract."),
"project-11-security":("Security and guardrails","Identity, least privilege, tenant isolation, inspection and immutable evidence surround every AI action.",["empty/malformed/expired/tampered tokens","missing claims","RBAC and cross-tenant denial","high-risk approval","prompt-injection variants","PII/secret redaction","quota boundary","audit-chain tampering"],"Rule-based controls are deterministic gates; probabilistic classifiers may augment but never silently replace them."),
"project-12-ml-cv":("ML and computer-vision lifecycle","Data, artifacts, promotion, drift and rollback must remain reproducible and measurable.",["empty/non-finite data","split determinism","training convergence","metric boundaries","artifact schema","promotion and rollback","drift/retraining trigger","detection, IoU and tracking state"],"NumPy exposes lifecycle invariants cheaply; framework execution is added separately in Project 19."),
"project-13-protocols":("MCP and A2A protocols","Versioned protocol state, cancellation, schemas, authorization and telemetry must fail explicitly.",["invalid JSON-RPC/version","pre-initialization calls","unknown methods/resources/prompts/tools","missing arguments","guardrail denial","request cancellation","A2A task failure","terminal-task cancellation"],"In-process transports focus learning on protocol contracts; network bindings are replaceable boundaries."),
"project-14-distributed-training":("PyTorch distributed training","All ranks must see disjoint data, synchronized updates and restartable atomic checkpoints.",["invalid world size/epochs/rate","non-finite hyperparameters","empty data","world larger than samples","unsafe run IDs","partition completeness","worker failure checkpoint","deterministic resume/checksum"],"CPU simulation verifies coordination; the isolated PyTorch dependency supports extending the same tests to DDP/FSDP."),
"project-15-optimized-inference":("Optimized LLM inference","Admission, cache capacity, batching, priorities and deadlines bound latency and memory.",["empty IDs/prompts","token-limit boundaries","expired admission","KV negative/exhausted capacity","duplicate request IDs","priority ordering","batch limits","prefix and speculative-cache behavior"],"A deterministic token engine exposes vLLM/Triton concepts without requiring unsupported macOS GPU runtimes."),
"project-16-gpu-platform":("Kubernetes GPU platform","Scheduling must respect GPU type, capacity, health, tenant quota and interruption recovery.",["invalid/duplicate nodes","invalid workloads","GPU-type mismatch","insufficient capacity","tenant quota","idempotent schedule","completion reclamation","spot drain and autoscale plan"],"The scheduler is executable without a GPU; Kubernetes client/YAML dependencies map decisions to real resources."),
"project-17-lakehouse-features":("Lakehouse and feature platform","Schema contracts, event-time commits and point-in-time joins prevent leakage and skew.",["missing IDs","NaN/Inf values","unsupported schema DLQ","duplicate ingest","future watermark exclusion","idempotent compaction","point-in-time leakage","online materialization and quality"],"In-memory semantics keep tests fast; DuckDB/PyArrow provide a path to actual columnar persistence."),
"project-18-distributed-orchestration":("Distributed ML orchestration","DAG validity, placement, retry and object-store bounds make distributed work predictable.",["invalid cluster capacity","empty/duplicate tasks","forward dependencies","invalid resources","retry success/exhaustion","unschedulable placement","object-store exhaustion","actor state and crash"],"The deterministic orchestrator explains Ray primitives; the isolated Ray dependency enables real local actors."),
"project-19-multi-framework":("TensorFlow, Keras and JAX lifecycle","Framework changes must preserve artifact schemas, numerical parity and inference contracts.",["misaligned/short/constant arrays","NaN/Inf training data","non-finite inference","artifact round trip","missing/corrupt/versioned artifact","parity success/failure","invalid tolerance","framework inventory"],"A portable linear artifact makes parity exact; real TensorFlow/Keras/JAX dependencies are isolated for extensions."),
"project-20-cloud-control-plane":("Multi-cloud ML control plane","Plans must enforce network, encryption, budget, integrity, idempotency, drift and failover policy.",["invalid identity/provider/region","zero replicas/budget","public/unencrypted policy denial","unknown instance","provider matrix","idempotent apply","tampered plan","drift, reconciliation and failover"],"Local planning avoids cloud cost; real AWS/GCP/Azure SDKs remain isolated adapters behind the control plane."),
}
TEMPLATE="""# Production reasoning — {title}

## Why this project exists

{invariant} This project is deliberately small enough to execute locally but preserves the decision points that dominate production incidents and staff-level design reviews.

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

{scenarios}

Tests use deterministic clocks, seeded data, temporary directories and local stores where possible. This avoids flaky CI. Live cloud/model/GPU tests belong in a separate opt-in suite because availability, cost and credentials would otherwise make the default suite non-reproducible.

## Design choice and trade-off

{tradeoff}

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

- Which invariant is financially or operationally most expensive to violate?
- Where is the linearization point for an idempotent mutation?
- Which state is authoritative during disagreement, and how is reconciliation bounded?
- What does graceful degradation preserve, and what must fail closed?
- Which metrics detect correctness loss before customers report it?
- What changes at 10× traffic, 100× data, multiple regions or adversarial tenants?
- Which decisions belong in the platform versus the application team, and why?

## Commands and evidence

Activate this project's `.venv`, run its CLI and project test file from `COMMANDS.md`, then inspect the matching `artifacts/project-*` report. The environment is a non-editable wheel snapshot so another project's installation cannot silently change this project.
"""
def main():
 for directory,(title,invariant,scenarios,tradeoff) in SPECS.items():
  rendered=TEMPLATE.format(title=title,invariant=invariant,scenarios="\n".join(f"- {item}" for item in scenarios),tradeoff=tradeoff)
  path=ROOT/"projects"/directory/"PROD.md";path.parent.mkdir(parents=True,exist_ok=True);path.write_text(rendered)
 print(f"Generated {len(SPECS)} production documents")
if __name__=="__main__":main()
