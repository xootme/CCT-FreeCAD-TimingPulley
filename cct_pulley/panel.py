"""CCT Timing Pulleys dock panel — matches the Fusion 360 sidebar UX."""
from __future__ import annotations

import webbrowser

try:
    from PySide2 import QtWidgets, QtCore
except ImportError:
    from PySide6 import QtWidgets, QtCore

import FreeCADGui

from . import config, paths, watcher


def show():
    """Show (or re-raise) the CCT dock panel. Safe to call multiple times."""
    import cct_pulley
    mw = FreeCADGui.getMainWindow()
    if mw is None:
        return

    panel = getattr(cct_pulley, "_panel_instance", None)

    if panel is None or not panel.isVisible():
        panel = CCTDockPanel(mw)
        mw.addDockWidget(QtCore.Qt.RightDockWidgetArea, panel)
        cct_pulley._panel_instance = panel   # keep reference on the real module

    panel.show()
    panel.raise_()
    watcher.ensure_started()


# ── Dock widget ──────────────────────────────────────────────────────────────

class CCTDockPanel(QtWidgets.QDockWidget):

    def __init__(self, parent=None):
        super().__init__("Timing Pulleys", parent)
        self.setObjectName("CCT_TimingPulleysPanel")
        self.setMinimumWidth(240)
        self.setAllowedAreas(
            QtCore.Qt.LeftDockWidgetArea | QtCore.Qt.RightDockWidgetArea
        )
        self.setWidget(self._build_widget())
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(5000)
        self._refresh()

    # ── Build UI ─────────────────────────────────────────────────────────────

    def _build_widget(self):
        root = QtWidgets.QWidget()
        vbox = QtWidgets.QVBoxLayout(root)
        vbox.setContentsMargins(10, 12, 10, 10)
        vbox.setSpacing(6)

        # Brand header
        lbl_brand = QtWidgets.QLabel("CheapCADTools")
        lbl_brand.setStyleSheet(
            "font-weight: bold; font-size: 13px; color: #761516;"
        )
        lbl_sub = QtWidgets.QLabel("Timing Belt Pulley Generator")
        lbl_sub.setStyleSheet("font-size: 11px; color: #555;")
        vbox.addWidget(lbl_brand)
        vbox.addWidget(lbl_sub)
        vbox.addWidget(_hline())

        # Primary: Open in Browser
        self.btn_online = QtWidgets.QPushButton("Open in Browser")
        self.btn_online.setToolTip(
            "Open the CCT Pulley Designer at cheapcadtools.com"
        )
        self.btn_online.setStyleSheet(
            "QPushButton {"
            "  background:#761516; color:white; font-weight:bold;"
            "  padding:9px 12px; border-radius:4px; font-size:12px;"
            "  border:none;"
            "}"
            "QPushButton:hover { background:#9b1e1e; }"
            "QPushButton:pressed { background:#5a1010; }"
        )
        self.btn_online.clicked.connect(self._open_online)
        vbox.addWidget(self.btn_online)

        # Secondary: Open Local
        self.btn_local = QtWidgets.QPushButton("Open Local App")
        self.btn_local.setToolTip(
            "Open the locally installed PulleyApp (port 5154)"
        )
        self.btn_local.setStyleSheet(
            "QPushButton {"
            "  background:#eaebed; color:#333; padding:7px 12px;"
            "  border-radius:4px; font-size:12px;"
            "  border:1px solid #ccc;"
            "}"
            "QPushButton:hover:enabled { background:#d4d5d7; }"
            "QPushButton:disabled { color:#aaa; }"
        )
        self.btn_local.clicked.connect(self._open_local)
        vbox.addWidget(self.btn_local)

        vbox.addWidget(_hline())

        # Status
        self.lbl_status = QtWidgets.QLabel()
        self.lbl_status.setStyleSheet("font-size: 11px;")
        self.lbl_status.setWordWrap(True)
        vbox.addWidget(self.lbl_status)

        self.lbl_watch = QtWidgets.QLabel()
        self.lbl_watch.setStyleSheet("font-size: 10px; color: #666;")
        self.lbl_watch.setWordWrap(True)
        vbox.addWidget(self.lbl_watch)

        vbox.addWidget(_hline())

        # Utility buttons
        for label, slot in (
            ("Restore Design from File…", self._restore),
            ("Import History…",           self._history),
            ("Settings…",                 self._settings),
        ):
            btn = QtWidgets.QPushButton(label)
            btn.setStyleSheet(
                "QPushButton { padding:5px 8px; font-size:11px;"
                " text-align:left; border:none; background:transparent; }"
                "QPushButton:hover { background:#f0f0f0; border-radius:3px; }"
            )
            btn.clicked.connect(slot)
            vbox.addWidget(btn)

        vbox.addStretch()
        return root

    # ── Refresh status ────────────────────────────────────────────────────────

    def _refresh(self):
        local_url = paths.local_pulleyapp_url()
        if local_url:
            self.lbl_status.setText(
                "<span style='color:#27ae60'>&#9679; Local app running</span>"
            )
            self.btn_local.setEnabled(True)
        else:
            self.lbl_status.setText(
                "<span style='color:#aaa'>&#9675; Local app not running</span>"
            )
            self.btn_local.setEnabled(False)

        watch_dir = config.watch_dir()
        self.lbl_watch.setText(f"Watch folder:\n{watch_dir}")

    # ── Button handlers ───────────────────────────────────────────────────────

    def _open_online(self):
        url = paths.designer_url()
        sep = "&" if "?" in url else "?"
        webbrowser.open(f"{url}{sep}freecad=1&mid={paths.machine_id()}")
        watcher.ensure_started()

    def _open_local(self):
        local = paths.local_pulleyapp_url()
        if local:
            sep = "&" if "?" in local else "?"
            webbrowser.open(
                f"{local}/tools/pulleys{sep}freecad=1&mid={paths.machine_id()}"
            )
        watcher.ensure_started()

    def _restore(self):
        FreeCADGui.runCommand("CCT_RestorePulley")

    def _history(self):
        FreeCADGui.runCommand("CCT_ImportHistory")

    def _settings(self):
        FreeCADGui.runCommand("CCT_Settings")


# ── Helpers ──────────────────────────────────────────────────────────────────

def _hline():
    line = QtWidgets.QFrame()
    line.setFrameShape(QtWidgets.QFrame.HLine)
    line.setFrameShadow(QtWidgets.QFrame.Sunken)
    return line
