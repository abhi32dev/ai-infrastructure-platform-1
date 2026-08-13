from __future__ import annotations
import json,re
from dataclasses import dataclass
from pathlib import Path

class ScaffoldError(RuntimeError):pass
@dataclass(frozen=True)
class ServiceConfig:name:str;port:int=8080;owner:str="ai-platform";environment:str="dev";tenant_header:str="X-Tenant-ID"

class GoldenPath:
 def generate(self,root:Path,config:ServiceConfig)->Path:
  if not re.fullmatch(r"[a-z][a-z0-9-]{2,40}",config.name):raise ValueError("service name must be lowercase kebab-case")
  if not 1024<=config.port<=65535:raise ValueError("port must be non-privileged")
  target=root/config.name
  if target.exists() and any(target.iterdir()):raise ScaffoldError("target already exists and is not empty")
  files=self._files(config)
  for relative,content in files.items():path=target/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(content)
  return target
 def validate(self,target:Path)->dict:
  required=["app/main.py","tests/test_health.py","Dockerfile","k8s/deployment.yaml","k8s/service.yaml","k8s/network-policy.yaml","terraform/main.tf",".github/workflows/ci.yml","CODEOWNERS","observability/slo.json","security/iam-policy.json","environments/dev.env","environments/test.env","environments/stage.env","environments/prod.env"]
  missing=[x for x in required if not (target/x).exists()];violations=[]
  if not missing:
   docker=(target/"Dockerfile").read_text();deployment=(target/"k8s/deployment.yaml").read_text();policy=json.loads((target/"security/iam-policy.json").read_text());workflow=(target/".github/workflows/ci.yml").read_text()
   if "USER app" not in docker:violations.append("container_runs_as_root")
   if "readOnlyRootFilesystem: true" not in deployment:violations.append("writable_root_filesystem")
   if "resources:" not in deployment:violations.append("missing_resource_limits")
   if any(statement.get("Action")=="*" or statement.get("Resource")=="*" for statement in policy["Statement"]):violations.append("wildcard_iam")
   if not all(stage in workflow for stage in ("pytest","pip-audit","docker build")):violations.append("incomplete_ci_gates")
  return {"valid":not missing and not violations,"missing":missing,"violations":violations,"files":sum(1 for p in target.rglob("*") if p.is_file())}
 def _files(self,c:ServiceConfig)->dict[str,str]:
  env=lambda name:f"SERVICE_NAME={c.name}\nENVIRONMENT={name}\nPORT={c.port}\nTENANT_HEADER={c.tenant_header}\n"
  return {
"app/main.py":f'''import json,os\nfrom http.server import BaseHTTPRequestHandler,HTTPServer\nclass Handler(BaseHTTPRequestHandler):\n def do_GET(self):\n  code=200 if self.path in ("/health/live","/health/ready") else 404\n  body={{"service":"{c.name}","path":self.path,"status":"ok" if code==200 else "not_found"}}\n  self.send_response(code);self.send_header("Content-Type","application/json");self.end_headers();self.wfile.write(json.dumps(body).encode())\nif __name__=="__main__":HTTPServer(("0.0.0.0",int(os.getenv("PORT","{c.port}"))),Handler).serve_forever()\n''',
"tests/test_health.py":'''from app.main import Handler\ndef test_handler_exists(): assert Handler is not None\n''',
"requirements.txt":"# dependency-free service\n",
"Dockerfile":f'''FROM python:3.11-slim\nRUN useradd --create-home app\nWORKDIR /app\nCOPY app app\nUSER app\nEXPOSE {c.port}\nCMD ["python","-m","app.main"]\n''',
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
