# Production reasoning — MCP and A2A protocols

## Why this project exists

Versioned protocol state, cancellation, schemas, authorization and telemetry must fail explicitly. This project is deliberately small enough to execute locally but preserves the decision points that dominate production incidents and staff-level design reviews.

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

- invalid JSON-RPC/version
- pre-initialization calls
- unknown methods/resources/prompts/tools
- missing arguments
- guardrail denial
- request cancellation
- A2A task failure
- terminal-task cancellation

Tests use deterministic clocks, seeded data, temporary directories and local stores where possible. This avoids flaky CI. Live cloud/model/GPU tests belong in a separate opt-in suite because availability, cost and credentials would otherwise make the default suite non-reproducible.

## Design choice and trade-off

In-process transports focus learning on protocol contracts; network bindings are replaceable boundaries.

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

**Staff/Principal answer.** Executing an unauthorized or schema-invalid remote tool is the costliest violation because protocol interoperability expands the trust boundary. Version negotiation, capabilities, scopes, schemas, budgets, and cancellation must be explicit.

**Implementation evidence.** [`ailab/protocols.py · MCPServer.handle`](../../ailab/protocols.py) is the concrete control point used by this project:

```python
def handle(self,request:dict)->dict|None:
  id=request.get("id");method=request.get("method","");params=request.get("params",{})
  if request.get("jsonrpc")!="2.0":return ProtocolError(-32600,"Invalid Request").response(id)
  try:
   with self.telemetry.span(f"mcp.{method}",protocol="mcp",method=method) as span:
    if method=="initialize":result=self._initialize(params)
    elif method=="notifications/initialized":self.initialized=True;return None
    elif method=="notifications/cancelled":self.cancelled.add(params.get("requestId"));return None
    else:
     if not self.initialized:raise ProtocolError(-32002,"Server not initialized")
     result=self._dispatch(method,params,id)
    self.telemetry.log("INFO","mcp request completed",span["trace_id"],method=method)
    return {"jsonrpc":"2.0","id":id,"result":result}
  except ProtocolError as exc:return exc.response(id)
  except Exception as exc:return ProtocolError(-32603,"Internal error",str(exc)).response(id)
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `MCPServer.handle` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 2. Where is the linearization point for an idempotent mutation?

**Staff/Principal answer.** An MCP call linearizes at its JSON-RPC result/error for the request ID; an A2A mutation linearizes at durable task state/artifact append. Transport delivery is not proof of remote execution.

**Implementation evidence.** [`ailab/protocols.py · A2AServer.send_message`](../../ailab/protocols.py) is the concrete control point used by this project:

```python
def send_message(self,message:dict,version="1.0",context_id=None)->dict:
  if version!=self.VERSION:raise ProtocolError(-32009,"VersionNotSupportedError",{"supported":[self.VERSION]})
  parts=message.get("parts",[])
  if message.get("role")!="user" or not parts:raise ProtocolError(-32602,"invalid message")
  text=" ".join(p.get("text","") for p in parts if p.get("type")=="text");guard=self.security.input_guard(text)
  if not guard.allowed:raise ProtocolError(-32001,"message blocked",asdict(guard))
  self.security.enforce(self.principal,"infer",self.principal.tenant,"a2a-task");task_id=uuid.uuid4().hex;now=time.time();self.db.execute("INSERT INTO tasks VALUES(?,?,?,?,?,?,?,?)",(task_id,context_id or uuid.uuid4().hex,"working",json.dumps([message]),json.dumps([]),json.dumps({}),now,now));self.db.commit()
  if message.get("metadata",{}).get("defer"):
   self.db.execute("UPDATE tasks SET state='submitted',updated_at=? WHERE id=?",(time.time(),task_id));self.db.commit();return self.get_task(task_id)
  with self.telemetry.span("a2a.send_message",protocol="a2a",task_id=task_id):
   started=time.perf_counter()
   try:artifact=self.handler({"text":guard.redacted or text,"task_id":task_id});state="completed";artifacts=[{"artifactId":uuid.uuid4().hex,"name":"result","parts":[{"type":"data","data":artifact}],"lastChunk":True}]
   except Exception as exc:state="failed";artifacts=[{"artifactId":uuid.uuid4().hex,"name":"error","parts":[{"type":"text","text":str(exc)}],"lastChunk":True}]
   self.telemetry.request("a2a",state=="completed",(time.perf_counter()-started)*1000,cost=.0001,model="remote-agent",tenant=self.principal.tenant)
  self.db.execute("UPDATE tasks SET state=?,artifacts=?,updated_at=? WHERE id=?",(state,json.dumps(artifacts),time.time(),task_id));self.db.commit();return self.get_task(task_id)
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `A2AServer.send_message` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 3. Which state is authoritative during disagreement, and how is reconciliation bounded?

**Staff/Principal answer.** The durable A2A task record and ordered messages/artifacts are authoritative; client polling state is derived. Reconciliation is bounded to a task ID and legal state transitions, with terminal states immutable.

**Implementation evidence.** [`ailab/protocols.py · A2AServer.get_task`](../../ailab/protocols.py) is the concrete control point used by this project:

```python
def get_task(self,id):
  row=self.db.execute("SELECT * FROM tasks WHERE id=?",(id,)).fetchone()
  if not row:raise ProtocolError(-32001,"TaskNotFoundError")
  return {"id":row["id"],"contextId":row["context_id"],"status":{"state":row["state"]},"history":json.loads(row["messages"]),"artifacts":json.loads(row["artifacts"]),"metadata":json.loads(row["metadata"])}
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `A2AServer.get_task` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 4. What does graceful degradation preserve, and what must fail closed?

**Staff/Principal answer.** Degrade by disabling optional capabilities, returning typed protocol errors, or canceling nonterminal work. Authentication, scope, schema, protocol version, budget, output inspection, and terminal-state integrity fail closed.

**Implementation evidence.** [`ailab/protocols.py · MCPServer._dispatch`](../../ailab/protocols.py) is the concrete control point used by this project:

```python
def _dispatch(self,m,p,id):
  if id in self.cancelled:raise ProtocolError(-32800,"Request cancelled")
  if m=="tools/list":return {"tools":[{"name":x.name,"description":x.description,"inputSchema":x.input_schema} for x in self.tools.values()]}
  if m=="resources/list":return {"resources":[{"uri":x.uri,"name":x.name,"mimeType":x.mime_type} for x in self.resources.values()]}
  if m=="prompts/list":return {"prompts":[{"name":x.name,"description":x.description,"arguments":[{"name":a,"required":True} for a in x.arguments]} for x in self.prompts.values()]}
  if m=="resources/read":
   uri=p.get("uri");resource=self.resources.get(uri)
   if not resource:raise ProtocolError(-32002,"Resource not found")
   self.security.enforce(self.principal,"retrieve",self.principal.tenant,uri);return {"contents":[{"uri":uri,"mimeType":resource.mime_type,"text":resource.reader()}]}
  if m=="prompts/get":
   prompt=self.prompts.get(p.get("name"))
   if not prompt:raise ProtocolError(-32602,"Unknown prompt")
   missing=set(prompt.arguments)-p.get("arguments",{}).keys()
   if missing:raise ProtocolError(-32602,"Missing prompt arguments",sorted(missing))
   return {"description":prompt.description,"messages":prompt.renderer(p["arguments"])}
  if m=="tools/call":
   tool=self.tools.get(p.get("name"))
   if not tool:raise ProtocolError(-32602,"Unknown tool")
   arguments=p.get("arguments",{});required=set(tool.input_schema.get("required",[]));missing=required-arguments.keys()
   if missing:raise ProtocolError(-32602,"Invalid tool arguments",sorted(missing))
   decision=self.security.input_guard(json.dumps(arguments))
   if not decision.allowed:raise ProtocolError(-32001,"Guardrail blocked tool input",asdict(decision))
   self.security.enforce(self.principal,"tool:write" if tool.risk=="high" else "tool:read",self.principal.tenant,tool.name,tool.risk)
   started=time.perf_counter();value=tool.handler(arguments);self.telemetry.request("mcp",True,(time.perf_counter()-started)*1000,cost=.00001,model="tool",tenant=self.principal.tenant);return {"content":[{"type":"text","text":json.dumps(value)}],"isError":False}
  raise ProtocolError(-32601,"Method not found")
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `MCPServer._dispatch` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 5. Which metrics detect correctness loss before customers report it?

**Staff/Principal answer.** Track negotiation failures, method/tool errors, schema rejection, auth denial, request/task latency, cancellation effectiveness, terminal-state distribution, artifact size, remote retries, and per-task cost.

**Implementation evidence.** [`ailab/protocols.py · A2AServer.list_tasks`](../../ailab/protocols.py) is the concrete control point used by this project:

```python
def list_tasks(self):return [self.get_task(row[0]) for row in self.db.execute("SELECT id FROM tasks ORDER BY created_at")]
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `A2AServer.list_tasks` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 6. What changes at 10× traffic, 100× data, multiple regions or adversarial tenants?

**Staff/Principal answer.** Use stateless protocol gateways plus durable task stores, backpressure, streaming artifacts, regional agent discovery, and version compatibility windows. Adversarial agents require capability allowlists, signed identity, quotas, and content inspection.

**Implementation evidence.** [`ailab/protocols.py · MCPServer._initialize`](../../ailab/protocols.py) is the concrete control point used by this project:

```python
def _initialize(self,p):
  if p.get("protocolVersion")!=self.REVISION:raise ProtocolError(-32602,"Unsupported protocol version",{"supported":[self.REVISION]})
  return {"protocolVersion":self.REVISION,"capabilities":{"tools":{"listChanged":False},"resources":{"subscribe":False},"prompts":{"listChanged":False},"logging":{}},"serverInfo":{"name":"ai-infrastructure-lab","version":"1.0"}}
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `MCPServer._initialize` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 7. Which decisions belong in the platform versus the application team, and why?

**Staff/Principal answer.** The platform owns transports, identity, discovery, protocol/version conformance, schemas, budgets, telemetry, and cancellation. Agent/application teams own skill semantics, tool implementations, artifact meaning, compensations, and delegation policy.

**Implementation evidence.** [`ailab/protocols.py · A2AServer.agent_card`](../../ailab/protocols.py) is the concrete control point used by this project:

```python
def agent_card(self)->dict:
  return {"name":self.card.name,"description":self.card.description,"version":self.card.version,"supportedInterfaces":[{"url":self.card.url,"protocolBinding":"HTTP+JSON","protocolVersion":self.card.protocol_version}],"capabilities":{"streaming":self.card.streaming},"defaultInputModes":["text/plain"],"defaultOutputModes":["application/json"],"skills":[asdict(x) for x in self.card.skills]}
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `A2AServer.agent_card` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

## Commands and evidence

Activate this project's `.venv`, run its CLI and project test file from `COMMANDS.md`, then inspect the matching `artifacts/project-*` report. The environment is a non-editable wheel snapshot so another project's installation cannot silently change this project.
