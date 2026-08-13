# Project 7 Environment
```bash
python3 scripts/bootstrap_project_env.py projects/project-07-recommendations --rebuild
source projects/project-07-recommendations/.venv/bin/activate
python -m ailab.recommendation_cli --user learner
python -m pytest -q tests/test_recommendations.py
deactivate
```
