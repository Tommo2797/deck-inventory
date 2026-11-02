import shutil
import stat
import subprocess
import zipfile

import pytest

from deck_inventory.decks import _ORDER_HEADER
from tools.make_share_zip import make_share_zip


def _build(tmp_path):
    proj = tmp_path / "proj"
    files = {
        "Start (Mac).command": "#!/bin/bash\n",
        "Start (Windows).bat": "@echo off\n",
        "README.txt": "ciao",
        ".gitignore": "x",
        ".gitattributes": "x",
        "settings.txt": "binder = https://x",
        "Inventory 2026-10-31 12.00.html": "<html>",
        "decks/mio.txt": "Legend:\n1 X",
        "decks/order.txt": "mio",
        "docs/spec.md": "x",
        ".git/HEAD": "x",
        ".superpowers/a.md": "x",
        ".DS_Store": "x",
        ".app/runtime/venv/bin/python": "x",
        ".app/src/pyproject.toml": "x",
        ".app/src/deck_inventory/__init__.py": "x",
        ".app/src/deck_inventory/__pycache__/a.pyc": "x",
        ".app/src/tests/test_a.py": "x",
        ".app/src/tests/fixtures/decks/f.txt": "x",
        ".app/src/.pytest_cache/v": "x",
        ".venv/bin/python": "x",
        ".app/src/.venv/lib/site.py": "x",
    }
    for rel, content in files.items():
        p = proj / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    (proj / "Start (Mac).command").chmod(0o755)
    out = tmp_path / "out.zip"
    make_share_zip(proj, out)
    return out


def test_included_and_excluded(tmp_path):
    names = set(zipfile.ZipFile(_build(tmp_path)).namelist())
    assert names == {
        "Deck Inventory/Start (Mac).command",
        "Deck Inventory/Start (Windows).bat",
        "Deck Inventory/README.txt",
        "Deck Inventory/decks/order.txt",
        "Deck Inventory/.app/src/pyproject.toml",
        "Deck Inventory/.app/src/deck_inventory/__init__.py",
    }


def test_order_txt_is_commented_example(tmp_path):
    zf = zipfile.ZipFile(_build(tmp_path))
    text = zf.read("Deck Inventory/decks/order.txt").decode("utf-8")
    assert text == _ORDER_HEADER
    assert all(line.startswith("#") for line in text.splitlines())


def test_exec_bit_preserved(tmp_path):
    zf = zipfile.ZipFile(_build(tmp_path))
    mode = zf.getinfo("Deck Inventory/Start (Mac).command").external_attr >> 16
    assert mode & stat.S_IXUSR
    mode = zf.getinfo("Deck Inventory/README.txt").external_attr >> 16
    assert not mode & stat.S_IXUSR


def test_deterministic(tmp_path):
    a = _build(tmp_path).read_bytes()
    assert a == _build(tmp_path).read_bytes()


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.mark.skipif(shutil.which("git") is None, reason="git non installato")
def test_git_repo_only_tracked_files(tmp_path):
    proj = tmp_path / "proj"
    files = {
        ".gitignore": "segreto.txt\n/.app/runtime/\n",
        "README.txt": "ciao",
        ".app/src/deck_inventory/__init__.py": "x",
        ".app/src/uv.lock": "x",
        ".app/src/deck_inventory/nuovo_non_aggiunto.py": "x",  # non tracciato
        "segreto.txt": "dati personali",  # ignorato e non nella lista delle esclusioni
        ".app/src/tests/test_a.py": "x",  # tracciato ma escluso lo stesso
        "settings.txt": "binder = https://x",  # tracciato per sbaglio: escluso lo stesso
    }
    for rel, content in files.items():
        p = proj / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    _git(proj, "init", "-q")
    _git(proj, "add", ".gitignore", "README.txt", ".app/src/deck_inventory/__init__.py",
         ".app/src/uv.lock", ".app/src/tests/test_a.py", "settings.txt")
    (proj / ".app/src/uv.lock").unlink()  # tracciato ma cancellato dal disco: si salta
    out = tmp_path / "out.zip"
    make_share_zip(proj, out)
    assert set(zipfile.ZipFile(out).namelist()) == {
        "Deck Inventory/README.txt",
        "Deck Inventory/.app/src/deck_inventory/__init__.py",
        "Deck Inventory/decks/order.txt",
    }


@pytest.mark.skipif(shutil.which("git") is None, reason="git non installato")
def test_subfolder_of_other_repo_uses_all_files(tmp_path):
    """Cartella dentro un altro repository (non ne è la radice): comportamento senza git."""
    _git(tmp_path, "init", "-q")
    proj = tmp_path / "proj"
    (proj / ".app/src").mkdir(parents=True)
    (proj / "README.txt").write_text("ciao")
    (proj / ".app/src/pyproject.toml").write_text("x")
    out = tmp_path / "out.zip"
    make_share_zip(proj, out)
    assert set(zipfile.ZipFile(out).namelist()) == {
        "Deck Inventory/README.txt",
        "Deck Inventory/.app/src/pyproject.toml",
        "Deck Inventory/decks/order.txt",
    }
