# CCT Timing Pulleys -- FreeCAD Add-on

FreeCAD add-on for the [CheapCADTools Timing Belt Pulley Generator](https://cheapcadtools.com/tools/pulleys).

Opens the pulley designer in your browser. Generated STEP/DXF files are
automatically watched and imported into the active FreeCAD document.

---

## Install via Addon Manager (recommended)

1. In FreeCAD: **Tools --> Addon Manager**
2. Click the **gear icon** (top-right) --> **Custom repositories**
3. Add: `https://github.com/xootme/CCT-FreeCAD-TimingPulley`
4. Close, refresh the list -- **CCT Timing Pulleys** appears
5. Click **Install**, then restart FreeCAD

After restart, a **CCT Timing Pulleys** workbench appears in the dropdown,
and commands are also available under **Part Design** and **Tools** menus.

---

## Manual install

### Windows
```powershell
# Symlink (edits picked up instantly -- recommended for development)
New-Item -ItemType SymbolicLink `
  -Path   "$env:APPDATA\FreeCAD\v1-1\Mod\CCT-FreeCAD-TimingPulley" `
  -Target "<path-to-clone>"

# Or copy
Copy-Item -Recurse "<path-to-clone>" "$env:APPDATA\FreeCAD\v1-1\Mod\CCT-FreeCAD-TimingPulley"
```

### Linux
```bash
# Symlink
ln -s /path/to/clone ~/.local/share/FreeCAD/v1-1/Mod/CCT-FreeCAD-TimingPulley

# Or copy
cp -r /path/to/clone ~/.local/share/FreeCAD/v1-1/Mod/CCT-FreeCAD-TimingPulley
```

### macOS
```bash
# Symlink
ln -s /path/to/clone \
  "$HOME/Library/Application Support/FreeCAD/v1-1/Mod/CCT-FreeCAD-TimingPulley"

# Or copy
cp -r /path/to/clone \
  "$HOME/Library/Application Support/FreeCAD/v1-1/Mod/CCT-FreeCAD-TimingPulley"
```

> For FreeCAD 0.21 drop the `v1-1/` segment from the path.

---

## Usage

1. Switch to the **CCT Timing Pulleys** workbench (or use the commands under
   **Part Design --> Timing Pulleys** or **Tools --> Timing Pulleys**)
2. Click **Open Pulley Designer** -- the web app opens in your browser
3. Design your pulley, click any download button (STEP / DXF)
4. Save the file to your configured watch folder (default: `~/Downloads/cct`)
5. The file auto-imports into the active FreeCAD document

### Commands

| Command | Description |
|---|---|
| Open Pulley Designer | Opens cheapcadtools.com/tools/pulleys in the browser |
| Restore Pulley Design | Pick a previously exported file and reopen the designer with its embedded parameters |
| Import History | View and re-restore from the last 100 imports |
| Settings | Configure the watch folder and auto-import behaviour |

---

## Requirements

- FreeCAD 0.21 or later (1.x recommended)
- Internet connection (for the hosted web designer)
- Optional: [CheapCADTools desktop app](https://cheapcadtools.com) for offline use

## License

MIT -- see [LICENSE](LICENSE)
