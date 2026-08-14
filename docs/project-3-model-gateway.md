# Project 3 - LLM Gateway, Model Router, and Cost Controller

## Implemented behavior

- Model registry with provider, context, cost, quality, and latency metadata
- Complexity-, quality-, latency-, privacy-, and context-aware routing
- Ordered fallback chain
- Per-model circuit breaker with cooldown
- Per-request cost cap and tenant daily budget
- Exact response cache isolated by tenant
- Idempotent request IDs
- Token and dollar usage ledger
- Persisted route decisions and explanations
- Shadow-model execution recorded separately from billed traffic
- Deterministic local providers for repeatable offline testing

## Request flow

```text
request -> idempotency/cache -> constraints -> route candidates
        -> budget precheck -> primary provider
        -> bounded fallback on provider failure
        -> usage + decision + cache ledger
        -> optional shadow request
```

## Exercises

1. Send balanced and high-quality versions of the same idea and compare models.
2. Force `privacy=local` and verify no hosted model appears in the decision.
3. Inject two failures per model and inspect the open circuit records.
4. Repeat an identical tenant request and observe a zero-cost cache hit.
5. Repeat it under another tenant and verify cache isolation.
6. Set a request cost below the expected output cost and observe rejection.
7. Run a shadow candidate and confirm it does not add a billed usage row.

## Interview questions

### 1. Which routing signals are known before inference, and which require feedback?

**Answer.** Before execution the gateway knows tenant, privacy requirement, prompt/context size, requested quality, deadline, request cost cap, model price, configured context limit, and circuit health. Actual output tokens, latency, provider errors, realized quality, and safety outcomes arrive afterward and update routing policy. Do not treat predicted quality as observed truth. `ModelGateway._route` performs the pre-inference eligibility/ranking boundary; `_record_success`, `_record_failure`, and shadow evaluation supply feedback.

```python
# ailab/model_gateway.py · ModelGateway._route
tokens = len(tokenize(request.prompt))
candidates = [model for model in self.models.values()
    if model.max_context >= tokens
    and (request.privacy != "local" or model.provider == "local")
    and self._healthy(model.name)]
if request.quality == "high" or complexity:
    candidates.sort(key=lambda model: (-model.quality_tier, model.input_cost_per_million))
```

### 2. How should a gateway estimate output cost before generation?

**Answer.** Tokenize or conservatively estimate input tokens, predict an output-token distribution by task/model, and reserve against a high percentile rather than the mean. Apply configured per-token prices and include tool, retrieval, and retry budgets. The lab currently prechecks estimated input spend and checks the request cap against actual cost afterward; production should reserve estimated output spend before the provider call as well.

```python
# ailab/model_gateway.py · ModelGateway._assert_budget
estimated_tokens = len(tokenize(request.prompt))
estimate = estimated_tokens * model.input_cost_per_million / 1_000_000
if self.spent(request.tenant) + estimate > self.tenant_daily_budget:
    raise BudgetExceeded(f"tenant {request.tenant} daily budget would be exceeded")
```

### 3. Why must request retries preserve an idempotency key?

**Answer.** A timeout does not reveal whether the provider completed and charged the request. A new identity can create duplicate output, spend, and side effects. Preserve a tenant-scoped request ID through client, gateway, and provider; return the committed response when available and reconcile ambiguous provider usage. The key must include tenant/policy scope so one tenant cannot observe another tenant's response.

```python
# ailab/model_gateway.py · ModelGateway._complete
request.validate()
request_id = request.request_id or uuid.uuid4().hex
prior = self.connection.execute(
    "SELECT u.*, d.reason FROM usage u JOIN decisions d USING(request_id) WHERE request_id=?",
    (request_id,),
).fetchone()
if prior:
    return GatewayResponse(request_id, prior["model"], prior["provider"],
        prior["response"], prior["cost"], True, prior["reason"], 0)
```

### 4. When should provider failures trigger fallback versus immediate failure?

**Answer.** Fallback only for retryable availability/timeout/rate-limit errors when another model still satisfies privacy, quality, context, deadline, and cost constraints. Fail immediately for authentication/configuration errors, invalid input, policy denial, budget exhaustion, non-retryable safety outcomes, or when fallback would violate data residency. `_complete` iterates only policy-eligible routes; it must not convert a fail-closed control into availability.

```python
# ailab/model_gateway.py · ModelGateway._complete
for fallback_count, model in enumerate(candidates):
    try:
        result = self.providers.call(model.provider, model.name, request.prompt)
        cost = (result.input_tokens * model.input_cost_per_million
                + result.output_tokens * model.output_cost_per_million) / 1_000_000
        self._record_success(request_id, request, model, result, cost, reason,
                             candidates, fallback_count, cache_key)
        return GatewayResponse(request_id, model.name, model.provider,
                               result.text, cost, False, reason, fallback_count)
    except BudgetExceeded:
        raise
    except Exception as exc:
        errors.append(f"{model.name}: {exc}")
        self._record_failure(model.name)
raise NoHealthyModel("all fallback models failed: " + "; ".join(errors))
```

### 5. How do circuit breakers interact with regional or model-wide outages?

**Answer.** Breakers need scoped identities: provider/model/region/credential pool, plus a carefully chosen global signal. Opening one regional breaker should redirect only to policy-approved regions; a model-wide error may open all model endpoints. Half-open probes must be rate-limited and excluded from normal traffic until healthy. Distributed breaker state can be eventually consistent, but every worker still needs local bulkheads so stale global state cannot overload a dependency.

```python
# ailab/model_gateway.py · ModelGateway._healthy
def _healthy(self, model: str) -> bool:
    row = self.connection.execute("SELECT * FROM health WHERE model=?", (model,)).fetchone()
    if not row or row["failures"] < self.failure_threshold:
        return True
    return row["opened_at"] is not None and time.time() - row["opened_at"] >= self.cooldown_seconds
```

### 6. What cache keys prevent cross-tenant or policy leakage?

**Answer.** Include tenant/security principal scope, normalized request, model and model version, prompt/template version, system policy, privacy/data-residency class, tool/retrieval context version, generation parameters, and safety policy. Hash sensitive material but do not remove the dimensions. Cache authorization must be rechecked on every hit, and private/local responses must never satisfy a public/shared key.

```text
sha256(tenant | principal-scope | model-version | prompt-version |
       privacy-policy | retrieval-version | generation-parameters |
       normalized-input)
```

The local gateway's tenant-aware request/cache boundary is `ModelGateway.complete`; production replaces the local store while retaining every policy dimension.

### 7. Why is shadow traffic operationally safer than a canary but less conclusive?

**Answer.** A shadow receives copied input but its output is not served, so wrong answers do not directly harm users and shadow failure cannot break the primary response. It is less conclusive because it does not measure user behavior, downstream side effects, interactive latency, or production feedback loops; duplicated provider calls also increase cost and privacy exposure. Shadow inputs must obey consent, residency, and redaction policy.

```python
# ailab/model_gateway.py · ModelGateway._shadow
try:
    self.providers.call(model.provider, model.name, prompt)
    status, error = "completed", None
except Exception as exc:
    status, error = "failed", str(exc)
latency = (time.perf_counter() - started) * 1000
self.connection.execute("INSERT INTO shadows VALUES (?,?,?,?,?,?)",
    (request_id, model.name, status, latency, error, time.time()))
self.connection.commit()
```

### 8. How would you enforce concurrency and token-rate quotas atomically?

**Answer.** Use a strongly consistent tenant bucket with two dimensions: active leases for concurrency and a token bucket/sliding window for rate. Admission atomically checks/refills/reserves both; completion releases the lease and reconciles estimated versus actual tokens. Leases expire to recover crashed workers, but fencing tokens prevent a late worker from double-releasing. Redis Lua, a transactional database row, or a dedicated quota service can supply the atomic operation.

```text
ADMIT(tenant, estimated_tokens):
  refill token bucket from monotonic time
  if active >= concurrency_limit or tokens < estimate: reject
  active += 1; tokens -= estimate; create expiring lease
  return lease_id, fencing_token
```

For the separate seven-question production architecture review, see [`projects/project-03-model-gateway/PROD.md`](../projects/project-03-model-gateway/PROD.md).

## Local versus production

SQLite makes every decision inspectable on one machine. A production gateway would use a transactional shared store for quotas, distributed rate limiting, async streaming transport, provider-specific cancellation, and regional health aggregation. The routing and accounting contracts remain the same; their coordination mechanism changes.
