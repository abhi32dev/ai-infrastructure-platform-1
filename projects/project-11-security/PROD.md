# Production reasoning — Security and guardrails

## Why this project exists

Identity, least privilege, tenant isolation, inspection and immutable evidence surround every AI action. This project is deliberately small enough to execute locally but preserves the decision points that dominate production incidents and staff-level design reviews.

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

- empty/malformed/expired/tampered tokens
- missing claims
- RBAC and cross-tenant denial
- high-risk approval
- prompt-injection variants
- PII/secret redaction
- quota boundary
- audit-chain tampering

Tests use deterministic clocks, seeded data, temporary directories and local stores where possible. This avoids flaky CI. Live cloud/model/GPU tests belong in a separate opt-in suite because availability, cost and credentials would otherwise make the default suite non-reproducible.

## Design choice and trade-off

Rule-based controls are deterministic gates; probabilistic classifiers may augment but never silently replace them.

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

**Staff/Principal answer.** Cross-tenant disclosure or execution without valid identity is the dominant risk because it creates irreversible legal and trust impact. Authentication, authorization, inspection, and tenant filtering must precede every expensive or data-bearing action.

**Implementation evidence.** [`ailab/security_guardrails.py · GuardrailGateway.enforce`](../../ailab/security_guardrails.py) is the concrete control point used by this project:

```python
def enforce(self,p:Principal,action,tenant,resource,risk="low"):
  self._quota(p);decision=self.authorize(p,action,tenant,risk);self._audit(p,action,resource,decision)
  if not decision.allowed:raise GuardrailBlocked(decision.policy,decision.reason)
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `GuardrailGateway.enforce` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 2. Where is the linearization point for an idempotent mutation?

**Staff/Principal answer.** A protected mutation linearizes only when authorization/quota checks and the hash-chained audit append are committed with the effect. Token verification alone is not a mutation acknowledgment.

**Implementation evidence.** [`ailab/security_guardrails.py · GuardrailGateway._audit`](../../ailab/security_guardrails.py) is the concrete control point used by this project:

```python
def _audit(self,p,action,resource,d):
  row=self.db.execute("SELECT event_hash FROM audit ORDER BY sequence DESC LIMIT 1").fetchone();previous=row[0] if row else "GENESIS";timestamp=time.time();values=(timestamp,p.subject,p.tenant,action,resource,"allow" if d.allowed else "deny",d.policy,d.reason,previous);event_hash=hashlib.sha256("|".join(map(str,values)).encode()).hexdigest();self.db.execute("INSERT INTO audit(timestamp,subject,tenant,action,resource,decision,policy,reason,previous_hash,event_hash) VALUES(?,?,?,?,?,?,?,?,?,?)",(*values,event_hash));self.db.commit()
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `GuardrailGateway._audit` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 3. Which state is authoritative during disagreement, and how is reconciliation bounded?

**Staff/Principal answer.** The protected data store plus verified audit chain is authoritative; caches and model responses are not. Reconciliation is bounded by tenant, resource identity, and retention window, and any broken chain becomes an incident rather than silently repaired evidence.

**Implementation evidence.** [`ailab/security_guardrails.py · GuardrailGateway.verify_audit_chain`](../../ailab/security_guardrails.py) is the concrete control point used by this project:

```python
def verify_audit_chain(self)->bool:
  previous="GENESIS"
  for r in self.db.execute("SELECT * FROM audit ORDER BY sequence"):
   payload="|".join(str(r[x]) for x in ("timestamp","subject","tenant","action","resource","decision","policy","reason","previous_hash"));expected=hashlib.sha256(payload.encode()).hexdigest()
   if r["previous_hash"]!=previous or r["event_hash"]!=expected:return False
   previous=expected
  return True
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `GuardrailGateway.verify_audit_chain` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 4. What does graceful degradation preserve, and what must fail closed?

**Staff/Principal answer.** Low-risk inference may degrade by redaction, safe templates, or reduced capability. Invalid identity, missing scope, cross-tenant access, injection, secrets, quota exhaustion, and audit-integrity failure must fail closed.

**Implementation evidence.** [`ailab/security_guardrails.py · GuardrailGateway.authorize`](../../ailab/security_guardrails.py) is the concrete control point used by this project:

```python
def authorize(self,p:Principal,action:str,resource_tenant:str,risk="low")->Decision:
  if p.tenant!=resource_tenant and "platform-admin" not in p.roles:return Decision(False,"authz.tenant","cross-tenant access denied")
  role_actions={"reader":{"retrieve"},"agent":{"retrieve","infer","tool:read"},"operator":{"retrieve","infer","tool:read","tool:write"},"platform-admin":{"*"}}
  allowed=any("*" in role_actions.get(role,set()) or action in role_actions.get(role,set()) for role in p.roles)
  if not allowed:return Decision(False,"authz.rbac",f"roles do not permit {action}")
  if risk=="high" and "operator" not in p.roles and "platform-admin" not in p.roles:return Decision(False,"authz.high_risk","operator approval required")
  return Decision(True,"authz.allow","least-privilege policy allowed action")
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `GuardrailGateway.authorize` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 5. Which metrics detect correctness loss before customers report it?

**Staff/Principal answer.** Track authentication/authorization denials, tenant-escape attempts, injection and PII detections, redaction, quota rejection, unusual tool use, audit verification, deletion/retention completion, and false-positive/negative review outcomes.

**Implementation evidence.** [`ailab/security_guardrails.py · GuardrailGateway._audit`](../../ailab/security_guardrails.py) is the concrete control point used by this project:

```python
def _audit(self,p,action,resource,d):
  row=self.db.execute("SELECT event_hash FROM audit ORDER BY sequence DESC LIMIT 1").fetchone();previous=row[0] if row else "GENESIS";timestamp=time.time();values=(timestamp,p.subject,p.tenant,action,resource,"allow" if d.allowed else "deny",d.policy,d.reason,previous);event_hash=hashlib.sha256("|".join(map(str,values)).encode()).hexdigest();self.db.execute("INSERT INTO audit(timestamp,subject,tenant,action,resource,decision,policy,reason,previous_hash,event_hash) VALUES(?,?,?,?,?,?,?,?,?,?)",(*values,event_hash));self.db.commit()
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `GuardrailGateway._audit` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 6. What changes at 10× traffic, 100× data, multiple regions or adversarial tenants?

**Staff/Principal answer.** Centralize policy distribution, isolate tenant keys/data, use regional enforcement, hardware-backed secrets, streaming audit, and abuse detection. Adversarial tenants require adaptive quotas but policy evaluation must remain deterministic and explainable.

**Implementation evidence.** [`ailab/security_guardrails.py · GuardrailGateway.input_guard`](../../ailab/security_guardrails.py) is the concrete control point used by this project:

```python
def input_guard(self,text:str,allow_pii=False)->Decision:
  lowered=text.lower();injection=next((x for x in self.INJECTION if x in lowered),None)
  if injection:return Decision(False,"input.prompt_injection",f"matched adversarial phrase: {injection}")
  redacted=self.EMAIL.sub("[EMAIL]",self.SSN.sub("[SSN]",text))
  if redacted!=text and not allow_pii:return Decision(True,"input.pii_redaction","PII redacted",redacted)
  return Decision(True,"input.accept","input accepted",text)
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `GuardrailGateway.input_guard` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 7. Which decisions belong in the platform versus the application team, and why?

**Staff/Principal answer.** The platform owns identity verification, policy engine, tenant isolation primitives, secret/PII controls, audit, quotas, and key lifecycle. Application teams own data classification, resource ownership, domain permissions, approved tools, and human risk decisions.

**Implementation evidence.** [`ailab/security_guardrails.py · GuardrailGateway.enforce`](../../ailab/security_guardrails.py) is the concrete control point used by this project:

```python
def enforce(self,p:Principal,action,tenant,resource,risk="low"):
  self._quota(p);decision=self.authorize(p,action,tenant,risk);self._audit(p,action,resource,decision)
  if not decision.allowed:raise GuardrailBlocked(decision.policy,decision.reason)
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `GuardrailGateway.enforce` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

## Commands and evidence

Activate this project's `.venv`, run its CLI and project test file from `COMMANDS.md`, then inspect the matching `artifacts/project-*` report. The environment is a non-editable wheel snapshot so another project's installation cannot silently change this project.
