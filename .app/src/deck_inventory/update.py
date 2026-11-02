"""Aggiornamento automatico dall'ultima release pubblicata su GitHub.

Tocca solo `.app/src/` e `README.txt`. Scambio delle cartelle con rollback:
o si installa tutta la versione nuova o resta quella di prima. Non solleva mai.
Solo standard library: deve funzionare anche se il resto del programma è rotto.
"""

import io
import json
import os
import re
import shutil
import time
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable, Literal

from deck_inventory import UPDATE_REPO, VERSION
from deck_inventory.changelog import between, format_entries, parse, parse_version

API_URL = "https://api.github.com/repos/{repo}/releases/latest"
API_ENV = "DECK_INVENTORY_UPDATE_API"  # solo per i test manuali: sostituisce l'URL completo
ASSET_NAME = "deck-inventory.zip"
REQUIRED = (".app/src/deck_inventory/__init__.py", ".app/src/pyproject.toml", "README.txt")
MOVE_ATTEMPTS = 5
MOVE_DELAY = 0.5
README_BAK = "README.txt.bak"

_rename = os.rename
_sleep = time.sleep


class UpdateError(Exception):
    pass


@dataclass
class Release:
    version: str
    zip_url: str


@dataclass
class Outcome:
    status: Literal["skipped", "current", "updated", "needs_launcher", "failed"]
    old: str
    new: str | None = None
    notes: str = ""


# --- rete ---------------------------------------------------------------------

def _request(url: str, timeout: float) -> bytes:
    req = urllib.request.Request(url, headers={
        "User-Agent": f"deck-inventory/{VERSION}",
        "Accept": "application/vnd.github+json",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def http_json(url: str) -> dict:
    return json.loads(_request(url, 3))


def http_bytes(url: str) -> bytes:
    return _request(url, 30)


def latest_release(fetch_json: Callable[[str], dict]) -> Release | None:
    override = os.environ.get(API_ENV, "").strip()
    try:
        data = fetch_json(override or API_URL.format(repo=UPDATE_REPO))
        tag = str(data["tag_name"]).strip()
        if parse_version(tag) is None:
            return None
        for asset in data.get("assets") or []:
            if asset.get("name") != ASSET_NAME:
                continue
            url = str(asset.get("browser_download_url") or "")
            # Solo HTTPS; l'override dei test manuali può puntare a un server locale.
            if url.startswith("https://") or (override and url):
                return Release(tag.lstrip("v"), url)
        return None
    except Exception:
        return None


# --- zip e metadati -----------------------------------------------------------

def _unsafe(name: str) -> bool:
    if name.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", name):
        return True
    return ".." in PurePosixPath(name.replace("\\", "/")).parts


def extract_release(data: bytes, staging: Path) -> Path:
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
        names = zf.namelist()
    except (zipfile.BadZipFile, ValueError, OSError) as e:
        raise UpdateError(f"zip non valido: {e}") from e
    with zf:
        bad = [n for n in names if _unsafe(n)]
        if bad:
            raise UpdateError(f"zip con percorso non ammesso: {bad[0]!r}")
        tops = {n.replace("\\", "/").split("/", 1)[0] for n in names}
        nested = len(tops) == 1 and all("/" in n.replace("\\", "/") for n in names)
        try:
            zf.extractall(staging)
        except (zipfile.BadZipFile, ValueError, OSError, EOFError) as e:
            raise UpdateError(f"zip non valido: {e}") from e
    root = staging / tops.pop() if nested else staging
    missing = [r for r in REQUIRED if not (root / r).is_file()]
    if missing:
        raise UpdateError(f"zip incompleto, manca {missing[0]}")
    return root


def read_meta(src_dir: Path) -> tuple[str, int]:
    text = (Path(src_dir) / "deck_inventory" / "__init__.py").read_text(encoding="utf-8")
    m = re.search(r"""^VERSION\s*=\s*["']([^"']+)["']""", text, re.MULTILINE)
    if not m:
        raise UpdateError(f"VERSION assente in {src_dir}")
    ml = re.search(r"^MIN_LAUNCHER\s*=\s*(\d+)", text, re.MULTILINE)
    return m.group(1), int(ml.group(1)) if ml else 1


def log_error(root: Path, message: str) -> None:
    try:
        log = Path(root) / ".app" / "runtime" / "last-error.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a", encoding="utf-8") as f:
            f.write(message.rstrip("\n") + "\n")
    except OSError:
        pass


# --- scambio delle cartelle ---------------------------------------------------

def _retry(action: Callable[[], None]) -> None:
    for attempt in range(MOVE_ATTEMPTS):
        try:
            action()
            return
        except OSError:
            if attempt == MOVE_ATTEMPTS - 1:
                raise
            _sleep(MOVE_DELAY)


def _move(src: Path, dst: Path) -> None:
    """Rinomina con più tentativi (file bloccati su Windows); ripiego: copia + rimozione.

    Se solleva, `src` è di nuovo completa (salvo errori anche nel ripristino).
    """
    try:
        _retry(lambda: _rename(src, dst))
        return
    except OSError:
        pass
    created = not dst.exists()
    try:
        shutil.copytree(src, dst)
    except BaseException:
        if created:
            shutil.rmtree(dst, ignore_errors=True)  # niente copie a metà
        raise
    try:
        _retry(lambda: shutil.rmtree(src))
    except OSError:
        # Rimozione interrotta da un file bloccato: rimette in `src` quanto già cancellato.
        shutil.copytree(dst, src, dirs_exist_ok=True)
        raise


def _remove(path: Path) -> None:
    if path.is_dir():
        _retry(lambda: shutil.rmtree(path))
    elif path.exists():
        path.unlink()


def _complete(src: Path) -> bool:
    return (src / "deck_inventory" / "__init__.py").is_file() and (src / "pyproject.toml").is_file()


def _restore(src: Path, previous: Path, readme: Path) -> None:
    """Rimette la vecchia `.app/src` (da `previous`) e il README salvato."""
    bak = previous / README_BAK
    if bak.exists():
        os.replace(bak, readme)
    if src.exists():
        try:
            _remove(src)
        except OSError:
            # File bloccato: si sovrascrive quel che resta con la versione vecchia.
            shutil.copytree(previous, src, dirs_exist_ok=True)
            shutil.rmtree(previous, ignore_errors=True)
            return
    _move(previous, src)


def _notes(src: Path, old: str, new: str) -> str:
    text = (src / "CHANGELOG.txt").read_text(encoding="utf-8")
    return format_entries(between(parse(text), old, new))


def check_and_update(root: Path, launcher: int,
                     fetch_json: Callable[[str], dict],
                     fetch_bytes: Callable[[str], bytes],
                     run_sync: Callable[[Path], bool],
                     now: Callable[[], str]) -> Outcome:
    root = Path(root)
    src = root / ".app" / "src"
    work = root / ".app" / "runtime" / "update"
    staging, previous = work / "staging", work / "previous"
    marker = work / "swap-in-progress"
    readme = root / "README.txt"

    def log(msg: str) -> None:
        try:
            stamp = now()
        except Exception:
            stamp = "?"
        log_error(root, f"{stamp} aggiornamento: {msg}")

    def sync(label: str) -> None:
        try:
            ok = run_sync(src)
        except Exception as e:
            ok = False
            label += f" ({e!r})"
        if not ok:
            log(f"uv sync non riuscito {label}")

    old = VERSION
    try:
        if (root / ".git").exists() or launcher < 1:
            return Outcome("skipped", old)
        _recover(src, previous, marker, readme, log, sync)
        old = read_meta(src)[0]
        release = latest_release(fetch_json)
        if release is None:
            return Outcome("skipped", old)
        new = release.version
        if parse_version(new) <= parse_version(old):
            return Outcome("current", old)
        notified = work / f"notified-{new}"
        if notified.exists():
            return Outcome("current", old)
    except Exception as e:
        log(f"controllo non riuscito: {e!r}")
        return Outcome("failed", old)

    old_moved = False
    readme_replaced = False
    try:
        had_readme = readme.exists()
        if staging.exists():
            _remove(staging)
        staging.mkdir(parents=True)
        rel_root = extract_release(fetch_bytes(release.zip_url), staging)
        rel_version, rel_min = read_meta(rel_root / ".app" / "src")
        if parse_version(rel_version) != parse_version(new):
            raise UpdateError(f"la release {new} contiene la versione {rel_version}")
        if rel_min > launcher:
            notified.touch()
            try:
                notes = _notes(rel_root / ".app" / "src", old, new)
            except Exception as e:
                log(f"CHANGELOG della {new} illeggibile: {e!r}")
                notes = ""
            _remove(staging)
            return Outcome("needs_launcher", old, new, notes)

        if previous.exists():
            _remove(previous)  # _recover ha già stabilito che non serve
        marker.touch()
        _move(src, previous)
        old_moved = True
        if had_readme:
            shutil.copy2(readme, previous / README_BAK)
        _move(rel_root / ".app" / "src", src)
        os.replace(rel_root / "README.txt", readme)
        readme_replaced = True
        if not run_sync(src):
            raise UpdateError("uv sync non riuscito con la nuova versione")
    except Exception as e:
        log(f"installazione della {new} non riuscita, resta la {old}: {e!r}")
        restored = True
        if old_moved:
            try:
                _restore(src, previous, readme)
                if readme_replaced and not had_readme and readme.exists():
                    readme.unlink()
                sync("anche sulla versione ripristinata")
            except Exception as e2:
                restored = False
                log(f"ripristino non riuscito, si riprova al prossimo avvio: {e2!r}")
        if restored:
            _settle(src, previous, marker, staging)
        else:
            _cleanup(staging)  # `previous` e il segnale restano per _recover
        return Outcome("failed", old, new)

    try:
        notes = _notes(src, old, new)
    except Exception as e:
        log(f"CHANGELOG della {new} illeggibile, note omesse: {e!r}")
        notes = ""
    marker.unlink(missing_ok=True)
    _cleanup(staging, previous)
    return Outcome("updated", old, new, notes)


def _recover(src, previous, marker, readme, log, sync) -> None:
    """Sistema i resti di uno scambio interrotto (programma chiuso a metà, ripristino fallito)."""
    if _complete(previous) and (marker.exists() or not _complete(src)):
        log("scambio interrotto trovato: ripristino la versione precedente")
        _restore(src, previous, readme)
        sync("dopo il ripristino della versione precedente")
    _settle(src, previous, marker)


def _settle(src: Path, previous: Path, marker: Path, *extra: Path) -> None:
    """Pulisce solo se `.app/src` è completa; altrimenti lascia tutto per il prossimo avvio."""
    _cleanup(*extra)
    if _complete(src):
        marker.unlink(missing_ok=True)
        _cleanup(previous)


def _cleanup(*paths: Path) -> None:
    for p in paths:
        shutil.rmtree(p, ignore_errors=True)
