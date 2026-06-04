"""Cross-platform paths for the CCT Pulley addon.

Uses FreeCAD's own user data dir so config / history land alongside other
FreeCAD per-user state (Windows: %APPDATA%/FreeCAD, Linux: ~/.local/share/FreeCAD,
macOS: ~/Library/Preferences/FreeCAD). Watch folder defaults to ~/Downloads/cct
which is what the web app's downloads naturally land in.
"""
from __future__ import annotations

import hashlib
import os
import platform
import sys
from pathlib import Path

import FreeCAD


# ── Data dir ────────────────────────────────────────────────────────────────

def addon_data_dir() -> Path:
    """Per-user state for this addon (config, history)."""
    base = Path(FreeCAD.getUserAppDataDir()) / "CheapCADTools"
    base.mkdir(parents=True, exist_ok=True)
    return base


def config_file() -> Path:
    return addon_data_dir() / "freecad_addon_config.json"


def history_file() -> Path:
    return addon_data_dir() / "freecad_import_history.json"


def default_watch_dir() -> Path:
    """Where the web app's downloaded STEP/DXF files arrive.

    Default: ~/Downloads (standard Windows/Linux/macOS downloads folder).
    The watcher filters for .step, .stp, and .dxf files only.
    """
    home = Path.home()
    # Common Downloads folder locations (case-insensitive)
    for candidate in (home / "Downloads", home / "downloads"):
        if candidate.is_dir():
            return candidate
    # Fallback: addon data dir
    d = addon_data_dir() / "downloads"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ── Machine identity (for trial-limit accounting) ───────────────────────────

def machine_id() -> str:
    """Stable 32-hex-char identifier for this machine.

    Mirrors PulleyApp launcher.py logic:
      Windows : registry MachineGuid
      Linux   : /etc/machine-id (or /var/lib/dbus/machine-id)
      macOS   : IOPlatformUUID
      fallback: hostname + username hash
    """
    try:
        if sys.platform == "win32":
            import winreg
            k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography")
            guid, _ = winreg.QueryValueEx(k, "MachineGuid")
            return hashlib.sha256(guid.encode()).hexdigest()[:32]
        if sys.platform.startswith("linux"):
            for p in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
                if os.path.exists(p):
                    with open(p) as f:
                        return hashlib.sha256(f.read().strip().encode()).hexdigest()[:32]
        if sys.platform == "darwin":
            import subprocess
            out = subprocess.check_output(
                ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                text=True, timeout=5,
            )
            for line in out.splitlines():
                if "IOPlatformUUID" in line:
                    uuid = line.split('"')[-2]
                    return hashlib.sha256(uuid.encode()).hexdigest()[:32]
    except Exception:
        pass
    fallback = f"{platform.node()}:{os.environ.get('USERNAME') or os.environ.get('USER', '')}"
    return hashlib.sha256(fallback.encode()).hexdigest()[:32]


# ── Local PulleyApp detection ───────────────────────────────────────────────

def local_pulleyapp_url() -> str | None:
    """Return the local PulleyApp URL if it's reachable, otherwise None.

    The paid tier installs PulleyApp on Flask port 5154. If we can hit it,
    we use it (unlimited generation). Otherwise we fall back to the hosted
    free tier.
    """
    import urllib.request
    try:
        urllib.request.urlopen("http://127.0.0.1:5154/", timeout=1)
        return "http://127.0.0.1:5154"
    except Exception:
        return None


WEB_BASE = "https://cheapcadtools.com"


def designer_url() -> str:
    """Pick the designer URL — local PulleyApp if installed, else hosted."""
    return (local_pulleyapp_url() or WEB_BASE) + "/tools/pulleys"


def restore_url(params_qs: str) -> str:
    """Build a designer URL with parameters from a restored design."""
    base = local_pulleyapp_url() or WEB_BASE
    return f"{base}/tools/pulleys?{params_qs}" if params_qs else f"{base}/tools/pulleys"
