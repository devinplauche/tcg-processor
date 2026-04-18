import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from secret_hygiene import find_secret_patterns


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


def test_secret_scanner_flags_common_secret_patterns():
    """Catch obvious credentials before they land in git history."""
    openai_sample = "OPENAI_API_KEY=\"" + "sk-" + "1234567890abcdefghijklmnop" + "\""
    github_sample = "github_token=" + "gh" + "p_" + "1234567890abcdefghijklmnopqrstuvwxyzAB"
    aws_sample = "aws_secret_access_key = " + "abcdefghijklmnopqrstuvwxyz1234567890ABCD"
    private_key_sample = "-----BEGIN " + "PRIVATE KEY-----"

    text = "\n".join(
        [
            openai_sample,
            github_sample,
            aws_sample,
            private_key_sample,
        ]
    )

    findings = find_secret_patterns("example.env", text)

    assert [finding.pattern_name for finding in findings] == [
        "OpenAI API key",
        "GitHub token",
        "AWS secret key assignment",
        "Private key block",
    ]


def test_secret_scanner_ignores_empty_values_and_comments():
    """Allow checked-in templates with blank placeholders."""
    text = "\n".join(
        [
            "# FLASK_SECRET_KEY=replace-me-locally",
            "OPENAI_API_KEY=",
            "client_secret = ''",
            "password = \"\"",
        ]
    )

    assert find_secret_patterns("frontend/mtg-inventory/.env.example", text) == []
