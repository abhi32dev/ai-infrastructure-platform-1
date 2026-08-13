# Project 1 Isolated Environment

```bash
python3 scripts/bootstrap_project_env.py projects/project-01-rag --rebuild
source projects/project-01-rag/.venv/bin/activate
python -m ailab.cli --help
python -m pytest -q tests/test_lab.py
deactivate
```

The environment contains a non-editable wheel snapshot. Re-run the bootstrap command only when intentionally updating this project's installed code.
