"""Crea lo zip da condividere: python make_share_zip.py <cartella_progetto> <out.zip>

Esclude runtime, impostazioni, pagine generate, mazzi personali e file di sviluppo
(test compresi).
Dentro lo zip mette un decks/order.txt di esempio (solo commenti).
"""
import fnmatch
import stat
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from deck_inventory.decks import _ORDER_HEADER  # noqa: E402

ROOT_NAME = "Deck Inventory"
EXCLUDED_DIRS = {".git", ".superpowers", "__pycache__", ".pytest_cache"}
EXCLUDED_PATHS = {".app/runtime", ".app/src/tests", "decks", "docs", "settings.txt", ".gitignore", ".gitattributes"}
EXCLUDED_NAMES = {".DS_Store"}
EXCLUDED_PATTERNS = ["Inventory *.html"]
FIXED_DATE = (2026, 1, 1, 0, 0, 0)


def _included(rel: Path) -> bool:
    if any(part in EXCLUDED_DIRS or part in EXCLUDED_NAMES for part in rel.parts):
        return False
    posix = rel.as_posix()
    if any(posix == p or posix.startswith(p + "/") for p in EXCLUDED_PATHS):
        return False
    if len(rel.parts) == 1 and any(fnmatch.fnmatch(rel.name, pat) for pat in EXCLUDED_PATTERNS):
        return False
    return True


def _add(zf: zipfile.ZipFile, name: str, data: bytes, mode: int) -> None:
    info = zipfile.ZipInfo(f"{ROOT_NAME}/{name}", FIXED_DATE)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3  # Unix: serve per far valere external_attr
    info.external_attr = (stat.S_IFREG | mode) << 16
    zf.writestr(info, data)


def make_share_zip(project_dir: Path, out_zip: Path) -> None:
    project_dir = Path(project_dir)
    entries = []
    for path in project_dir.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(project_dir)
        if _included(rel):
            entries.append((rel.as_posix(), path))
    entries.append(("decks/order.txt", None))
    with zipfile.ZipFile(out_zip, "w") as zf:
        for name, path in sorted(entries):
            if path is None:
                _add(zf, name, _ORDER_HEADER.encode("utf-8"), 0o644)
                continue
            executable = bool(path.stat().st_mode & stat.S_IXUSR) or path.suffix == ".command"
            _add(zf, name, path.read_bytes(), 0o755 if executable else 0o644)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("Uso: make_share_zip.py <cartella_progetto> <out.zip>")
    make_share_zip(Path(sys.argv[1]), Path(sys.argv[2]))
    print(f"Creato {sys.argv[2]}")
