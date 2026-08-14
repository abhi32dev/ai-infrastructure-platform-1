# Production reasoning — Evaluation and release gates

## Why this project exists

No model or prompt change is promoted without versioned evidence and explicit thresholds. This project is deliberately small enough to execute locally but preserves the decision points that dominate production incidents and staff-level design reviews.

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

- empty suite
- invalid experiment counts
- quality/safety regression
- latency/cost threshold failure
- invalid judge scores
- low judge agreement
- outlier-resistant consensus
- MLflow persistence

Tests use deterministic clocks, seeded data, temporary directories and local stores where possible. This avoids flaky CI. Live cloud/model/GPU tests belong in a separate opt-in suite because availability, cost and credentials would otherwise make the default suite non-reproducible.

## Design choice and trade-off

Deterministic judges make CI stable; model judges are additive and require calibration against human labels.

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

**Staff/Principal answer.** Promoting a systematically unsafe or regressed model is costlier than delaying a release. Versioned datasets, judge calibration, statistical validity, and explicit thresholds must all be tied to the exact candidate artifact and configuration.

**Implementation evidence.** [`ailab/eval_platform.py · EvaluationPlatform.gate`](../../ailab/eval_platform.py) is the concrete control point used by this project:

```python
def gate(self, run_id: str, thresholds: GateThresholds) -> dict:
        row=self.connection.execute("SELECT summary FROM runs WHERE id=?",(run_id,)).fetchone()
        if not row: raise ValueError(f"unknown run: {run_id}")
        summary=json.loads(row["summary"]); reasons=[]
        if summary["quality"] < thresholds.minimum_quality: reasons.append("quality_below_threshold")
        if summary["safety"] < thresholds.minimum_safety: reasons.append("safety_below_threshold")
        if summary["p95_latency_ms"] > thresholds.maximum_p95_latency_ms: reasons.append("latency_above_threshold")
        if summary["average_cost_usd"] > thresholds.maximum_average_cost_usd: reasons.append("cost_above_threshold")
        decision="promote" if not reasons else "block"
        self.connection.execute("INSERT OR REPLACE INTO release_decisions VALUES (?,?,?,?,?)",(run_id,decision,json.dumps(reasons),json.dumps(asdict(thresholds)),time.time()))
        self.connection.commit(); return {"run_id":run_id,"decision":decision,"reasons":reasons,"summary":summary}
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `EvaluationPlatform.gate` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 2. Where is the linearization point for an idempotent mutation?

**Staff/Principal answer.** The release decision linearizes when the immutable evaluation result and gate outcome are persisted for a candidate/suite version. Dashboard display or a model registry tag must consume that record rather than independently recomputing policy.

**Implementation evidence.** [`ailab/mlflow_tracking.py · MLflowTracker.log_evaluation`](../../ailab/mlflow_tracking.py) is the concrete control point used by this project:

```python
def log_evaluation(self, candidate: str, version: str, metrics: dict[str, float], config: dict[str, Any], artifact: Path | None = None) -> str:
        with self.mlflow.start_run(run_name=f"{candidate}-{version}") as run:
            self.mlflow.log_params({"candidate": candidate, "version": version, **config})
            self.mlflow.log_metrics(metrics)
            if artifact: self.mlflow.log_artifact(str(artifact))
            self.mlflow.set_tag("release.gate", "evaluation")
            return run.info.run_id
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `MLflowTracker.log_evaluation` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 3. Which state is authoritative during disagreement, and how is reconciliation bounded?

**Staff/Principal answer.** The versioned suite, raw case results, and recorded gate policy are authoritative. Aggregates are reproducible derivatives; reconciliation reruns only the bounded suite/candidate pair and compares immutable inputs before replacing a disputed summary.

**Implementation evidence.** [`ailab/eval_platform.py · EvaluationPlatform.run`](../../ailab/eval_platform.py) is the concrete control point used by this project:

```python
def run(self, suite_id: str, candidate: Candidate, judge: Callable[[EvalCase, str], float] | None = None) -> str:
        row = self.connection.execute("SELECT cases FROM suites WHERE id=?", (suite_id,)).fetchone()
        if not row: raise ValueError(f"unknown suite: {suite_id}")
        cases = [EvalCase(item["id"], item["prompt"], tuple(item["expected_terms"]), tuple(item["forbidden_terms"])) for item in json.loads(row["cases"])]
        run_id = uuid.uuid4().hex; results=[]
        for case in cases:
            started=time.perf_counter(); output=candidate.handler(case.prompt); latency=(time.perf_counter()-started)*1000
            lowered=output.lower(); required=sum(term.lower() in lowered for term in case.expected_terms)/max(len(case.expected_terms),1)
            safety=float(not any(term.lower() in lowered for term in case.forbidden_terms))
            judge_score=judge(case,output) if judge else required*safety
            result=CaseResult(case.id,required,safety,judge_score,latency,candidate.estimated_cost_per_call,output); results.append(result)
            self.connection.execute("INSERT INTO case_results VALUES (?,?,?,?)",(run_id,case.id,json.dumps(asdict(result)),output))
        summary=self._summarize(results)
        self.connection.execute("INSERT INTO runs VALUES (?,?,?,?,?,?,?)",(run_id,suite_id,candidate.name,candidate.version,"evaluated",json.dumps(summary),time.time()))
        self.connection.commit(); return run_id
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `EvaluationPlatform.run` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 4. What does graceful degradation preserve, and what must fail closed?

**Staff/Principal answer.** A failed optional judge may be excluded only if minimum judge count and agreement still hold. Safety, dataset integrity, required metrics, and statistical assumptions fail closed; unavailable evidence cannot be interpreted as a pass.

**Implementation evidence.** [`ailab/eval_platform.py · consensus_judge`](../../ailab/eval_platform.py) is the concrete control point used by this project:

```python
def consensus_judge(judges: Iterable[tuple[str, Callable[[EvalCase, str], float]]], minimum_agreement: float = 2 / 3) -> Callable[[EvalCase, str], float]:
    """Build a median-based judge panel that rejects weak agreement."""
    panel = list(judges)
    if len(panel) < 3:
        raise ValueError("a consensus panel requires at least three judges")
    if not 0.5 <= minimum_agreement <= 1.0:
        raise ValueError("minimum_agreement must be between 0.5 and 1.0")
    def evaluate(case: EvalCase, output: str) -> float:
        votes = [JudgeVote(name, float(fn(case, output))) for name, fn in panel]
        if any(not 0.0 <= vote.score <= 1.0 for vote in votes):
            raise ValueError("judge scores must be between 0 and 1")
        median = statistics.median(vote.score for vote in votes)
        side = median >= 0.5
        agreement = sum((vote.score >= 0.5) == side for vote in votes) / len(votes)
        if agreement < minimum_agreement:
            raise ValueError(f"judge panel agreement {agreement:.3f} is below {minimum_agreement:.3f}")
        return median
    return evaluate
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `consensus_judge` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 5. Which metrics detect correctness loss before customers report it?

**Staff/Principal answer.** Track per-slice quality and safety, judge agreement, outlier rate, latency/cost, gate failure reasons, candidate-control deltas, and online/offline correlation. Slice and agreement drift expose evaluation blindness before aggregate quality moves.

**Implementation evidence.** [`ailab/eval_platform.py · EvaluationPlatform._summarize`](../../ailab/eval_platform.py) is the concrete control point used by this project:

```python
def _summarize(results: list[CaseResult]) -> dict:
        latencies=sorted(result.latency_ms for result in results); index=max(0,math.ceil(0.95*len(latencies))-1)
        return {"cases":len(results),"quality":statistics.mean(r.judge_score for r in results),"safety":statistics.mean(r.safety for r in results),"p95_latency_ms":latencies[index],"average_cost_usd":statistics.mean(r.cost_usd for r in results)}
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `EvaluationPlatform._summarize` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 6. What changes at 10× traffic, 100× data, multiple regions or adversarial tenants?

**Staff/Principal answer.** Parallelize cases, stratify large datasets, cache immutable judge calls, and maintain regional evaluation data boundaries. At 100× data use sampled CI plus scheduled exhaustive runs; adversarial inputs require protected hidden sets and contamination checks.

**Implementation evidence.** [`ailab/eval_platform.py · EvaluationPlatform.run`](../../ailab/eval_platform.py) is the concrete control point used by this project:

```python
def run(self, suite_id: str, candidate: Candidate, judge: Callable[[EvalCase, str], float] | None = None) -> str:
        row = self.connection.execute("SELECT cases FROM suites WHERE id=?", (suite_id,)).fetchone()
        if not row: raise ValueError(f"unknown suite: {suite_id}")
        cases = [EvalCase(item["id"], item["prompt"], tuple(item["expected_terms"]), tuple(item["forbidden_terms"])) for item in json.loads(row["cases"])]
        run_id = uuid.uuid4().hex; results=[]
        for case in cases:
            started=time.perf_counter(); output=candidate.handler(case.prompt); latency=(time.perf_counter()-started)*1000
            lowered=output.lower(); required=sum(term.lower() in lowered for term in case.expected_terms)/max(len(case.expected_terms),1)
            safety=float(not any(term.lower() in lowered for term in case.forbidden_terms))
            judge_score=judge(case,output) if judge else required*safety
            result=CaseResult(case.id,required,safety,judge_score,latency,candidate.estimated_cost_per_call,output); results.append(result)
            self.connection.execute("INSERT INTO case_results VALUES (?,?,?,?)",(run_id,case.id,json.dumps(asdict(result)),output))
        summary=self._summarize(results)
        self.connection.execute("INSERT INTO runs VALUES (?,?,?,?,?,?,?)",(run_id,suite_id,candidate.name,candidate.version,"evaluated",json.dumps(summary),time.time()))
        self.connection.commit(); return run_id
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `EvaluationPlatform.run` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 7. Which decisions belong in the platform versus the application team, and why?

**Staff/Principal answer.** The platform owns dataset/version schemas, execution, judge interfaces, statistics, lineage, and gate enforcement. Application teams own representative cases, rubric semantics, risk weights, business slices, and accountable threshold approval.

**Implementation evidence.** [`ailab/eval_platform.py · EvaluationPlatform.register_suite`](../../ailab/eval_platform.py) is the concrete control point used by this project:

```python
def register_suite(self, name: str, version: str, cases: list[EvalCase]) -> str:
        if not cases: raise ValueError("evaluation suite cannot be empty")
        suite_id = f"{name}:{version}"
        self.connection.execute("INSERT OR REPLACE INTO suites VALUES (?,?,?,?,?)", (suite_id, name, version, json.dumps([asdict(case) for case in cases]), time.time()))
        self.connection.commit(); return suite_id
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `EvaluationPlatform.register_suite` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

## Commands and evidence

Activate this project's `.venv`, run its CLI and project test file from `COMMANDS.md`, then inspect the matching `artifacts/project-*` report. The environment is a non-editable wheel snapshot so another project's installation cannot silently change this project.
