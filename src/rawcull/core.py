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
