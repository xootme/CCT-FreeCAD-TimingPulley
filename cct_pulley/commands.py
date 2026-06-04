"""FreeCAD Gui::Command classes — the toolbar buttons users see.

Four commands:
    CCT_OpenDesigner   — open the web designer (local PulleyApp if installed,
                         else cheapcadtools.com)
    CCT_RestorePulley  — pick a previously exported STEP/DXF/SVG and reopen
                         the designer with that file's embedded parameters
    CCT_ImportHistory  — view + re-restore from the last 100 imports
    CCT_Settings       — configure the watch folder + auto-import flag
"""
from __future__ import annotations

import os
import webbrowser
from pathlib import Path

import FreeCAD
import FreeCADGui

from . import config, importer, paths, watcher


_ADDON_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _icon(name: str) -> str:
    return os.path.join(_ADDON_DIR, "Resources", "icons", name)


# ── Open designer ───────────────────────────────────────────────────────────

class _OpenDesignerCommand:
    def GetResources(self):
        return {
            "Pixmap":  _icon("64x64.png"),
            "MenuText": "Open Pulley Designer",
            "ToolTip":  "Open the CheapCADTools Timing Pulley designer in your browser.\n"
                        "Downloads (STEP/DXF) auto-import into the active FreeCAD document.",
        }

    def IsActive(self):
        return True

    def Activated(self):
        # Start the watcher (idempotent) so anything downloaded gets picked up.
        watcher.ensure_started()

        # Tell the user where downloads need to land
        watch_dir = config.watch_dir()
        FreeCAD.Console.PrintMessage(
            f"[CCT] watching for STEP/DXF files in: {watch_dir}\n"
            f"      save your browser downloads there to auto-import\n"
        )

        url = paths.designer_url()
        # Pass machine_id as a query param so a future server endpoint can
        # enforce per-machine trial limits without breaking the file-watcher UX.
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}freecad=1&mid={paths.machine_id()}"
        webbrowser.open(url)


# ── Restore design ──────────────────────────────────────────────────────────

class _RestorePulleyCommand:
    def GetResources(self):
        return {
            "Pixmap":  _icon("32x32.png"),
            "MenuText": "Restore Pulley Design",
            "ToolTip":  "Pick a previously exported STEP, DXF, or SVG file and "
                        "reopen the web designer with its embedded parameters.",
        }

    def IsActive(self):
        return True

    def Activated(self):
        try:
            from PySide2 import QtWidgets
        except ImportError:
            from PySide6 import QtWidgets

        parent = FreeCADGui.getMainWindow()
        filepath, _ = QtWidgets.QFileDialog.getOpenFileName(
            parent,
            "Select an exported CheapCAD Tools file",
            str(Path.home()),
            "CAD files (*.step *.stp *.dxf *.svg *.stl);;All files (*)",
        )
        if not filepath:
            return

        params = importer.extract_cct_metadata(filepath)
        if not params:
            QtWidgets.QMessageBox.information(
                parent, "Restore Pulley Design",
                "No CheapCAD Tools design data found in this file.\n\n"
                "Only files exported from CheapCAD Tools contain embedded parameters.",
            )
            return

        qs = importer.params_to_qs(params)
        url = paths.restore_url(qs)
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}freecad=1&mid={paths.machine_id()}"
        FreeCAD.Console.PrintMessage(f"[CCT] restoring design from {filepath}\n")
        webbrowser.open(url)


# ── Import history dialog ───────────────────────────────────────────────────

class _ImportHistoryCommand:
    def GetResources(self):
        return {
            "Pixmap":  _icon("32x32.png"),
            "MenuText": "Import History",
            "ToolTip":  "View and reopen previous CheapCAD Tools imports (last 100).",
        }

    def IsActive(self):
        return True

    def Activated(self):
        try:
            from PySide2 import QtWidgets
        except ImportError:
            from PySide6 import QtWidgets

        parent = FreeCADGui.getMainWindow()
        history = importer.load_history()
        if not history:
            QtWidgets.QMessageBox.information(
                parent, "Import History",
                "No import history yet.\n\n"
                "Import CheapCAD Tools files to start building history.",
            )
            return

        dlg = QtWidgets.QDialog(parent)
        dlg.setWindowTitle("CCT — Import History")
        dlg.resize(540, 380)
        layout = QtWidgets.QVBoxLayout(dlg)

        layout.addWidget(QtWidgets.QLabel("Pick an import to reopen in the designer:"))

        listw = QtWidgets.QListWidget()
        for entry in reversed(history):
            ts    = entry.get("timestamp", "")[:16].replace("T", " ")
            ftype = entry.get("file_type", "?")
            fname = entry.get("file_name", "?")
            listw.addItem(f"{ts}   [{ftype}]   {fname}")
        if listw.count():
            listw.setCurrentRow(0)
        layout.addWidget(listw, 1)

        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Open | QtWidgets.QDialogButtonBox.Close,
            parent=dlg,
        )
        btns.button(QtWidgets.QDialogButtonBox.Open).setText("Reopen in Designer")
        layout.addWidget(btns)

        clear_btn = QtWidgets.QPushButton("Clear history…")
        btns.addButton(clear_btn, QtWidgets.QDialogButtonBox.ResetRole)

        def do_open():
            row = listw.currentRow()
            if row < 0:
                return
            entry  = history[len(history) - 1 - row]   # display is newest-first
            params = entry.get("params", {})
            if not params:
                QtWidgets.QMessageBox.information(
                    dlg, "Import History",
                    "No design parameters stored for this entry.",
                )
                return
            qs = importer.params_to_qs(params)
            url = paths.restore_url(qs)
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}freecad=1&mid={paths.machine_id()}"
            webbrowser.open(url)
            dlg.accept()

        def do_clear():
            r = QtWidgets.QMessageBox.question(
                dlg, "Clear Import History",
                "Permanently delete all import history?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            )
            if r == QtWidgets.QMessageBox.Yes:
                f = paths.history_file()
                if f.exists():
                    f.unlink()
                dlg.reject()

        btns.accepted.connect(do_open)
        btns.rejected.connect(dlg.reject)
        clear_btn.clicked.connect(do_clear)
        listw.itemDoubleClicked.connect(do_open)

        dlg.exec_()


# ── Settings dialog ─────────────────────────────────────────────────────────

class _SettingsCommand:
    def GetResources(self):
        return {
            "Pixmap":  _icon("32x32.png"),
            "MenuText": "Settings…",
            "ToolTip":  "Configure the download watch folder and auto-import behaviour.",
        }

    def IsActive(self):
        return True

    def Activated(self):
        try:
            from PySide2 import QtWidgets
        except ImportError:
            from PySide6 import QtWidgets

        parent = FreeCADGui.getMainWindow()
        cfg = config.load()

        dlg = QtWidgets.QDialog(parent)
        dlg.setWindowTitle("CCT Timing Pulleys — Settings")
        dlg.resize(560, 200)
        form = QtWidgets.QFormLayout(dlg)

        # Watch dir row
        watch_row = QtWidgets.QHBoxLayout()
        watch_edit = QtWidgets.QLineEdit(cfg.get("watch_dir") or str(paths.default_watch_dir()))
        watch_browse = QtWidgets.QPushButton("Browse…")
        watch_row.addWidget(watch_edit, 1)
        watch_row.addWidget(watch_browse)

        def browse():
            d = QtWidgets.QFileDialog.getExistingDirectory(
                dlg, "Pick a folder to watch for downloads", watch_edit.text(),
            )
            if d:
                watch_edit.setText(d)
        watch_browse.clicked.connect(browse)

        form.addRow("Watch folder:", watch_row)

        auto_chk = QtWidgets.QCheckBox("Auto-import new STEP/DXF files into the active document")
        auto_chk.setChecked(bool(cfg.get("auto_import", True)))
        form.addRow("", auto_chk)

        # Local PulleyApp status row (informational)
        local_url = paths.local_pulleyapp_url()
        status_text = (
            f"<b style='color:#2ecc71'>● Local PulleyApp detected</b> on {local_url} — using local generation"
            if local_url else
            "<span style='color:#888'>○ Local PulleyApp not running — using free online tier at cheapcadtools.com</span>"
        )
        form.addRow("Status:", QtWidgets.QLabel(status_text))

        # Buttons
        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel,
            parent=dlg,
        )
        form.addRow(btns)

        def save():
            new_cfg = dict(cfg)
            new_cfg["watch_dir"]   = watch_edit.text().strip()
            new_cfg["auto_import"] = auto_chk.isChecked()
            config.save(new_cfg)
            watcher.ensure_started()  # picks up the new path
            dlg.accept()

        btns.accepted.connect(save)
        btns.rejected.connect(dlg.reject)
        dlg.exec_()


# ── Timing Pulley panel (Part Design menu entry) ────────────────────────────

class _TimingPulleyCommand:
    """Opens the CCT Timing Pulleys side panel — the Part Design menu entry."""

    def GetResources(self):
        return {
            "Pixmap":   _icon("64x64.png"),
            "MenuText": "Timing Pulley",
            "ToolTip":  "Open the CCT Timing Pulley designer panel.\n"
                        "Design pulleys in your browser; results auto-import here.",
        }

    def IsActive(self):
        return True

    def Activated(self):
        from . import panel
        panel.show()


# ── Register with FreeCAD ───────────────────────────────────────────────────

FreeCADGui.addCommand("CCT_TimingPulley",  _TimingPulleyCommand())
FreeCADGui.addCommand("CCT_OpenDesigner",  _OpenDesignerCommand())
FreeCADGui.addCommand("CCT_RestorePulley", _RestorePulleyCommand())
FreeCADGui.addCommand("CCT_ImportHistory", _ImportHistoryCommand())
FreeCADGui.addCommand("CCT_Settings",      _SettingsCommand())
