# Production reasoning — Model gateway

## Why this project exists

Every request must be attributable, policy-routed, budgeted, isolated and safely degradable. This project is deliberately small enough to execute locally but preserves the decision points that dominate production incidents and staff-level design reviews.

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

- empty tenant/prompt
- invalid quality/privacy policy
- negative, NaN and infinite cost caps
- cache and request-id idempotency
- tenant cache isolation
- provider failure and fallback
- circuit open/cooldown
- shadow failure without billing

Tests use deterministic clocks, seeded data, temporary directories and local stores where possible. This avoids flaky CI. Live cloud/model/GPU tests belong in a separate opt-in suite because availability, cost and credentials would otherwise make the default suite non-reproducible.

## Design choice and trade-off

A local registry makes routing explainable; production adapters add provider rate limits and distributed budget counters.

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

**Staff/Principal answer.** Cross-tenant budget/cache leakage and privacy misrouting are more expensive than choosing a suboptimal model. Routing constraints and tenant identity must be enforced before cache lookup and provider execution so cost or latency optimization cannot bypass policy.

**Implementation evidence.** [`ailab/model_gateway.py · ModelGateway.complete`](../../ailab/model_gateway.py) is the concrete control point used by this project:

```python
def complete(self, request: GatewayRequest, shadow_model: str | None = None) -> GatewayResponse:
        with self._lock:
            return self._complete(request, shadow_model)
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `ModelGateway.complete` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 2. Where is the linearization point for an idempotent mutation?

**Staff/Principal answer.** For an idempotent request, the linearization point is the committed response/usage record keyed by tenant and request identity. Provider completion alone is not sufficient because a crash before ledger persistence remains ambiguous and requires provider-side idempotency or reconciliation.

**Implementation evidence.** [`ailab/model_gateway.py · ModelGateway._record_success`](../../ailab/model_gateway.py) is the concrete control point used by this project:

```python
def _record_success(self, request_id: str, request: GatewayRequest, model: ModelConfig, result: ProviderResult, cost: float, reason: str, candidates: list[ModelConfig], fallback_count: int, cache_key: str) -> None:
        now = time.time()
        self.connection.execute("INSERT INTO usage VALUES (?,?,?,?,?,?,?,?,?)", (request_id, request.tenant, model.name, model.provider, result.text, result.input_tokens, result.output_tokens, cost, now))
        self.connection.execute("INSERT INTO decisions VALUES (?,?,?,?,?,?,?)", (request_id, request.tenant, model.name, reason, json.dumps([item.name for item in candidates]), fallback_count, now))
        self.connection.execute("INSERT OR REPLACE INTO cache VALUES (?,?,?,?,?,?)", (cache_key, json.dumps({"text": result.text}), model.name, model.provider, cost, now))
        self.connection.execute("INSERT OR REPLACE INTO health VALUES (?,0,NULL)", (model.name,))
        self.connection.commit()
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `ModelGateway._record_success` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 3. Which state is authoritative during disagreement, and how is reconciliation bounded?

**Staff/Principal answer.** The usage and routing ledger is authoritative for charged spend; cache and in-memory circuit state are derived accelerators. Reconciliation is bounded by request IDs and provider usage records, never by estimating from aggregate invoices alone.

**Implementation evidence.** [`ailab/model_gateway.py · ModelGateway.spent`](../../ailab/model_gateway.py) is the concrete control point used by this project:

```python
def spent(self, tenant: str) -> float:
        cutoff = time.time() - 86400
        return float(self.connection.execute("SELECT COALESCE(SUM(cost),0) FROM usage WHERE tenant=? AND created_at>=?", (tenant, cutoff)).fetchone()[0])
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `ModelGateway.spent` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 4. What does graceful degradation preserve, and what must fail closed?

**Staff/Principal answer.** Degrade to the next policy-eligible healthy model, a tenant-safe cache hit, or a controlled local model. Privacy restrictions, tenant budgets, input validation, and isolation fail closed even if that means rejecting the request.

**Implementation evidence.** [`ailab/model_gateway.py · ModelGateway._complete`](../../ailab/model_gateway.py) is the concrete control point used by this project:

```python
def _complete(self, request: GatewayRequest, shadow_model: str | None = None) -> GatewayResponse:
        request.validate()
        request_id = request.request_id or uuid.uuid4().hex
        prior = self.connection.execute("SELECT u.*, d.reason FROM usage u JOIN decisions d USING(request_id) WHERE request_id=?", (request_id,)).fetchone()
        if prior:
            return GatewayResponse(request_id, prior["model"], prior["provider"], prior["response"], prior["cost"], True, prior["reason"], 0)
        cache_key = hashlib.sha256(json.dumps({"tenant": request.tenant, "prompt": request.prompt, "quality": request.quality, "privacy": request.privacy}, sort_keys=True).encode()).hexdigest()
        cached = self.connection.execute("SELECT * FROM cache WHERE cache_key=?", (cache_key,)).fetchone()
        if cached:
            value = json.loads(cached["response"])
            return GatewayResponse(request_id, cached["model"], cached["provider"], value["text"], 0.0, True, "exact response cache hit", 0)
        candidates, reason = self._route(request)
        self._assert_budget(request, candidates[0])
        errors = []
        for fallback_count, model in enumerate(candidates):
            try:
                result = self.providers.call(model.provider, model.name, request.prompt)
                cost = (result.input_tokens * model.input_cost_per_million + result.output_tokens * model.output_cost_per_million) / 1_000_000
                if request.max_cost_usd is not None and cost > request.max_cost_usd:
                    raise BudgetExceeded(f"actual request cost {cost:.8f} exceeds cap {request.max_cost_usd:.8f}")
                self._record_success(request_id, request, model, result, cost, reason, candidates, fallback_count, cache_key)
                if shadow_model:
                    self._shadow(request_id, shadow_model, request.prompt)
                return GatewayResponse(request_id, model.name, model.provider, result.text, cost, False, reason, fallback_count)
            except BudgetExceeded:
                raise
            except Exception as exc:
                errors.append(f"{model.name}: {exc}")
                self._record_failure(model.name)
        raise NoHealthyModel("all fallback models failed: " + "; ".join(errors))
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `ModelGateway._complete` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 5. Which metrics detect correctness loss before customers report it?

**Staff/Principal answer.** Monitor route distribution, fallback rate, open circuits, provider errors, cache hit rate, per-tenant spend, quality proxy, token counts, and p95/p99 latency. A sudden route/fallback shift often detects provider or policy regression before outright failures.

**Implementation evidence.** [`ailab/model_gateway.py · ModelGateway.inspect`](../../ailab/model_gateway.py) is the concrete control point used by this project:

```python
def inspect(self) -> dict:
        return {table: [dict(row) for row in self.connection.execute(f"SELECT * FROM {table}")] for table in ("usage", "health", "decisions", "shadows")}
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `ModelGateway.inspect` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 6. What changes at 10× traffic, 100× data, multiple regions or adversarial tenants?

**Staff/Principal answer.** Use distributed rate/budget counters, consistent request routing, provider-specific bulkheads, globally replicated policy, and regional egress controls. Adversarial tenants need hard concurrency/token ceilings and cache keys that include every policy-relevant dimension.

**Implementation evidence.** [`ailab/model_gateway.py · ModelGateway._route`](../../ailab/model_gateway.py) is the concrete control point used by this project:

```python
def _route(self, request: GatewayRequest) -> tuple[list[ModelConfig], str]:
        tokens = len(tokenize(request.prompt))
        complexity = len(content_tokens(request.prompt)) > 25 or any(word in request.prompt.lower() for word in ("analyze", "architecture", "tradeoff", "compare", "failure"))
        candidates = [model for model in self.models.values() if model.max_context >= tokens and (request.privacy != "local" or model.provider == "local") and self._healthy(model.name)]
        if not candidates: raise NoHealthyModel("no model satisfies context, privacy, and health constraints")
        if request.quality == "high" or complexity:
            candidates.sort(key=lambda model: (-model.quality_tier, model.input_cost_per_million))
            reason = "quality/complexity policy selected highest quality healthy model"
        elif request.quality == "fast":
            candidates.sort(key=lambda model: (model.latency_tier, model.input_cost_per_million))
            reason = "latency policy selected fastest healthy model"
        else:
            candidates.sort(key=lambda model: (model.input_cost_per_million + model.output_cost_per_million, -model.quality_tier))
            reason = "balanced policy selected lowest-cost adequate model"
        return candidates, reason
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `ModelGateway._route` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 7. Which decisions belong in the platform versus the application team, and why?

**Staff/Principal answer.** The platform owns provider adapters, identity, budgets, safety, routing primitives, circuits, telemetry, and audit. Application teams own quality/latency requirements, approved model sets, prompt semantics, and business-specific degradation order within platform constraints.

**Implementation evidence.** [`ailab/model_gateway.py · GatewayRequest.validate`](../../ailab/model_gateway.py) is the concrete control point used by this project:

```python
def validate(self) -> None:
        if not self.tenant.strip() or not self.prompt.strip(): raise ValueError("tenant and prompt are required")
        if self.quality not in {"balanced", "fast", "high"}: raise ValueError("unsupported quality policy")
        if self.privacy not in {"any", "local"}: raise ValueError("unsupported privacy policy")
        if self.max_cost_usd is not None and (not math.isfinite(self.max_cost_usd) or self.max_cost_usd < 0): raise ValueError("max_cost_usd must be finite and non-negative")
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `GatewayRequest.validate` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

## Commands and evidence

Activate this project's `.venv`, run its CLI and project test file from `COMMANDS.md`, then inspect the matching `artifacts/project-*` report. The environment is a non-editable wheel snapshot so another project's installation cannot silently change this project.
