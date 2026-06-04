# -*- coding: utf-8 -*-
# CCT Timing Pulleys -- FreeCAD workbench entry point


class CCTTimingPulleysWorkbench(Workbench):
    """CheapCADTools Timing Belt Pulley Generator workbench."""

    MenuText = "CCT Timing Pulleys"
    ToolTip  = "Open the CCT Timing Pulley web designer and auto-import results"

    def __init__(self):
        import os
        import cct_pulley
        addon_dir = os.path.dirname(os.path.dirname(os.path.abspath(cct_pulley.__file__)))
        self.__class__.Icon = os.path.join(
            addon_dir, "Resources", "icons", "CCT_TimingPulleys.svg"
        )
        # Register commands and connect the workbenchActivated signal early
        # (deferred 1 s so the main window exists) — this means "Timing Pulley"
        # appears in the Part Design menu WITHOUT the user needing to activate
        # the CCT workbench first.
        try:
            try:
                from PySide2 import QtCore
            except ImportError:
                from PySide6 import QtCore
            QtCore.QTimer.singleShot(1000, self._early_setup)
        except Exception:
            pass

    def _early_setup(self):
        """Deferred startup: register commands and hook workbenchActivated."""
        try:
            from cct_pulley import commands  # noqa: F401
            import FreeCADGui as _Gui
            mw = _Gui.getMainWindow()
            if mw is not None:
                mw.workbenchActivated.connect(self._on_wb_activated)
                # If Part Design is already active when FreeCAD finishes loading
                try:
                    active = _Gui.activeWorkbench()
                    if active and active.__class__.__name__ == "PartDesignWorkbench":
                        self._inject_into_part_design()
                except Exception:
                    pass
        except Exception:
            pass

    def Initialize(self):
        """Called once when CCT workbench is first activated — set up toolbar/menu."""
        # Commands may already be registered by _early_setup; importing again is safe.
        try:
            from cct_pulley import commands  # noqa: F401
        except Exception:
            pass

        self.list = ["CCT_TimingPulley", "CCT_RestorePulley",
                     "CCT_ImportHistory", "CCT_Settings"]
        self.appendToolbar("CCT Timing Pulleys", self.list)
        self.appendMenu("CCT Timing Pulleys", self.list)

        try:
            from cct_pulley import watcher
            watcher.ensure_started()
        except Exception:
            pass

    def _on_wb_activated(self, wb_name):
        if wb_name == "PartDesignWorkbench":
            self._inject_into_part_design()

    def _inject_into_part_design(self):
        """Add 'Timing Pulley' to the Part Design menu (idempotent)."""
        try:
            import FreeCADGui as _Gui
            mw = _Gui.getMainWindow()
            if mw is None:
                return
            for action in mw.menuBar().actions():
                menu = action.menu()
                if menu and action.text().replace("&", "") == "Part Design":
                    # Idempotency check
                    if any(a.text() == "Timing Pulley" for a in menu.actions()):
                        return
                    menu.addSeparator()
                    cmd = _Gui.Command.get("CCT_TimingPulley")
                    if cmd:
                        acts = cmd.getAction()
                        if acts:
                            menu.addAction(acts[0])
                    break
        except Exception:
            pass

    def Activated(self):
        """Called every time this workbench is activated."""
        try:
            from cct_pulley import watcher
            watcher.ensure_started()
        except Exception:
            pass

    def Deactivated(self):
        pass

    def GetClassName(self):
        return "Gui::PythonWorkbench"


Gui.addWorkbench(CCTTimingPulleysWorkbench())
