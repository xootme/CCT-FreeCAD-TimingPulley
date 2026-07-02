# conftest.py — stub out FreeCAD so server.py can be imported without FreeCAD installed
import sys
import types
import tempfile

# Build a minimal FreeCAD stub before any test module imports server.py
_fc = types.ModuleType("FreeCAD")
_fc.Console = types.SimpleNamespace(
    PrintMessage=lambda msg: None,
    PrintError=lambda msg: None,
)
_fc.getUserAppDataDir = lambda: tempfile.gettempdir() + "/"
sys.modules.setdefault("FreeCAD", _fc)
