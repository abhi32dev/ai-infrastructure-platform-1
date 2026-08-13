# Project 3 Isolated Environment

```bash
python3 scripts/bootstrap_project_env.py projects/project-03-model-gateway --rebuild
source projects/project-03-model-gateway/.venv/bin/activate
python -m ailab.gateway_cli --help
python -m pytest -q tests/test_model_gateway.py
deactivate
```

The environment contains a non-editable wheel snapshot. Re-run the bootstrap command only when intentionally updating this project's installed code.
