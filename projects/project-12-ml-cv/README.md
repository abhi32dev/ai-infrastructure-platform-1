# Project 12 Environment
```bash
python3 scripts/bootstrap_project_env.py projects/project-12-ml-cv --rebuild
source projects/project-12-ml-cv/.venv/bin/activate
python -m ailab.ml_cli
python -m pytest -q tests/test_ml_lifecycle.py
deactivate
```
