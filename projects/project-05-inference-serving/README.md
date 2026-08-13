# Project 5 Environment
```bash
python3 scripts/bootstrap_project_env.py projects/project-05-inference-serving --rebuild
source projects/project-05-inference-serving/.venv/bin/activate
python -m ailab.inference_cli --requests 40 --batch-size 8
python -m pytest -q tests/test_inference_server.py
deactivate
```
