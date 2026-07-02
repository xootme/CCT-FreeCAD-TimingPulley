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

from . import config, importer, paths, server, watcher, session  # noqa: F401 (watcher used in _do_uninstall)


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

        # Ensure the local server is running (start it if we own the exe).
        server.ensure_running()

        # Open the designer (local if server is up, hosted otherwise).
        url = paths.designer_url()
        session.open_designer_with_session(url)


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
            str(paths.default_watch_dir()),
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
            from PySide2 import QtWidgets, QtCore
        except ImportError:
            from PySide6 import QtWidgets, QtCore

        parent = FreeCADGui.getMainWindow()
        cfg = config.load()

        dlg = QtWidgets.QDialog(parent)
        dlg.setWindowTitle("CCT Timing Pulleys — Settings")
        dlg.resize(560, 260)
        layout = QtWidgets.QVBoxLayout(dlg)
        form = QtWidgets.QFormLayout()
        layout.addLayout(form)

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

        # Save / Cancel buttons
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
            watcher.ensure_started()
            dlg.accept()

        btns.accepted.connect(save)
        btns.rejected.connect(dlg.reject)

        # ── Danger zone ─────────────────────────────────────────────────────
        sep = QtWidgets.QFrame()
        sep.setFrameShape(QtWidgets.QFrame.HLine)
        sep.setFrameShadow(QtWidgets.QFrame.Sunken)
        layout.addWidget(sep)

        danger_row = QtWidgets.QHBoxLayout()
        danger_row.addStretch()
        uninstall_btn = QtWidgets.QPushButton("Uninstall CCT Addin…")
        uninstall_btn.setStyleSheet(
            "QPushButton { color:#c0392b; border:1px solid #c0392b; background:transparent;"
            " padding:5px 14px; border-radius:4px; font-size:11px; }"
            "QPushButton:hover { background:#fdf0ef; }"
        )
        uninstall_btn.clicked.connect(lambda: _do_uninstall(dlg, parent))
        danger_row.addWidget(uninstall_btn)
        layout.addLayout(danger_row)

        dlg.exec_()


def _do_uninstall(settings_dlg, parent):
    """Uninstall the CCT addin.

    Strategy: delete user data now (no live file locks), write a cleanup
    script that removes the addon folder after FreeCAD exits, then close
    FreeCAD so the OS releases all file handles before the script runs.
    """
    import shutil
    import subprocess
    import sys
    import tempfile

    try:
        from PySide2 import QtWidgets, QtCore
    except ImportError:
        from PySide6 import QtWidgets, QtCore

    # ── Confirm ──────────────────────────────────────────────────────────────
    confirm = QtWidgets.QMessageBox(parent)
    confirm.setWindowTitle("Uninstall CCT Timing Pulleys")
    confirm.setIcon(QtWidgets.QMessageBox.Warning)
    confirm.setText(
        "<b>Uninstall CCT Timing Pulleys?</b><br><br>"
        "This will:<br>"
        "&bull;&nbsp; Remove your config, import history, and licence file<br>"
        "&bull;&nbsp; Delete the addon folder from FreeCAD<br>"
        "&bull;&nbsp; Close FreeCAD to complete the process<br><br>"
        "<b>Save any open work before continuing.</b>"
    )
    confirm.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.Cancel)
    confirm.setDefaultButton(QtWidgets.QMessageBox.Cancel)
    confirm.button(QtWidgets.QMessageBox.Yes).setText("Uninstall && Close FreeCAD")
    if confirm.exec_() != QtWidgets.QMessageBox.Yes:
        return

    addon_dir = Path(_ADDON_DIR)

    # ── Stop background services ──────────────────────────────────────────────
    try:
        watcher.stop()
    except Exception:
        pass
    try:
        server.stop_if_we_started()
    except Exception:
        pass

    # ── Delete user data (no file locks on these) ─────────────────────────────
    try:
        shutil.rmtree(str(paths.addon_data_dir()), ignore_errors=True)
    except Exception:
        pass

    # ── Write a cleanup script that deletes files then relaunches FreeCAD ────
    pulleyapp_dir = os.path.join(
        os.environ.get("APPDATA") or os.path.expanduser("~"),
        "CheapCADTools", "PulleyApp",
    )
    freecad_exe = os.path.join(os.path.dirname(sys.executable), "FreeCAD.exe")
    if not os.path.isfile(freecad_exe):
        freecad_exe = os.path.join(os.path.dirname(sys.executable), "FreeCAD")

    if sys.platform == "win32":
        script = tempfile.NamedTemporaryFile(
            mode="w", suffix=".bat", delete=False, encoding="utf-8"
        )
        # Wait for FreeCAD to fully exit, delete everything, then relaunch.
        script.write(
            "@echo off\n"
            "ping -n 4 127.0.0.1 >nul\n"
            f'taskkill /f /im PulleyApp.exe >nul 2>&1\n'
            f'rmdir /s /q "{addon_dir}"\n'
            f'rmdir /s /q "{pulleyapp_dir}"\n'
            f'start "" "{freecad_exe}"\n'
        )
        script.close()
        subprocess.Popen(
            ["cmd", "/c", script.name],
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    else:
        script = tempfile.NamedTemporaryFile(
            mode="w", suffix=".sh", delete=False, encoding="utf-8"
        )
        script.write(
            "#!/bin/sh\n"
            "sleep 3\n"
            f'pkill -f PulleyApp 2>/dev/null\n'
            f'rm -rf "{addon_dir}"\n'
            f'rm -rf "{pulleyapp_dir}"\n'
            f'"{freecad_exe}" &\n'
        )
        script.close()
        os.chmod(script.name, 0o755)
        subprocess.Popen(["/bin/sh", script.name])

    # ── Close settings dialog ────────────────────────────────────────────────
    settings_dlg.accept()

    # Show what will be deleted and let the user dismiss before FreeCAD closes.
    info = QtWidgets.QMessageBox(parent)
    info.setWindowTitle("Uninstall Complete")
    info.setIcon(QtWidgets.QMessageBox.Information)
    info.setText(
        "CCT Timing Pulleys has been uninstalled.\n\n"
        "Click OK to restart FreeCAD."
    )
    info.setStandardButtons(QtWidgets.QMessageBox.Ok)
    info.exec_()

    # Close this FreeCAD instance — the batch script relaunches it after
    # deleting the addon folder, ensuring the clean version loads.
    FreeCADGui.getMainWindow().close()


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
