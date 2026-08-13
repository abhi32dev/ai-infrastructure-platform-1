#!/usr/bin/env python3
"""Create an isolated, non-editable environment for one project."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def execute(command: list[str], cwd: Path = ROOT) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("project", type=Path, help="Project environment directory under projects/")
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    project = args.project.resolve()
    projects_root = (ROOT / "projects").resolve()
    if project.parent != projects_root or not project.is_dir():
        raise SystemExit(f"project must be one direct child of {projects_root}")
    environment = project / ".venv"
    if args.rebuild and environment.exists():
        shutil.rmtree(environment)
    if not environment.exists():
        execute([sys.executable, "-m", "venv", str(environment)])
    python = environment / "bin" / "python"
    pip = environment / "bin" / "pip"
    requirements = project / "requirements-dev.txt"
    if requirements.exists():
        execute([str(pip), "install", "--disable-pip-version-check", "-r", str(requirements)])
    with tempfile.TemporaryDirectory(prefix="ailab-wheel-") as temporary:
        wheel_dir = Path(temporary)
        execute([str(pip), "wheel", "--no-deps", "--no-build-isolation", "--wheel-dir", str(wheel_dir), str(ROOT)])
        wheel = next(wheel_dir.glob("*.whl"))
        execute([str(pip), "install", "--force-reinstall", "--no-deps", str(wheel)])
        wheel_hash = hashlib.sha256(wheel.read_bytes()).hexdigest()
    smoke_module = (project / "smoke-module.txt").read_text().strip()
    execute([str(python), "-c", f"import {smoke_module}; print({smoke_module}.__file__)"] , cwd=Path("/tmp"))
    freeze = subprocess.run([str(pip), "freeze", "--all"], text=True, capture_output=True, check=True).stdout
    (project / "installed-freeze.txt").write_text(freeze)
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project": project.name,
        "python": subprocess.run([str(python), "--version"], text=True, capture_output=True, check=True).stdout.strip(),
        "environment": str(environment.relative_to(ROOT)),
        "install_mode": "non-editable wheel snapshot",
        "wheel_sha256": wheel_hash,
        "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True, check=True).stdout.strip(),
    }
    (project / "environment-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
