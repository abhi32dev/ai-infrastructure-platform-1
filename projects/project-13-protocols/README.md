# MCP and A2A Protocol Lab Environment
```bash
python3 scripts/bootstrap_project_env.py projects/project-13-protocols --rebuild
source projects/project-13-protocols/.venv/bin/activate
python -m ailab.protocol_cli --data /tmp/ailab-protocol-demo
python -m pytest -q tests/test_protocols.py
deactivate
```
