# Project 11 Environment
```bash
python3 scripts/bootstrap_project_env.py projects/project-11-security --rebuild
source projects/project-11-security/.venv/bin/activate
python -m ailab.security_cli
python -m pytest -q tests/test_security_guardrails.py
deactivate
```
