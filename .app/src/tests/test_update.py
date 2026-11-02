import ast
import hashlib
import io
import zipfile
from pathlib import Path

import pytest

from deck_inventory import update
from tools.make_share_zip import make_share_zip

ZIP_URL = "https://github.com/esempio/deck-inventory/releases/download/v1.1.0/deck-inventory.zip"

CHANGELOG = """# novità
== 1.2.0 ==
- Terza cosa.

== 1.1.0 ==
- Seconda cosa.

== 1.0.0 (2026-10-31) ==
- Prima versione.
"""

USER_FILES = {
    "settings.txt": "binder = https://x",
    "decks/x.txt": "Legend:\n1 X",
    "Inventory a.html": "<html>",
    "Start (Mac).command": "#!/bin/bash\necho vecchio\n",
}


def _write_project(base: Path, version: str, min_launcher: int | None = None,
                   changelog: str = CHANGELOG, readme: str | None = None) -> Path:
    init = f'VERSION = "{version}"\n'
    if min_launcher is not None:
        init += f"MIN_LAUNCHER = {min_launcher}\n"
    init += 'UPDATE_REPO = "esempio/deck-inventory"\n'
    files = {
        ".app/src/deck_inventory/__init__.py": init,
        ".app/src/deck_inventory/modulo.py": f"# codice {version}\n",
        ".app/src/CHANGELOG.txt": changelog,
        ".app/src/pyproject.toml": f'[project]\nname = "x"\n# {version}\n',
        "README.txt": f"README {version}\n" if readme is None else readme,
        **USER_FILES,
    }
    for rel, content in files.items():
        p = base / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    return base


def _release_zip(tmp_path: Path, version: str, **kw) -> bytes:
    src = _write_project(tmp_path / f"rel-{version}-{len(kw)}", version, **kw)
    (src / "README.txt").write_text(f"README NUOVO {version}\n", encoding="utf-8")
    out = tmp_path / f"rel-{version}-{len(kw)}.zip"
    make_share_zip(src, out)
    return out.read_bytes()


def _snapshot(root: Path) -> dict[str, str]:
    """Hash di tutti i file del progetto, escluso .app/runtime."""
    out = {}
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root).as_posix()
        if p.is_file() and not rel.startswith(".app/runtime"):
            out[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def _api(tag: str = "v1.1.0", url: str = ZIP_URL):
    data = {"tag_name": tag, "assets": [{"name": "deck-inventory.zip", "browser_download_url": url}]}
    return lambda u: data


class Sync:
    def __init__(self, results=(True,)):
        self.results = list(results)
        self.calls: list[Path] = []

    def __call__(self, src: Path) -> bool:
        self.calls.append(src)
        return self.results.pop(0) if self.results else True


def _now():
    return "2026-11-02 12:00:00"


@pytest.fixture(autouse=True)
def _no_env_and_no_wait(monkeypatch):
    monkeypatch.delenv("DECK_INVENTORY_UPDATE_API", raising=False)
    monkeypatch.setattr(update, "_sleep", lambda s: None)


@pytest.fixture
def proj(tmp_path):
    return _write_project(tmp_path / "Deck Inventory", "1.0.0")


def _run(proj, data: bytes | None = None, *, launcher=1, fetch_json=None, sync=None):
    def fetch_bytes(url):
        assert url == ZIP_URL
        if data is None:
            raise AssertionError("download non previsto")
        return data
    return update.check_and_update(proj, launcher, fetch_json or _api(), fetch_bytes,
                                   sync or Sync(), _now)


def _error_log(proj) -> str:
    log = proj / ".app/runtime/last-error.log"
    return log.read_text(encoding="utf-8") if log.exists() else ""


# --- salti ---------------------------------------------------------------

def test_git_folder_skips(proj):
    (proj / ".git").mkdir()
    before = _snapshot(proj)
    out = _run(proj)
    assert out.status == "skipped"
    assert _snapshot(proj) == before


def test_no_launcher_env_skips(proj):
    before = _snapshot(proj)
    assert _run(proj, launcher=0).status == "skipped"
    assert _snapshot(proj) == before


def _raise(url):
    raise OSError("rete assente")


@pytest.mark.parametrize("fetch_json", [
    _raise,
    lambda u: {},
    lambda u: {"tag_name": "latest", "assets": []},
    lambda u: {"tag_name": "v1.1.0", "assets": []},
    lambda u: {"tag_name": "v1.1.0", "assets": [{"name": "altro.zip", "browser_download_url": ZIP_URL}]},
    lambda u: {"tag_name": "v1.1.0", "assets": [{"name": "deck-inventory.zip",
                                                 "browser_download_url": "http://x/deck-inventory.zip"}]},
])
def test_api_errors_skip(proj, fetch_json):
    before = _snapshot(proj)
    out = _run(proj, fetch_json=fetch_json)
    assert out.status == "skipped"
    assert _snapshot(proj) == before


def test_latest_release_uses_repo_url_and_env_override(monkeypatch):
    seen = []

    def fetch(url):
        seen.append(url)
        return {"tag_name": "v1.2.3", "assets": [{"name": "deck-inventory.zip", "browser_download_url": ZIP_URL}]}

    rel = update.latest_release(fetch)
    assert rel == update.Release("1.2.3", ZIP_URL)
    assert seen[-1] == update.API_URL.format(repo=update.UPDATE_REPO)
    # Con l'override (solo test manuali) anche un URL http locale è accettato.
    monkeypatch.setenv("DECK_INVENTORY_UPDATE_API", "http://127.0.0.1:8000/latest.json")
    local = "http://127.0.0.1:8000/deck-inventory.zip"
    rel = update.latest_release(lambda u: seen.append(u) or
                                {"tag_name": "1.2.3", "assets": [{"name": "deck-inventory.zip",
                                                                  "browser_download_url": local}]})
    assert seen[-1] == "http://127.0.0.1:8000/latest.json"
    assert rel == update.Release("1.2.3", local)


@pytest.mark.parametrize("tag", ["v1.0.0", "v0.9.9"])
def test_same_or_older_is_current(proj, tag):
    before = _snapshot(proj)
    out = _run(proj, fetch_json=_api(tag))
    assert out.status == "current"
    assert out.old == "1.0.0"
    assert _snapshot(proj) == before


# --- aggiornamento riuscito ----------------------------------------------

def test_update_success(proj, tmp_path):
    data = _release_zip(tmp_path, "1.1.0")
    user_before = {k: v for k, v in _snapshot(proj).items() if not k.startswith(".app/") and k != "README.txt"}
    sync = Sync()
    out = _run(proj, data, sync=sync)
    assert out.status == "updated", _error_log(proj)
    assert (out.old, out.new) == ("1.0.0", "1.1.0")
    assert '"1.1.0"' in (proj / ".app/src/deck_inventory/__init__.py").read_text(encoding="utf-8")
    assert (proj / ".app/src/deck_inventory/modulo.py").read_text(encoding="utf-8") == "# codice 1.1.0\n"
    assert (proj / "README.txt").read_text(encoding="utf-8") == "README NUOVO 1.1.0\n"
    after = _snapshot(proj)
    for rel, digest in user_before.items():
        assert after[rel] == digest, rel
    assert "1.1.0" in out.notes and "Seconda cosa." in out.notes
    assert "1.0.0" not in out.notes and "1.2.0" not in out.notes
    assert sync.calls == [proj / ".app/src"]
    upd = proj / ".app/runtime/update"
    assert not (upd / "staging").exists()
    assert not (upd / "previous").exists()
    # Al secondo avvio non c'è più niente da fare.
    assert _run(proj).status == "current"


def test_skipped_versions_notes(proj, tmp_path):
    data = _release_zip(tmp_path, "1.2.0")
    out = _run(proj, data, fetch_json=_api("v1.2.0"))
    assert out.status == "updated", _error_log(proj)
    assert out.notes.index("Versione 1.2.0") < out.notes.index("Versione 1.1.0")
    assert "Prima versione." not in out.notes


def test_bad_changelog_still_updates(proj, tmp_path):
    data = _release_zip(tmp_path, "1.1.0", changelog="== 1.1.0 ==\nriga senza trattino\n")
    out = _run(proj, data)
    assert out.status == "updated"
    assert out.notes == ""
    assert '"1.1.0"' in (proj / ".app/src/deck_inventory/__init__.py").read_text(encoding="utf-8")
    assert "CHANGELOG" in _error_log(proj)


def test_rename_fallback_to_copy(proj, tmp_path, monkeypatch):
    """Simula Windows: la rinomina fallisce sempre → copia + rimozione."""
    calls = []

    def locked(src, dst):
        calls.append(src)
        raise PermissionError("file in uso")

    monkeypatch.setattr(update, "_rename", locked)
    data = _release_zip(tmp_path, "1.1.0")
    out = _run(proj, data)
    assert out.status == "updated", _error_log(proj)
    assert len(calls) == 2 * update.MOVE_ATTEMPTS
    assert '"1.1.0"' in (proj / ".app/src/deck_inventory/__init__.py").read_text(encoding="utf-8")
    assert not (proj / ".app/runtime/update/previous").exists()


def test_move_retries_then_renames(tmp_path, monkeypatch):
    real = update._rename
    failures = [PermissionError("in uso")] * 3
    sleeps = []

    def flaky(src, dst):
        if failures:
            raise failures.pop()
        real(src, dst)

    monkeypatch.setattr(update, "_rename", flaky)
    monkeypatch.setattr(update, "_sleep", sleeps.append)
    monkeypatch.setattr(update.shutil, "copytree", lambda *a, **k: pytest.fail("ripiego non previsto"))
    src = tmp_path / "a"
    (src / "sub").mkdir(parents=True)
    (src / "sub/f.txt").write_text("x")
    update._move(src, tmp_path / "b")
    assert (tmp_path / "b/sub/f.txt").read_text() == "x"
    assert not src.exists()
    assert sleeps == [update.MOVE_DELAY] * 3


# --- fallimenti: resta la versione vecchia --------------------------------

def _zip_with(entries: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in entries.items():
            zf.writestr(name, content)
    return buf.getvalue()


def _good_entries(version="1.1.0"):
    return {
        "Deck Inventory/README.txt": "nuovo",
        "Deck Inventory/.app/src/pyproject.toml": "x",
        "Deck Inventory/.app/src/CHANGELOG.txt": CHANGELOG,
        "Deck Inventory/.app/src/deck_inventory/__init__.py": f'VERSION = "{version}"\n',
    }


@pytest.mark.parametrize("make", [
    lambda good: good[: len(good) // 2],
    lambda good: _zip_with({**_good_entries(), "../evil.txt": "x"}),
    lambda good: _zip_with({**_good_entries(), "Deck Inventory/../../../../evil.txt": "x"}),
    lambda good: _zip_with({**_good_entries(), "/tmp/evil.txt": "x"}),
    lambda good: _zip_with({k: v for k, v in _good_entries().items() if not k.endswith("__init__.py")}),
    lambda good: _zip_with({k: v for k, v in _good_entries().items() if not k.endswith("README.txt")}),
    lambda good: _zip_with({k: v for k, v in _good_entries().items() if not k.endswith("pyproject.toml")}),
], ids=["troncato", "dotdot", "dotdot-annidato", "assoluto", "senza-init", "senza-readme", "senza-pyproject"])
def test_bad_zip_keeps_old(proj, tmp_path, make):
    data = make(_release_zip(tmp_path, "1.1.0"))
    before = _snapshot(proj)
    sync = Sync()
    out = _run(proj, data, sync=sync)
    assert out.status == "failed"
    assert _snapshot(proj) == before
    assert sync.calls == []
    log = _error_log(proj)
    assert "2026-11-02 12:00:00" in log and "1.1.0" in log
    assert not any(p.name == "evil.txt" for p in tmp_path.rglob("*"))
    assert not Path("/tmp/evil.txt").exists() or Path("/tmp/evil.txt").read_text() != "x"


def test_sync_failure_rolls_back(proj, tmp_path):
    data = _release_zip(tmp_path, "1.1.0")
    before = _snapshot(proj)
    sync = Sync([False, True])
    out = _run(proj, data, sync=sync)
    assert out.status == "failed"
    assert _snapshot(proj) == before
    assert (proj / "README.txt").read_text(encoding="utf-8") == "README 1.0.0\n"
    assert sync.calls == [proj / ".app/src"] * 2
    assert "sync" in _error_log(proj)
    assert not (proj / ".app/runtime/update/previous").exists()


def test_exception_after_swap_rolls_back(proj, tmp_path):
    data = _release_zip(tmp_path, "1.1.0")
    before = _snapshot(proj)
    calls = []

    def sync(src):
        calls.append(src)
        if len(calls) == 1:
            raise OSError("disco pieno")
        return True

    out = _run(proj, data, sync=sync)
    assert out.status == "failed"
    assert _snapshot(proj) == before
    assert len(calls) == 2  # risincronizza la versione rimessa a posto
    assert "disco pieno" in _error_log(proj)


def test_needs_launcher_once(proj, tmp_path):
    data = _release_zip(tmp_path, "1.1.0", min_launcher=2)
    before = _snapshot(proj)
    out = _run(proj, data)
    assert out.status == "needs_launcher"
    assert out.new == "1.1.0"
    assert _snapshot(proj) == before
    assert (proj / ".app/runtime/update/notified-1.1.0").exists()
    out = _run(proj)  # nessun download la seconda volta
    assert out.status == "current"
    assert _snapshot(proj) == before


def test_version_mismatch_fails(proj, tmp_path):
    data = _release_zip(tmp_path, "1.2.0")
    before = _snapshot(proj)
    out = _run(proj, data, fetch_json=_api("v1.1.0"))
    assert out.status == "failed"
    assert _snapshot(proj) == before


# --- funzioni di supporto -------------------------------------------------

def test_read_meta(tmp_path):
    _write_project(tmp_path, "2.3.4")
    assert update.read_meta(tmp_path / ".app/src") == ("2.3.4", 1)
    _write_project(tmp_path, "2.3.4", min_launcher=3)
    assert update.read_meta(tmp_path / ".app/src") == ("2.3.4", 3)


def test_log_error_appends(tmp_path):
    update.log_error(tmp_path, "uno")
    update.log_error(tmp_path, "due")
    assert (tmp_path / ".app/runtime/last-error.log").read_text(encoding="utf-8") == "uno\ndue\n"


def test_module_has_no_ui_imports():
    """A livello di modulo solo standard library e changelog: i dialoghi si importano
    solo dentro main, quando c'è un messaggio da mostrare."""
    tree = ast.parse(Path(update.__file__).read_text(encoding="utf-8"))
    imported = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            imported |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported |= {f"{node.module}.{a.name}" for a in node.names} | {node.module}
    for name in imported:
        assert not any(bad in name for bad in ("tkinter", "playwright", "dialogs", "deck_inventory.main"))


# --- file bloccati e scambi interrotti -------------------------------------

def _lock(monkeypatch, locked: Path):
    """Simula un file bloccato su Windows: rmtree cancella il resto e poi fallisce."""
    real = update.shutil.rmtree

    def rmtree(path, ignore_errors=False, **kw):
        path = Path(path)
        if locked.exists() and path in locked.parents:
            for f in path.rglob("*"):
                if f.is_file() and f != locked:
                    f.unlink()
            if not ignore_errors:
                raise PermissionError(f"in uso: {locked}")
            return
        real(path, ignore_errors=ignore_errors, **kw)

    monkeypatch.setattr(update.shutil, "rmtree", rmtree)


def _always_locked_rename(src, dst):
    raise PermissionError("in uso")


def test_locked_file_during_first_move_keeps_old_src(proj, tmp_path, monkeypatch):
    data = _release_zip(tmp_path, "1.1.0")
    before = _snapshot(proj)
    monkeypatch.setattr(update, "_rename", _always_locked_rename)
    _lock(monkeypatch, proj / ".app/src/deck_inventory/modulo.py")
    sync = Sync()
    out = _run(proj, data, sync=sync)
    monkeypatch.undo()
    assert out.status == "failed"
    assert _snapshot(proj) == before
    assert sync.calls == []
    upd = proj / ".app/runtime/update"
    assert not (upd / "previous").exists() and not (upd / "swap-in-progress").exists()


def test_locked_file_during_rollback_overlays_old_src(proj, tmp_path, monkeypatch):
    data = _release_zip(tmp_path, "1.1.0")
    before = _snapshot(proj)
    _lock(monkeypatch, proj / ".app/src/deck_inventory/modulo.py")
    sync = Sync([False, True])
    out = _run(proj, data, sync=sync)
    monkeypatch.undo()
    assert out.status == "failed"
    assert _snapshot(proj) == before
    assert len(sync.calls) == 2
    assert not (proj / ".app/runtime/update/swap-in-progress").exists()


def test_partial_copy_of_old_src_is_never_restored(proj, tmp_path, monkeypatch):
    """La copia di ripiego src→previous si interrompe: src resta quella buona."""
    data = _release_zip(tmp_path, "1.1.0")
    before = _snapshot(proj)

    prev = proj / ".app/runtime/update/previous"

    def broken_copytree(src, dst, **kw):
        # Copia a metà che sembra completa e che non si riesce a cancellare (file bloccato).
        (Path(dst) / "deck_inventory").mkdir(parents=True)
        (Path(dst) / "deck_inventory/__init__.py").write_text('VERSION = "1.0.0"\n')
        (Path(dst) / "pyproject.toml").write_text("parziale")
        raise OSError("disco pieno")

    partial = proj / ".app/runtime/update/previous.partial"
    monkeypatch.setattr(update, "_rename", _always_locked_rename)
    monkeypatch.setattr(update.shutil, "copytree", broken_copytree)
    _lock(monkeypatch, partial / "pyproject.toml")
    out = _run(proj, data)
    monkeypatch.undo()
    assert out.status == "failed"
    assert _snapshot(proj) == before
    assert not prev.exists()  # la copia a metà non prende mai il nome `previous`
    assert partial.exists()  # non cancellabile (file bloccato)
    # Al prossimo avvio la copia parziale rimasta viene solo eliminata.
    assert update.check_and_update(proj, 1, _api("v1.0.0"), None, Sync(), _now).status == "current"
    assert _snapshot(proj) == before
    assert not partial.exists()


def test_killed_during_copy_fallback_keeps_good_src(proj):
    """Chiuso durante la copia src→previous.partial: al riavvio src resta, la copia sparisce."""
    import shutil
    before = _snapshot(proj)
    upd = proj / ".app/runtime/update"
    partial = upd / "previous.partial"
    shutil.copytree(proj / ".app/src", partial)  # sembra completa, ma è .partial
    (partial / "deck_inventory/modulo.py").unlink()
    (upd / "swap-in-progress").touch()
    sync = Sync()
    out = update.check_and_update(proj, 1, _api("v1.0.0"), None, sync, _now)
    assert out.status == "current"
    assert _snapshot(proj) == before
    assert not partial.exists() and not (upd / "previous").exists()
    assert not (upd / "swap-in-progress").exists()
    assert sync.calls == []


def test_killed_after_successful_swap_keeps_new_version(proj, tmp_path, monkeypatch):
    """Chiuso dopo un uv sync riuscito ma prima della pulizia: niente ripristino."""
    data = _release_zip(tmp_path, "1.1.0")

    def killed(*a):
        raise KeyboardInterrupt

    monkeypatch.setattr(update, "_notes", killed)
    with pytest.raises(KeyboardInterrupt):
        _run(proj, data)
    monkeypatch.undo()
    upd = proj / ".app/runtime/update"
    assert (upd / "previous").exists() and not (upd / "swap-in-progress").exists()
    sync = Sync()
    out = update.check_and_update(proj, 1, _api("v1.1.0"), None, sync, _now)
    assert out.status == "current" and out.old == "1.1.0"
    assert '"1.1.0"' in (proj / ".app/src/deck_inventory/__init__.py").read_text(encoding="utf-8")
    assert not (upd / "previous").exists()
    assert sync.calls == []


def _interrupted(proj, *, src_state: str):
    """Riproduce i resti di uno scambio interrotto a metà."""
    upd = proj / ".app/runtime/update"
    upd.mkdir(parents=True, exist_ok=True)
    (upd / "swap-in-progress").touch()
    (proj / ".app/src").rename(upd / "previous")
    if src_state == "half-new":
        (upd / "previous/README.txt.bak").write_bytes((proj / "README.txt").read_bytes())
        (proj / ".app/src/deck_inventory").mkdir(parents=True)
        (proj / ".app/src/deck_inventory/__init__.py").write_text('VERSION = "1.1.0"\n')
        (proj / "README.txt").write_text("README NUOVO 1.1.0\n")


@pytest.mark.parametrize("src_state", ["missing", "half-new"])
def test_interrupted_swap_is_recovered(proj, src_state):
    before = _snapshot(proj)
    _interrupted(proj, src_state=src_state)
    sync = Sync()
    out = update.check_and_update(proj, 1, _api("v1.0.0"), None, sync, _now)
    assert out.status == "current"
    assert out.old == "1.0.0"
    assert _snapshot(proj) == before
    upd = proj / ".app/runtime/update"
    assert not (upd / "previous").exists() and not (upd / "swap-in-progress").exists()
    assert "scambio interrotto" in _error_log(proj)


def test_interrupted_swap_recovery_runs_sync(proj):
    _interrupted(proj, src_state="half-new")
    sync = Sync()
    update.check_and_update(proj, 1, _api("v1.0.0"), None, sync, _now)
    assert sync.calls == [proj / ".app/src"]


def test_leftover_previous_without_marker_is_cleaned(proj):
    import shutil
    before = _snapshot(proj)
    prev = proj / ".app/runtime/update/previous"
    shutil.copytree(proj / ".app/src", prev)
    (prev / "deck_inventory/modulo.py").write_text("# vecchia roba\n")
    sync = Sync()
    out = update.check_and_update(proj, 1, _api("v1.0.0"), None, sync, _now)
    assert out.status == "current"
    assert _snapshot(proj) == before
    assert not prev.exists()
    assert sync.calls == []


def test_failed_restore_keeps_previous_for_next_run(proj, tmp_path, monkeypatch):
    data = _release_zip(tmp_path, "1.1.0")
    before = _snapshot(proj)

    def broken_restore(src, previous, readme):
        raise OSError("ripristino impossibile")

    monkeypatch.setattr(update, "_restore", broken_restore)
    out = _run(proj, data, sync=Sync([False]))
    assert out.status == "failed"
    upd = proj / ".app/runtime/update"
    assert (upd / "previous/deck_inventory/__init__.py").exists()
    assert (upd / "swap-in-progress").exists()
    monkeypatch.undo()
    out = update.check_and_update(proj, 1, _api("v1.0.0"), None, Sync(), _now)
    assert out.status == "current"
    assert _snapshot(proj) == before


# --- punto di ingresso (main) ------------------------------------------------

class FakeUI:
    def __init__(self):
        self.infos: list[str] = []

    def info(self, message: str) -> None:
        self.infos.append(message)


@pytest.fixture
def main_env(monkeypatch):
    monkeypatch.delenv("DECK_INVENTORY_NO_DIALOG", raising=False)
    monkeypatch.setenv("DECK_INVENTORY_LAUNCHER", "1")
    monkeypatch.delenv("DECK_INVENTORY_UV", raising=False)


def _fake_check(monkeypatch, outcome, calls=None):
    def fake(root, launcher, fetch_json, fetch_bytes, run_sync, now):
        if calls is not None:
            calls.append({"root": root, "launcher": launcher, "run_sync": run_sync, "now": now})
        return outcome
    monkeypatch.setattr(update, "check_and_update", fake)


def test_main_messages(main_env, monkeypatch, proj):
    ui = FakeUI()
    _fake_check(monkeypatch, update.Outcome("updated", "1.0.0", "1.1.0", "Versione 1.1.0\n• Seconda cosa."))
    assert update.main(["x", str(proj)], ui) == 0
    assert len(ui.infos) == 1
    assert "dalla versione 1.0.0 alla versione 1.1.0" in ui.infos[0]
    assert "Novità" in ui.infos[0] and "Seconda cosa." in ui.infos[0]

    ui = FakeUI()
    _fake_check(monkeypatch, update.Outcome("needs_launcher", "1.0.0", "2.0.0"))
    assert update.main(["x", str(proj)], ui) == 0
    assert len(ui.infos) == 1
    assert f"https://github.com/{update.UPDATE_REPO}/releases/latest" in ui.infos[0]
    assert "versione 2.0.0" in ui.infos[0] and "versione 1.0.0" in ui.infos[0]

    for status in ("current", "skipped", "failed"):
        ui = FakeUI()
        _fake_check(monkeypatch, update.Outcome(status, "1.0.0", "1.1.0"))
        assert update.main(["x", str(proj)], ui) == 0
        assert ui.infos == []


def test_main_passes_launcher_and_root(main_env, monkeypatch, proj):
    calls = []
    _fake_check(monkeypatch, update.Outcome("current", "1.0.0"), calls)
    monkeypatch.setenv("DECK_INVENTORY_LAUNCHER", "3")
    assert update.main(["x", str(proj)], FakeUI()) == 0
    assert calls[0]["launcher"] == 3 and Path(calls[0]["root"]) == proj
    assert isinstance(calls[0]["now"](), str)

    calls.clear()
    for value in (None, "", "abc"):
        if value is None:
            monkeypatch.delenv("DECK_INVENTORY_LAUNCHER")
        else:
            monkeypatch.setenv("DECK_INVENTORY_LAUNCHER", value)
        assert update.main(["x", str(proj)], FakeUI()) == 0
    assert [c["launcher"] for c in calls] == [0, 0, 0]


def test_main_no_dialog_env(main_env, monkeypatch, proj):
    monkeypatch.setenv("DECK_INVENTORY_NO_DIALOG", "1")
    for outcome in (update.Outcome("updated", "1.0.0", "1.1.0", "note"),
                    update.Outcome("needs_launcher", "1.0.0", "2.0.0")):
        ui = FakeUI()
        _fake_check(monkeypatch, outcome)
        assert update.main(["x", str(proj)], ui) == 0
        assert ui.infos == []


def test_main_never_fails(main_env, monkeypatch, proj):
    def boom(*a, **k):
        raise RuntimeError("imprevisto")
    monkeypatch.setattr(update, "check_and_update", boom)
    assert update.main(["x", str(proj)], FakeUI()) == 0
    assert "imprevisto" in _error_log(proj)

    class BrokenUI:
        def info(self, message):
            raise RuntimeError("niente finestre")
    _fake_check(monkeypatch, update.Outcome("updated", "1.0.0", "1.1.0", "note"))
    assert update.main(["x", str(proj)], BrokenUI()) == 0
    assert "niente finestre" in _error_log(proj)

    assert update.main(["x"], FakeUI()) == 0  # cartella mancante


def test_main_missing_uv_means_sync_false(main_env, monkeypatch, proj):
    calls = []
    _fake_check(monkeypatch, update.Outcome("current", "1.0.0"), calls)
    assert update.main(["x", str(proj)], FakeUI()) == 0
    assert calls[0]["run_sync"](proj / ".app/src") is False

    calls.clear()
    monkeypatch.setenv("DECK_INVENTORY_UV", str(proj / "uv-inesistente"))
    assert update.main(["x", str(proj)], FakeUI()) == 0
    assert calls[0]["run_sync"](proj / ".app/src") is False


def test_main_run_sync_command(main_env, monkeypatch, proj):
    calls, runs = [], []

    class Done:
        def __init__(self, code):
            self.returncode = code

    def fake_run(cmd, **kw):
        runs.append(cmd)
        return Done(0 if len(runs) == 1 else 1)
    monkeypatch.setattr(update.subprocess, "run", fake_run)
    uv = proj / ".app/runtime/uv/uv"
    uv.parent.mkdir(parents=True)
    uv.write_text("", encoding="utf-8")
    monkeypatch.setenv("DECK_INVENTORY_UV", str(uv))
    _fake_check(monkeypatch, update.Outcome("current", "1.0.0"), calls)
    update.main(["x", str(proj)], FakeUI())
    src = proj / ".app/src"
    assert calls[0]["run_sync"](src) is True
    assert calls[0]["run_sync"](src) is False
    assert runs[0] == [str(uv), "sync", "--project", str(src), "--frozen", "--no-dev"]
