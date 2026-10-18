"""Windows integration, stdlib only: Recycle Bin, read-only files, console colors, Explorer menu."""

from __future__ import annotations

import os
import re
import stat
import sys
from pathlib import Path

IS_WINDOWS = sys.platform == "win32"


# --------------------------------------------------------------------------- read-only files
def clear_readonly(p: Path) -> None:
    """Files copied off an SD card are often read-only; Windows then refuses to delete them."""
    try:
        mode = p.stat().st_mode
        if not mode & stat.S_IWRITE:
            os.chmod(p, mode | stat.S_IWRITE)
    except OSError:
        pass


def unlink_force(p: Path) -> None:
    try:
        p.unlink()
    except PermissionError:
        clear_readonly(p)
        p.unlink()


# --------------------------------------------------------------------------- Recycle Bin
def recycle(paths: list[Path]) -> list[tuple[Path, str]]:
    """Send files to the Recycle Bin in ONE shell operation (one Ctrl+Z / 'Restore' batch).

    Returns [(path, error)] for files that are still on disk afterwards.
    Uses SHFileOperationW with FOF_ALLOWUNDO. FOF_WANTNUKEWARNING makes Windows *ask*
    instead of silently deleting permanently when a file can't go to the bin
    (e.g. on an SD card / USB stick, or when the bin is too small).
    """
    if not paths:
        return []
    import ctypes
    from ctypes import wintypes

    FO_DELETE = 0x0003
    FOF_SILENT = 0x0004
    FOF_NOCONFIRMATION = 0x0010
    FOF_ALLOWUNDO = 0x0040
    FOF_NOERRORUI = 0x0400
    FOF_WANTNUKEWARNING = 0x4000

    class SHFILEOPSTRUCTW(ctypes.Structure):
        # shellapi.h packs this struct to 1 byte on 32-bit, 8 on 64-bit
        _pack_ = 8 if ctypes.sizeof(ctypes.c_void_p) == 8 else 1
        _fields_ = [
            ("hwnd", wintypes.HWND),
            ("wFunc", wintypes.UINT),
            ("pFrom", ctypes.c_void_p),
            ("pTo", ctypes.c_void_p),
            ("fFlags", ctypes.c_ushort),
            ("fAnyOperationsAborted", wintypes.BOOL),
            ("hNameMappings", ctypes.c_void_p),
            ("lpszProgressTitle", wintypes.LPCWSTR),
        ]

    # Double-NUL-terminated list of absolute paths.
    buf = ctypes.create_unicode_buffer("\0".join(str(p.resolve()) for p in paths) + "\0\0")
    op = SHFILEOPSTRUCTW()
    op.wFunc = FO_DELETE
    op.pFrom = ctypes.cast(buf, ctypes.c_void_p)
    op.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI | FOF_WANTNUKEWARNING

    rc = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
    why = (
        "cancelled" if op.fAnyOperationsAborted
        else f"SHFileOperation error 0x{rc:X}" if rc
        else "still exists after recycling"
    )
    return [(p, why) for p in paths if p.exists()]


# --------------------------------------------------------------------------- console
def enable_ansi() -> bool:
    """Turn on ANSI escape processing in classic conhost (Windows Terminal has it already)."""
    if not IS_WINDOWS:
        return True
    try:
        import ctypes

        k = ctypes.windll.kernel32
        h = k.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.c_uint32()
        if not k.GetConsoleMode(h, ctypes.byref(mode)):
            return False
        return bool(k.SetConsoleMode(h, mode.value | 0x0004))  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
    except Exception:
        return False


# --------------------------------------------------------------------------- Explorer menu
MENU_KEYS = (
    r"Software\Classes\Directory\shell\rawcull",              # right-click ON a folder
    r"Software\Classes\Directory\Background\shell\rawcull",   # right-click INSIDE a folder
)
MENU_TITLE = "Cull RAWs (rawcull)"


def menu_command() -> str:
    """Command that opens the desktop app on the clicked folder."""
    if getattr(sys, "frozen", False):  # running as the PyInstaller rawcull.exe
        return f'"{sys.executable}" "%V"'
    # pythonw.exe = no stray console window behind the app
    exe = re.sub(r"python\.exe$", "pythonw.exe", sys.executable, flags=re.IGNORECASE)
    return f'"{exe}" -m rawcull.gui "%V"'


def is_context_menu_installed() -> bool:
    if not IS_WINDOWS:
        return False
    import winreg

    try:
        winreg.OpenKey(winreg.HKEY_CURRENT_USER, MENU_KEYS[0] + r"\command").Close()
        return True
    except OSError:
        return False


def show_in_explorer(p: Path) -> None:
    import subprocess

    if IS_WINDOWS:
        subprocess.Popen(["explorer", "/select,", str(p)])
    else:
        subprocess.Popen(["xdg-open", str(p.parent)])


def prefers_dark() -> bool:
    """Windows 'Choose your app mode: Dark' (used for the window colour before the page loads)."""
    if not IS_WINDOWS:
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
            return winreg.QueryValueEx(k, "AppsUseLightTheme")[0] == 0
    except OSError:
        return False


def set_dpi_aware() -> None:
    """Crisp Tk fonts on high-DPI / scaled displays instead of blurry bitmap scaling."""
    if not IS_WINDOWS:
        return
    import ctypes

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # per-monitor (8.1+)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def install_context_menu() -> None:
    import winreg

    for key in MENU_KEYS:
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key) as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, MENU_TITLE)
            winreg.SetValueEx(k, "Icon", 0, winreg.REG_SZ, "shell32.dll,31")  # recycle bin icon
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key + r"\command") as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, menu_command())


def uninstall_context_menu() -> None:
    import winreg

    for key in MENU_KEYS:
        for sub in (key + r"\command", key):
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, sub)
            except FileNotFoundError:
                pass
