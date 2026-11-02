import subprocess
import zipfile

import pytest

from conftest import DUMMY_BINDER
from tools import publish
from tools.make_share_zip import make_share_zip

INIT = 'VERSION = "1.0.0"\nMIN_LAUNCHER = 1\nUPDATE_REPO = "Tommo2797/deck-inventory"\n'
CHANGELOG = (
    "# commento\n\n"
    "== 1.1.0 ==\n- Novità uno.\n- Novità due.\n\n"
    "== 1.0.0 (2026-10-31) ==\n- Prima versione.\n"
)
README = "DECK INVENTORY\n\nNOVITÀ\n------\nvecchio\n"


def test_check_version():
    publish.check_version("1.1.0", "v1.0.0")
    publish.check_version("1.1.0", None)
    with pytest.raises(ValueError):
        publish.check_version("1.0.0", "v1.0.0")
    with pytest.raises(ValueError):
        publish.check_version("0.9.9", "v1.0.0")
    with pytest.raises(ValueError):
        publish.check_version("1.1", "v1.0.0")
    with pytest.raises(ValueError):
        publish.check_version("v1.1.0", "v1.0.0")


def test_bump_version():
    out = publish.bump_version(INIT, "1.1.0")
    assert out == INIT.replace('"1.0.0"', '"1.1.0"')
    with pytest.raises(ValueError):
        publish.bump_version("MIN_LAUNCHER = 1\n", "1.1.0")


def test_release_notes():
    assert publish.release_notes(CHANGELOG, "1.1.0") == "Versione 1.1.0\n• Novità uno.\n• Novità due."


def test_release_notes_missing():
    with pytest.raises(ValueError):
        publish.release_notes(CHANGELOG, "1.2.0")
    with pytest.raises(ValueError):
        publish.release_notes("== 1.2.0 ==\n", "1.2.0")


def _project(tmp_path):
    root = tmp_path / "proj"
    files = {
        ".app/src/deck_inventory/__init__.py": INIT,
        ".app/src/CHANGELOG.txt": CHANGELOG,
        ".app/src/tests/private/x.csv": "x",
        "README.txt": README,
        "settings.txt": f"binder = {DUMMY_BINDER}\n",
        "Start (Mac).command": "#!/bin/bash\n",
    }
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return root


class FakeSh:
    """Esegue finto: registra i comandi e risponde come git/gh in uno stato sano."""

    def __init__(self, porcelain="", login="Tommo2797", latest="v1.0.0", fail_on=None):
        self.calls: list[list[str]] = []
        self.envs: list[str | None] = []
        self.porcelain, self.login, self.latest, self.fail_on = porcelain, login, latest, fail_on

    def __call__(self, cmd):
        import os

        self.calls.append(cmd)
        self.envs.append(os.environ.get("DECK_INVENTORY_TEST_BINDER"))
        joined = " ".join(cmd)
        if self.fail_on and joined.startswith(self.fail_on):
            raise subprocess.CalledProcessError(1, cmd, "", "errore finto")
        if cmd[:3] == ["git", "rev-parse", "--abbrev-ref"]:
            return "main\n"
        if cmd[:2] == ["git", "status"]:
            return self.porcelain
        if cmd[:2] == ["git", "rev-parse"]:
            return "abc123\n"
        if cmd[:3] == ["gh", "api", "user"]:
            return self.login + "\n"
        if cmd[:3] == ["gh", "release", "view"]:
            if self.latest is None:
                raise subprocess.CalledProcessError(1, cmd, "", "release not found")
            return self.latest + "\n"
        return ""

    def has(self, *prefix):
        return any(c[: len(prefix)] == list(prefix) for c in self.calls)

    def index(self, *prefix):
        return next(i for i, c in enumerate(self.calls) if c[: len(prefix)] == list(prefix))


def test_run_refuses_dirty_tree(tmp_path, capsys):
    root = _project(tmp_path)
    sh = FakeSh(porcelain=" M README.txt\n")
    assert publish.run(["1.1.0"], sh, root=root) == 1
    assert not sh.has("git", "commit")
    assert "modifiche non salvate" in capsys.readouterr().out


def test_run_refuses_wrong_branch(tmp_path, capsys):
    root = _project(tmp_path)
    sh = FakeSh()
    sh_call = sh.__call__

    def on_branch(cmd):
        if cmd[:3] == ["git", "rev-parse", "--abbrev-ref"]:
            return "feature/x\n"
        return sh_call(cmd)

    assert publish.run(["1.1.0", "--dry-run"], on_branch, root=root) == 1
    assert "main" in capsys.readouterr().out


def test_run_refuses_wrong_gh_account(tmp_path, capsys):
    root = _project(tmp_path)
    sh = FakeSh(login="altro")
    assert publish.run(["1.1.0"], sh, root=root) == 1
    assert "gh" in capsys.readouterr().out
    assert not sh.has("gh", "release", "view")


def test_run_refuses_old_version(tmp_path):
    root = _project(tmp_path)
    sh = FakeSh(latest="v1.1.0")
    assert publish.run(["1.1.0"], sh, root=root) == 1
    assert not any("pytest" in c for call in sh.calls for c in call)


def test_run_refuses_missing_changelog_entry(tmp_path, capsys):
    root = _project(tmp_path)
    sh = FakeSh()
    assert publish.run(["1.2.0"], sh, root=root) == 1
    assert "CHANGELOG" in capsys.readouterr().out


def test_run_refuses_without_private_data(tmp_path, capsys):
    root = _project(tmp_path)
    (root / ".app/src/tests/private/x.csv").unlink()
    (root / ".app/src/tests/private").rmdir()
    sh = FakeSh()
    assert publish.run(["1.1.0", "--dry-run"], sh, root=root) == 1
    assert "tests/private" in capsys.readouterr().out


def test_run_refuses_failing_tests(tmp_path, capsys):
    root = _project(tmp_path)
    sh = FakeSh(fail_on=publish.sys.executable)
    assert publish.run(["1.1.0"], sh, root=root) == 1
    assert "test" in capsys.readouterr().out
    assert not sh.has("git", "commit")


def test_run_dry_run_changes_nothing(tmp_path, capsys):
    root = _project(tmp_path)
    before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
    sh = FakeSh()
    assert publish.run(["1.1.0", "--dry-run"], sh, root=root) == 0
    assert not sh.has("git", "commit")
    assert not sh.has("git", "tag")
    assert not sh.has("git", "push")
    assert not sh.has("gh", "release", "create")
    assert {p: p.read_bytes() for p in root.rglob("*") if p.is_file()} == before
    out = capsys.readouterr().out
    assert "v1.1.0" in out
    assert DUMMY_BINDER not in out


def test_run_online_tests_get_binder_from_settings(tmp_path, capsys):
    root = _project(tmp_path)
    sh = FakeSh()
    assert publish.run(["1.1.0", "--dry-run"], sh, root=root) == 0
    pytest_calls = [i for i, c in enumerate(sh.calls) if c[:3] == [publish.sys.executable, "-m", "pytest"]]
    assert len(pytest_calls) == 2
    online = pytest_calls[1]
    assert sh.calls[online][-2:] == ["-m", "online"]
    assert sh.envs[online] == DUMMY_BINDER
    # mai nella riga di comando, mai stampato, e non resta nell'ambiente
    assert not any(DUMMY_BINDER in part for c in sh.calls for part in c)
    assert DUMMY_BINDER not in capsys.readouterr().out
    assert publish.os.environ.get("DECK_INVENTORY_TEST_BINDER") != DUMMY_BINDER


def test_run_skip_online_warns(tmp_path, capsys):
    root = _project(tmp_path)
    sh = FakeSh()
    assert publish.run(["1.1.0", "--dry-run", "--skip-online"], sh, root=root) == 0
    assert not any(c[-2:] == ["-m", "online"] for c in sh.calls)
    assert "SALTATO" in capsys.readouterr().out


def test_run_online_requires_binder_link(tmp_path, capsys):
    root = _project(tmp_path)
    (root / "settings.txt").unlink()
    sh = FakeSh()
    assert publish.run(["1.1.0", "--dry-run"], sh, root=root) == 1
    assert "settings.txt" in capsys.readouterr().out


def test_run_full_sequence(tmp_path, monkeypatch):
    root = _project(tmp_path)
    monkeypatch.setattr(publish, "_today", lambda: "2026-11-02")
    sh = FakeSh()
    assert publish.run(["1.1.0"], sh, root=root) == 0

    assert 'VERSION = "1.1.0"' in (root / ".app/src/deck_inventory/__init__.py").read_text(encoding="utf-8")
    assert "== 1.1.0 (2026-11-02) ==" in (root / ".app/src/CHANGELOG.txt").read_text(encoding="utf-8")
    readme = (root / "README.txt").read_text(encoding="utf-8")
    assert "Versione 1.1.0 (2026-11-02)\n• Novità uno." in readme and "vecchio" not in readme

    i_commit = sh.index("git", "commit")
    i_tag = sh.index("git", "tag")
    i_push = sh.index("git", "push")
    i_release = sh.index("gh", "release", "create")
    assert i_commit < i_tag < i_push < i_release
    assert sh.calls[i_commit][-2:] == ["-m", "release: v1.1.0"]
    assert sh.calls[i_tag] == ["git", "tag", "v1.1.0"]
    assert sh.calls[i_push] == ["git", "push", "origin", "main", "v1.1.0"]
    release = sh.calls[i_release]
    assert release[3] == "v1.1.0"
    assert release[4].endswith("/deck-inventory.zip")
    assert release[release.index("--repo") + 1] == "Tommo2797/deck-inventory"
    assert release[release.index("--title") + 1] == "Deck Inventory 1.1.0"
    assert release[release.index("--notes") + 1] == "Versione 1.1.0 (2026-11-02)\n• Novità uno.\n• Novità due."


def test_run_no_previous_release(tmp_path):
    root = _project(tmp_path)
    sh = FakeSh(latest=None)
    assert publish.run(["1.1.0", "--dry-run"], sh, root=root) == 0


def test_run_failure_after_commit_reports_progress(tmp_path, capsys):
    root = _project(tmp_path)
    sh = FakeSh(fail_on="git push")
    assert publish.run(["1.1.0"], sh, root=root) == 1
    out = capsys.readouterr().out
    assert "Già fatto" in out and "commit" in out and "tag v1.1.0" in out
    assert "Non fatto" in out and "release" in out
    assert not sh.has("gh", "release", "create")


def test_share_zip_excludes_publish_tools(tmp_path):
    proj = tmp_path / "proj"
    for rel in [
        "README.txt",
        ".app/src/tools/make_share_zip.py",
        ".app/src/tools/publish.py",
        ".app/src/tools/publish.sh",
    ]:
        p = proj / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x")
    out = tmp_path / "out.zip"
    make_share_zip(proj, out)
    names = set(zipfile.ZipFile(out).namelist())
    assert names == {
        "Deck Inventory/README.txt",
        "Deck Inventory/.app/src/tools/make_share_zip.py",
        "Deck Inventory/decks/order.txt",
    }
