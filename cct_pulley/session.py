"""Session management for FreeCAD addin.

Handles creating browser sessions and registering machine_id via API.
"""

import json
import webbrowser
import urllib.request

import FreeCAD

from . import paths


def open_designer_with_session(designer_url, machine_id=None):
    """Create a session, register machine_id, and open designer in browser.

    Args:
        designer_url: Base URL to the designer (e.g., https://cheapcadtools.com/tools/pulleys)
        machine_id: Optional machine ID to register. If None, uses paths.machine_id()

    Fallback: If API call fails, opens designer without session_id.
    """
    if machine_id is None:
        machine_id = paths.machine_id()

    try:
        # Extract base URL (everything before /tools/pulleys or similar)
        base_url = designer_url.split('/tools')[0] if '/tools' in designer_url else designer_url.rsplit('/', 1)[0]

        # Create session
        session_req = urllib.request.Request(
            f"{base_url}/api/session/create",
            method='POST'
        )
        with urllib.request.urlopen(session_req, timeout=5) as resp:
            session_data = json.loads(resp.read().decode())
            session_id = session_data.get('session_id')

        # Register machine_id with session
        mid_data = json.dumps({
            'session_id': session_id,
            'machine_id': machine_id
        }).encode('utf-8')
        mid_req = urllib.request.Request(
            f"{base_url}/api/session/register-machine",
            data=mid_data,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        with urllib.request.urlopen(mid_req, timeout=5) as resp:
            resp.read()  # Consume response

        # Open designer with session (no mid in URL)
        sep = "&" if "?" in designer_url else "?"
        final_url = f"{designer_url}{sep}freecad=1&session_id={session_id}"
        webbrowser.open(final_url)

    except Exception as e:
        FreeCAD.Console.PrintError(f"[CCT] Failed to create session: {e}\n")
        # Fallback: open without session_id (user will be queued normally)
        sep = "&" if "?" in designer_url else "?"
        webbrowser.open(f"{designer_url}{sep}freecad=1")
