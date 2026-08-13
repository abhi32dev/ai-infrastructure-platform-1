# Project 8 Environment
```bash
python3 scripts/bootstrap_project_env.py projects/project-08-batch-platform --rebuild
source projects/project-08-batch-platform/.venv/bin/activate
python -m ailab.batch_cli --items 30
python -m pytest -q tests/test_batch_platform.py
deactivate
```
