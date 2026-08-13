# Comprehensive Command Runbook

Run commands from the repository root:

```bash
cd /Users/abhi/Documents/Codex/ai-infrastructure-lab
```

Commands use Python 3.11+ and do not require paid APIs unless explicitly stated.

## Per-project environments

Each project has its own environment. Build once, then activate only the project being exercised:

```bash
python3 scripts/bootstrap_project_env.py projects/project-01-rag --rebuild
python3 scripts/bootstrap_project_env.py projects/project-02-agent-runtime --rebuild
python3 scripts/bootstrap_project_env.py projects/project-03-model-gateway --rebuild
python3 scripts/verify_project_envs.py
```

Activate/deactivate examples:

```bash
source projects/project-01-rag/.venv/bin/activate
python -m ailab.cli --help
deactivate

source projects/project-02-agent-runtime/.venv/bin/activate
python -m ailab.agent_cli --help
deactivate

source projects/project-03-model-gateway/.venv/bin/activate
python -m ailab.gateway_cli --help
deactivate
```

## Verify everything currently implemented

```bash
python3 scripts/verify.py
python3 -m pytest -q
```

Evidence is written to:

```text
artifacts/verification/latest.json
artifacts/verification/latest.txt
```

## Project 1 - Local RAG platform foundation

Reset, ingest, inspect, and ask through the deterministic offline provider:

```bash
python3 -m ailab.cli reset
python3 -m ailab.cli ingest examples/knowledge --chunk-size 90 --overlap 18
python3 -m ailab.cli status
python3 -m ailab.cli ask "Why are checkpoints and idempotency both needed?" --top-k 3
python3 -m ailab.cli ask "Compare lexical and dense retrieval" --top-k 3
```

Optional Ollama path after installing Ollama and pulling the model:

```bash
ollama pull qwen2.5:3b
python3 -m ailab.cli ask "Compare lexical and dense retrieval" --provider ollama
```

Expected negative case—an empty index is rejected:

```bash
python3 -m ailab.cli --db /tmp/ailab-empty.db reset
python3 -m ailab.cli --db /tmp/ailab-empty.db ask "This must fail"
```

## Project 2 - Durable agent runtime

Start a safe incident-remediation workflow. It executes read/draft steps, pauses before the high-risk action, and prints a `run_id`:

```bash
python3 -m ailab.agent_cli start --incident INC-1001
```

Use the printed ID in the commands below:

```bash
python3 -m ailab.agent_cli inspect RUN_ID
python3 -m ailab.agent_cli approve RUN_ID apply --actor abhishek --reason "Reviewed remediation plan"
python3 -m ailab.agent_cli resume RUN_ID
python3 -m ailab.agent_cli inspect RUN_ID
```

Denial path using a newly started run:

```bash
python3 -m ailab.agent_cli start --incident INC-DENY
python3 -m ailab.agent_cli deny RUN_ID apply --actor abhishek --reason "Unsafe action"
python3 -m ailab.agent_cli resume RUN_ID
```

The automated suite additionally demonstrates allowlist denial, argument validation, timeouts, retry exhaustion, dead-letter storage, checkpoint reuse, and exactly-once invocation during resume:

```bash
python3 -m pytest -q tests/test_agent_runtime.py
```

## Project 3 - Model gateway, router, and cost controller

```bash
python3 -m ailab.gateway_cli complete "Summarize this request" --tenant demo
python3 -m ailab.gateway_cli complete "Analyze architecture failure tradeoffs" --tenant demo --quality high --shadow-model medium-hosted
python3 -m ailab.gateway_cli complete "Analyze confidential architecture" --tenant private --quality high --privacy local
python3 -m ailab.gateway_cli inspect
python3 -m pytest -q tests/test_model_gateway.py
python3 scripts/verify_model_gateway.py
```

Expected negative cost-cap case:

```bash
python3 -m ailab.gateway_cli complete "Analyze architecture" --quality high --max-cost 0.000001
```

## Git status and history

## Project 7 - Recommendations and experimentation
```bash
python3 -m ailab.recommendation_cli --user learner
python3 -m pytest -q tests/test_recommendations.py
python3 scripts/verify_recommendations.py
python3 scripts/bootstrap_project_env.py projects/project-07-recommendations --rebuild
source projects/project-07-recommendations/.venv/bin/activate
python -m ailab.recommendation_cli --user learner
deactivate
```

## Project 6 - Streaming features
```bash
python3 -m ailab.streaming_cli --events 30
python3 -m pytest -q tests/test_streaming_features.py
python3 scripts/verify_streaming_features.py
python3 scripts/bootstrap_project_env.py projects/project-06-streaming-features --rebuild
source projects/project-06-streaming-features/.venv/bin/activate
python -m ailab.streaming_cli --events 30
deactivate
```

## Project 5 - Inference serving
```bash
python3 -m ailab.inference_cli --requests 40 --batch-size 8
python3 -m pytest -q tests/test_inference_server.py
python3 scripts/verify_inference_server.py
python3 scripts/bootstrap_project_env.py projects/project-05-inference-serving --rebuild
source projects/project-05-inference-serving/.venv/bin/activate
python -m ailab.inference_cli --requests 40 --batch-size 8
deactivate
```

## Project 4 - Evaluation and release gating

```bash
python3 -m ailab.eval_cli demo
python3 -m ailab.eval_cli ab-test --success-a 100 --total-a 1000 --success-b 140 --total-b 1000
python3 -m pytest -q tests/test_eval_platform.py
python3 scripts/verify_eval_platform.py
```

Isolated environment:

```bash
python3 scripts/bootstrap_project_env.py projects/project-04-evaluation --rebuild
source projects/project-04-evaluation/.venv/bin/activate
python -m ailab.eval_cli demo
deactivate
```

```bash
git status --short --branch
git log --oneline --decorate -10
```
