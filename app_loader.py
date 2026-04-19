from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


_APP_MODULE_NAME = "mtg_inventory_app"
_APP_PATH = Path(__file__).resolve().parent / "frontend" / "mtg-inventory" / "app.py"
_APP_DIR = _APP_PATH.parent


def load_app():
    if str(_APP_DIR) not in sys.path:
        sys.path.insert(0, str(_APP_DIR))

    spec = importlib.util.spec_from_file_location(_APP_MODULE_NAME, _APP_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load Flask app from {_APP_PATH}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.app


app = load_app()
