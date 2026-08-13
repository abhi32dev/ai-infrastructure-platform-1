# Per-Project Environment Isolation

Every project owns a virtual environment at `projects/<project-name>/.venv`. Virtual environments are intentionally excluded from Git because they contain machine-specific absolute paths. Each project instead commits:

- `requirements-dev.txt`: direct dependencies pinned to exact versions
- `installed-freeze.txt`: complete installed dependency snapshot
- `environment-manifest.json`: Python version, absolute environment path, install mode, Git revision, and wheel hash
- `README.md`: activation, smoke-test, and project-test commands
- `smoke-module.txt`: module checked after installation

The lab package is installed as a non-editable wheel snapshot. It does not point back to repository source. Consequently, editing a later project does not silently change an earlier environment. Updating a project's installed snapshot is an explicit bootstrap operation.

## Create or intentionally refresh an environment

```bash
python3 scripts/bootstrap_project_env.py projects/project-01-rag --rebuild
```

## Activate one project

```bash
source projects/project-01-rag/.venv/bin/activate
python -m ailab.cli --help
deactivate
```

Only one environment should be active in a shell. Activation changes `PATH`; it does not launch a background process. Persistent services for later projects will have project-specific Compose names, ports, volumes, and environment files.

## Verify isolation

```bash
python3 scripts/verify_project_envs.py
```

The verifier runs outside the repository working directory and proves each import resolves from that project's `.venv/site-packages`, not the mutable repository checkout.

