from pathlib import Path

import pytest

from rawcull.cli import EXIT_ABORTED, EXIT_ERROR, EXIT_OK, EXIT_UNSAFE, main
from rawcull.core import build_plan, split_name


def make_session(tmp_path: Path, raws, jpgs, raw_dir="RAW", jpg_dir="JPG") -> Path:
    (tmp_path / raw_dir).mkdir()
    (tmp_path / jpg_dir).mkdir()
    for n in raws:
        (tmp_path / raw_dir / n).write_bytes(b"r" * 100)
    for n in jpgs:
        (tmp_path / jpg_dir / n).write_bytes(b"j")
    return tmp_path


def names(d: Path) -> set[str]:
    return {p.name for p in d.iterdir()}


# ----------------------------------------------------------------- core
def test_split_name():
    assert split_name("DSC01234.ARW") == ("DSC01234", "arw")
    assert split_name("DSC01234.ARW.xmp") == ("DSC01234", "arw.xmp")
    assert split_name("noext") == ("noext", "")


def test_basic_plan(tmp_path):
    s = make_session(tmp_path, ["A.ARW", "B.ARW", "C.ARW"], ["A.JPG", "C.JPG"])
    plan = build_plan(s / "RAW", s / "JPG")
    assert [p.name for p in plan.to_remove] == ["B.ARW"]
    assert {p.name for p in plan.kept_raws} == {"A.ARW", "C.ARW"}


def test_sidecars_follow_their_raw(tmp_path):
    s = make_session(tmp_path, ["A.ARW", "A.ARW.xmp", "B.ARW", "B.xmp", "B.ARW.pp3"], ["A.JPG"])
    plan = build_plan(s / "RAW", s / "JPG")
    assert {p.name for p in plan.to_remove} == {"B.ARW", "B.xmp", "B.ARW.pp3"}
    assert [p.name for p in plan.raws_to_remove] == ["B.ARW"]


def test_unknown_and_hidden_files_untouched(tmp_path):
    s = make_session(tmp_path, ["A.ARW", "notes.txt", ".DS_Store", "B.ARW.txt"], ["A.JPG"])
    plan = build_plan(s / "RAW", s / "JPG")
    assert plan.to_remove == []
    assert {p.name for p in plan.ignored_raw_dir} == {"notes.txt", "B.ARW.txt"}


def test_case_insensitive_by_default(tmp_path):
    s = make_session(tmp_path, ["dsc1.ARW", "DSC2.arw"], ["DSC1.jpg", "dsc2.JPEG"])
    assert build_plan(s / "RAW", s / "JPG").to_remove == []
    assert len(build_plan(s / "RAW", s / "JPG", case_sensitive=True).to_remove) == 2


def test_first_dot_key(tmp_path):
    # edited exports like "A.edit.jpg" still protect A.ARW (key = before first dot)
    s = make_session(tmp_path, ["A.ARW"], ["A.edit.jpg"])
    # suffix "edit.jpg" isn't a jpg ext -> not a keeper
    assert len(build_plan(s / "RAW", s / "JPG").to_remove) == 1


def test_jpg_without_raw_reported(tmp_path):
    s = make_session(tmp_path, ["A.ARW", "B.ARW"], ["A.JPG", "Z.JPG"])
    plan = build_plan(s / "RAW", s / "JPG")
    assert [p.name for p in plan.jpg_without_raw] == ["Z.JPG"]


# ----------------------------------------------------------------- cli
def test_dry_run_changes_nothing(tmp_path):
    s = make_session(tmp_path, ["A.ARW", "B.ARW"], ["A.JPG"])
    assert main([str(s), "-n"]) == EXIT_OK
    assert names(s / "RAW") == {"A.ARW", "B.ARW"}


def test_delete_with_yes(tmp_path):
    s = make_session(tmp_path, ["A.ARW", "B.ARW", "B.ARW.xmp"], ["A.JPG"])
    assert main([str(s), "-y", "--delete"]) == EXIT_OK
    assert names(s / "RAW") == {"A.ARW"}
    logs = list(s.glob("rawcull-*.log"))
    assert len(logs) == 1 and "B.ARW" in logs[0].read_text()


def test_move_to(tmp_path):
    s = make_session(tmp_path, ["A.ARW", "B.ARW"], ["A.JPG"])
    assert main([str(s), "-y", "--move-to", "rejected", "--no-log"]) == EXIT_OK
    assert names(s / "RAW") == {"A.ARW"}
    assert names(s / "rejected") == {"B.ARW"}


def test_refuses_when_no_jpgs(tmp_path):
    s = make_session(tmp_path, ["A.ARW", "B.ARW"], [])
    assert main([str(s), "-y"]) == EXIT_UNSAFE
    assert names(s / "RAW") == {"A.ARW", "B.ARW"}


def test_refuses_on_name_mismatch(tmp_path):
    # renamed JPGs -> nothing matches -> 100% would be removed
    s = make_session(tmp_path, [f"DSC{i}.ARW" for i in range(10)], ["session_01.jpg"])
    assert main([str(s), "-y"]) == EXIT_UNSAFE
    assert len(names(s / "RAW")) == 10


def test_force_overrides(tmp_path):
    s = make_session(tmp_path, ["A.ARW", "B.ARW"], ["Z.JPG"])
    assert main([str(s), "-y", "--delete", "--force", "--no-log"]) == EXIT_OK
    assert names(s / "RAW") == set()


def test_non_tty_without_yes_refuses(tmp_path, monkeypatch):
    s = make_session(tmp_path, ["A.ARW", "B.ARW"], ["A.JPG"])
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    assert main([str(s)]) == EXIT_ABORTED
    assert names(s / "RAW") == {"A.ARW", "B.ARW"}


def test_lowercase_folder_names_and_jpeg(tmp_path):
    s = make_session(tmp_path, ["A.ARW", "B.ARW"], ["A.JPG"], raw_dir="raw", jpg_dir="jpeg")
    assert main([str(s), "-y", "--delete", "--no-log"]) == EXIT_OK
    assert names(s / "raw") == {"A.ARW"}


def test_missing_folder(tmp_path):
    (tmp_path / "RAW").mkdir()
    assert main([str(tmp_path), "-n"]) == EXIT_ERROR


def test_same_folder_rejected(tmp_path):
    (tmp_path / "X").mkdir()
    assert main(["--raw", str(tmp_path / "X"), "--jpg", str(tmp_path / "X"), "-n"]) == EXIT_ERROR


def test_stale_plan_aborts(tmp_path, monkeypatch):
    """If JPGs change between preview and confirmation, nothing is deleted."""
    s = make_session(tmp_path, ["A.ARW", "B.ARW", "C.ARW"], ["A.JPG", "C.JPG"])
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)

    def fake_input(prompt):
        (s / "JPG" / "C.JPG").unlink()  # user deletes one more JPG meanwhile
        return "y"

    monkeypatch.setattr("builtins.input", fake_input)
    assert main([str(s), "--delete", "--no-log"]) == EXIT_ABORTED
    assert names(s / "RAW") == {"A.ARW", "B.ARW", "C.ARW"}


@pytest.mark.parametrize("answer,expected", [("n", EXIT_ABORTED), ("", EXIT_ABORTED), ("y", EXIT_OK)])
def test_interactive_confirm(tmp_path, monkeypatch, answer, expected):
    s = make_session(tmp_path, ["A.ARW", "B.ARW"], ["A.JPG"])
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _: answer)
    assert main([str(s), "--delete", "--no-log"]) == expected


# ----------------------------------------------------------------- Windows specifics
import os
import stat
import sys

from rawcull import winutil

win_only = pytest.mark.skipif(sys.platform != "win32", reason="Windows-only")


def test_unlink_force_handles_readonly(tmp_path, monkeypatch):
    f = tmp_path / "A.ARW"
    f.write_bytes(b"x")
    os.chmod(f, stat.S_IREAD)
    real_unlink = Path.unlink
    calls = []

    def fake_unlink(self, *a, **k):  # emulate Windows: read-only => PermissionError
        calls.append(self)
        if not self.stat().st_mode & stat.S_IWRITE:
            raise PermissionError(13, "Access is denied")
        return real_unlink(self, *a, **k)

    monkeypatch.setattr(Path, "unlink", fake_unlink)
    winutil.unlink_force(f)
    assert not f.exists() and len(calls) == 2


def test_menu_command_opens_gui(monkeypatch):
    monkeypatch.setattr(sys, "executable", r"C:\Py\python.exe")
    assert winutil.menu_command() == '"C:\\Py\\pythonw.exe" -m rawcull.gui "%V"'
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", r"C:\Apps\rawcull.exe")
    assert winutil.menu_command() == '"C:\\Apps\\rawcull.exe" "%V"'


@win_only
def test_recycle_bin(tmp_path):
    s = make_session(tmp_path, ["A.ARW", "B.ARW", "B.ARW.xmp"], ["A.JPG"])
    os.chmod(s / "RAW" / "B.ARW", stat.S_IREAD)  # SD-card style read-only file
    assert main([str(s), "-y", "--no-log"]) == EXIT_OK  # default action on Windows = Recycle Bin
    assert names(s / "RAW") == {"A.ARW"}


@win_only
def test_delete_readonly_on_windows(tmp_path):
    s = make_session(tmp_path, ["A.ARW", "B.ARW"], ["A.JPG"])
    os.chmod(s / "RAW" / "B.ARW", stat.S_IREAD)
    assert main([str(s), "-y", "--delete", "--no-log"]) == EXIT_OK
    assert names(s / "RAW") == {"A.ARW"}


@win_only
def test_context_menu_roundtrip():
    import winreg

    winutil.install_context_menu()
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, winutil.MENU_KEYS[0] + r"\command") as k:
            assert "rawcull" in winreg.QueryValueEx(k, "")[0]
        assert winutil.is_context_menu_installed()
    finally:
        winutil.uninstall_context_menu()
    with pytest.raises(FileNotFoundError):
        winreg.OpenKey(winreg.HKEY_CURRENT_USER, winutil.MENU_KEYS[0])


# ----------------------------------------------------------------- desktop bridge (no window needed)
import json as _json

from rawcull.bridge import SessionApi, normalize_session


@pytest.fixture
def api_env(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    pushed = []
    (tmp_path / "sess").mkdir()
    s = make_session(tmp_path / "sess", ["A.ARW", "B.ARW", "B.ARW.xmp", "C.ARW", "D.ARW", "notes.txt"],
                     ["A.JPG", "C.JPG", "D.JPG", "Z.JPG"])
    api = SessionApi(push=pushed.append)
    return api, s, pushed


def test_normalize_session_variants(tmp_path):
    s = make_session(tmp_path, ["A.ARW"], ["A.JPG"])
    assert normalize_session(s / "RAW") == s
    assert normalize_session(s / "JPG") == s
    assert normalize_session(s / "JPG" / "A.JPG") == s     # a dropped file inside the session
    assert normalize_session(s) == s


def test_assess_messages(tmp_path):
    from rawcull.core import assess

    s = make_session(tmp_path, ["A.ARW", "B.ARW"], [])
    a = assess(build_plan(s / "RAW", s / "JPG"))
    assert not a.safe and "EVERY RAW" in a.errors[0]


def test_bridge_snapshot_is_json_and_complete(api_env):
    api, s, _ = api_env
    snap = api.open_session(str(s / "JPG"))
    _json.dumps(snap)                                          # must cross the JS bridge
    assert snap["session"]["path"] == str(s.resolve()) and snap["problem"] is None
    assert snap["stats"] == {"keepers": 4, "raws": 4, "kept": 3, "remove": 1, "sidecars": 1, "bytes": 200}
    assert [f["name"] for f in snap["files"]["remove"]] == ["B.ARW", "B.ARW.xmp"]
    assert [f["kind"] for f in snap["files"]["remove"]] == ["raw", "sidecar"]
    assert [f["name"] for f in snap["files"]["orphan"]] == ["Z.JPG"]
    assert [f["name"] for f in snap["files"]["ignored"]] == ["notes.txt"]
    init = api.init()
    assert init["snapshot"]["signature"] == snap["signature"] and init["action"] in ("trash", "delete")


def test_bridge_remove_and_stale_signature(api_env):
    api, s, pushed = api_env
    snap = api.open_session(str(s))
    (s / "JPG" / "D.JPG").unlink()                             # user kept culling; page not refreshed yet
    r = api.remove("move", False, snap["signature"])
    assert r["ok"] is False and r["reason"] == "stale"
    assert names(s / "RAW") >= {"B.ARW", "D.ARW"}              # nothing touched
    r = api.remove("move", False, r["snapshot"]["signature"])
    assert r["ok"] and r["done"] == 3 and r["log"].startswith("rawcull-")
    assert names(s / "_rejected") == {"B.ARW", "B.ARW.xmp", "D.ARW"}
    assert r["snapshot"]["stats"]["remove"] == 0
    assert any("onProgress" in js for js in pushed)


def test_bridge_blocked_unless_forced(api_env):
    api, s, _ = api_env
    for f in (s / "JPG").iterdir():
        f.unlink()
    snap = api.rescan() if api._session else api.open_session(str(s))
    assert snap["errors"]
    r = api.remove("delete", False, snap["signature"])
    assert r["reason"] == "blocked" and (s / "RAW" / "A.ARW").exists()
    r = api.remove("delete", True, snap["signature"])
    assert r["ok"] and r["done"] == 5


def test_bridge_missing_folders_and_options(api_env, tmp_path):
    api, s, _ = api_env
    (tmp_path / "empty").mkdir()
    assert "Couldn't find" in api.open_session(str(tmp_path / "empty"))["problem"]
    assert "not found" in api.open_session(str(tmp_path / "nope"))["problem"]
    api.open_session(str(s))
    snap = api.set_options(case_sensitive=False, sidecars=False)
    assert [f["name"] for f in snap["files"]["remove"]] == ["B.ARW"]
    assert api.init()["options"] == {"caseSensitive": False, "sidecars": False}   # persisted


def test_bridge_watcher_pushes_on_change(api_env):
    api, s, pushed = api_env
    api.open_session(str(s))
    assert api._poll_changes() is False                       # nothing changed
    import os, time
    (s / "JPG" / "A.JPG").unlink()
    st = os.stat(s / "JPG"); os.utime(s / "JPG", ns=(st.st_atime_ns, st.st_mtime_ns + 10**9))
    assert api._poll_changes() is True
    js = pushed[-1]
    assert js.startswith("window.rawcull && window.rawcull.onSnapshot")
    assert '"remove": 2' in js
    assert js.isascii()                                         # safe for every webview backend


def test_bridge_drop(api_env):
    api, s, pushed = api_env
    api._handle_drop({"dataTransfer": {"files": [{"name": "C.JPG", "pywebviewFullPath": str(s / "JPG" / "C.JPG")}]}})
    assert api._session == s.resolve() and "onSnapshot" in pushed[-1]
    api._handle_drop({"dataTransfer": {"files": [{"name": "x"}]}})
    assert "onDropFailed" in pushed[-1]


def test_bridge_exposes_only_intended_methods():
    public = {n for n in dir(SessionApi) if not n.startswith("_")}
    assert public == {"init", "pick_session", "open_session", "pick_dir", "rescan", "set_options",
                      "set_action", "remove", "reveal", "open_session_folder", "set_context_menu"}
