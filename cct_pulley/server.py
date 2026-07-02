"""Local PulleyApp server lifecycle for the FreeCAD addin.

Responsibilities:
  - Detect whether the local server is reachable at port 5154.
  - Start PulleyApp.exe if not running and the EXE is installed.
  - Track whether *we* started it so we only stop what we own.
  - Register an atexit hook that terminates the server when FreeCAD exits.
"""
from __future__ import annotations

import atexit
import json
import os
import subprocess
import tempfile
import time
import urllib.request
import zipfile

import FreeCAD

_LOCAL_URL   = "http://127.0.0.1:5154/"
_APPDATA     = os.environ.get("APPDATA") or os.path.expanduser("~")
_EXE_PATH    = os.path.join(_APPDATA, "CheapCADTools", "PulleyApp", "PulleyApp.exe")
_CONFIG_FILE = os.path.join(_APPDATA, "CheapCADTools", "config.json")

# None  → server was already running when we checked (or we haven't tried)
# Popen → we launched it
_proc: subprocess.Popen | None = None


def _register_watch_dir(watch_dir: str) -> None:
    """Write freecad_watch_dir to shared config.json so app.py can mirror files there."""
    try:
        os.makedirs(os.path.dirname(_CONFIG_FILE), exist_ok=True)
        try:
            with open(_CONFIG_FILE, encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            cfg = {}
        cfg["freecad_watch_dir"] = watch_dir
        cfg["freecad_connected"] = True
        with open(_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        FreeCAD.Console.PrintWarning(f"[CCT] could not register watch dir: {e}\n")


def _unregister_watch_dir() -> None:
    """Clear freecad_connected flag so app.py stops mirroring."""
    try:
        if not os.path.exists(_CONFIG_FILE):
            return
        with open(_CONFIG_FILE, encoding="utf-8") as f:
            cfg = json.load(f)
        cfg.pop("freecad_connected", None)
        with open(_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass


def is_installed() -> bool:
    """Return True if PulleyApp.exe exists on disk."""
    return os.path.isfile(_EXE_PATH)


def is_running() -> bool:
    """Return True if the local server answers on port 5154."""
    try:
        urllib.request.urlopen(_LOCAL_URL, timeout=1)
        return True
    except Exception:
        return False


def ensure_running() -> bool:
    """Start PulleyApp.exe if not already up.

    Does nothing (and leaves _proc = None) when the server is already running —
    we did not start it, so we must not stop it.

    Returns True if the server is reachable after the call.
    """
    global _proc
    if is_running():
        FreeCAD.Console.PrintMessage("[CCT] Local server already running\n")
        from . import config as _cfg
        _register_watch_dir(str(_cfg.watch_dir()))
        return True

    if not os.path.isfile(_EXE_PATH):
        FreeCAD.Console.PrintMessage(
            f"[CCT] PulleyApp.exe not found at {_EXE_PATH}; "
            "falling back to web app\n"
        )
        return False

    FreeCAD.Console.PrintMessage(f"[CCT] Starting local server: {_EXE_PATH}\n")
    _env = {**os.environ, "PULLEY_NO_BROWSER": "1"}
    _proc = subprocess.Popen([_EXE_PATH], env=_env)

    for _ in range(16):          # wait up to 8 s
        time.sleep(0.5)
        if is_running():
            FreeCAD.Console.PrintMessage("[CCT] Local server ready\n")
            from . import config as _cfg
            _register_watch_dir(str(_cfg.watch_dir()))
            return True

    FreeCAD.Console.PrintMessage("[CCT] Local server did not respond within 8 s\n")
    return False


def stop_if_we_started() -> None:
    """Terminate the server only if this addin launched it."""
    global _proc
    if _proc is None:
        return
    FreeCAD.Console.PrintMessage("[CCT] Stopping local server (addin started it)\n")
    _unregister_watch_dir()
    try:
        _proc.terminate()
    except Exception as e:
        FreeCAD.Console.PrintError(f"[CCT] Could not terminate server: {e}\n")
    _proc = None


# Register so FreeCAD process exit triggers clean shutdown.
atexit.register(stop_if_we_started)


_INSTALL_DIR = os.path.join(_APPDATA, "CheapCADTools", "PulleyApp")
_FALLBACK_URL = "https://github.com/xootme/PulleyApp-releases/releases/latest/download/PulleyApp.zip"


def download_and_install(app_url: str = '', progress_cb=None) -> bool:
    """Download PulleyApp.zip and extract to %APPDATA%\\CheapCADTools\\PulleyApp.

    progress_cb(msg: str) — called with status strings during download/install.
    Returns True on success, False on failure.
    """
    url = app_url or _FALLBACK_URL

    def _report(msg):
        FreeCAD.Console.PrintMessage(f"[CCT] {msg}\n")
        if progress_cb:
            progress_cb(msg)

    _report("Downloading PulleyApp…")
    try:
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
            tmp_path = tmp.name

        def _reporthook(block, block_size, total):
            if total > 0 and progress_cb:
                pct = min(100, int(block * block_size * 100 / total))
                progress_cb(f"Downloading… {pct}%")

        urllib.request.urlretrieve(url, tmp_path, _reporthook)
        _report("Installing…")

        os.makedirs(_INSTALL_DIR, exist_ok=True)
        with zipfile.ZipFile(tmp_path, 'r') as zf:
            for member in zf.namelist():
                # Strip leading "PulleyApp/" folder from zip paths
                parts = member.split('/', 1)
                target = parts[1] if len(parts) > 1 else member
                if not target:
                    continue
                dest = os.path.join(_INSTALL_DIR, target)
                if member.endswith('/'):
                    os.makedirs(dest, exist_ok=True)
                else:
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    with zf.open(member) as src, open(dest, 'wb') as dst:
                        dst.write(src.read())

        os.unlink(tmp_path)
        _report("PulleyApp installed successfully.")
        return True

    except Exception as exc:
        FreeCAD.Console.PrintError(f"[CCT] Install failed: {exc}\n")
        if progress_cb:
            progress_cb(f"Install failed: {exc}")
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        return False
