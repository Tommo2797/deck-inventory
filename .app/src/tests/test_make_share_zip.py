import stat
import zipfile

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
