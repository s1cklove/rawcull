"""rawcull desktop app: a Mantine UI in a native window (WebView2 on Windows) via pywebview.

    rawcull-gui [SESSION]        or        pythonw -m rawcull.gui [SESSION]

Set RAWCULL_DEBUG=1 to get devtools (right-click → Inspect).
"""

from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

from . import winutil
from .bridge import SessionApi

WEB_DIR = Path(__file__).with_name("web")   # built by `npm run build` in ui/


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if any(a in ("-h", "--help") for a in argv):
        print(__doc__)
        return 0
    selftest = "--selftest" in argv   # CI: open the window, check page + bridge, exit 0/1
    argv = [a for a in argv if a != "--selftest"]

    index = WEB_DIR / "index.html"
    if not index.exists():
        msg = (f"UI files are missing ({index}).\n"
               "Build them first:  cd ui && npm install && npm run build")
        print(msg, file=sys.stderr)
        _fatal_box(msg)
        return 1

    import webview
    from webview.dom import DOMEventHandler

    holder: dict = {}

    def push(js: str) -> None:
        w = holder.get("window")
        if w is not None:
            w.run_js(js)

    def folder_dialog(start: str):
        res = holder["window"].create_file_dialog(webview.FileDialog.FOLDER, directory=start or "")
        return res[0] if res else None

    api = SessionApi(Path(argv[0]) if argv else None, push=push, folder_dialog=folder_dialog)
    dark = winutil.prefers_dark()
    window = webview.create_window(
        "rawcull", url=str(index), js_api=api,
        width=1100, height=780, min_size=(820, 600),
        background_color="#18171D" if dark else "#FFFFFF",
    )
    holder["window"] = window

    def on_loaded() -> None:
        # Real file-system paths of dropped items are only provided to a Python 'drop' handler.
        # (dragover's preventDefault is done in the page itself — no Python round-trip per mouse move.)
        window.dom.document.events.drop += DOMEventHandler(api._handle_drop, prevent_default=True)

    window.events.loaded += on_loaded
    window.events.closed += api._stop_watching
    threading.Thread(target=api._watch_forever, daemon=True).start()

    result = {"ok": False}

    def run_selftest() -> None:
        import time

        deadline = time.time() + 45
        while time.time() < deadline:
            try:
                if window.evaluate_js(
                    "!!(window.pywebview && window.pywebview.api && window.pywebview.api.init)"
                    " && document.body.innerText.indexOf('Open a photo session') >= 0"
                ):
                    result["ok"] = True
                    break
            except Exception:
                pass
            time.sleep(0.5)
        window.destroy()

    webview.start(run_selftest if selftest else None, http_server=True,
                  debug=bool(os.environ.get("RAWCULL_DEBUG")), private_mode=True)
    if selftest:
        return 0 if result["ok"] else 1
    return 0


def _fatal_box(msg: str) -> None:
    if winutil.IS_WINDOWS:
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, msg, "rawcull", 0x10)


if __name__ == "__main__":
    raise SystemExit(main())
