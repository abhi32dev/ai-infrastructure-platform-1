# Project 6 Environment
```bash
python3 scripts/bootstrap_project_env.py projects/project-06-streaming-features --rebuild
source projects/project-06-streaming-features/.venv/bin/activate
python -m ailab.streaming_cli --events 30
python -m pytest -q tests/test_streaming_features.py
deactivate
```
