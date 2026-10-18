"""What happens to rejected files: Recycle Bin / move / delete, plus the run log. Shared by CLI and GUI."""

from __future__ import annotations

import datetime as dt
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from . import __version__, winutil

Progress = Optional[Callable[[int, int], None]]
# executor(paths, progress) -> [(path, error message)] for the files that failed
Executor = Callable[[list, Progress], list]

KINDS = ("trash", "move", "delete")
DEFAULT_MOVE_DIR = "_rejected"


class ActionError(Exception):
    pass


@dataclass
class Action:
    kind: str
    prompt: str   # "Send to Recycle Bin"
    done: str     # "sent to the Recycle Bin"
    run: Executor


def default_kind() -> str:
    return "trash" if winutil.IS_WINDOWS else "delete"


def _per_file(fn: Callable[[Path], None]) -> Executor:
    def run(paths: list[Path], progress: Progress = None) -> list[tuple[Path, str]]:
        failed = []
        for i, p in enumerate(paths):
            try:
                fn(p)
            except OSError as e:
                failed.append((p, e.strerror or str(e)))
            if progress:
                progress(i + 1, len(paths))
        return failed
    return run


def make_action(kind: str, session: Path, move_to: Path | None = None) -> Action:
    if kind == "move":
        dest = move_to or Path(DEFAULT_MOVE_DIR)
        dest = dest if dest.is_absolute() else session / dest

        def move(p: Path) -> None:
            dest.mkdir(parents=True, exist_ok=True)
            target = dest / p.name
            if target.exists():
                raise FileExistsError(0, f"{target} already exists")
            winutil.clear_readonly(p)  # cross-drive moves are copy + delete
            shutil.move(str(p), str(target))
        try:
            shown = str(dest.relative_to(session)) + os.sep  # "_rejected\\" rather than a long path
        except ValueError:
            shown = str(dest)
        return Action("move", f"Move to {shown}", f"moved to {shown}", _per_file(move))

    if kind == "trash":
        if winutil.IS_WINDOWS:
            def recycle(paths: list[Path], progress: Progress = None):
                failed = winutil.recycle(paths)
                if progress:
                    progress(len(paths), len(paths))
                return failed
            return Action("trash", "Send to Recycle Bin", "sent to the Recycle Bin", recycle)
        try:
            from send2trash import send2trash  # type: ignore
        except ImportError:
            raise ActionError("Trash outside Windows needs 'send2trash' (pip install send2trash)")
        return Action("trash", "Trash", "trashed", _per_file(lambda p: send2trash(str(p))))

    if kind == "delete":
        return Action("delete", "PERMANENTLY delete", "deleted", _per_file(winutil.unlink_force))

    raise ValueError(kind)


def write_log(session: Path, raw_dir: Path, jpg_dir: Path, action: Action,
              paths: list[Path], failed: dict[Path, str]) -> Path:
    now = dt.datetime.now()
    log = session / f"rawcull-{now:%Y%m%d-%H%M%S}.log"
    lines = [f"# rawcull {__version__} {now.isoformat(timespec='seconds')}",
             f"# raw={raw_dir} jpg={jpg_dir} action={action.done}"]
    lines += [f"FAIL\t{p}\t{failed[p]}" if p in failed else f"OK\t{p}" for p in paths]
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return log
