"""CCT Timing Pulleys dock panel."""
from __future__ import annotations

import os
import webbrowser

try:
    from PySide2 import QtWidgets, QtCore, QtGui
except ImportError:
    from PySide6 import QtWidgets, QtCore, QtGui

import FreeCADGui

from . import config, paths, server, watcher, session, license as _license

_CCT_RED   = "#761516"
_CCT_GRAY  = "#eaebed"
_PAID_URL  = "https://cheapcadtools.com/product/freecad-timing-pulley-addin/"


def show():
    """Show (or re-raise) the CCT dock panel."""
    import cct_pulley
    mw = FreeCADGui.getMainWindow()
    if mw is None:
        return

    panel = getattr(cct_pulley, "_panel_instance", None)
    if panel is None or not panel.isVisible():
        panel = CCTDockPanel(mw)
        mw.addDockWidget(QtCore.Qt.RightDockWidgetArea, panel)
        cct_pulley._panel_instance = panel

    panel.show()
    panel.raise_()
    watcher.ensure_started()


# ── Free trial warning dialog ─────────────────────────────────────────────────

class _FreeTrialDialog(QtWidgets.QDialog):
    """Shown before opening the free web app."""

    LAUNCHED = False   # class-level: suppress on subsequent clicks in same session

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("CCT Timing Pulleys — Free Trial")
        self.setMinimumWidth(400)
        self.setModal(True)
        self._result = None

        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(18, 18, 18, 18)

        # Header
        hdr = QtWidgets.QLabel("Free Web App Trial")
        hdr.setStyleSheet(
            f"font-size:15px; font-weight:bold; color:{_CCT_RED};"
        )
        layout.addWidget(hdr)

        # Info box
        info = QtWidgets.QLabel(
            "<b>Free tier limitations:</b><br>"
            "&bull;&nbsp; Maximum <b>2 downloads per week</b><br>"
            "&bull;&nbsp; Runs on a <b>shared server</b> — may be slow at peak times<br>"
            "&bull;&nbsp; Requires an internet connection"
        )
        info.setWordWrap(True)
        info.setStyleSheet("font-size:12px; padding:8px; background:#fff8f8;"
                           " border:1px solid #f0d0d0; border-radius:4px;")
        layout.addWidget(info)

        # Paid app pitch
        paid = QtWidgets.QLabel(
            "<b>Paid Local App — $9.99 / year</b><br>"
            "&bull;&nbsp; Runs <b>locally on Windows or Linux</b> — no internet needed<br>"
            "&bull;&nbsp; <b>Unlimited</b> downloads<br>"
            "&bull;&nbsp; Fast — no shared server<br>"
            "<span style='color:#27ae60;'>"
            "&bull;&nbsp; <b>30% of every sale is donated to FreeCAD</b>"
            "</span>"
        )
        paid.setWordWrap(True)
        paid.setStyleSheet("font-size:12px; padding:8px; background:#f0fff4;"
                           " border:1px solid #b2dfdb; border-radius:4px;")
        layout.addWidget(paid)

        layout.addSpacing(4)

        # Buttons
        btn_row = QtWidgets.QHBoxLayout()

        btn_get = QtWidgets.QPushButton("Get Paid App  →")
        btn_get.setStyleSheet(
            f"QPushButton {{ background:{_CCT_RED}; color:white; font-weight:bold;"
            f" padding:9px 16px; border-radius:4px; font-size:12px; border:none; }}"
            f"QPushButton:hover {{ background:#9b1e1e; }}"
        )
        btn_get.clicked.connect(self._get_paid)
        btn_row.addWidget(btn_get)

        btn_ok = QtWidgets.QPushButton("OK, start the web app")
        btn_ok.setStyleSheet(
            "QPushButton { background:#eaebed; color:#333; padding:9px 16px;"
            " border-radius:4px; font-size:12px; border:1px solid #bbb; }"
            "QPushButton:hover { background:#d4d5d7; }"
        )
        btn_ok.clicked.connect(self._launch_free)
        btn_row.addWidget(btn_ok)

        layout.addLayout(btn_row)

    def _get_paid(self):
        webbrowser.open(_PAID_URL)
        self._result = "paid"
        self.accept()

    def _launch_free(self):
        self._result = "free"
        self.accept()

    @classmethod
    def confirm(cls, parent=None):
        """Return 'free', 'paid', or None (cancelled). Skips on repeat clicks."""
        if cls.LAUNCHED:
            return "free"
        dlg = cls(parent)
        dlg.exec_()
        if dlg._result == "free":
            cls.LAUNCHED = True
        return dlg._result


# ── Dock widget ───────────────────────────────────────────────────────────────

class CCTDockPanel(QtWidgets.QDockWidget):

    def __init__(self, parent=None):
        super().__init__("Timing Pulleys", parent)
        self.setObjectName("CCT_TimingPulleysPanel")
        self.setMinimumWidth(250)
        self.setAllowedAreas(
            QtCore.Qt.LeftDockWidgetArea | QtCore.Qt.RightDockWidgetArea
        )
        self.setWidget(self._build_widget())
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(5000)
        self._refresh()

    def _build_widget(self):
        root = QtWidgets.QWidget()
        vbox = QtWidgets.QVBoxLayout(root)
        vbox.setContentsMargins(10, 12, 10, 10)
        vbox.setSpacing(6)

        # Brand header
        lbl_brand = QtWidgets.QLabel("CheapCADTools")
        lbl_brand.setStyleSheet(
            f"font-weight:bold; font-size:14px; color:{_CCT_RED};"
        )
        lbl_sub = QtWidgets.QLabel("Timing Belt Pulley Generator")
        lbl_sub.setStyleSheet("font-size:11px; color:#555;")
        vbox.addWidget(lbl_brand)
        vbox.addWidget(lbl_sub)
        vbox.addWidget(_hline())

        # Free Web App Trial button (primary)
        self.btn_free = QtWidgets.QPushButton("Free Web App Trial")
        self.btn_free.setToolTip(
            "Open the free CCT web designer (max 2 downloads/week, shared server)"
        )
        self.btn_free.setStyleSheet(
            f"QPushButton {{ background:{_CCT_RED}; color:white; font-weight:bold;"
            f" padding:9px 12px; border-radius:4px; font-size:13px; border:none; }}"
            f"QPushButton:hover {{ background:#9b1e1e; }}"
            f"QPushButton:pressed {{ background:#5a1010; }}"
        )
        self.btn_free.clicked.connect(self._open_free)
        vbox.addWidget(self.btn_free)

        # Paid Local App button (secondary)
        self.btn_paid = QtWidgets.QPushButton("Paid Local App")
        self.btn_paid.setToolTip(
            "Open the locally installed PulleyApp (port 5154)\n"
            "Unlimited downloads, runs offline — $9.99/yr"
        )
        self.btn_paid.setStyleSheet(
            "QPushButton { background:#eaebed; color:#333; padding:7px 12px;"
            " border-radius:4px; font-size:13px; border:1px solid #bbb; }"
            "QPushButton:hover:enabled { background:#d4d5d7; }"
            "QPushButton:disabled { color:#aaa; }"
        )
        self.btn_paid.clicked.connect(self._open_paid)
        vbox.addWidget(self.btn_paid)

        vbox.addWidget(_hline())

        # Status
        self.lbl_status = QtWidgets.QLabel()
        self.lbl_status.setStyleSheet("font-size:11px;")
        self.lbl_status.setWordWrap(True)
        vbox.addWidget(self.lbl_status)

        self.lbl_watch = QtWidgets.QLabel()
        self.lbl_watch.setStyleSheet("font-size:10px; color:#666;")
        self.lbl_watch.setWordWrap(True)
        vbox.addWidget(self.lbl_watch)

        vbox.addWidget(_hline())

        # Utility buttons — bold, larger
        for label, slot in (
            ("Restore Design from File…", self._restore),
            ("Import History…",           self._history),
            ("Settings…",                 self._settings),
            ("Instruction Video",         self._video),
        ):
            btn = QtWidgets.QPushButton(label)
            btn.setStyleSheet(
                "QPushButton { padding:7px 10px; font-size:12px; font-weight:bold;"
                " text-align:left; border:none; background:transparent; }"
                "QPushButton:hover { background:#f0f0f0; border-radius:3px; }"
            )
            btn.clicked.connect(slot)
            vbox.addWidget(btn)

        vbox.addStretch()
        return root

    def _refresh(self):
        local_url = paths.local_pulleyapp_url()
        exe_installed = server.is_installed()
        paid_active = local_url or exe_installed

        if local_url:
            self.lbl_status.setText(
                "<span style='color:#27ae60'>&#9679; Local app running</span>"
            )
            self.btn_paid.setToolTip(
                f"Open local PulleyApp on {local_url} — unlimited downloads"
            )
        elif exe_installed:
            self.lbl_status.setText(
                "<span style='color:#e67e22'>&#9679; Local app installed (not running)</span>"
            )
            self.btn_paid.setToolTip(
                "Click to start the local PulleyApp and open the designer."
            )
        else:
            self.lbl_status.setText(
                "<span style='color:#aaa'>&#9675; Local app not installed</span>"
            )
            self.btn_paid.setToolTip(
                "Enter your licence key to activate the local PulleyApp.\n"
                "Purchase at cheapcadtools.com — $9.99/yr."
            )

        # btn_paid is always enabled — when not installed it opens the licence dialog
        self.btn_paid.setEnabled(True)

        if paid_active:
            self.btn_paid.setStyleSheet(
                f"QPushButton {{ background:{_CCT_RED}; color:white; font-weight:bold;"
                f" padding:9px 12px; border-radius:4px; font-size:13px; border:none; }}"
                f"QPushButton:hover {{ background:#9b1e1e; }}"
                f"QPushButton:pressed {{ background:#5a1010; }}"
            )
            self.btn_free.setStyleSheet(
                "QPushButton { background:#eaebed; color:#aaa; padding:7px 12px;"
                " border-radius:4px; font-size:13px; border:1px solid #bbb; }"
                "QPushButton:hover { background:#d4d5d7; color:#333; }"
            )
        else:
            # Not installed — secondary style but still clickable (opens licence dialog)
            self.btn_paid.setStyleSheet(
                "QPushButton { background:#eaebed; color:#555; padding:9px 12px;"
                " border-radius:4px; font-size:13px; border:1px solid #bbb; }"
                "QPushButton:hover { background:#d4d5d7; }"
            )
            self.btn_free.setStyleSheet(
                f"QPushButton {{ background:{_CCT_RED}; color:white; font-weight:bold;"
                f" padding:9px 12px; border-radius:4px; font-size:13px; border:none; }}"
                f"QPushButton:hover {{ background:#9b1e1e; }}"
                f"QPushButton:pressed {{ background:#5a1010; }}"
            )

        watch_dir = config.watch_dir()
        self.lbl_watch.setText(f"Watch folder:\n{watch_dir}")

    def _open_free(self):
        result = _FreeTrialDialog.confirm(self)
        if result == "free":
            # Free trial always uses the hosted web app — never local
            url = paths.WEB_BASE + "/tools/pulleys"
            session.open_designer_with_session(url)
            watcher.ensure_started()

    def _open_paid(self):
        if not server.is_installed():
            _LicenceDialog.show_and_activate(self)
            return
        server.ensure_running()
        local = paths.local_pulleyapp_url()
        if local:
            session.open_designer_with_session(f"{local}/")
        watcher.ensure_started()

    def _restore(self):
        FreeCADGui.runCommand("CCT_RestorePulley")

    def _history(self):
        FreeCADGui.runCommand("CCT_ImportHistory")

    def _settings(self):
        FreeCADGui.runCommand("CCT_Settings")

    def _video(self):
        webbrowser.open("https://www.youtube.com/watch?v=UP1FnCfZPzc")


class _LicenceDialog(QtWidgets.QDialog):
    """Key-entry dialog shown when the local app is not installed."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("CCT Timing Pulleys — Activate")
        self.setMinimumWidth(420)
        self.setModal(True)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        hdr = QtWidgets.QLabel("Enter Your Licence Key")
        hdr.setStyleSheet(f"font-size:15px; font-weight:bold; color:{_CCT_RED};")
        layout.addWidget(hdr)

        info = QtWidgets.QLabel(
            "Purchase a licence at <a href='https://cheapcadtools.com/product/"
            "freecad-timing-pulley-addin/'>cheapcadtools.com</a> then paste "
            "your key below.<br><br>"
            "The key is in your order confirmation email."
        )
        info.setWordWrap(True)
        info.setOpenExternalLinks(True)
        info.setStyleSheet("font-size:12px;")
        layout.addWidget(info)

        self._key_input = QtWidgets.QLineEdit()
        self._key_input.setPlaceholderText("CCT-XXXXXX-XXXXXX-XXXXXX-XXXXXX")
        self._key_input.setStyleSheet(
            "font-family:monospace; font-size:13px; padding:8px;"
            " border:1px solid #ccc; border-radius:4px;"
        )
        layout.addWidget(self._key_input)

        self._status = QtWidgets.QLabel("")
        self._status.setWordWrap(True)
        self._status.setStyleSheet("font-size:12px; min-height:20px;")
        layout.addWidget(self._status)

        btn_row = QtWidgets.QHBoxLayout()
        self._btn_activate = QtWidgets.QPushButton("Activate")
        self._btn_activate.setStyleSheet(
            f"QPushButton {{ background:{_CCT_RED}; color:white; font-weight:bold;"
            f" padding:9px 20px; border-radius:4px; font-size:12px; border:none; }}"
            f"QPushButton:hover {{ background:#9b1e1e; }}"
            f"QPushButton:disabled {{ background:#bbb; }}"
        )
        self._btn_activate.clicked.connect(self._do_activate)
        btn_row.addWidget(self._btn_activate)

        btn_cancel = QtWidgets.QPushButton("Cancel")
        btn_cancel.setStyleSheet(
            "QPushButton { background:#eaebed; color:#333; padding:9px 16px;"
            " border-radius:4px; font-size:12px; border:1px solid #bbb; }"
            "QPushButton:hover { background:#d4d5d7; }"
        )
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)
        layout.addLayout(btn_row)

    def _do_activate(self):
        key = self._key_input.text().strip()
        if not key:
            self._status.setText("<span style='color:#c0392b;'>Please enter a licence key.</span>")
            return
        self._btn_activate.setEnabled(False)
        self._btn_activate.setText("Activating…")
        self._status.setText("")
        QtWidgets.QApplication.processEvents()

        result = _license.activate(key)

        self._btn_activate.setEnabled(True)
        self._btn_activate.setText("Activate")

        if result.get("ok"):
            until = result.get("valid_until", "")[:10]
            self._status.setText(
                f"<span style='color:#27ae60;'>&#10003; Activated! Valid until {until}.<br>"
                f"Download PulleyApp from your order email or "
                f"<a href='https://cheapcadtools.com'>cheapcadtools.com</a>.</span>"
            )
            self._status.setOpenExternalLinks(True)
            self._btn_activate.setEnabled(False)
        else:
            msg = result.get("error", "Activation failed.")
            self._status.setText(f"<span style='color:#c0392b;'>&#10007; {msg}</span>")

    @classmethod
    def show_and_activate(cls, parent=None):
        dlg = cls(parent)
        dlg.exec_()


def _hline():
    line = QtWidgets.QFrame()
    line.setFrameShape(QtWidgets.QFrame.HLine)
    line.setFrameShadow(QtWidgets.QFrame.Sunken)
    return line
