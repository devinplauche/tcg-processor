import shutil
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _run_git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_git_is_available():
    """Security checks require git metadata; fail fast if unavailable."""
    assert shutil.which("git"), "git is required for secret-hygiene checks"


def test_env_files_not_tracked():
    """Prevent accidental commit of local secret files."""
    env_files = [
        "frontend/mtg-inventory/.env",
        "frontend/mtg-inventory/.env.local",
    ]
    for file_path in env_files:
        proc = _run_git("ls-files", file_path)
        assert proc.returncode == 0
        assert not proc.stdout.strip(), f"{file_path} must not be tracked by git"


def test_env_files_are_ignored():
    """Ensure local env files are protected by ignore rules."""
    env_files = [
        "frontend/mtg-inventory/.env",
        "frontend/mtg-inventory/.env.local",
    ]
    for file_path in env_files:
        proc = _run_git("check-ignore", file_path)
        assert proc.returncode == 0, f"{file_path} should be ignored by git"