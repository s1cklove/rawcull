"""Tiny persisted settings (%APPDATA%\\rawcull\\settings.json)."""

from __future__ import annotations

import json
import os
from pathlib import Path


def settings_file() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / ".config")
    return Path(base) / "rawcull" / "settings.json"


def load() -> dict:
    try:
        data = json.loads(settings_file().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save(d: dict) -> None:
    try:
        f = settings_file()
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
