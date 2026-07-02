"""Persistent addon config (watch directory, auto-import flag)."""
from __future__ import annotations

import json
from typing import Any

from . import paths


_DEFAULTS = {
    "watch_dir":   "",     # "" → use paths.default_watch_dir()
    "auto_import": True,
    "open_in_new_tab": True,
}


def load() -> dict[str, Any]:
    f = paths.config_file()
    if not f.exists():
        return dict(_DEFAULTS)
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
        return {**_DEFAULTS, **data}
    except Exception:
        return dict(_DEFAULTS)


def save(data: dict[str, Any]) -> None:
    f = paths.config_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(data, indent=2), encoding="utf-8")


def watch_dir() -> str:
    cfg = load()
    saved = cfg.get("watch_dir") or ""
    default = paths.default_watch_dir()
    if not saved:
        return str(default)
    # Migrate: if saved path is exactly the Downloads folder (no CCT_Import), upgrade it.
    from pathlib import Path
    saved_path = Path(saved)
    if saved_path == default.parent and saved_path.name.lower() != "cct_import":
        new_dir = str(default)
        save({**cfg, "watch_dir": new_dir})
        return new_dir
    return saved
