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

- Which routing signals are known before inference, and which require feedback?
- How should a gateway estimate output cost before generation?
- Why must request retries preserve an idempotency key?
- When should provider failures trigger fallback versus immediate failure?
- How do circuit breakers interact with regional or model-wide outages?
- What cache keys prevent cross-tenant or policy leakage?
- Why is shadow traffic operationally safer than a canary but less conclusive?
- How would you enforce concurrency and token-rate quotas atomically?

## Local versus production

SQLite makes every decision inspectable on one machine. A production gateway would use a transactional shared store for quotas, distributed rate limiting, async streaming transport, provider-specific cancellation, and regional health aggregation. The routing and accounting contracts remain the same; their coordination mechanism changes.

