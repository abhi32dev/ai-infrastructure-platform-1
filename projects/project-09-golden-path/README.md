# Project 9 Environment
```bash
python3 scripts/bootstrap_project_env.py projects/project-09-golden-path --rebuild
source projects/project-09-golden-path/.venv/bin/activate
python -m ailab.golden_path_cli demo-service --output /tmp/ailab-services
python -m pytest -q tests/test_golden_path.py
deactivate
```
