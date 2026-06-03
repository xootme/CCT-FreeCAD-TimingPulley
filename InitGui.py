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

    def Initialize(self):
        """Called once on first workbench activation — register commands and inject menus."""
        from cct_pulley import commands  # noqa: F401

        # CCT workbench toolbar + menu (for users who switch to this workbench)
        self.list = ["CCT_TimingPulley", "CCT_RestorePulley",
                     "CCT_ImportHistory", "CCT_Settings"]
        self.appendToolbar("CCT Timing Pulleys", self.list)
        self.appendMenu("CCT Timing Pulleys", self.list)

        # Inject "Timing Pulley" into Part Design menu via signal.
        # Using a bound method (self._on_wb_activated) avoids the exec()
        # shared-namespace issue — Python resolves it via self, not globals.
        try:
            import FreeCADGui as _Gui
            mw = _Gui.getMainWindow()
            if mw is not None:
                mw.workbenchActivated.connect(self._on_wb_activated)
                # Handle case where Part Design is already active at load time
                try:
                    active = _Gui.activeWorkbench()
                    if active and active.__class__.__name__ == "PartDesignWorkbench":
                        self._inject_into_part_design()
                except Exception:
                    pass
        except Exception:
            pass

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
