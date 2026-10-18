"""The API the desktop UI talks to.

Every public method of :class:`SessionApi` is callable from the page as
``window.pywebview.api.<name>(...)`` and returns plain JSON-able data.
Pushes from Python to the page go through ``window.rawcull.on*`` callbacks.

Kept free of any webview import so it can be unit-tested without a window.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
from pathlib import Path
from typing import Any, Callable, Optional

from . import __version__, settings, winutil
from .actions import KINDS, ActionError, default_kind, make_action, write_log
from .core import Plan, assess, build_plan, dirs_problem, find_session_dirs, split_name

WATCH_SECONDS = 1.5

Push = Callable[[str], None]          # runs a JS snippet in the page
FolderDialog = Callable[[str], Optional[str]]


def normalize_session(p: Path) -> Path:
    """Accept the session folder, its RAW\\/JPG\\ subfolder, or any file inside either."""
    if p.is_file():
        p = p.parent
    if p.name.casefold() in ("raw", "jpg", "jpeg") and all(find_session_dirs(p.parent)):
        return p.parent
    return p


def plan_signature(plan: Plan) -> str:
    """Identifies exactly which files the user was shown; removal refuses on mismatch."""
    h = hashlib.sha1()
    for p in plan.to_remove:
        h.update(str(p).encode("utf-8", "surrogatepass") + b"\0")
    return h.hexdigest()


def _size(p: Path) -> int:
    try:
        return p.stat().st_size
    except OSError:
        return 0


class SessionApi:
    def __init__(self, initial_session: Path | None = None,
                 push: Push | None = None, folder_dialog: FolderDialog | None = None):
        self._push_js = push
        self._folder_dialog = folder_dialog
        self._initial = initial_session
        self._settings = settings.load()
        self._lock = threading.RLock()
        self._busy = False
        self._session: Path | None = None
        self._raw: Path | None = None
        self._jpg: Path | None = None
        self._mtimes: tuple | None = None
        self._stop = threading.Event()

    # ================================================================ called from the page
    def init(self) -> dict:
        snap = None
        if self._initial is not None:
            snap = self.open_session(str(self._initial))
            self._initial = None
        elif self._session is not None:
            snap = self.rescan()
        return {
            "version": __version__,
            "platform": "windows" if winutil.IS_WINDOWS else "other",
            "action": self._settings.get("action") if self._settings.get("action") in KINDS else default_kind(),
            "options": self._options(),
            "menuInstalled": winutil.is_context_menu_installed(),
            "snapshot": snap,
        }

    def pick_session(self) -> dict | None:
        start = str(self._session.parent) if self._session else self._settings.get("last_dir", "")
        chosen = self._folder_dialog(start) if self._folder_dialog else None
        return self.open_session(chosen) if chosen else None

    def open_session(self, path: str) -> dict:
        p = normalize_session(Path(path.strip().strip('"')).expanduser())
        with self._lock:
            if not p.is_dir():
                return {"problem": f"Folder not found: {p}"}
            self._session = p.resolve()
            self._raw, self._jpg = find_session_dirs(self._session)
            self._settings["last_dir"] = str(self._session.parent)
            settings.save(self._settings)
            return self._scan()

    def pick_dir(self, which: str) -> dict | None:
        if which not in ("raw", "jpg"):
            raise ValueError(which)
        start = str(self._session or self._settings.get("last_dir", ""))
        chosen = self._folder_dialog(start) if self._folder_dialog else None
        if not chosen:
            return None
        with self._lock:
            d = Path(chosen).resolve()
            if which == "raw":
                self._raw = d
            else:
                self._jpg = d
            if self._session is None:
                self._session = d.parent
            return self._scan()

    def rescan(self) -> dict | None:
        with self._lock:
            return self._scan() if self._session else None

    def set_options(self, case_sensitive: bool, sidecars: bool) -> dict | None:
        self._settings.update(case_sensitive=bool(case_sensitive), sidecars=bool(sidecars))
        settings.save(self._settings)
        return self.rescan()

    def set_action(self, kind: str) -> None:
        if kind in KINDS:
            self._settings["action"] = kind
            settings.save(self._settings)

    def remove(self, kind: str, force: bool, signature: str) -> dict:
        """Remove exactly the files the page showed (identified by `signature`)."""
        with self._lock:
            if self._busy:
                return {"ok": False, "reason": "busy", "message": "Already working."}
            if not self._ready():
                return {"ok": False, "reason": "no-session", "message": "No session open."}
            plan = build_plan(self._raw, self._jpg, **self._plan_opts())
            if plan_signature(plan) != signature:
                return {"ok": False, "reason": "stale",
                        "message": "The folders changed since the list was shown. Nothing was removed — "
                                   "check the updated list.",
                        "snapshot": self._snapshot(plan)}
            a = assess(plan)
            if not a.safe and not force:
                return {"ok": False, "reason": "blocked", "message": " ".join(a.errors)}
            if not plan.to_remove:
                return {"ok": False, "reason": "empty", "message": "Nothing to remove."}
            try:
                action = make_action(kind, self._session)
            except (ActionError, ValueError) as e:
                return {"ok": False, "reason": "action", "message": str(e)}
            self._busy = True
            session, raw, jpg, paths = self._session, self._raw, self._jpg, list(plan.to_remove)

        try:  # the slow part runs outside the lock; the watcher skips while busy
            failed = dict(action.run(paths, lambda i, n: self._push("onProgress", i, n)))
            log_name = None
            try:
                log_name = write_log(session, raw, jpg, action, paths, failed).name
            except OSError:
                pass
        finally:
            with self._lock:
                self._busy = False
        with self._lock:
            snap = self._scan()
        return {
            "ok": True,
            "done": len(paths) - len(failed),
            "verb": action.done,
            "failed": [{"name": p.name, "error": why} for p, why in failed.items()],
            "log": log_name,
            "snapshot": snap,
        }

    def reveal(self, path: str) -> None:
        winutil.show_in_explorer(Path(path))

    def open_session_folder(self) -> None:
        if self._session:
            if winutil.IS_WINDOWS:
                os.startfile(self._session)  # type: ignore[attr-defined]
            else:
                winutil.show_in_explorer(self._session / ".")

    def set_context_menu(self, on: bool) -> bool:
        if winutil.IS_WINDOWS:
            (winutil.install_context_menu if on else winutil.uninstall_context_menu)()
        return winutil.is_context_menu_installed()

    # ================================================================ called from Python (private: not exposed to JS)
    def _handle_drop(self, event: dict) -> None:
        """DOM 'drop' handler (pywebview fills in pywebviewFullPath for real files/folders)."""
        files = (event.get("dataTransfer") or {}).get("files") or []
        paths = [f.get("pywebviewFullPath") for f in files if f.get("pywebviewFullPath")]
        if not paths:
            self._push("onDropFailed")
            return
        self._push("onSnapshot", self.open_session(paths[0]))

    def _watch_forever(self) -> None:
        """Background thread: re-scan when either folder changes (you keep culling in Explorer)."""
        while not self._stop.wait(WATCH_SECONDS):
            self._poll_changes()

    def _poll_changes(self) -> bool:
        with self._lock:
            if self._busy or not self._ready():
                return False
            m = self._folder_mtimes()
            if m is None or m == self._mtimes:
                return False
            snap = self._scan()
        self._push("onSnapshot", snap)
        return True

    def _stop_watching(self) -> None:
        self._stop.set()

    # ================================================================ internals
    def _push(self, fn: str, *args: Any) -> None:
        if self._push_js is None:
            return
        # ASCII-only JSON (\uXXXX escapes): some webview backends size the script in characters
        # but read it as UTF-8 bytes, truncating pushes that contain e.g. Cyrillic folder names.
        payload = ",".join(json.dumps(a, ensure_ascii=True) for a in args)
        try:
            self._push_js(f"window.rawcull && window.rawcull.{fn} && window.rawcull.{fn}({payload})")
        except Exception:
            pass  # window closing etc.

    def _options(self) -> dict:
        return {"caseSensitive": bool(self._settings.get("case_sensitive", False)),
                "sidecars": bool(self._settings.get("sidecars", True))}

    def _plan_opts(self) -> dict:
        o = self._options()
        return dict(case_sensitive=o["caseSensitive"], include_sidecars=o["sidecars"])

    def _ready(self) -> bool:
        return (self._session is not None and self._raw is not None and self._jpg is not None
                and self._raw.is_dir() and self._jpg.is_dir())

    def _folder_mtimes(self) -> tuple | None:
        try:
            return (os.stat(self._raw).st_mtime_ns, os.stat(self._jpg).st_mtime_ns)
        except (OSError, TypeError):
            return None

    def _rel(self, d: Path | None) -> str | None:
        if d is None:
            return None
        try:
            return str(d.relative_to(self._session)) + os.sep
        except ValueError:
            return str(d)

    def _scan(self) -> dict:
        self._mtimes = self._folder_mtimes()
        base = {"session": {"path": str(self._session), "name": self._session.name},
                "rawDir": self._rel(self._raw), "jpgDir": self._rel(self._jpg)}
        missing = [n for n, d in (("RAW", self._raw), ("JPG", self._jpg)) if d is None or not d.is_dir()]
        if missing:
            return {**base, "problem": f"Couldn't find a {' or '.join(missing)} folder here. "
                                       "Open the session folder itself, or choose the folders manually."}
        problem = dirs_problem(self._raw, self._jpg)
        if problem:
            return {**base, "problem": problem}
        try:
            plan = build_plan(self._raw, self._jpg, **self._plan_opts())
        except OSError as e:
            return {**base, "problem": f"Couldn't read the folders: {e}"}
        return self._snapshot(plan)

    def _snapshot(self, plan: Plan) -> dict:
        a = assess(plan)

        def row(p: Path, kind: str) -> dict:
            return {"name": p.name, "path": str(p), "kind": kind, "size": _size(p)}

        remove = [row(p, "raw" if split_name(p.name)[1] in plan.raw_exts else "sidecar") for p in plan.to_remove]
        return {
            "session": {"path": str(self._session), "name": self._session.name},
            "rawDir": self._rel(self._raw),
            "jpgDir": self._rel(self._jpg),
            "problem": None,
            "stats": {
                "keepers": len(plan.kept_keys),
                "raws": plan.total_raws,
                "kept": len(plan.kept_raws),
                "remove": len(plan.raws_to_remove),
                "sidecars": len(plan.sidecars_to_remove),
                "bytes": sum(r["size"] for r in remove),
            },
            "errors": a.errors,
            "warnings": a.warnings,
            "files": {
                "remove": remove,
                "orphan": [row(p, "jpg") for p in plan.jpg_without_raw],
                "ignored": [row(p, "raw") for p in plan.ignored_raw_dir]
                           + [row(p, "jpg") for p in plan.ignored_jpg_dir],
            },
            "signature": plan_signature(plan),
        }
