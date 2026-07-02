"""
Tests for cct_pulley/server.py — server lifecycle (check → start → stop).

These run with plain pytest; FreeCAD is stubbed in conftest.py.
The server module is reloaded for each test so module-level _proc state
does not bleed between cases.
"""
import importlib
import subprocess
import sys
import types
import unittest.mock as mock

import pytest


def _load_server(monkeypatch, exe_exists: bool):
    """Re-import server.py with a clean _proc = None and a controlled EXE path."""
    # Remove cached module so we get a fresh _proc = None each test
    sys.modules.pop("cct_pulley.server", None)
    sys.modules.pop("cct_pulley", None)

    # Make cct_pulley importable from the addin root without installing it
    addin_root = str(__file__).replace("\\tests\\test_server_lifecycle.py", "")
    if addin_root not in sys.path:
        sys.path.insert(0, addin_root)

    import cct_pulley.server as srv

    # Point EXE path at a real or fake location
    fake_exe = addin_root + "\\fake_PulleyApp.exe" if exe_exists else "C:\\nonexistent\\PulleyApp.exe"
    monkeypatch.setattr(srv, "_EXE_PATH", fake_exe)

    if exe_exists:
        # os.path.isfile must return True for the fake path
        monkeypatch.setattr("os.path.isfile", lambda p: p == fake_exe)

    return srv


# ── Test 1 ────────────────────────────────────────────────────────────────────

def test_already_running_does_not_set_proc(monkeypatch):
    """Server already up → ensure_running() returns True and _proc stays None."""
    srv = _load_server(monkeypatch, exe_exists=False)

    monkeypatch.setattr(srv, "is_running", lambda: True)

    result = srv.ensure_running()

    assert result is True
    assert srv._proc is None


# ── Test 2 ────────────────────────────────────────────────────────────────────

def test_stop_when_not_started_is_noop(monkeypatch):
    """stop_if_we_started() with _proc = None must not raise or call terminate."""
    srv = _load_server(monkeypatch, exe_exists=False)
    assert srv._proc is None

    srv.stop_if_we_started()   # should be silent

    assert srv._proc is None


# ── Test 3 ────────────────────────────────────────────────────────────────────

def test_starts_and_stops_when_exe_present(monkeypatch):
    """Not running + EXE present → proc is launched; stop_if_we_started terminates it."""
    srv = _load_server(monkeypatch, exe_exists=True)

    # First call returns False (server not up), second returns True (it came up)
    _responses = iter([False, True])
    monkeypatch.setattr(srv, "is_running", lambda: next(_responses))
    monkeypatch.setattr(srv, "_EXE_PATH", "fake_PulleyApp.exe")
    monkeypatch.setattr("os.path.isfile", lambda p: True)
    monkeypatch.setattr("time.sleep", lambda _: None)   # don't actually sleep

    mock_proc = mock.MagicMock(spec=subprocess.Popen)
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: mock_proc)

    result = srv.ensure_running()

    assert result is True
    assert srv._proc is mock_proc

    srv.stop_if_we_started()

    mock_proc.terminate.assert_called_once()
    assert srv._proc is None


# ── Test 4 ────────────────────────────────────────────────────────────────────

def test_exe_missing_returns_false(monkeypatch):
    """EXE not installed → ensure_running() returns False without spawning anything."""
    srv = _load_server(monkeypatch, exe_exists=False)

    monkeypatch.setattr(srv, "is_running", lambda: False)
    monkeypatch.setattr("os.path.isfile", lambda p: False)

    spawned = []
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: spawned.append(a) or mock.MagicMock())

    result = srv.ensure_running()

    assert result is False
    assert spawned == []
    assert srv._proc is None


# ── Test 5 ────────────────────────────────────────────────────────────────────

def test_startup_timeout_proc_is_set_and_can_be_stopped(monkeypatch):
    """EXE launched but never responds → ensure_running returns False.
    _proc is still set (we own it) so stop_if_we_started() terminates it.
    """
    srv = _load_server(monkeypatch, exe_exists=True)

    monkeypatch.setattr(srv, "is_running", lambda: False)   # never comes up
    monkeypatch.setattr(srv, "_EXE_PATH", "fake_PulleyApp.exe")
    monkeypatch.setattr("os.path.isfile", lambda p: True)
    monkeypatch.setattr("time.sleep", lambda _: None)

    mock_proc = mock.MagicMock(spec=subprocess.Popen)
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: mock_proc)

    result = srv.ensure_running()

    assert result is False
    assert srv._proc is mock_proc   # we launched it — we own it

    srv.stop_if_we_started()
    mock_proc.terminate.assert_called_once()
    assert srv._proc is None
