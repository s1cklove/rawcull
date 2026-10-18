"""Pure planning logic. Only reads directory listings; never modifies anything."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

# Extensions are compared case-insensitively, without the leading dot.
DEFAULT_RAW_EXTS = frozenset({"arw", "srf", "sr2", "cr2", "cr3", "nef", "raf", "orf", "rw2", "dng", "pef"})
DEFAULT_JPG_EXTS = frozenset({"jpg", "jpeg", "hif", "heif", "heic"})
# Editor sidecars that live next to RAWs: DSC0001.xmp, DSC0001.ARW.xmp, DSC0001.ARW.pp3, ...
DEFAULT_SIDECAR_EXTS = frozenset({"xmp", "pp3", "dop", "on1"})


def split_name(name: str) -> tuple[str, str]:
    """'DSC01234.ARW.xmp' -> ('DSC01234', 'arw.xmp').

    Key = everything before the *first* dot (i.e. ``name.split('.')[0]``),
    suffix = everything after it, lowercased.
    """
    key, _, suffix = name.partition(".")
    return key, suffix.lower()


@dataclass
class Plan:
    raw_dir: Path
    jpg_dir: Path
    raw_exts: frozenset[str]
    kept_keys: set[str] = field(default_factory=set)            # keys that still have a JPG
    to_remove: list[Path] = field(default_factory=list)         # RAWs + their sidecars
    kept_raws: list[Path] = field(default_factory=list)
    ignored_raw_dir: list[Path] = field(default_factory=list)   # unknown files: never touched
    ignored_jpg_dir: list[Path] = field(default_factory=list)
    jpg_without_raw: list[Path] = field(default_factory=list)
    duplicate_jpg_keys: dict[str, list[Path]] = field(default_factory=dict)

    @property
    def raws_to_remove(self) -> list[Path]:
        return [p for p in self.to_remove if split_name(p.name)[1] in self.raw_exts]

    @property
    def sidecars_to_remove(self) -> list[Path]:
        return [p for p in self.to_remove if split_name(p.name)[1] not in self.raw_exts]

    @property
    def total_raws(self) -> int:
        return len(self.kept_raws) + len(self.raws_to_remove)

    def bytes_to_remove(self) -> int:
        return sum(p.stat().st_size for p in self.to_remove)


def _list_files(d: Path) -> list[Path]:
    # Hidden files (.DS_Store, macOS ._DSC0001.ARW, ...) are ignored entirely.
    return sorted(p for p in d.iterdir() if p.is_file() and not p.name.startswith("."))


def classify_raw_dir_entry(
    suffix: str, raw_exts: frozenset[str], sidecar_exts: frozenset[str], include_sidecars: bool
) -> str:
    """Return 'raw', 'sidecar' or 'other' for a suffix chain like 'arw' / 'arw.xmp' / 'xmp'."""
    if suffix in raw_exts:
        return "raw"
    if include_sidecars:
        parts = suffix.split(".")
        if parts[-1] in sidecar_exts and (len(parts) == 1 or (len(parts) == 2 and parts[0] in raw_exts)):
            return "sidecar"
    return "other"


def build_plan(
    raw_dir: Path,
    jpg_dir: Path,
    *,
    raw_exts: frozenset[str] = DEFAULT_RAW_EXTS,
    jpg_exts: frozenset[str] = DEFAULT_JPG_EXTS,
    sidecar_exts: frozenset[str] = DEFAULT_SIDECAR_EXTS,
    case_sensitive: bool = False,
    include_sidecars: bool = True,
) -> Plan:
    norm = (lambda k: k) if case_sensitive else str.casefold
    plan = Plan(raw_dir=raw_dir, jpg_dir=jpg_dir, raw_exts=raw_exts)

    # JPG side: which keys survived the cull.
    jpg_by_key: dict[str, list[Path]] = {}
    for p in _list_files(jpg_dir):
        key, suffix = split_name(p.name)
        if suffix in jpg_exts:
            jpg_by_key.setdefault(norm(key), []).append(p)
        else:
            plan.ignored_jpg_dir.append(p)
    plan.kept_keys = set(jpg_by_key)
    plan.duplicate_jpg_keys = {k: v for k, v in jpg_by_key.items() if len(v) > 1}

    # RAW side.
    raw_keys: set[str] = set()
    for p in _list_files(raw_dir):
        key, suffix = split_name(p.name)
        kind = classify_raw_dir_entry(suffix, raw_exts, sidecar_exts, include_sidecars)
        if kind == "other":
            plan.ignored_raw_dir.append(p)
            continue
        nkey = norm(key)
        if kind == "raw":
            raw_keys.add(nkey)
        if nkey in plan.kept_keys:
            if kind == "raw":
                plan.kept_raws.append(p)
        else:
            plan.to_remove.append(p)

    plan.jpg_without_raw = sorted(p for k, ps in jpg_by_key.items() if k not in raw_keys for p in ps)
    return plan


@dataclass
class Assessment:
    errors: list[str]    # refuse unless forced
    warnings: list[str]  # informational

    @property
    def safe(self) -> bool:
        return not self.errors


def assess(plan: Plan, *, max_fraction: float = 0.95) -> Assessment:
    errors: list[str] = []
    warnings: list[str] = []
    if not plan.kept_keys and plan.total_raws:
        errors.append(f"No JPGs found in {plan.jpg_dir} — this would remove EVERY RAW. Wrong folder?")
    elif plan.total_raws:
        frac = len(plan.raws_to_remove) / plan.total_raws
        if frac > max_fraction:
            errors.append(
                f"{frac:.0%} of RAWs would be removed (limit {max_fraction:.0%}). "
                "If names don't match (e.g. renamed JPGs), this is a disaster."
            )
    if plan.jpg_without_raw:
        warnings.append(f"{len(plan.jpg_without_raw)} JPG(s) have no matching RAW "
                        "(shot JPG-only, or names don't match?)")
    if plan.duplicate_jpg_keys:
        example = ", ".join(p.name for p in next(iter(plan.duplicate_jpg_keys.values())))
        warnings.append(f"{len(plan.duplicate_jpg_keys)} name(s) have several JPGs, e.g. {example}")
    if plan.ignored_raw_dir:
        warnings.append(f"{len(plan.ignored_raw_dir)} unrecognised file(s) in the RAW folder are left untouched")
    if plan.ignored_jpg_dir:
        warnings.append(f"{len(plan.ignored_jpg_dir)} non-JPG file(s) in the JPG folder don't count as keepers")
    return Assessment(errors, warnings)


def find_subdir(session: Path, names: tuple[str, ...]) -> Path | None:
    """Find SESSION\\<name> case-insensitively (RAW, raw, Raw...); None if 0 or >1 match."""
    if not session.is_dir():
        return None
    wanted = {n.casefold() for n in names}
    hits = [c for c in session.iterdir() if c.is_dir() and c.name.casefold() in wanted]
    return hits[0] if len(hits) == 1 else None


def find_session_dirs(session: Path) -> tuple[Path | None, Path | None]:
    return find_subdir(session, ("RAW",)), find_subdir(session, ("JPG", "JPEG"))


def dirs_problem(raw: Path, jpg: Path) -> str | None:
    raw, jpg = raw.resolve(), jpg.resolve()
    if raw == jpg or raw in jpg.parents or jpg in raw.parents:
        return f"RAW and JPG folders must be separate, non-nested folders ({raw} vs {jpg})"
    return None
