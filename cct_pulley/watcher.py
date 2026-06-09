"""Watch the configured downloads folder for new STEP/DXF files and import them.

QFileSystemWatcher fires on directory changes; we then scan and import any
fresh files. mtime tracking prevents re-importing the same file.

The watcher runs on FreeCAD's Qt main thread, so all imports happen there too —
no thread-safety issues with FreeCAD's document API.
"""
from __future__ import annotations

import os
from pathlib import Path

import FreeCAD

from . import config, importer


# Singleton state
_watcher = None
_seen: dict[str, float] = {}   # filename → mtime at last import


def _on_dir_changed(path: str) -> None:
    """QFileSystemWatcher callback. Scan dir, import new files."""
    cfg = config.load()
    if not cfg.get("auto_import", True):
        return
    try:
        for fname in sorted(os.listdir(path)):
            fp = os.path.join(path, fname)
            ext = os.path.splitext(fname.lower())[1]
            if not os.path.isfile(fp) or ext not in importer.IMPORT_EXTS:
                continue
            try:
                mtime = os.path.getmtime(fp)
            except OSError:
                continue
            if _seen.get(fname) != mtime:
                _seen[fname] = mtime
                if importer.has_cct_signature(fp):
                    importer.import_file(fp)
                else:
                    FreeCAD.Console.PrintLog(f"[CCT] skipped {fname} (no CCT signature)\n")
    except Exception as e:
        FreeCAD.Console.PrintWarning(f"[CCT] watcher scan failed: {e}\n")


def _snapshot_existing(path: str) -> None:
    """Record mtimes of files already in the watch dir so they aren't imported
    on first scan (only files arriving AFTER startup count)."""
    try:
        for fname in os.listdir(path):
            fp = os.path.join(path, fname)
            if os.path.isfile(fp):
                try:
                    _seen[fname] = os.path.getmtime(fp)
                except OSError:
                    pass
    except Exception:
        pass


def ensure_started() -> None:
    """Idempotent: start the watcher on the configured dir if not already running."""
    global _watcher
    try:
        from PySide2 import QtCore
    except ImportError:
        # FreeCAD 0.21+/1.x uses PySide6 on some platforms
        try:
            from PySide6 import QtCore
        except ImportError:
            FreeCAD.Console.PrintError("[CCT] PySide not available — file watcher disabled\n")
            return

    watch_path = config.watch_dir()
    Path(watch_path).mkdir(parents=True, exist_ok=True)

    if _watcher is not None:
        # Already running — reconfigure if path changed
        current = set(_watcher.directories())
        if watch_path not in current:
            _watcher.removePaths(list(current))
            _watcher.addPath(watch_path)
            _seen.clear()
            _snapshot_existing(watch_path)
            FreeCAD.Console.PrintMessage(f"[CCT] watcher repointed → {watch_path}\n")
        return

    _watcher = QtCore.QFileSystemWatcher()
    _watcher.addPath(watch_path)
    _watcher.directoryChanged.connect(_on_dir_changed)
    _snapshot_existing(watch_path)
    FreeCAD.Console.PrintMessage(
        f"[CCT] file watcher started on {watch_path}\n"
        f"      auto-importing new STEP/DXF files into the active document\n"
    )


def stop() -> None:
    global _watcher
    if _watcher is not None:
        try:
            _watcher.removePaths(list(_watcher.directories()))
        except Exception:
            pass
        _watcher = None
        _seen.clear()
        FreeCAD.Console.PrintMessage("[CCT] file watcher stopped\n")
