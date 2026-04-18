#!/usr/bin/env python3
"""Bootstrap local developer defaults for the repo."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_ENV = REPO_ROOT / "frontend" / "mtg-inventory" / ".env.example"
LOCAL_ENV = REPO_ROOT / "frontend" / "mtg-inventory" / ".env.local"
HOOKS_PATH = ".githooks"


def _run_git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def ensure_env_local() -> str:
    if LOCAL_ENV.exists():
        return f"Skipped {LOCAL_ENV.relative_to(REPO_ROOT)} because it already exists."

    LOCAL_ENV.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(EXAMPLE_ENV, LOCAL_ENV)
    return f"Created {LOCAL_ENV.relative_to(REPO_ROOT)} from {EXAMPLE_ENV.relative_to(REPO_ROOT)}."


def ensure_repo_hooks() -> str:
    proc = _run_git("config", "--local", "core.hooksPath", HOOKS_PATH)
    if proc.returncode != 0:
        stderr = proc.stderr.strip() or "git config failed"
        raise RuntimeError(stderr)
    return f"Configured git hooks path to {HOOKS_PATH}."


def main() -> int:
    if not EXAMPLE_ENV.exists():
        print(f"setup-dev: missing template file {EXAMPLE_ENV}", file=sys.stderr)
        return 1

    try:
        print(ensure_env_local())
        print(ensure_repo_hooks())
    except RuntimeError as exc:
        print(f"setup-dev: {exc}", file=sys.stderr)
        return 1

    print("Local setup is ready. Fill in frontend/mtg-inventory/.env.local before running live integrations.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
