# rawcull

Cull your JPGs, and `rawcull` removes the RAWs that lost their twin.

```
D:\Photos\2026-10-18\
├── RAW\   DSC01001.ARW  DSC01002.ARW  DSC01003.ARW ...
└── JPG\   DSC01001.JPG                DSC01003.JPG ...   ← you deleted DSC01002.JPG
```

A Windows desktop app (React + Mantine in a native WebView2 window via pywebview) plus a
command-line tool, on the same Python core. The CLI is pure standard library. There's also a single
`rawcull.exe` that needs neither Python nor Node.

## Get it

**Just the app (no Python):** grab `rawcull.exe` from the latest GitHub Release, or from
*Actions → build rawcull.exe → Run workflow → artifact*. Put it anywhere, e.g. `C:\Tools\`.
Windows SmartScreen will warn once because the exe isn't code-signed: *More info → Run anyway*.

**With Python 3.9+:**

```powershell
py -m pip install --user ".[app]"   # from the repo folder; drop [app] if you only want the CLI
rawcull-gui                         # desktop app
rawcull D:\Photos\2026-10-18        # command line
```

The desktop app needs the built UI in `src\rawcull\web\` (the release zip has it). From a fresh
git checkout, build it once with `cd ui; npm ci; npm run build`.

If the commands aren't found, use `py -m rawcull.gui` / `py -m rawcull` (pip's Scripts folder isn't on PATH).

## Desktop app

1. **Open a session.** Drag the session folder, its `RAW\`/`JPG\`, or any photo from it into the
   window. You can also press *Open* (Ctrl+O), or right-click the folder in Explorer → *Cull RAWs
   (rawcull)*. Turn that menu entry on once in *⋯ → “Cull RAWs” in folder right-click menu*; on
   Windows 11 it's under *Show more options*.
2. **Check the counts.** You see keepers, RAWs kept, RAWs to remove and space freed, plus any
   warnings. The tabs list **To remove**, **JPGs without RAW** and **Ignored files**.
   Double-click a row, or use its icon, to show the file in Explorer.
3. **Keep culling in Explorer** if you like: the list refreshes by itself ("Watching for changes").
4. **Choose what happens to rejects**: **Recycle Bin** (default), **Move to `_rejected\`** or
   **Delete**. Then press the button and confirm. A toast reports the result and the name of the log file.

The app follows the Windows light/dark setting. It uses the same Mantine theme and surface
colours as the Lectory web app (GitLab-like blue, Inter, small radii). It remembers your action and
options between runs.

## Command line

```powershell
rawcull D:\Photos\2026-10-18            # plan → confirm → Recycle Bin
rawcull D:\Photos\2026-10-18 -n         # dry run
rawcull . --delete                      # permanent delete instead of Recycle Bin
rawcull . --move-to _rejected           # move instead (relative to the session folder)
rawcull --raw E:\DCIM\RAW --jpg D:\x\JPG -y
rawcull -h                              # everything else
```

Exit codes: `0` ok · `1` error · `2` aborted · `3` refused by a safety check.

## How matching works

- Key = part of the file name **before the first dot** (`DSC01234.ARW.xmp` → `DSC01234`),
  case-insensitive (switchable).
- A RAW is kept if *any* keeper (`jpg, jpeg, hif, heif, heic`) with the same key exists.
- Sidecars (`DSC01234.xmp`, `DSC01234.ARW.xmp`, `.pp3`, `.dop`, `.on1`) go together with their RAW (switchable).
- Folders `RAW` and `JPG`/`JPEG` are found in any letter case.

## Safety

| Situation | Behaviour |
|---|---|
| JPG folder has no JPGs (wrong folder) | blocked, since it would remove everything |
| More than 95 % of RAWs would go (e.g. renamed JPGs) | blocked unless you override |
| RAW and JPG are the same or nested folders | error |
| Unknown files in RAW (`notes.txt`, `Thumbs.db`, …), hidden dot-files | never touched, listed |
| Read-only files (typical when copied off an SD card) | handled |
| Folders changed between showing the list and confirming | nothing is removed; list refreshed |
| Recycle Bin unavailable (SD card, USB stick, bin too small) | Windows asks before deleting permanently |
| Every run | writes `rawcull-<timestamp>.log` into the session |

Recycle Bin removals are one batch, so *Restore* brings them back together.

## Development

```powershell
py -m pip install -e ".[app,test]"
py -m pytest                                   # core, CLI, desktop bridge (no window needed)

cd ui
npm ci
npm run dev        # UI in the browser against an in-memory mock (no Python), hot reload
npm run build      # type-check + build into src\rawcull\web\
cd ..
py -m rawcull.gui  # the real app; set RAWCULL_DEBUG=1 for devtools

powershell -ExecutionPolicy Bypass -File packaging\build_exe.ps1    # -> dist\rawcull.exe (+ self-test)
```

Mock scenarios for UI work: `index.html?mock=session|empty|blocked|problem|clean`.

**Layout**

- `src/rawcull/core.py`: matching and safety checks
- `actions.py`: Recycle Bin / move / delete, plus the log
- `cli.py`: command line
- `bridge.py`: the API the UI calls
- `gui.py`: the window
- `ui/`: React + Mantine

**CI**

- `tests` runs pytest on Windows and Linux and type-checks and builds the UI.
- `build rawcull.exe` builds the exe on Windows and runs `rawcull.exe --selftest`. The self-test opens
  the real window, checks that the page rendered and the Python bridge answers, then exits 0/1.
- Pushing a `v*` tag attaches the exe to a GitHub Release.
