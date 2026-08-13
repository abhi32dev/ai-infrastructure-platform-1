# Comprehensive Command Runbook

Run commands from the repository root:

```bash
cd /Users/abhi/Documents/Codex/ai-infrastructure-lab
```

Commands use Python 3.11+ and do not require paid APIs unless explicitly stated.

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

## Git status and history

```bash
git status --short --branch
git log --oneline --decorate -10
```

