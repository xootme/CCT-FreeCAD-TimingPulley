"""Licence key management for the CCT FreeCAD addin.

Flow:
  1. User enters key in the Licence dialog (panel.py).
  2. activate(key) posts to /api/desktop/activate on Render with key + machine_id.
  3. Server validates the key, checks it isn't already bound to a different machine,
     and stores the binding.  Returns ok + valid_until.
  4. Key is saved locally in addon_data_dir/licence.json.
  5. verify() is called on each FreeCAD startup (≤ once per VERIFY_INTERVAL_DAYS)
     to confirm the key is still valid.  Offline grace is handled server-side.
"""
from __future__ import annotations

import json
import platform
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

from . import paths

_API_BASE          = "https://pulleywebapp.onrender.com"
_VERIFY_INTERVAL   = timedelta(days=7)


def _key_file() -> Path:
    return paths.addon_data_dir() / "licence.json"


def load() -> dict:
    """Return stored licence record, or {} if none."""
    try:
        with open(_key_file(), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(data: dict) -> None:
    with open(_key_file(), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def is_activated() -> bool:
    """Quick local check — no network call."""
    return bool(load().get("key"))


def activate(key: str) -> dict:
    """Activate key for this machine.

    Returns {'ok': True, 'valid_until': '...'} on success,
    or {'error': '...'} on failure.
    """
    key = key.strip().upper()
    if not key:
        return {"error": "Licence key is required."}

    mid = paths.machine_id()
    payload = json.dumps({
        "licence_key": key,
        "machine_id":  mid,
        "hostname":    platform.node()[:64],
    }).encode()

    req = urllib.request.Request(
        f"{_API_BASE}/api/desktop/activate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        try:
            result = json.loads(e.read())
        except Exception:
            result = {"error": f"Server error ({e.code})"}
    except Exception as e:
        result = {"error": f"Could not reach activation server: {e}"}

    if result.get("ok"):
        _save({
            "key":          key,
            "machine_id":   mid,
            "valid_until":  result.get("valid_until", ""),
            "verified_at":  datetime.now().isoformat(),
        })

    return result


def verify(force: bool = False) -> dict:
    """Verify stored key is still valid.  Skips network if recently verified.

    Returns {'ok': True, 'valid_until': '...'} or {'error': '...'}.
    """
    data = load()
    key  = data.get("key", "")
    if not key:
        return {"error": "No licence key stored."}

    # Skip network call if verified recently
    if not force:
        try:
            last = datetime.fromisoformat(data.get("verified_at", ""))
            if datetime.now() - last < _VERIFY_INTERVAL:
                return {"ok": True, "valid_until": data.get("valid_until", ""), "cached": True}
        except Exception:
            pass

    mid = data.get("machine_id") or paths.machine_id()
    payload = json.dumps({"licence_key": key, "machine_id": mid}).encode()
    req = urllib.request.Request(
        f"{_API_BASE}/api/desktop/verify",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        try:
            result = json.loads(e.read())
        except Exception:
            result = {"error": f"Server error ({e.code})"}
    except Exception as e:
        result = {"error": f"Could not reach server: {e}"}

    if result.get("ok"):
        data["verified_at"] = datetime.now().isoformat()
        data["valid_until"] = result.get("valid_until", data.get("valid_until", ""))
        _save(data)

    return result
