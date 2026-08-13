# Project 2 Isolated Environment

```bash
python3 scripts/bootstrap_project_env.py projects/project-02-agent-runtime --rebuild
source projects/project-02-agent-runtime/.venv/bin/activate
python -m ailab.agent_cli --help
python -m pytest -q tests/test_agent_runtime.py
deactivate
```

The environment contains a non-editable wheel snapshot. Re-run the bootstrap command only when intentionally updating this project's installed code.
