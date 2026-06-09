"""STEP / DXF import + CCT metadata extraction.

Ports the metadata-extract logic from the Fusion 360 addin
(PulleyWebApp.py:_extract_cct_metadata) — pure stdlib, no Fusion deps.

The import side uses FreeCAD's Part and importDXF modules.
"""
from __future__ import annotations

import datetime
import json
import os
import re
import shutil
from pathlib import Path
from typing import Optional

import FreeCAD
import FreeCADGui

from . import paths


# ── Metadata extraction (mirrors Fusion 360 addin) ──────────────────────────

def extract_cct_metadata(filepath: str | Path) -> dict:
    """Read CCT design params embedded in a STEP / DXF / SVG file.

    Returns {} on failure or if no CCT block found.
    """
    try:
        text = Path(filepath).read_text(encoding="utf-8", errors="replace")
    except Exception:
        return {}

    ext = Path(filepath).suffix.lower()
    blob: Optional[str] = None
    if ext in (".step", ".stp", ".stl"):
        m = re.search(r"/\* CCT:(\{.+?\}) \*/", text)
        if m:
            blob = m.group(1)
    elif ext == ".dxf":
        m = re.search(r"999\nCCT:(\{.+})", text)
        if m:
            blob = m.group(1)
    elif ext == ".svg":
        m = re.search(r"<cct>([\s\S]+?)</cct>", text)
        if m:
            blob = m.group(1)

    if not blob:
        return {}
    try:
        data = json.loads(blob)
        if "cct" in data:
            params = dict(data["cct"])
            if "sv" in data:
                params.setdefault("sv", data["sv"])
            return params
        return data
    except Exception:
        return {}


def params_to_qs(params: dict) -> str:
    """Build a URL query string from design params (skip None/empty)."""
    import urllib.parse
    return urllib.parse.urlencode({k: v for k, v in params.items() if v not in (None, "")})


# ── Import history ──────────────────────────────────────────────────────────

def record_import(fname: str, file_type: str, params: dict) -> None:
    """Append an import record; keeps newest 100 entries."""
    f = paths.history_file()
    try:
        history = json.loads(f.read_text(encoding="utf-8")) if f.exists() else []
    except Exception:
        history = []
    history.append({
        "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
        "file_type": file_type,
        "file_name": fname,
        "params":    params,
    })
    if len(history) > 100:
        history = history[-100:]
    try:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(history, indent=2), encoding="utf-8")
    except Exception as e:
        FreeCAD.Console.PrintWarning(f"[CCT] history write failed: {e}\n")


def load_history() -> list[dict]:
    f = paths.history_file()
    if not f.exists():
        return []
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return []


# ── CCT signature check ──────────────────────────────────────────────────────

def has_cct_signature(filepath: str | Path) -> bool:
    """Return True if the file carries a CCT signature block.

    Reads only the bytes where the marker is known to appear:
      STEP/STP — comment inserted between ENDSEC and DATA (first 4 KB)
      DXF      — group-code 999 comment before EOF marker (last 2 KB)
    """
    try:
        p = Path(filepath)
        ext = p.suffix.lower()
        size = p.stat().st_size
        if ext in (".step", ".stp"):
            with open(p, "rb") as f:
                head = f.read(4096).decode("utf-8", errors="replace")
            return "/* CCT:" in head
        elif ext == ".dxf":
            with open(p, "rb") as f:
                f.seek(max(0, size - 2048))
                tail = f.read().decode("utf-8", errors="replace")
            return "999\nCCT:" in tail
    except Exception:
        pass
    return False


# ── File import (called from watcher event on Qt main thread) ───────────────

IMPORT_EXTS = {".step", ".stp", ".dxf"}


def ensure_active_doc():
    """Return the active document, creating a new one if none exists."""
    doc = FreeCAD.ActiveDocument
    if doc is None:
        doc = FreeCAD.newDocument("CCT_Pulley")
    return doc


def import_file(filepath: str | Path) -> bool:
    """Import a STEP or DXF file into the active FreeCAD document.

    Returns True on success. Moves the imported file to <watch>/imported/
    so the watcher doesn't fire on it again.
    """
    filepath = Path(filepath)
    if not filepath.exists():
        return False
    ext = filepath.suffix.lower()
    if ext not in IMPORT_EXTS:
        return False

    try:
        doc = ensure_active_doc()
        before_objs = set(o.Name for o in doc.Objects)

        if ext in (".step", ".stp"):
            import Part
            Part.insert(str(filepath), doc.Name)
        elif ext == ".dxf":
            import importDXF
            importDXF.insert(str(filepath), doc.Name)

        doc.recompute()

        # Tag newly imported objects with the embedded CCT params (if any)
        # so the design can be restored later from the FreeCAD file.
        params = extract_cct_metadata(filepath)
        if params:
            new_objs = [o for o in doc.Objects if o.Name not in before_objs]
            params_json = json.dumps(params, separators=(",", ":"))
            for o in new_objs:
                try:
                    if hasattr(o, "addProperty"):
                        o.addProperty("App::PropertyString", "CCT_Params",
                                      "CheapCADTools", "Design parameters")
                        o.CCT_Params = params_json
                except Exception:
                    pass  # property might already exist or object type rejects it

        # History bookkeeping
        record_import(filepath.name, ext.lstrip(".").upper(), params)

        # Move file out of the watch folder so it isn't re-imported on every poll
        imported_dir = filepath.parent / "imported"
        imported_dir.mkdir(exist_ok=True)
        dest = imported_dir / filepath.name
        if dest.exists():
            dest.unlink()
        shutil.move(str(filepath), str(dest))

        # Fit the view
        try:
            FreeCADGui.SendMsgToActiveView("ViewFit")
        except Exception:
            pass

        FreeCAD.Console.PrintMessage(f"[CCT] imported {filepath.name}\n")
        return True

    except Exception as e:
        import traceback
        FreeCAD.Console.PrintError(
            f"[CCT] import failed for {filepath.name}: {e}\n{traceback.format_exc()}\n"
        )
        return False
