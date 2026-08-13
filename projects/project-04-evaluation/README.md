# Project 4 Environment
```bash
python3 scripts/bootstrap_project_env.py projects/project-04-evaluation --rebuild
source projects/project-04-evaluation/.venv/bin/activate
python -m ailab.eval_cli demo
python -m pytest -q tests/test_eval_platform.py
deactivate
```
