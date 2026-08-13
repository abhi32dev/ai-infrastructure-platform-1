# Project 10 Environment
```bash
python3 scripts/bootstrap_project_env.py projects/project-10-observability --rebuild
source projects/project-10-observability/.venv/bin/activate
python -m ailab.observability_cli
python -m pytest -q tests/test_observability.py
deactivate
```
