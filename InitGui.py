"""
InitGui.py -- CCT Timing Pulleys addon entry point.

Registers a lightweight workbench so FreeCAD's addon loader recognises and
executes this file on startup (the NoneWorkbench pattern is unreliable on
FreeCAD 1.x Windows).  Commands are also added to the Part Design menu and
Tools menu so they are accessible without switching workbenches.
"""
import os
import sys
import traceback

import FreeCAD
import FreeCADGui

# Make cct_pulley package importable from this directory
_ADDON_DIR = os.path.dirname(os.path.abspath(__file__))
if _ADDON_DIR not in sys.path:
    sys.path.insert(0, _ADDON_DIR)

FreeCAD.Console.PrintMessage("[CCT] InitGui.py starting\n")

_COMMANDS = [
    "CCT_OpenDesigner",
    "CCT_RestorePulley",
    "CCT_ImportHistory",
    "CCT_Settings",
]

# ── Register commands ────────────────────────────────────────────────────────
try:
    from cct_pulley import commands  # noqa: F401 -- side-effect: addCommand calls
    FreeCAD.Console.PrintMessage("[CCT] commands registered\n")
except Exception:
    FreeCAD.Console.PrintError(
        "[CCT] failed to register commands:\n" + traceback.format_exc() + "\n"
    )

# ── Workbench ────────────────────────────────────────────────────────────────
# A real Workbench subclass is required for reliable startup loading on all
# platforms.  Users are not expected to switch to this workbench; commands
# also appear under Part Design and Tools menus.

class CCTTimingPulleysWorkbench(FreeCADGui.Workbench):
    MenuText = "CCT Timing Pulleys"
    ToolTip  = "CheapCADTools Timing Belt Pulley Generator"
    Icon     = os.path.join(_ADDON_DIR, "Resources", "icons", "64x64.png")

    def Initialize(self):
        self.appendToolbar("Timing Pulleys", _COMMANDS)
        self.appendMenu("Timing Pulleys", _COMMANDS)
        # Start file watcher when workbench first activates
        try:
            from cct_pulley import watcher
            watcher.ensure_started()
        except Exception:
            FreeCAD.Console.PrintError(
                "[CCT] watcher start failed:\n" + traceback.format_exc() + "\n"
            )

    def GetClassName(self):
        return "Gui::PythonWorkbench"


try:
    FreeCADGui.addWorkbench(CCTTimingPulleysWorkbench())
    FreeCAD.Console.PrintMessage("[CCT] workbench registered\n")
except Exception:
    FreeCAD.Console.PrintError(
        "[CCT] workbench register failed:\n" + traceback.format_exc() + "\n"
    )

# ── Also inject into Part Design + Tools menus (cross-workbench convenience) ─

_TARGET_WB       = "PartDesignWorkbench"
_TOOLBAR_TITLE   = "Timing Pulleys"
_TOOLBAR_OBJNAME = "CCT_TimingPulleysToolbar"
_MENU_MARKER     = "_cct_pulley_marker"


def _inject_part_design(wb_name):
    """Idempotently add a Timing Pulleys submenu + toolbar to Part Design."""
    if wb_name != _TARGET_WB:
        return
    try:
        try:
            from PySide2 import QtWidgets
        except ImportError:
            from PySide6 import QtWidgets

        mw = FreeCADGui.getMainWindow()
        if mw is None:
            return

        # Submenu
        for action in mw.menuBar().actions():
            menu = action.menu()
            if menu and action.text().replace("&", "") == "Part Design":
                if not any(getattr(a, _MENU_MARKER, False) for a in menu.actions()):
                    menu.addSeparator()
                    sub = menu.addMenu(_TOOLBAR_TITLE)
                    setattr(sub.menuAction(), _MENU_MARKER, True)
                    for cmd_name in _COMMANDS:
                        cmd = FreeCADGui.Command.get(cmd_name)
                        if cmd:
                            acts = cmd.getAction()
                            if acts:
                                sub.addAction(acts[0])
                break

        # Toolbar
        if mw.findChild(QtWidgets.QToolBar, _TOOLBAR_OBJNAME) is None:
            tb = mw.addToolBar(_TOOLBAR_TITLE)
            tb.setObjectName(_TOOLBAR_OBJNAME)
            for cmd_name in _COMMANDS:
                cmd = FreeCADGui.Command.get(cmd_name)
                if cmd:
                    acts = cmd.getAction()
                    if acts:
                        tb.addAction(acts[0])
    except Exception:
        FreeCAD.Console.PrintError(
            "[CCT] Part Design injection failed:\n" + traceback.format_exc() + "\n"
        )


def _inject_tools_menu():
    """Add a Timing Pulleys submenu to the Tools menu."""
    try:
        try:
            from PySide2 import QtWidgets
        except ImportError:
            from PySide6 import QtWidgets

        mw = FreeCADGui.getMainWindow()
        if mw is None:
            return
        for action in mw.menuBar().actions():
            menu = action.menu()
            if menu and action.text().replace("&", "") == "Tools":
                sub = menu.addMenu(_TOOLBAR_TITLE)
                for cmd_name in _COMMANDS:
                    cmd = FreeCADGui.Command.get(cmd_name)
                    if cmd:
                        acts = cmd.getAction()
                        if acts:
                            sub.addAction(acts[0])
                break
    except Exception:
        FreeCAD.Console.PrintError(
            "[CCT] Tools menu injection failed:\n" + traceback.format_exc() + "\n"
        )


try:
    try:
        from PySide2 import QtCore
    except ImportError:
        from PySide6 import QtCore

    def _wire():
        mw = FreeCADGui.getMainWindow()
        if mw is not None:
            try:
                mw.workbenchActivated.connect(_inject_part_design)
            except Exception:
                pass
            _inject_tools_menu()
            # Handle the case where Part Design is already active at load time
            try:
                active = FreeCADGui.activeWorkbench()
                if active and active.__class__.__name__ == _TARGET_WB:
                    _inject_part_design(_TARGET_WB)
            except Exception:
                pass

    QtCore.QTimer.singleShot(0, _wire)
    FreeCAD.Console.PrintMessage("[CCT] InitGui.py complete\n")
except Exception:
    FreeCAD.Console.PrintError(
        "[CCT] wire-up failed:\n" + traceback.format_exc() + "\n"
    )
