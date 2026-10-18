"""Command-line interface for rawcull. (The desktop app is rawcull.gui.)"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import __version__, winutil
from .actions import ActionError, default_kind, make_action, write_log
from .core import (
    DEFAULT_JPG_EXTS,
    DEFAULT_RAW_EXTS,
    DEFAULT_SIDECAR_EXTS,
    Plan,
    assess,
    build_plan,
    dirs_problem,
    find_session_dirs,
)

EXIT_OK, EXIT_ERROR, EXIT_ABORTED, EXIT_UNSAFE = 0, 1, 2, 3


# --------------------------------------------------------------------------- output helpers
class Out:
    def __init__(self, color: bool):
        self.color = color

    def _c(self, code: str, s: str) -> str:
        return f"\033[{code}m{s}\033[0m" if self.color else s

    def bold(self, s: str) -> str: return self._c("1", s)
    def red(self, s: str) -> str: return self._c("31", s)
    def yellow(self, s: str) -> str: return self._c("33", s)
    def green(self, s: str) -> str: return self._c("32", s)
    def dim(self, s: str) -> str: return self._c("2", s)

    def warn(self, s: str) -> None: print(self.yellow("warning: ") + s)
    def err(self, s: str) -> None: print(self.red("error: ") + s)


def human(n: float) -> str:
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if n < 1024 or unit == "TiB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    raise AssertionError


def show_list(out: Out, title: str, paths: list[Path], limit: int | None) -> None:
    if not paths:
        return
    print(f"  {title} ({len(paths)}):")
    shown = paths if limit is None else paths[:limit]
    for p in shown:
        print("    " + out.dim(p.name))
    if len(shown) < len(paths):
        print("    " + out.dim(f"... and {len(paths) - len(shown)} more (use -v to list all)"))


# --------------------------------------------------------------------------- arg parsing
def parse_exts(s: str) -> frozenset[str]:
    exts = frozenset(e.strip().lstrip(".").lower() for e in s.split(",") if e.strip())
    if not exts:
        raise argparse.ArgumentTypeError("empty extension list")
    return exts


def fraction(s: str) -> float:
    v = float(s)
    if not 0 <= v <= 1:
        raise argparse.ArgumentTypeError("must be between 0 and 1")
    return v


def build_parser() -> argparse.ArgumentParser:
    default_action = "Recycle Bin" if winutil.IS_WINDOWS else "permanent delete"
    p = argparse.ArgumentParser(
        prog="rawcull",
        description=(
            "Remove RAW files (and their sidecars) whose JPG twin has been deleted. "
            "Files are matched by the part of the name before the first dot."
        ),
        epilog=(
            "Exit codes: 0 ok, 1 error, 2 aborted by user, 3 refused by a safety check.\n"
            "Typical use:  rawcull D:\\Photos\\2026-10-18   (preview, then confirm)\n"
            "Desktop app:  rawcull-gui"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("session", nargs="?", type=Path, default=Path("."),
                   help="session folder containing RAW\\ and JPG\\ (default: current folder)")
    p.add_argument("--raw", type=Path, metavar="DIR", help="RAW folder (default: SESSION\\RAW, any case)")
    p.add_argument("--jpg", type=Path, metavar="DIR", help="JPG folder (default: SESSION\\JPG or SESSION\\JPEG)")

    act = p.add_argument_group(f"what to do with rejected RAWs (default: {default_action})")
    m = act.add_mutually_exclusive_group()
    m.add_argument("--trash", action="store_true",
                   help="send to the Recycle Bin (default on Windows; elsewhere needs 'send2trash')")
    m.add_argument("--delete", action="store_true", help="delete permanently")
    m.add_argument("--move-to", type=Path, metavar="DIR",
                   help="move into DIR (relative paths are relative to SESSION)")

    run = p.add_argument_group("run control")
    run.add_argument("-n", "--dry-run", action="store_true", help="only show the plan, change nothing")
    run.add_argument("-y", "--yes", action="store_true", help="don't ask for confirmation")
    run.add_argument("-v", "--verbose", action="store_true", help="list every file, not just the first few")
    run.add_argument("--no-log", action="store_true", help="don't write rawcull-<timestamp>.log into SESSION")
    run.add_argument("--pause", action="store_true", help="wait for Enter before exiting")
    run.add_argument("--color", choices=("auto", "always", "never"), default="auto")

    safety = p.add_argument_group("matching & safety")
    safety.add_argument("--raw-ext", type=parse_exts, default=DEFAULT_RAW_EXTS, metavar="EXTS",
                        help="comma-separated RAW extensions (default: %s)" % ",".join(sorted(DEFAULT_RAW_EXTS)))
    safety.add_argument("--jpg-ext", type=parse_exts, default=DEFAULT_JPG_EXTS, metavar="EXTS",
                        help="comma-separated 'keeper' extensions (default: %s)" % ",".join(sorted(DEFAULT_JPG_EXTS)))
    safety.add_argument("--sidecar-ext", type=parse_exts, default=DEFAULT_SIDECAR_EXTS, metavar="EXTS",
                        help="sidecar extensions removed together with the RAW (default: %s)"
                        % ",".join(sorted(DEFAULT_SIDECAR_EXTS)))
    safety.add_argument("--no-sidecars", action="store_true", help="never touch sidecar files")
    safety.add_argument("--case-sensitive", action="store_true",
                        help="treat DSC0001 and dsc0001 as different shots")
    safety.add_argument("--max-fraction", type=fraction, default=0.95, metavar="F",
                        help="refuse if more than this fraction of RAWs would be removed (default: 0.95)")
    safety.add_argument("--force", action="store_true", help="override the refusable safety checks")

    win = p.add_argument_group("Windows Explorer integration (current user, no admin needed)")
    win.add_argument("--install-context-menu", action="store_true",
                     help=f"add '{winutil.MENU_TITLE}' (opens the desktop app) to the folder right-click menu")
    win.add_argument("--uninstall-context-menu", action="store_true", help="remove it again")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


# --------------------------------------------------------------------------- steps
def resolve_dirs(args: argparse.Namespace, out: Out) -> tuple[Path, Path] | None:
    auto_raw, auto_jpg = find_session_dirs(args.session) if not (args.raw and args.jpg) else (None, None)
    raw, jpg = args.raw or auto_raw, args.jpg or auto_jpg
    ok = True
    for label, d, flag in (("RAW", raw, "--raw"), ("JPG", jpg, "--jpg")):
        if d is None:
            out.err(f"couldn't find a single {label} folder in '{args.session.resolve()}' (pass {flag} DIR)")
            ok = False
        elif not d.is_dir():
            out.err(f"{label} folder '{d}' doesn't exist or isn't a folder")
            ok = False
    if not ok:
        return None
    problem = dirs_problem(raw, jpg)
    if problem:
        out.err(problem)
        return None
    return raw.resolve(), jpg.resolve()


def print_summary(plan: Plan, args: argparse.Namespace, out: Out) -> None:
    limit = None if args.verbose else 10
    print(out.bold("rawcull plan"))
    print(f"  RAW folder : {plan.raw_dir}")
    print(f"  JPG folder : {plan.jpg_dir}")
    print(f"  keepers    : {len(plan.kept_keys)} JPG name(s)")
    print(f"  RAWs       : {plan.total_raws} total, "
          f"{out.green(str(len(plan.kept_raws)) + ' kept')}, "
          f"{out.red(str(len(plan.raws_to_remove)) + ' to remove')}")
    if plan.sidecars_to_remove:
        print(f"  sidecars   : {len(plan.sidecars_to_remove)} to remove with their RAWs")
    if plan.to_remove:
        print(f"  frees      : {human(plan.bytes_to_remove())}")
    show_list(out, "to remove", plan.to_remove, limit)
    if args.verbose:
        show_list(out, "JPGs without RAW", plan.jpg_without_raw, None)
        show_list(out, "ignored in RAW folder", plan.ignored_raw_dir, None)
        show_list(out, "ignored in JPG folder", plan.ignored_jpg_dir, None)


def confirm(prompt: str) -> bool:
    try:
        return input(prompt).strip().lower() in ("y", "yes", "д", "да")
    except EOFError:
        return False


def run(args: argparse.Namespace, out: Out) -> int:
    if args.install_context_menu or args.uninstall_context_menu:
        if not winutil.IS_WINDOWS:
            out.err("the Explorer context menu is Windows-only")
            return EXIT_ERROR
        if args.install_context_menu:
            winutil.install_context_menu()
            print(out.green(f"Added '{winutil.MENU_TITLE}' to the folder right-click menu.")
                  + out.dim("\n(Windows 11: it's under 'Show more options' / Shift+right-click.)"))
        else:
            winutil.uninstall_context_menu()
            print(out.green("Context menu entry removed."))
        return EXIT_OK

    dirs = resolve_dirs(args, out)
    if dirs is None:
        return EXIT_ERROR
    raw_dir, jpg_dir = dirs
    session = args.session.resolve()

    opts = dict(
        raw_exts=args.raw_ext, jpg_exts=args.jpg_ext, sidecar_exts=args.sidecar_ext,
        case_sensitive=args.case_sensitive, include_sidecars=not args.no_sidecars,
    )
    plan = build_plan(raw_dir, jpg_dir, **opts)
    print_summary(plan, args, out)

    a = assess(plan, max_fraction=args.max_fraction)
    for w in a.warnings:
        out.warn(w)
    for e in a.errors:
        (out.warn if args.force else out.err)(("(forced) " if args.force else "") + e)
    if not a.safe and not args.force:
        out.err("refusing. Use --force (or --max-fraction) if this is really intended.")
        return EXIT_UNSAFE

    if not plan.to_remove:
        print(out.green("Nothing to do — every RAW still has its JPG."))
        return EXIT_OK
    if args.dry_run:
        print(out.dim("dry run: nothing changed"))
        return EXIT_OK

    kind = "move" if args.move_to else "trash" if args.trash else "delete" if args.delete else default_kind()
    try:
        action = make_action(kind, session, args.move_to)
    except ActionError as e:
        out.err(str(e))
        return EXIT_ERROR

    if not args.yes:
        if not sys.stdin.isatty():
            out.err("not an interactive console and no --yes given; refusing to act")
            return EXIT_ABORTED
        if not confirm(f"{action.prompt}: {len(plan.to_remove)} file(s)? [y/N] "):
            print("Aborted, nothing changed.")
            return EXIT_ABORTED

    # Re-scan right before acting: if you were still culling in Explorer meanwhile,
    # the plan may be stale. Never act on a stale plan.
    if build_plan(raw_dir, jpg_dir, **opts).to_remove != plan.to_remove:
        out.err("folders changed since the plan was shown; nothing was changed. Run again.")
        return EXIT_ABORTED

    failed = dict(action.run(plan.to_remove, None))
    for p, why in failed.items():
        out.err(f"{p.name}: {why}")
    done = len(plan.to_remove) - len(failed)
    print(out.green(f"{done} file(s) {action.done}.") + (out.red(f" {len(failed)} failed.") if failed else ""))
    if not args.no_log:
        try:
            print(out.dim(f"log: {write_log(session, raw_dir, jpg_dir, action, plan.to_remove, failed)}"))
        except OSError as e:
            out.warn(f"couldn't write log: {e}")
    return EXIT_ERROR if failed else EXIT_OK


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    use_color = args.color == "always" or (
        args.color == "auto" and sys.stdout.isatty() and "NO_COLOR" not in os.environ
        and winutil.enable_ansi()
    )
    out = Out(use_color)
    try:
        code = run(args, out)
    except KeyboardInterrupt:
        print("\nInterrupted.")
        code = EXIT_ABORTED
    if args.pause:
        try:
            input("\nPress Enter to close...")
        except EOFError:
            pass
    return code


if __name__ == "__main__":
    raise SystemExit(main())
