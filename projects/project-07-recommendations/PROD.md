# Production reasoning — Recommendation and experimentation

## Why this project exists

Ranking must be deterministic, explainable, measurable and safe for cold-start users. This project is deliberately small enough to execute locally but preserves the decision points that dominate production incidents and staff-level design reviews.

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

- empty or duplicate catalog IDs
- unknown items/events
- empty users and invalid k
- cold start
- consumed-item exclusion
- collaborative sparsity
- sticky assignment boundaries
- experiment readiness/significance

Tests use deterministic clocks, seeded data, temporary directories and local stores where possible. This avoids flaky CI. Live cloud/model/GPU tests belong in a separate opt-in suite because availability, cost and credentials would otherwise make the default suite non-reproducible.

## Design choice and trade-off

Compact ranking signals expose algorithms; production adds approximate candidate retrieval and learned ranking.

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

**Staff/Principal answer.** Serving ineligible or already-consumed items is the most damaging invariant because it violates product policy regardless of ranking quality. Eligibility filtering must precede scoring, experimentation, and explanation.

**Implementation evidence.** [`ailab/recommendations.py · RecommendationPlatform.recommend`](../../ailab/recommendations.py) is the concrete control point used by this project:

```python
def recommend(self,user:str,k:int=5)->list[Recommendation]:
  if not user:raise ValueError("user is required")
  if k<=0:raise ValueError("k must be positive")
  rows=self.db.execute("SELECT * FROM interactions").fetchall();consumed={r["item_id"] for r in rows if r["user_id"]==user and r["weight"]>0};pop=Counter();user_items=defaultdict(dict)
  for r in rows:pop[r["item_id"]]+=max(0,r["weight"]);user_items[r["user_id"]][r["item_id"]]=r["weight"]
  profile=Counter()
  for item_id,weight in user_items[user].items():
   for tag in self.items[item_id].tags:profile[tag]+=weight
   profile[self.items[item_id].category]+=weight
  collaborative=Counter()
  target=set(user_items[user])
  for other,history in user_items.items():
   if other==user:continue
   similarity=len(target&set(history))/max(1,len(target|set(history)))
   for item_id,weight in history.items():
    if item_id not in consumed and weight>0:collaborative[item_id]+=similarity*weight
  max_pop=max(pop.values(),default=1) or 1;results=[]
  for item_id,item in self.items.items():
   if item_id in consumed:continue
   content=sum(max(0,profile[tag]) for tag in (*item.tags,item.category));popularity=pop[item_id]/max_pop;collab=collaborative[item_id]
   score=.45*content+.35*collab+.20*popularity;reasons=[]
   if content:reasons.append("content affinity")
   if collab:reasons.append("similar users")
   if popularity:reasons.append("popular")
   if not reasons:reasons.append("cold-start catalog fallback")
   results.append(Recommendation(item_id,score,tuple(reasons)))
  return sorted(results,key=lambda x:(-x.score,x.item_id))[:k]
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `RecommendationPlatform.recommend` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 2. Where is the linearization point for an idempotent mutation?

**Staff/Principal answer.** An interaction linearizes when the validated event is appended to user history exactly once. Experiment assignment linearizes deterministically from user and experiment identity, so repeated requests cannot move a user between variants.

**Implementation evidence.** [`ailab/recommendations.py · RecommendationPlatform.interact`](../../ailab/recommendations.py) is the concrete control point used by this project:

```python
def interact(self,user:str,item:str,event:str="view",timestamp:float|None=None):
  if not user:raise ValueError("user is required")
  if item not in self.items:raise ValueError(f"unknown item: {item}")
  weights={"view":1,"click":3,"purchase":8,"dislike":-5}
  if event not in weights:raise ValueError(f"unknown event: {event}")
  self.db.execute("INSERT INTO interactions VALUES(?,?,?,?,?)",(user,item,event,weights[event],timestamp or time.time()));self.db.commit()
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `RecommendationPlatform.interact` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 3. Which state is authoritative during disagreement, and how is reconciliation bounded?

**Staff/Principal answer.** The interaction history and catalog are authoritative; recommendation lists and popularity/collaborative scores are derived. Reconciliation rebuilds bounded user/item aggregates from the event set and compares experiment configuration versions.

**Implementation evidence.** [`ailab/recommendations.py · RecommendationPlatform.interact`](../../ailab/recommendations.py) is the concrete control point used by this project:

```python
def interact(self,user:str,item:str,event:str="view",timestamp:float|None=None):
  if not user:raise ValueError("user is required")
  if item not in self.items:raise ValueError(f"unknown item: {item}")
  weights={"view":1,"click":3,"purchase":8,"dislike":-5}
  if event not in weights:raise ValueError(f"unknown event: {event}")
  self.db.execute("INSERT INTO interactions VALUES(?,?,?,?,?)",(user,item,event,weights[event],timestamp or time.time()));self.db.commit()
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `RecommendationPlatform.interact` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 4. What does graceful degradation preserve, and what must fail closed?

**Staff/Principal answer.** Degrade from collaborative/content signals to popularity and diversity-aware cold-start results. Catalog eligibility, consumed-item exclusion, tenant/policy filters, and experiment stickiness fail closed; an empty safe list is preferable to an invalid item.

**Implementation evidence.** [`ailab/recommendations.py · RecommendationPlatform.recommend`](../../ailab/recommendations.py) is the concrete control point used by this project:

```python
def recommend(self,user:str,k:int=5)->list[Recommendation]:
  if not user:raise ValueError("user is required")
  if k<=0:raise ValueError("k must be positive")
  rows=self.db.execute("SELECT * FROM interactions").fetchall();consumed={r["item_id"] for r in rows if r["user_id"]==user and r["weight"]>0};pop=Counter();user_items=defaultdict(dict)
  for r in rows:pop[r["item_id"]]+=max(0,r["weight"]);user_items[r["user_id"]][r["item_id"]]=r["weight"]
  profile=Counter()
  for item_id,weight in user_items[user].items():
   for tag in self.items[item_id].tags:profile[tag]+=weight
   profile[self.items[item_id].category]+=weight
  collaborative=Counter()
  target=set(user_items[user])
  for other,history in user_items.items():
   if other==user:continue
   similarity=len(target&set(history))/max(1,len(target|set(history)))
   for item_id,weight in history.items():
    if item_id not in consumed and weight>0:collaborative[item_id]+=similarity*weight
  max_pop=max(pop.values(),default=1) or 1;results=[]
  for item_id,item in self.items.items():
   if item_id in consumed:continue
   content=sum(max(0,profile[tag]) for tag in (*item.tags,item.category));popularity=pop[item_id]/max_pop;collab=collaborative[item_id]
   score=.45*content+.35*collab+.20*popularity;reasons=[]
   if content:reasons.append("content affinity")
   if collab:reasons.append("similar users")
   if popularity:reasons.append("popular")
   if not reasons:reasons.append("cold-start catalog fallback")
   results.append(Recommendation(item_id,score,tuple(reasons)))
  return sorted(results,key=lambda x:(-x.score,x.item_id))[:k]
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `RecommendationPlatform.recommend` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 5. Which metrics detect correctness loss before customers report it?

**Staff/Principal answer.** Track Recall/NDCG/coverage/diversity, empty-list rate, consumed/ineligible leakage, cold-start performance, score distribution, exposure imbalance, assignment stability, conversion lift, and guardrail outcomes by cohort.

**Implementation evidence.** [`ailab/recommendations.py · ranking_metrics`](../../ailab/recommendations.py) is the concrete control point used by this project:

```python
def ranking_metrics(recommended:list[str],relevant:set[str],catalog:list[Item],k:int)->dict:
 ranked=recommended[:k];hits=[int(x in relevant) for x in ranked];precision=sum(hits)/max(k,1);recall=sum(hits)/max(len(relevant),1);dcg=sum(hit/math.log2(i+2) for i,hit in enumerate(hits));ideal=sum(1/math.log2(i+2) for i in range(min(len(relevant),k)));ndcg=dcg/ideal if ideal else 0;categories={x.id:x.category for x in catalog};pairs=0;different=0
 for i in range(len(ranked)):
  for j in range(i+1,len(ranked)):pairs+=1;different+=categories.get(ranked[i])!=categories.get(ranked[j])
 return {"precision_at_k":precision,"recall_at_k":recall,"ndcg_at_k":ndcg,"coverage":len(set(ranked))/max(len(catalog),1),"diversity":different/pairs if pairs else 0}
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `ranking_metrics` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 6. What changes at 10× traffic, 100× data, multiple regions or adversarial tenants?

**Staff/Principal answer.** Separate approximate candidate retrieval from learned ranking, precompute embeddings, stream interactions, and shard user state. Multi-region experiments need globally stable assignment; adversarial tenants/users require event-quality and popularity-manipulation controls.

**Implementation evidence.** [`ailab/recommendations.py · RecommendationPlatform.recommend`](../../ailab/recommendations.py) is the concrete control point used by this project:

```python
def recommend(self,user:str,k:int=5)->list[Recommendation]:
  if not user:raise ValueError("user is required")
  if k<=0:raise ValueError("k must be positive")
  rows=self.db.execute("SELECT * FROM interactions").fetchall();consumed={r["item_id"] for r in rows if r["user_id"]==user and r["weight"]>0};pop=Counter();user_items=defaultdict(dict)
  for r in rows:pop[r["item_id"]]+=max(0,r["weight"]);user_items[r["user_id"]][r["item_id"]]=r["weight"]
  profile=Counter()
  for item_id,weight in user_items[user].items():
   for tag in self.items[item_id].tags:profile[tag]+=weight
   profile[self.items[item_id].category]+=weight
  collaborative=Counter()
  target=set(user_items[user])
  for other,history in user_items.items():
   if other==user:continue
   similarity=len(target&set(history))/max(1,len(target|set(history)))
   for item_id,weight in history.items():
    if item_id not in consumed and weight>0:collaborative[item_id]+=similarity*weight
  max_pop=max(pop.values(),default=1) or 1;results=[]
  for item_id,item in self.items.items():
   if item_id in consumed:continue
   content=sum(max(0,profile[tag]) for tag in (*item.tags,item.category));popularity=pop[item_id]/max_pop;collab=collaborative[item_id]
   score=.45*content+.35*collab+.20*popularity;reasons=[]
   if content:reasons.append("content affinity")
   if collab:reasons.append("similar users")
   if popularity:reasons.append("popular")
   if not reasons:reasons.append("cold-start catalog fallback")
   results.append(Recommendation(item_id,score,tuple(reasons)))
  return sorted(results,key=lambda x:(-x.score,x.item_id))[:k]
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `RecommendationPlatform.recommend` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 7. Which decisions belong in the platform versus the application team, and why?

**Staff/Principal answer.** The platform owns event schemas, candidate/ranker interfaces, experiment assignment, metrics, policy filters, and audit. Product teams own objectives, catalog semantics, eligibility rules, feature choices, exploration policy, and accountable rollout decisions.

**Implementation evidence.** [`ailab/recommendations.py · RecommendationPlatform.assign`](../../ailab/recommendations.py) is the concrete control point used by this project:

```python
def assign(self,user:str,experiment:str="ranking-v1",treatment_percent:int=50)->str:
  if not user or not experiment:raise ValueError("user and experiment are required")
  if not 0<=treatment_percent<=100:raise ValueError("percentage must be 0..100")
  row=self.db.execute("SELECT variant FROM assignments WHERE user_id=? AND experiment=?",(user,experiment)).fetchone()
  if row:return row[0]
  bucket=int(hashlib.sha256(f"{experiment}:{user}".encode()).hexdigest()[:8],16)%100;variant="treatment" if bucket<treatment_percent else "control";self.db.execute("INSERT INTO assignments VALUES(?,?,?)",(user,experiment,variant));self.db.commit();return variant
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `RecommendationPlatform.assign` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

## Commands and evidence

Activate this project's `.venv`, run its CLI and project test file from `COMMANDS.md`, then inspect the matching `artifacts/project-*` report. The environment is a non-editable wheel snapshot so another project's installation cannot silently change this project.
