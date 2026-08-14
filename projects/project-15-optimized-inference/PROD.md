# Production reasoning — Optimized LLM inference

## Why this project exists

Admission, cache capacity, batching, priorities and deadlines bound latency and memory. This project is deliberately small enough to execute locally but preserves the decision points that dominate production incidents and staff-level design reviews.

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

- empty IDs/prompts
- token-limit boundaries
- expired admission
- KV negative/exhausted capacity
- duplicate request IDs
- priority ordering
- batch limits
- prefix and speculative-cache behavior

Tests use deterministic clocks, seeded data, temporary directories and local stores where possible. This avoids flaky CI. Live cloud/model/GPU tests belong in a separate opt-in suite because availability, cost and credentials would otherwise make the default suite non-reproducible.

## Design choice and trade-off

A deterministic token engine exposes vLLM/Triton concepts without requiring unsupported macOS GPU runtimes.

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

**Staff/Principal answer.** KV-cache overcommit is the costliest operational violation because it can crash a shared worker and violate every tenant's latency SLO. Admission must jointly enforce memory, deadlines, priority, and duplicate identity.

**Implementation evidence.** [`ailab/llm_inference_optimized.py · KVCache.reserve`](../../ailab/llm_inference_optimized.py) is the concrete control point used by this project:

```python
def reserve(self,key:str,tokens:int):
  if tokens<0:raise ValueError("tokens cannot be negative")
  if key in self.entries:return False
  if self.used+tokens>self.capacity:raise CacheExhausted("KV cache capacity exceeded")
  self.entries[key]=tokens;self.used+=tokens;return True
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `KVCache.reserve` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 2. Where is the linearization point for an idempotent mutation?

**Staff/Principal answer.** A request linearizes at terminal generation completion/error and KV release; admission only reserves capacity. Duplicate request IDs must resolve to the same logical request rather than consume a second cache allocation.

**Implementation evidence.** [`ailab/llm_inference_optimized.py · ContinuousBatchEngine.step`](../../ailab/llm_inference_optimized.py) is the concrete control point used by this project:

```python
def step(self)->list[dict]:
  batch=self.queue[:self.max_batch];self.queue=self.queue[self.max_batch:];results=[]
  for request in batch:
   if request.deadline is not None and request.deadline<=time.time():self.completed[request.request_id]={"status":"expired"};continue
   prefix=hashlib.sha256(request.prompt[:64].encode()).hexdigest();hit=prefix in self.prefix_cache;tokens=min(request.max_tokens,max(1,len(request.prompt.split())//2));self.cache.reserve(request.request_id,tokens)
   result={"request_id":request.request_id,"status":"completed","tokens":tokens,"prefix_cache_hit":hit,"quantized_bytes":tokens,"text":f"generated:{request.prompt[:24]}"};self.prefix_cache[prefix]=True;self.completed[request.request_id]=result;results.append(result);self.cache.release(request.request_id)
  return results
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `ContinuousBatchEngine.step` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 3. Which state is authoritative during disagreement, and how is reconciliation bounded?

**Staff/Principal answer.** The active-request table and KV allocation ledger are authoritative for worker capacity; prefix cache is derived and evictable. Reconciliation is bounded to active request IDs and releases orphaned allocations after worker recovery.

**Implementation evidence.** [`ailab/llm_inference_optimized.py · ContinuousBatchEngine.submit`](../../ailab/llm_inference_optimized.py) is the concrete control point used by this project:

```python
def submit(self,request:GenerationRequest):
  request.validate()
  if request.request_id in self.completed or any(x.request_id==request.request_id for x in self.queue):return "duplicate"
  if request.deadline is not None and request.deadline<=time.time():raise AdmissionRejected("deadline already expired")
  self.queue.append(request);self.queue.sort(key=lambda x:(-x.priority,x.request_id));return "queued"
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `ContinuousBatchEngine.submit` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 4. What does graceful degradation preserve, and what must fail closed?

**Staff/Principal answer.** Degrade by evicting reusable prefixes, reducing batch size, disabling speculative decoding, or rejecting impossible deadlines. Tenant isolation, memory capacity, request validation, and deadline admission fail closed.

**Implementation evidence.** [`ailab/llm_inference_optimized.py · ContinuousBatchEngine.submit`](../../ailab/llm_inference_optimized.py) is the concrete control point used by this project:

```python
def submit(self,request:GenerationRequest):
  request.validate()
  if request.request_id in self.completed or any(x.request_id==request.request_id for x in self.queue):return "duplicate"
  if request.deadline is not None and request.deadline<=time.time():raise AdmissionRejected("deadline already expired")
  self.queue.append(request);self.queue.sort(key=lambda x:(-x.priority,x.request_id));return "queued"
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `ContinuousBatchEngine.submit` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 5. Which metrics detect correctness loss before customers report it?

**Staff/Principal answer.** Track admission rejection reason, queue wait, time-to-first-token, inter-token latency, tokens/sec, batch occupancy, KV bytes/utilization/evictions, prefix hit rate, speculative acceptance, deadline misses, and fairness by priority/tenant.

**Implementation evidence.** [`ailab/llm_inference_optimized.py · ContinuousBatchEngine.step`](../../ailab/llm_inference_optimized.py) is the concrete control point used by this project:

```python
def step(self)->list[dict]:
  batch=self.queue[:self.max_batch];self.queue=self.queue[self.max_batch:];results=[]
  for request in batch:
   if request.deadline is not None and request.deadline<=time.time():self.completed[request.request_id]={"status":"expired"};continue
   prefix=hashlib.sha256(request.prompt[:64].encode()).hexdigest();hit=prefix in self.prefix_cache;tokens=min(request.max_tokens,max(1,len(request.prompt.split())//2));self.cache.reserve(request.request_id,tokens)
   result={"request_id":request.request_id,"status":"completed","tokens":tokens,"prefix_cache_hit":hit,"quantized_bytes":tokens,"text":f"generated:{request.prompt[:24]}"};self.prefix_cache[prefix]=True;self.completed[request.request_id]=result;results.append(result);self.cache.release(request.request_id)
  return results
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `ContinuousBatchEngine.step` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 6. What changes at 10× traffic, 100× data, multiple regions or adversarial tenants?

**Staff/Principal answer.** Shard models across accelerator workers, use paged KV, disaggregated prefill/decode, continuous admission, and model-aware routing. Multi-region needs weight/cache locality; adversarial tenants require token/concurrency caps and prefix-cache isolation.

**Implementation evidence.** [`ailab/llm_inference_optimized.py · KVCache.reserve`](../../ailab/llm_inference_optimized.py) is the concrete control point used by this project:

```python
def reserve(self,key:str,tokens:int):
  if tokens<0:raise ValueError("tokens cannot be negative")
  if key in self.entries:return False
  if self.used+tokens>self.capacity:raise CacheExhausted("KV cache capacity exceeded")
  self.entries[key]=tokens;self.used+=tokens;return True
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `KVCache.reserve` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 7. Which decisions belong in the platform versus the application team, and why?

**Staff/Principal answer.** The platform owns runtime kernels, memory/admission scheduling, batching, fairness, model loading, telemetry, and quotas. Application teams own model choice, sampling policy, prompt limits, quality validation, and acceptable deadline/fallback behavior.

**Implementation evidence.** [`ailab/llm_inference_optimized.py · GenerationRequest.validate`](../../ailab/llm_inference_optimized.py) is the concrete control point used by this project:

```python
def validate(self):
  if not self.request_id.strip():raise ValueError("request_id is required")
  if not self.prompt.strip():raise ValueError("prompt is required")
  if self.max_tokens<1:raise ValueError("max_tokens must be positive")
  if self.max_tokens>4096:raise ValueError("max_tokens exceeds policy")
  if self.deadline is not None and not math.isfinite(self.deadline):raise ValueError("deadline must be finite")
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `GenerationRequest.validate` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

## Commands and evidence

Activate this project's `.venv`, run its CLI and project test file from `COMMANDS.md`, then inspect the matching `artifacts/project-*` report. The environment is a non-editable wheel snapshot so another project's installation cannot silently change this project.
