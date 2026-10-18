# rawcull

Cull your JPGs in Explorer, and `rawcull` removes the RAWs that lost their twin.

```
D:\Photos\2026-10-18\
├── RAW\   DSC01001.ARW  DSC01002.ARW  DSC01003.ARW ...
└── JPG\   DSC01001.JPG                DSC01003.JPG ...   ← you deleted DSC01002.JPG
```

```console
> rawcull D:\Photos\2026-10-18
rawcull plan
  RAW folder : D:\Photos\2026-10-18\RAW
  JPG folder : D:\Photos\2026-10-18\JPG
  keepers    : 28 JPG name(s)
  RAWs       : 40 total, 27 kept, 13 to remove
  frees      : 312.4 MiB
  to remove (13):
    DSC01002.ARW
    ...
Send to Recycle Bin: 13 file(s)? [y/N]
```

Pure Python ≥ 3.9 standard library, no dependencies. Built for Windows; also runs on Linux/macOS.

## Install

```powershell
py -m pip install --user git+https://github.com/<you>/rawcull   # or, from the folder: py -m pip install .
rawcull --install-context-menu                                  # optional, see below
```

If `rawcull` isn't found afterwards, use `py -m rawcull ...` (pip's Scripts folder isn't on PATH).

## Usage

**Explorer:** after `rawcull --install-context-menu`, right-click the session folder (or empty space
inside it) → **Cull RAWs (rawcull)**. On Windows 11 it's under *Show more options* (Shift+right-click).
A console opens with the plan, asks `y/N`, and waits for Enter before closing.
`rawcull --uninstall-context-menu` removes it. Both are per-user; no admin rights needed.

**Console:**

```powershell
rawcull D:\Photos\2026-10-18            # plan → confirm → Recycle Bin
rawcull D:\Photos\2026-10-18 -n         # dry run
rawcull . --delete                      # permanent delete instead of Recycle Bin
rawcull . --move-to _rejected           # move instead (relative to the session folder)
rawcull --raw E:\DCIM\RAW --jpg D:\x\JPG -y
rawcull -h                              # everything else
```

Rejected files go to the **Recycle Bin** by default, all in one operation, so *Restore* brings
them back together. If a file can't go to the bin (SD card, USB stick, bin too small), Windows
asks before deleting it permanently rather than doing it silently.

### Matching rules

- Key = part of the file name **before the first dot** (`DSC01234.ARW.xmp` → `DSC01234`),
  case-insensitive (`--case-sensitive` to change).
- A RAW is kept if *any* keeper (`jpg,jpeg,hif,heif,heic`) with the same key exists.
- Sidecars (`DSC01234.xmp`, `DSC01234.ARW.xmp`, `.pp3`, `.dop`, `.on1`) go together with their RAW
  (`--no-sidecars` keeps them).
- Folders `RAW` and `JPG`/`JPEG` are found in any letter case.

### Safety checks

| Situation | Behaviour |
|---|---|
| JPG folder has no JPGs (wrong path) | refuse (exit 3), since it would remove everything |
| More than 95 % of RAWs would go (e.g. renamed JPGs) | refuse; `--max-fraction` / `--force` override |
| RAW and JPG are the same or nested folders | error |
| Unknown files in RAW (`notes.txt`, `Thumbs.db`, …), hidden dot-files | never touched, reported |
| Read-only files (typical when copied off an SD card) | handled |
| JPGs without a RAW, duplicate names | warned |
| Folders changed between preview and "y" (still culling?) | abort, nothing changed |
| Not an interactive console and no `-y` | refuse |
| Every run | writes `rawcull-<timestamp>.log` into the session (`--no-log` to skip) |

Exit codes: `0` ok · `1` error · `2` aborted · `3` refused by a safety check.

## Development

```powershell
py -m pip install -e ".[test]"
py -m pytest
```

CI runs the tests on Windows and Linux. The Recycle Bin, read-only and context-menu tests only run on Windows.
