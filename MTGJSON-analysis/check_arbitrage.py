#!/usr/bin/env python3
"""Compatibility wrapper for the canonical backend arbitrage checker."""

from pathlib import Path
import runpy


def main() -> None:
    target = (
        Path(__file__).resolve().parents[1]
        / "backend"
        / "compute"
        / "MTGJSON-analysis"
        / "check_arbitrage.py"
    )
    runpy.run_path(str(target), run_name="__main__")


if __name__ == "__main__":
    main()
