# Production reasoning — Platform golden path

## Why this project exists

Secure defaults must be generated, validated and upgradeable without blocking legitimate escape hatches. This project is deliberately small enough to execute locally but preserves the decision points that dominate production incidents and staff-level design reviews.

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

- invalid names and ports
- existing target collision
- missing generated files
- root/writable container
- missing limits/probes
- wildcard IAM
- incomplete CI gates
- Compose and Kubernetes validation

Tests use deterministic clocks, seeded data, temporary directories and local stores where possible. This avoids flaky CI. Live cloud/model/GPU tests belong in a separate opt-in suite because availability, cost and credentials would otherwise make the default suite non-reproducible.

## Design choice and trade-off

Generation accelerates adoption; policy validation is still required because templates inevitably drift.

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

**Staff/Principal answer.** A generated workload with excessive privilege or missing resource bounds creates fleet-wide security and availability exposure. Secure defaults and validation are therefore harder requirements than template convenience.

**Implementation evidence.** [`ailab/golden_path.py · GoldenPath.validate`](../../ailab/golden_path.py) is the concrete control point used by this project:

```python
def validate(self,target:Path)->dict:
  required=["app/main.py","tests/test_health.py","Dockerfile","compose.yaml","k8s/deployment.yaml","k8s/service.yaml","k8s/network-policy.yaml","terraform/main.tf",".github/workflows/ci.yml","CODEOWNERS","observability/slo.json","security/iam-policy.json","environments/dev.env","environments/test.env","environments/stage.env","environments/prod.env"]
  missing=[x for x in required if not (target/x).exists()];violations=[]
  if not missing:
   docker=(target/"Dockerfile").read_text();deployment=(target/"k8s/deployment.yaml").read_text();policy=json.loads((target/"security/iam-policy.json").read_text());workflow=(target/".github/workflows/ci.yml").read_text()
   if "USER app" not in docker:violations.append("container_runs_as_root")
   if "readOnlyRootFilesystem: true" not in deployment:violations.append("writable_root_filesystem")
   if "resources:" not in deployment:violations.append("missing_resource_limits")
   if any(statement.get("Action")=="*" or statement.get("Resource")=="*" for statement in policy["Statement"]):violations.append("wildcard_iam")
   if not all(stage in workflow for stage in ("pytest","pip-audit","docker build")):violations.append("incomplete_ci_gates")
  return {"valid":not missing and not violations,"missing":missing,"violations":violations,"files":sum(1 for p in target.rglob("*") if p.is_file())}
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `GoldenPath.validate` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 2. Where is the linearization point for an idempotent mutation?

**Staff/Principal answer.** Generation linearizes when the complete scaffold is written to a previously non-conflicting service directory. Existing targets are rejected so a second invocation cannot partially overwrite user-owned changes.

**Implementation evidence.** [`ailab/golden_path.py · GoldenPath.generate`](../../ailab/golden_path.py) is the concrete control point used by this project:

```python
def generate(self,root:Path,config:ServiceConfig)->Path:
  if not re.fullmatch(r"[a-z][a-z0-9-]{2,40}",config.name):raise ValueError("service name must be lowercase kebab-case")
  if not 1024<=config.port<=65535:raise ValueError("port must be non-privileged")
  target=root/config.name
  if target.exists() and any(target.iterdir()):raise ScaffoldError("target already exists and is not empty")
  files=self._files(config)
  for relative,content in files.items():path=target/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(content)
  return target
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `GoldenPath.generate` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 3. Which state is authoritative during disagreement, and how is reconciliation bounded?

**Staff/Principal answer.** The checked-in generated service repository is authoritative for deployed intent; the template is a starting version, not ongoing truth. Reconciliation is a bounded policy scan and explicit upgrade diff, never an automatic overwrite.

**Implementation evidence.** [`ailab/golden_path.py · GoldenPath.validate`](../../ailab/golden_path.py) is the concrete control point used by this project:

```python
def validate(self,target:Path)->dict:
  required=["app/main.py","tests/test_health.py","Dockerfile","compose.yaml","k8s/deployment.yaml","k8s/service.yaml","k8s/network-policy.yaml","terraform/main.tf",".github/workflows/ci.yml","CODEOWNERS","observability/slo.json","security/iam-policy.json","environments/dev.env","environments/test.env","environments/stage.env","environments/prod.env"]
  missing=[x for x in required if not (target/x).exists()];violations=[]
  if not missing:
   docker=(target/"Dockerfile").read_text();deployment=(target/"k8s/deployment.yaml").read_text();policy=json.loads((target/"security/iam-policy.json").read_text());workflow=(target/".github/workflows/ci.yml").read_text()
   if "USER app" not in docker:violations.append("container_runs_as_root")
   if "readOnlyRootFilesystem: true" not in deployment:violations.append("writable_root_filesystem")
   if "resources:" not in deployment:violations.append("missing_resource_limits")
   if any(statement.get("Action")=="*" or statement.get("Resource")=="*" for statement in policy["Statement"]):violations.append("wildcard_iam")
   if not all(stage in workflow for stage in ("pytest","pip-audit","docker build")):violations.append("incomplete_ci_gates")
  return {"valid":not missing and not violations,"missing":missing,"violations":violations,"files":sum(1 for p in target.rglob("*") if p.is_file())}
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `GoldenPath.validate` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 4. What does graceful degradation preserve, and what must fail closed?

**Staff/Principal answer.** Optional observability or convenience integrations can be omitted with explicit findings. Non-root execution, least-privilege IAM, network policy, probes, limits, and deployment gates fail closed in validation.

**Implementation evidence.** [`ailab/golden_path.py · GoldenPath._files`](../../ailab/golden_path.py) is the concrete control point used by this project:

```python
def _files(self,c:ServiceConfig)->dict[str,str]:
  env=lambda name:f"SERVICE_NAME={c.name}\nENVIRONMENT={name}\nPORT={c.port}\nTENANT_HEADER={c.tenant_header}\n"
  return {
"app/main.py":f'''import json,os\nfrom http.server import BaseHTTPRequestHandler,HTTPServer\nclass Handler(BaseHTTPRequestHandler):\n def do_GET(self):\n  code=200 if self.path in ("/health/live","/health/ready") else 404\n  body={{"service":"{c.name}","path":self.path,"status":"ok" if code==200 else "not_found"}}\n  self.send_response(code);self.send_header("Content-Type","application/json");self.end_headers();self.wfile.write(json.dumps(body).encode())\nif __name__=="__main__":HTTPServer(("0.0.0.0",int(os.getenv("PORT","{c.port}"))),Handler).serve_forever()\n''',
"tests/test_health.py":'''from app.main import Handler\ndef test_handler_exists(): assert Handler is not None\n''',
"requirements.txt":"# dependency-free service\n",
"Dockerfile":f'''FROM python:3.11-slim\nRUN useradd --create-home app\nWORKDIR /app\nCOPY app app\nUSER app\nEXPOSE {c.port}\nCMD ["python","-m","app.main"]\n''',
"compose.yaml":f'''services:\n  app:\n    build: .\n    ports: ["{c.port}:{c.port}"]\n    environment: {{PORT: "{c.port}"}}\n    read_only: true\n    user: app\n    healthcheck:\n      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:{c.port}/health/ready')"]\n      interval: 10s\n      timeout: 2s\n      retries: 3\n''',
"k8s/deployment.yaml":f'''apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: {c.name}\nspec:\n  replicas: 2\n  selector:\n    matchLabels:\n      app: {c.name}\n  template:\n    metadata:\n      labels:\n        app: {c.name}\n    spec:\n      serviceAccountName: {c.name}\n      containers:\n      - name: app\n        image: {c.name}:latest\n        ports:\n        - containerPort: {c.port}\n        readinessProbe:\n          httpGet:\n            path: /health/ready\n            port: {c.port}\n        livenessProbe:\n          httpGet:\n            path: /health/live\n            port: {c.port}\n        securityContext:\n          runAsNonRoot: true\n          readOnlyRootFilesystem: true\n          allowPrivilegeEscalation: false\n        resources:\n          requests:\n            cpu: 100m\n            memory: 128Mi\n          limits:\n            cpu: 500m\n            memory: 512Mi\n''',
"k8s/service.yaml":f'''apiVersion: v1\nkind: Service\nmetadata:\n  name: {c.name}\nspec:\n  selector:\n    app: {c.name}\n  ports:\n  - port: 80\n    targetPort: {c.port}\n''',
"k8s/network-policy.yaml":f'''apiVersion: networking.k8s.io/v1\nkind: NetworkPolicy\nmetadata:\n  name: {c.name}-default-deny\nspec:\n  podSelector:\n    matchLabels:\n      app: {c.name}\n  policyTypes:\n  - Ingress\n  - Egress\n  ingress: []\n  egress:\n  - to:\n    - namespaceSelector: {{}}\n''',
"terraform/main.tf":'''terraform { required_version = ">= 1.6" }\nvariable "environment" { type=string validation { condition=contains(["dev","test","stage","prod"],var.environment) error_message="invalid environment" } }\nvariable "service_name" { type=string }\noutput "qualified_name" { value="${var.service_name}-${var.environment}" }\n''',
".github/workflows/ci.yml":'''name: ci\non: [push, pull_request]\njobs:\n  validate:\n    runs-on: ubuntu-latest\n    steps:\n    - uses: actions/checkout@v4\n    - uses: actions/setup-python@v5\n      with: {python-version: "3.11"}\n    - run: pip install pytest pip-audit\n    - run: pytest\n    - run: pip-audit -r requirements.txt\n    - run: docker build -t service:${{ github.sha }} .\n''',
"CODEOWNERS":f"* @{c.owner}\nsecurity/ @{c.owner}\nk8s/ @{c.owner}\n",
"observability/slo.json":json.dumps({"availability":.999,"p95_latency_ms":250,"error_budget_window_days":30,"signals":["requests","errors","latency","saturation"]},indent=2)+"\n",
"security/iam-policy.json":json.dumps({"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":["logs:CreateLogStream","logs:PutLogEvents"],"Resource":f"arn:aws:logs:*:*:log-group:/services/{c.name}:*"}]},indent=2)+"\n",
"environments/dev.env":env("dev"),"environments/test.env":env("test"),"environments/stage.env":env("stage"),"environments/prod.env":env("prod"),
"README.md":f"# {c.name}\n\nGenerated by the AI Platform golden path. Health endpoints: `/health/live`, `/health/ready`.\n"
  }
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `GoldenPath._files` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 5. Which metrics detect correctness loss before customers report it?

**Staff/Principal answer.** Measure adoption, generation success, policy-pass rate, exception age, upgrade lag, deployment lead time, rollback rate, vulnerability findings, resource-limit violations, and SLO coverage across generated services.

**Implementation evidence.** [`ailab/golden_path.py · GoldenPath.validate`](../../ailab/golden_path.py) is the concrete control point used by this project:

```python
def validate(self,target:Path)->dict:
  required=["app/main.py","tests/test_health.py","Dockerfile","compose.yaml","k8s/deployment.yaml","k8s/service.yaml","k8s/network-policy.yaml","terraform/main.tf",".github/workflows/ci.yml","CODEOWNERS","observability/slo.json","security/iam-policy.json","environments/dev.env","environments/test.env","environments/stage.env","environments/prod.env"]
  missing=[x for x in required if not (target/x).exists()];violations=[]
  if not missing:
   docker=(target/"Dockerfile").read_text();deployment=(target/"k8s/deployment.yaml").read_text();policy=json.loads((target/"security/iam-policy.json").read_text());workflow=(target/".github/workflows/ci.yml").read_text()
   if "USER app" not in docker:violations.append("container_runs_as_root")
   if "readOnlyRootFilesystem: true" not in deployment:violations.append("writable_root_filesystem")
   if "resources:" not in deployment:violations.append("missing_resource_limits")
   if any(statement.get("Action")=="*" or statement.get("Resource")=="*" for statement in policy["Statement"]):violations.append("wildcard_iam")
   if not all(stage in workflow for stage in ("pytest","pip-audit","docker build")):violations.append("incomplete_ci_gates")
  return {"valid":not missing and not violations,"missing":missing,"violations":violations,"files":sum(1 for p in target.rglob("*") if p.is_file())}
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `GoldenPath.validate` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 6. What changes at 10× traffic, 100× data, multiple regions or adversarial tenants?

**Staff/Principal answer.** Version templates and policies independently, provide automated upgrade pull requests, distribute validation, and cache immutable dependencies. Multi-region adds environment overlays; adversarial teams require signed provenance and exception governance.

**Implementation evidence.** [`ailab/golden_path.py · GoldenPath.generate`](../../ailab/golden_path.py) is the concrete control point used by this project:

```python
def generate(self,root:Path,config:ServiceConfig)->Path:
  if not re.fullmatch(r"[a-z][a-z0-9-]{2,40}",config.name):raise ValueError("service name must be lowercase kebab-case")
  if not 1024<=config.port<=65535:raise ValueError("port must be non-privileged")
  target=root/config.name
  if target.exists() and any(target.iterdir()):raise ScaffoldError("target already exists and is not empty")
  files=self._files(config)
  for relative,content in files.items():path=target/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(content)
  return target
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `GoldenPath.generate` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

### 7. Which decisions belong in the platform versus the application team, and why?

**Staff/Principal answer.** The platform owns secure baseline controls, supported deployment patterns, validation, lifecycle upgrades, and exception workflow. Application teams own service code, business SLOs, resource tuning, data policy, and reviewed deviations.

**Implementation evidence.** [`ailab/golden_path.py · GoldenPath._files`](../../ailab/golden_path.py) is the concrete control point used by this project:

```python
def _files(self,c:ServiceConfig)->dict[str,str]:
  env=lambda name:f"SERVICE_NAME={c.name}\nENVIRONMENT={name}\nPORT={c.port}\nTENANT_HEADER={c.tenant_header}\n"
  return {
"app/main.py":f'''import json,os\nfrom http.server import BaseHTTPRequestHandler,HTTPServer\nclass Handler(BaseHTTPRequestHandler):\n def do_GET(self):\n  code=200 if self.path in ("/health/live","/health/ready") else 404\n  body={{"service":"{c.name}","path":self.path,"status":"ok" if code==200 else "not_found"}}\n  self.send_response(code);self.send_header("Content-Type","application/json");self.end_headers();self.wfile.write(json.dumps(body).encode())\nif __name__=="__main__":HTTPServer(("0.0.0.0",int(os.getenv("PORT","{c.port}"))),Handler).serve_forever()\n''',
"tests/test_health.py":'''from app.main import Handler\ndef test_handler_exists(): assert Handler is not None\n''',
"requirements.txt":"# dependency-free service\n",
"Dockerfile":f'''FROM python:3.11-slim\nRUN useradd --create-home app\nWORKDIR /app\nCOPY app app\nUSER app\nEXPOSE {c.port}\nCMD ["python","-m","app.main"]\n''',
"compose.yaml":f'''services:\n  app:\n    build: .\n    ports: ["{c.port}:{c.port}"]\n    environment: {{PORT: "{c.port}"}}\n    read_only: true\n    user: app\n    healthcheck:\n      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:{c.port}/health/ready')"]\n      interval: 10s\n      timeout: 2s\n      retries: 3\n''',
"k8s/deployment.yaml":f'''apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: {c.name}\nspec:\n  replicas: 2\n  selector:\n    matchLabels:\n      app: {c.name}\n  template:\n    metadata:\n      labels:\n        app: {c.name}\n    spec:\n      serviceAccountName: {c.name}\n      containers:\n      - name: app\n        image: {c.name}:latest\n        ports:\n        - containerPort: {c.port}\n        readinessProbe:\n          httpGet:\n            path: /health/ready\n            port: {c.port}\n        livenessProbe:\n          httpGet:\n            path: /health/live\n            port: {c.port}\n        securityContext:\n          runAsNonRoot: true\n          readOnlyRootFilesystem: true\n          allowPrivilegeEscalation: false\n        resources:\n          requests:\n            cpu: 100m\n            memory: 128Mi\n          limits:\n            cpu: 500m\n            memory: 512Mi\n''',
"k8s/service.yaml":f'''apiVersion: v1\nkind: Service\nmetadata:\n  name: {c.name}\nspec:\n  selector:\n    app: {c.name}\n  ports:\n  - port: 80\n    targetPort: {c.port}\n''',
"k8s/network-policy.yaml":f'''apiVersion: networking.k8s.io/v1\nkind: NetworkPolicy\nmetadata:\n  name: {c.name}-default-deny\nspec:\n  podSelector:\n    matchLabels:\n      app: {c.name}\n  policyTypes:\n  - Ingress\n  - Egress\n  ingress: []\n  egress:\n  - to:\n    - namespaceSelector: {{}}\n''',
"terraform/main.tf":'''terraform { required_version = ">= 1.6" }\nvariable "environment" { type=string validation { condition=contains(["dev","test","stage","prod"],var.environment) error_message="invalid environment" } }\nvariable "service_name" { type=string }\noutput "qualified_name" { value="${var.service_name}-${var.environment}" }\n''',
".github/workflows/ci.yml":'''name: ci\non: [push, pull_request]\njobs:\n  validate:\n    runs-on: ubuntu-latest\n    steps:\n    - uses: actions/checkout@v4\n    - uses: actions/setup-python@v5\n      with: {python-version: "3.11"}\n    - run: pip install pytest pip-audit\n    - run: pytest\n    - run: pip-audit -r requirements.txt\n    - run: docker build -t service:${{ github.sha }} .\n''',
"CODEOWNERS":f"* @{c.owner}\nsecurity/ @{c.owner}\nk8s/ @{c.owner}\n",
"observability/slo.json":json.dumps({"availability":.999,"p95_latency_ms":250,"error_budget_window_days":30,"signals":["requests","errors","latency","saturation"]},indent=2)+"\n",
"security/iam-policy.json":json.dumps({"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":["logs:CreateLogStream","logs:PutLogEvents"],"Resource":f"arn:aws:logs:*:*:log-group:/services/{c.name}:*"}]},indent=2)+"\n",
"environments/dev.env":env("dev"),"environments/test.env":env("test"),"environments/stage.env":env("stage"),"environments/prod.env":env("prod"),
"README.md":f"# {c.name}\n\nGenerated by the AI Platform golden path. Health endpoints: `/health/live`, `/health/ready`.\n"
  }
```

**How to defend this in an interview.** State the invariant and failure impact first, identify `GoldenPath._files` as the enforcement or evidence boundary, then explain the local-to-production substitution without claiming the lab proves distributed scale.

## Commands and evidence

Activate this project's `.venv`, run its CLI and project test file from `COMMANDS.md`, then inspect the matching `artifacts/project-*` report. The environment is a non-editable wheel snapshot so another project's installation cannot silently change this project.
