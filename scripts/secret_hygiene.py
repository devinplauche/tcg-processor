#!/usr/bin/env python3
"""Shared secret-hygiene helpers for local hooks and CI tests."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXCLUDED_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".pdf",
    ".zip",
    ".gz",
    ".jar",
    ".db",
    ".sqlite",
    ".sqlite3",
    ".pyc",
}


@dataclass(frozen=True)
class SecretPattern:
    name: str
    regex: re.Pattern[str]


SECRET_PATTERNS: Sequence[SecretPattern] = (
    SecretPattern(
        "AWS access key",
        re.compile(r"AKIA[0-9A-Z]{16}"),
    ),
    SecretPattern(
        "AWS secret key assignment",
        re.compile(r"(?i)aws(.{0,20})?(secret|access).{0,20}[:=].{0,5}[A-Za-z0-9/+=]{40}"),
    ),
    SecretPattern(
        "GitHub token",
        re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,255}\b"),
    ),
    SecretPattern(
        "GitHub fine-grained token",
        re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,255}\b"),
    ),
    SecretPattern(
        "OpenAI API key",
        re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    ),
    SecretPattern(
        "Stripe live secret key",
        re.compile(r"\bsk_live_[A-Za-z0-9]{16,}\b"),
    ),
    SecretPattern(
        "Slack token",
        re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,200}\b"),
    ),
    SecretPattern(
        "Private key block",
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    ),
    SecretPattern(
        "Generic secret assignment",
        re.compile(
            r"(?i)\b[A-Z0-9_-]*(api[_-]?key|secret|token|password|client[_-]?secret)[A-Z0-9_-]*\b\s*[:=]\s*['\"]?[A-Za-z0-9_\-/+=]{16,}['\"]?"
        ),
    ),
)


@dataclass(frozen=True)
class ScanFinding:
    path: str
    line_number: int
    pattern_name: str
    line: str


def _run_git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def get_staged_text_files() -> list[str]:
    diff_proc = _run_git("diff", "--cached", "--name-only", "--diff-filter=ACMR")
    if diff_proc.returncode != 0:
        raise RuntimeError(diff_proc.stderr.strip() or "Unable to list staged files.")

    files: list[str] = []
    for raw_path in diff_proc.stdout.splitlines():
        path = raw_path.strip()
        if not path:
            continue
        if Path(path).suffix.lower() in DEFAULT_EXCLUDED_SUFFIXES:
            continue
        files.append(path)
    return files


def get_staged_file_text(path: str) -> str:
    show_proc = _run_git("show", f":{path}")
    if show_proc.returncode != 0:
        raise RuntimeError(show_proc.stderr.strip() or f"Unable to read staged contents for {path}.")
    return show_proc.stdout


def find_secret_patterns(path: str, text: str) -> list[ScanFinding]:
    findings: list[ScanFinding] = []

    def _is_placeholder_assignment(line: str) -> bool:
        if "=" in line:
            _, value = line.split("=", 1)
        elif ":" in line:
            _, value = line.split(":", 1)
        else:
            return False

        token = value.strip().strip("'\"").lower()
        placeholder_markers = (
            "your_",
            "your-",
            "placeholder",
            "replace",
            "example",
            "_here",
            "_configured_secret",
            "xxxx",
            "xxxxx",
        )
        if any(marker in token for marker in placeholder_markers):
            return True
        if token.startswith("<") and token.endswith(">"):
            return True
        if token and all(ch in "xX-" for ch in token):
            return True
        return False

    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        for pattern in SECRET_PATTERNS:
            if pattern.regex.search(line):
                if pattern.name == "Generic secret assignment" and _is_placeholder_assignment(line):
                    break
                findings.append(
                    ScanFinding(
                        path=path,
                        line_number=line_number,
                        pattern_name=pattern.name,
                        line=line.strip(),
                    )
                )
                break
    return findings


def scan_paths(paths: Iterable[str]) -> list[ScanFinding]:
    findings: list[ScanFinding] = []
    for path in paths:
        findings.extend(find_secret_patterns(path, get_staged_file_text(path)))
    return findings


def format_findings(findings: Sequence[ScanFinding]) -> str:
    lines = ["Potential secrets found in staged changes:"]
    for finding in findings:
        lines.append(
            f"- {finding.path}:{finding.line_number} matched {finding.pattern_name}: {finding.line}"
        )
    lines.append("Move secrets to local env files or your secret manager before committing.")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scan staged changes for common secret patterns.")
    parser.parse_args(argv)

    try:
        paths = get_staged_text_files()
        findings = scan_paths(paths)
    except RuntimeError as exc:
        print(f"secret-hygiene: {exc}", file=sys.stderr)
        return 2

    if findings:
        print(format_findings(findings), file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
