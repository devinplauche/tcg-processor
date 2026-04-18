#!/usr/bin/env python3
"""
Scan MTG card images using LangChain + Ollama vision (qwen3-vl:8b) and export to CSV.

Usage:
    python langchain_scan_cards.py                           # defaults: cropped v5 folder
    python langchain_scan_cards.py --input-dir ./my_images
    python langchain_scan_cards.py --output-csv my_results.csv --resume
    python langchain_scan_cards.py --limit 10                # quick test run
"""
from __future__ import annotations

import argparse
import base64
import csv
import json
import re as _re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from langchain_core.messages import HumanMessage
from langchain_ollama import ChatOllama
from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent
_DEFAULT_INPUT = _SCRIPT_DIR / "google_drive_downloads_cropped_v5"
_DEFAULT_OUTPUT = _SCRIPT_DIR / "ollama_scan_results.csv"
_PROGRESS_FILE = _SCRIPT_DIR / "ollama_scan_progress.json"
_OLLAMA_URL = "http://localhost:11434"
_MODEL = "qwen3-vl:8b"
_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

_PROMPT = (
    "You are an expert Magic: The Gathering card identifier. "
    "Examine the card image carefully, paying attention to the card name at the top, "
    "set symbol, mana cost, type line, and any text in the bottom-right corner. "
    "Respond ONLY with a valid JSON object — no prose, no markdown fences: "
    '{"card_name":"exact name from top of card","set_name":"full set name","set_code":"3-letter code",'
    '"colors":["W"|"U"|"B"|"R"|"G" or []],"mana_cost":"e.g. {2}{U}{U}","type_line":"e.g. Creature — Dragon",'
    '"rarity":"common|uncommon|rare|mythic","power_toughness":"e.g. 5/5 or null if not creature",'
    '"confidence":0.0}  '
    'Set confidence between 0.0 (no idea) and 1.0 (certain). '
    'If you cannot read a field clearly, use null.'
)

_FALLBACK_PROMPT = (
    "Look at this Magic: The Gathering card. "
    "Read only the large card name printed at the very top of the card frame. "
    "Reply with ONLY a JSON object, nothing else: "
    '{"card_name":"name here","confidence":0.0}'
)

# CSV columns in a stable order
_CSV_FIELDS = [
    "filename",
    "card_name",
    "set_name",
    "set_code",
    "colors",
    "mana_cost",
    "type_line",
    "rarity",
    "power_toughness",
    "confidence",
    "status",
    "error",
    "timestamp",
]


# ---------------------------------------------------------------------------
# Pydantic schema for structured output
# ---------------------------------------------------------------------------

class CardIdentification(BaseModel):
    card_name: str = Field(description="Exact card name from the top of the card")
    set_name: Optional[str] = Field(default=None, description="Full expansion set name")
    set_code: Optional[str] = Field(default=None, description="3-4 letter set code")
    colors: Optional[list[str]] = Field(default=None, description="Color identity list: W, U, B, R, G")
    mana_cost: Optional[str] = Field(default=None, description="Mana cost string e.g. {2}{U}")
    type_line: Optional[str] = Field(default=None, description="Full type line e.g. Creature — Dragon")
    rarity: Optional[str] = Field(default=None, description="common|uncommon|rare|mythic")
    power_toughness: Optional[str] = Field(default=None, description="Power/toughness for creatures e.g. 5/5")
    confidence: float = Field(default=0.0, description="Confidence 0.0-1.0")

    @field_validator("colors", mode="before")
    @classmethod
    def coerce_colors(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            return [c.strip() for c in v.split(",") if c.strip()]
        return v

    @field_validator("confidence", mode="before")
    @classmethod
    def clamp_confidence(cls, v):
        try:
            return max(0.0, min(1.0, float(v)))
        except (TypeError, ValueError):
            return 0.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def build_llm(host: str, model: str, num_predict: int = 512) -> ChatOllama:
    """Construct a ChatOllama instance with thinking disabled."""
    return ChatOllama(
        model=model,
        base_url=host,
        temperature=0.1,
        num_predict=num_predict,
        # Suppress chain-of-thought tokens from qwen3-vl thinking variants
        extra_body={"think": False},
    )


def check_ollama(host: str, model: str) -> bool:
    """Verify Ollama is running and the model is available."""
    try:
        import ollama as _ollama
        client = _ollama.Client(host=host)
        models = [m.model for m in client.list().models]
        found = any(model in m for m in models)
        if not found:
            print(f"[!] Model '{model}' not found. Available: {models}")
            print(f"    Run: ollama pull {model}")
        return found
    except Exception as e:
        print(f"[!] Cannot connect to Ollama at {host}: {e}")
        print("    Make sure Ollama is running (ollama serve)")
        return False


def _extract_json(raw: str) -> str:
    """Extract the first valid JSON object from model output."""
    text = _re.sub(r"```(?:json)?\s*", "", raw)
    text = text.replace("```", "").strip()

    start = text.find("{")
    if start == -1:
        raise ValueError(f"No JSON object in response: {raw[:300]}")

    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]

    end = text.rfind("}") + 1
    if end > start:
        return text[start:end]

    raise ValueError(f"Unbalanced JSON in response: {raw[:300]}")


_MIME_MAP = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".bmp": "image/bmp",
    ".webp": "image/webp",
}


def _mime_for(path: Path) -> str:
    """Return the MIME type for an image path based on its extension."""
    return _MIME_MAP.get(path.suffix.lower(), "image/jpeg")


def _invoke_with_image(llm: ChatOllama, prompt: str, img_bytes: bytes, mime: str = "image/jpeg", debug: bool = False) -> str:
    """Send a vision request via LangChain and return the raw text response."""
    img_b64 = base64.b64encode(img_bytes).decode("utf-8")
    message = HumanMessage(
        content=[
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{img_b64}"}},
        ]
    )
    response = llm.invoke([message])
    # Strip any <think>...</think> blocks that qwen3-vl may still emit
    raw = response.content or ""
    raw = _re.sub(r"<think>.*?</think>", "", raw, flags=_re.DOTALL).strip()
    if debug:
        print(f"\n  [DEBUG] {raw[:400]}")
    return raw


def identify_card(image_path: Path, llm: ChatOllama, fallback_llm: ChatOllama, debug: bool = False) -> dict:
    """Send an image to Ollama vision via LangChain and parse the card identification."""
    img_bytes = image_path.read_bytes()
    mime = _mime_for(image_path)

    attempts = [
        (llm,          _PROMPT),
        (fallback_llm, _FALLBACK_PROMPT),
    ]

    raw_text = ""
    for attempt_num, (model_instance, prompt) in enumerate(attempts, 1):
        raw_text = _invoke_with_image(model_instance, prompt, img_bytes, mime=mime, debug=debug)
        if debug:
            print(f"  [DEBUG attempt={attempt_num}] raw length={len(raw_text)}")
        if raw_text.strip():
            break
        if debug:
            print("  [DEBUG] Empty response — retrying with fallback")

    if not raw_text.strip():
        raise ValueError("Empty response from model after all attempts")

    json_str = _extract_json(raw_text)
    raw_dict = json.loads(json_str)

    # Validate and normalise via Pydantic schema
    card = CardIdentification.model_validate(raw_dict)
    card_data = card.model_dump()

    # Normalise colors list to a comma-separated string for CSV
    colors = card_data.get("colors") or []
    card_data["colors"] = ", ".join(colors)

    return card_data


# ---------------------------------------------------------------------------
# Progress / resume helpers
# ---------------------------------------------------------------------------

def load_progress(progress_path: Path) -> set:
    """Load set of already-scanned filenames."""
    if progress_path.exists():
        try:
            with open(progress_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return set(data.get("scanned", []))
        except (json.JSONDecodeError, ValueError) as exc:
            print(f"[!] Corrupted progress file at {progress_path}: {exc}. Starting fresh.")
            return set()
    return set()


def save_progress(progress_path: Path, scanned: set):
    """Persist scanned filenames for resume."""
    progress_path.parent.mkdir(parents=True, exist_ok=True)
    with open(progress_path, "w", encoding="utf-8") as f:
        json.dump({"scanned": sorted(scanned), "updated": datetime.now().isoformat()}, f)


# ---------------------------------------------------------------------------
# CSV writing
# ---------------------------------------------------------------------------

def init_csv(csv_path: Path, append: bool = False):
    """Create or open the CSV file; write header if new."""
    if not append or not csv_path.exists():
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=_CSV_FIELDS)
            writer.writeheader()


def append_csv_row(csv_path: Path, row: dict):
    """Append a single result row to the CSV."""
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_CSV_FIELDS)
        writer.writerow({k: row.get(k, "") for k in _CSV_FIELDS})


# ---------------------------------------------------------------------------
# Main scanning loop
# ---------------------------------------------------------------------------

def scan_folder(
    input_dir: Path,
    output_csv: Path,
    host: str,
    model: str,
    resume: bool = True,
    limit: int | None = None,
    debug: bool = False,
):
    """Scan all card images in *input_dir*, writing results to *output_csv*."""

    # Collect image files
    image_files = sorted(
        p for p in input_dir.iterdir()
        if p.suffix.lower() in _IMAGE_EXTENSIONS
    )
    total = len(image_files)
    print(f"[*] Found {total} image(s) in {input_dir}")

    if total == 0:
        print("[!] No images found. Check --input-dir path.")
        return

    # Resume support
    scanned: set = set()
    if resume:
        scanned = load_progress(_PROGRESS_FILE)
        if scanned:
            print(f"[*] Resuming — {len(scanned)} already scanned")

    init_csv(output_csv, append=resume and output_csv.exists())

    pending = [p for p in image_files if p.name not in scanned]
    if limit is not None:
        pending = pending[:limit]

    print(f"[*] Scanning {len(pending)} image(s) with {model} ...")
    print(f"[*] Output → {output_csv}")
    print()

    # Build LangChain LLM instances (primary + fallback with simpler prompt)
    llm = build_llm(host, model)
    fallback_llm = build_llm(host, model)

    success_count = 0
    error_count = 0
    start_time = time.time()

    for idx, img_path in enumerate(pending, 1):
        tag = f"[{idx}/{len(pending)}]"
        try:
            if not img_path.is_file() or img_path.stat().st_size <= 0:
                raise ValueError("Input image is empty or missing")

            print(f"{tag} {img_path.name} ...", end=" ", flush=True)
            card = identify_card(img_path, llm, fallback_llm, debug=debug)

            row = {
                "filename": img_path.name,
                "card_name": card.get("card_name", ""),
                "set_name": card.get("set_name", ""),
                "set_code": card.get("set_code", ""),
                "colors": card.get("colors", ""),
                "mana_cost": card.get("mana_cost", ""),
                "type_line": card.get("type_line", ""),
                "rarity": card.get("rarity", ""),
                "power_toughness": card.get("power_toughness", ""),
                "confidence": card.get("confidence", ""),
                "status": "success",
                "error": "",
                "timestamp": datetime.now().isoformat(),
            }

            append_csv_row(output_csv, row)
            scanned.add(img_path.name)
            success_count += 1

            conf = card.get("confidence", "?")
            print(f"→ {card.get('card_name', '???')}  (conf {conf})")

        except KeyboardInterrupt:
            print("\n[!] Interrupted — saving progress.")
            save_progress(_PROGRESS_FILE, scanned)
            break

        except Exception as e:
            error_count += 1
            print(f"ERROR: {e}")
            row = {
                "filename": img_path.name,
                "status": "error",
                "error": str(e)[:200],
                "timestamp": datetime.now().isoformat(),
            }
            append_csv_row(output_csv, row)
            # Keep failed files pending so a later rerun can retry after fixes.

        # Save progress every 25 images
        if idx % 25 == 0:
            save_progress(_PROGRESS_FILE, scanned)

    # Final save
    save_progress(_PROGRESS_FILE, scanned)

    elapsed = time.time() - start_time
    print()
    print(f"[✓] Done — {success_count} identified, {error_count} errors")
    print(f"    Elapsed: {elapsed:.1f}s ({elapsed / max(len(pending), 1):.1f}s per card)")
    print(f"    CSV: {output_csv}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(
        description="Scan MTG card images with LangChain + Ollama vision (qwen3-vl:8b)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python ollama_scan_cards.py
  python ollama_scan_cards.py --input-dir ./google_drive_downloads
  python ollama_scan_cards.py --limit 5 --no-resume
  python ollama_scan_cards.py --model qwen3-vl:4b --ollama-url http://192.168.1.50:11434
        """,
    )
    p.add_argument(
        "--input-dir",
        type=Path,
        default=_DEFAULT_INPUT,
        help=f"Folder of card images (default: {_DEFAULT_INPUT.name})",
    )
    p.add_argument(
        "--output-csv",
        type=Path,
        default=_DEFAULT_OUTPUT,
        help=f"Output CSV path (default: {_DEFAULT_OUTPUT.name})",
    )
    p.add_argument(
        "--model",
        default=_MODEL,
        help=f"Ollama vision model (default: {_MODEL})",
    )
    p.add_argument(
        "--ollama-url",
        default=_OLLAMA_URL,
        help=f"Ollama server URL (default: {_OLLAMA_URL})",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only scan this many images (for testing)",
    )
    p.add_argument(
        "--no-resume",
        action="store_true",
        help="Start fresh, ignoring any previous progress",
    )
    p.add_argument(
        "--debug",
        action="store_true",
        help="Print raw model responses for debugging",
    )
    return p.parse_args()


def main():
    args = parse_args()

    print("=" * 60)
    print("  MTG Card Scanner — LangChain + Ollama Vision")
    print(f"  Model   : {args.model}")
    print(f"  Input   : {args.input_dir}")
    print(f"  Output  : {args.output_csv}")
    print("=" * 60)
    print()

    if not args.input_dir.is_dir():
        print(f"[!] Input directory not found: {args.input_dir}")
        sys.exit(1)

    if not check_ollama(args.ollama_url, args.model):
        sys.exit(1)

    if args.no_resume and _PROGRESS_FILE.exists():
        _PROGRESS_FILE.unlink()

    scan_folder(
        input_dir=args.input_dir,
        output_csv=args.output_csv,
        host=args.ollama_url,
        model=args.model,
        resume=not args.no_resume,
        limit=args.limit,
        debug=args.debug,
    )


if __name__ == "__main__":
    main()
