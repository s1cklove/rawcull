# Builds dist\rawcull.exe — single-file desktop app; the target PC needs no Python or Node.
# (WebView2 is part of Windows 10/11.)
# Run from the repo root:   powershell -ExecutionPolicy Bypass -File packaging\build_exe.ps1
$ErrorActionPreference = "Stop"

Push-Location ui
npm ci
npm run build          # -> src\rawcull\web
Pop-Location

py -m pip install --upgrade pyinstaller
py -m pip install -e ".[app]"
py -m PyInstaller --noconfirm --clean --onefile --windowed `
    --name rawcull `
    --icon src\rawcull\rawcull.ico `
    --add-data "src\rawcull\web;rawcull\web" `
    --add-data "src\rawcull\rawcull.ico;rawcull" `
    packaging\rawcull_gui.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

# Start it for real: window opens, page renders, Python bridge answers -> exit code 0.
$p = Start-Process dist\rawcull.exe -ArgumentList "--selftest" -PassThru
if (-not $p.WaitForExit(90000)) { Stop-Process $p -Force; throw "rawcull.exe --selftest timed out" }
if ($p.ExitCode -ne 0) { throw "rawcull.exe --selftest failed (exit $($p.ExitCode))" }
Write-Host "Built and self-tested: $(Resolve-Path dist\rawcull.exe)"
