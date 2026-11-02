"""Aggiornamento automatico dall'ultima release pubblicata su GitHub.

Avvio (dai launcher, prima del programma): python -m deck_inventory.update <cartella del progetto>

Contratto fisso con i launcher (che non si aggiornano mai): chiamano
`python -m deck_inventory.update <ROOT>` e passano le variabili d'ambiente
DECK_INVENTORY_LAUNCHER (numero di versione del launcher) e DECK_INVENTORY_UV
(percorso di uv). Le versioni future devono mantenere questo percorso di modulo
e questi nomi; se i launcher devono cambiare, alzare MIN_LAUNCHER.
Altri vincoli che valgono per OGNI versione futura:
- Dopo lo scambio, il messaggio "aggiornato" lo mostra `deck_inventory.dialogs`
  della versione NUOVA (importato dentro `main`): `dialogs.info(str)` deve
  continuare a esistere e quel modulo deve importare solo standard library o
  moduli stabili del pacchetto.
- I launcher usano sempre uv 0.13.1 (UV_VERSION, fisso): ogni pyproject.toml e
  uv.lock futuri devono funzionare con `uv sync --frozen` di quella versione,
  altrimenti ogni aggiornamento fallisce il sync e torna indietro.
- I launcher, prima di questo passo, fanno `uv sync` e importano da `.app/src`:
  se `.app/src` è incompleta il programma non arriva qui e nessun ripristino
  automatico è possibile. Per questo lo scambio lascia `.app/src` mancante solo
  per l'istante fra due rinomine consecutive.

Tocca solo `.app/src/` e `README.txt`. Scambio delle cartelle con rollback:
o si installa tutta la versione nuova o resta quella di prima. Non solleva mai.
Solo standard library: deve funzionare anche se il resto del programma è rotto.
"""

import io
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Callable, Literal

from deck_inventory import UPDATE_REPO, VERSION
from deck_inventory.changelog import between, format_entries, parse, parse_version

if os.name == "nt":
    import msvcrt
else:
    import fcntl

API_URL = "https://api.github.com/repos/{repo}/releases/latest"
API_ENV = "DECK_INVENTORY_UPDATE_API"  # solo per i test manuali: sostituisce l'URL completo
ASSET_NAME = "deck-inventory.zip"
REQUIRED = (".app/src/deck_inventory/__init__.py", ".app/src/pyproject.toml", ".app/src/uv.lock",
            "README.txt")
MOVE_ATTEMPTS = 5
MOVE_DELAY = 0.5
README_BAK = "README.txt.bak"

UPDATED_MESSAGE = (
    "Deck Inventory è stato aggiornato dalla versione {old} alla versione {new}.\n\n"
    "Novità:\n{notes}"
)
NEEDS_LAUNCHER_MESSAGE = (
    "È disponibile la versione {new} di Deck Inventory, ma per installarla serve "
    "scaricarla di nuovo a mano da:\n"
    "https://github.com/{repo}/releases/latest\n\n"
    "Per ora continui a usare la versione {old}."
)

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

def _request(url: str, timeout: float, accept: str) -> bytes:
    req = urllib.request.Request(url, headers={
        "User-Agent": f"deck-inventory/{VERSION}",
        "Accept": accept,
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def http_json(url: str) -> dict:
    return json.loads(_request(url, 3, "application/vnd.github+json"))


def http_bytes(url: str) -> bytes:
    # browser_download_url rimanda (redirect) al file vero: si chiede il file, non JSON.
    return _request(url, 30, "application/octet-stream")


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
    # La copia va in `<dst>.partial` e prende il nome finale solo quando è finita:
    # una `dst` che esiste è sempre completa, anche se il programma viene chiuso a metà.
    tmp = _partial(dst)
    shutil.rmtree(tmp, ignore_errors=True)
    try:
        shutil.copytree(src, tmp)
        # Copia appena creata: nessuno la tiene aperta (il blocco riguarda `src`).
        _retry(lambda: os.rename(tmp, dst))
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    try:
        _retry(lambda: shutil.rmtree(src))
    except OSError:
        # Rimozione interrotta da un file bloccato: rimette in `src` quanto già cancellato.
        shutil.copytree(dst, src, dirs_exist_ok=True)
        raise


def _partial(path: Path) -> Path:
    return path.with_name(path.name + ".partial")


def _remove(path: Path) -> None:
    if path.is_dir():
        _retry(lambda: shutil.rmtree(path))
    elif path.exists():
        path.unlink()


def _complete(src: Path) -> bool:
    return (src / "deck_inventory" / "__init__.py").is_file() and (src / "pyproject.toml").is_file()


def _restore(src: Path, previous: Path, readme: Path, bak: Path) -> None:
    """Rimette la vecchia `.app/src` (da `previous`) e il README salvato in `bak`."""
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


def _overlay_previous(src: Path, previous: Path, log: Callable[[str], None]) -> None:
    """Ultima risorsa dopo un ripristino fallito: copia la versione vecchia sopra `.app/src`.

    I launcher fanno `uv sync` e importano da `.app/src` prima di arrivare qui: se
    `.app/src` resta incompleta, nessun ripristino automatico può più partire.
    `previous` e il segnale restano: se il programma riparte, il prossimo avvio
    rifà il ripristino pulito.
    """
    try:
        if _complete(previous):
            shutil.copytree(previous, src, dirs_exist_ok=True)
            log("copiata la versione precedente sopra .app/src (ultima risorsa); "
                "al prossimo avvio si completa il ripristino")
            return
        log("la copia della versione precedente in .app/runtime/update/previous è incompleta")
    except Exception as e:
        log(f"anche la copia della versione precedente sopra .app/src non è riuscita: {e!r}")
    log("ATTENZIONE: .app/src potrebbe essere incompleta. Se Deck Inventory non parte, "
        f"riscaricalo da https://github.com/{UPDATE_REPO}/releases/latest "
        "(settings.txt e la cartella decks si possono copiare nella nuova cartella)")


def _notes(src: Path, old: str, new: str) -> str:
    text = (src / "CHANGELOG.txt").read_text(encoding="utf-8")
    return format_entries(between(parse(text), old, new))


# --- blocco: un solo aggiornamento alla volta ---------------------------------

LOCK_NAME = "lock"


def _lock_posix(fd: int) -> None:
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)


def _unlock_posix(fd: int) -> None:
    fcntl.flock(fd, fcntl.LOCK_UN)


def _lock_windows(fd: int) -> None:
    # Si blocca sempre il primo byte (anche oltre la fine del file vuoto: è ammesso).
    os.lseek(fd, 0, os.SEEK_SET)
    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)


def _unlock_windows(fd: int) -> None:
    os.lseek(fd, 0, os.SEEK_SET)
    msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)


if os.name == "nt":
    _lock_fd, _unlock_fd = _lock_windows, _unlock_windows
else:
    _lock_fd, _unlock_fd = _lock_posix, _unlock_posix


def _acquire(path: Path) -> int | None:
    """Apre e blocca `path` senza aspettare. None se lo tiene già un altro avvio.

    Il blocco del sistema operativo sparisce da solo se il processo muore.
    Solleva OSError per gli altri errori (cartella non scrivibile, blocchi non supportati).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o644)
    try:
        _lock_fd(fd)
    except (BlockingIOError, PermissionError):
        # Occupato: POSIX → EWOULDBLOCK, Windows (LK_NBLCK) → EACCES.
        os.close(fd)
        return None
    except BaseException:
        os.close(fd)
        raise
    return fd


def _release(fd: int) -> None:
    try:
        _unlock_fd(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def check_and_update(root: Path, launcher: int,
                     fetch_json: Callable[[str], dict],
                     fetch_bytes: Callable[[str], bytes],
                     run_sync: Callable[[Path], bool],
                     now: Callable[[], str]) -> Outcome:
    root = Path(root)
    if (root / ".git").exists() or launcher < 1:
        return Outcome("skipped", VERSION)
    log = _logger(root, now)
    # Due avvii quasi insieme (doppio doppio clic): il secondo non tocca niente,
    # neanche il ripristino, finché il primo non ha finito.
    try:
        fd = _acquire(root / ".app" / "runtime" / "update" / LOCK_NAME)
    except OSError as e:
        log(f"blocco non disponibile, aggiornamento saltato: {e!r}")
        return Outcome("failed", VERSION)
    if fd is None:
        return Outcome("skipped", VERSION)
    try:
        return _check_and_update_locked(root, launcher, fetch_json, fetch_bytes, run_sync, log)
    finally:
        _release(fd)


def _logger(root: Path, now: Callable[[], str]) -> Callable[[str], None]:
    def log(msg: str) -> None:
        try:
            stamp = now()
        except Exception:
            stamp = "?"
        log_error(root, f"{stamp} aggiornamento: {msg}")
    return log


def _check_and_update_locked(root: Path, launcher: int,
                             fetch_json: Callable[[str], dict],
                             fetch_bytes: Callable[[str], bytes],
                             run_sync: Callable[[Path], bool],
                             log: Callable[[str], None]) -> Outcome:
    src = root / ".app" / "src"
    work = root / ".app" / "runtime" / "update"
    staging, previous = work / "staging", work / "previous"
    marker = work / "swap-in-progress"
    bak = work / README_BAK
    readme = root / "README.txt"

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
        _recover(src, previous, marker, readme, bak, log, sync)
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
        # Tutto il preparabile si fa prima: fra le due rinomine di `.app/src`
        # (vecchia → previous, nuova → src) non c'è nient'altro.
        bak.unlink(missing_ok=True)
        if had_readme:
            shutil.copy2(readme, bak)
        marker.touch()
        _move(src, previous)
        old_moved = True
        _move(rel_root / ".app" / "src", src)
        os.replace(rel_root / "README.txt", readme)
        readme_replaced = True
        if not run_sync(src):
            raise UpdateError("uv sync non riuscito con la nuova versione")
        marker.unlink(missing_ok=True)  # scambio concluso: da qui in poi niente ripristino
    except Exception as e:
        log(f"installazione della {new} non riuscita, resta la {old}: {e!r}")
        restored = True
        if old_moved:
            try:
                _restore(src, previous, readme, bak)
                if readme_replaced and not had_readme and readme.exists():
                    readme.unlink()
                sync("anche sulla versione ripristinata")
            except Exception as e2:
                restored = False
                log(f"ripristino della versione precedente non riuscito: {e2!r}")
                _overlay_previous(src, previous, log)
        if restored:
            _settle(src, previous, marker, bak, staging)
        else:
            _cleanup(staging)  # `previous` e il segnale restano per _recover
        return Outcome("failed", old, new)

    try:
        notes = _notes(src, old, new)
    except Exception as e:
        log(f"CHANGELOG della {new} illeggibile, note omesse: {e!r}")
        notes = ""
    _settle(src, previous, marker, bak, staging)
    return Outcome("updated", old, new, notes)


def _recover(src, previous, marker, readme, bak, log, sync) -> None:
    """Sistema i resti di uno scambio interrotto (programma chiuso a metà, ripristino fallito).

    Funziona solo se `.app/src` è abbastanza completa da far arrivare i launcher
    fin qui (vedi il contratto in cima al modulo).
    """
    if _complete(previous) and (marker.exists() or not _complete(src)):
        log("scambio interrotto trovato: ripristino la versione precedente")
        try:
            _restore(src, previous, readme, bak)
        except Exception as e:
            log(f"ripristino della versione precedente non riuscito: {e!r}")
            _overlay_previous(src, previous, log)
            raise
        sync("dopo il ripristino della versione precedente")
    _settle(src, previous, marker, bak)


def _settle(src: Path, previous: Path, marker: Path, bak: Path, *extra: Path) -> None:
    """Pulisce solo se `.app/src` è completa; altrimenti lascia tutto per il prossimo avvio.

    Le copie `.partial` non sono mai affidabili e si eliminano sempre.
    """
    _cleanup(_partial(src), _partial(previous), *extra)
    if _complete(src):
        marker.unlink(missing_ok=True)
        bak.unlink(missing_ok=True)
        _cleanup(previous)


def _cleanup(*paths: Path) -> None:
    for p in paths:
        shutil.rmtree(p, ignore_errors=True)


# --- punto di ingresso --------------------------------------------------------

def _launcher_version() -> int:
    try:
        return int(os.environ.get("DECK_INVENTORY_LAUNCHER", "0"))
    except ValueError:
        return 0


def _uv_sync(src: Path) -> bool:
    uv = os.environ.get("DECK_INVENTORY_UV", "").strip()
    if not uv or not Path(uv).is_file():
        return False
    try:
        return subprocess.run([uv, "sync", "--project", str(src), "--frozen", "--no-dev"]).returncode == 0
    except OSError:
        return False


def _message(outcome: Outcome) -> str | None:
    if outcome.status == "updated":
        return UPDATED_MESSAGE.format(old=outcome.old, new=outcome.new, notes=outcome.notes)
    if outcome.status == "needs_launcher":
        return NEEDS_LAUNCHER_MESSAGE.format(old=outcome.old, new=outcome.new, repo=UPDATE_REPO)
    return None


def main(argv: list[str], ui=None) -> int:
    """Passo di aggiornamento dei launcher. Restituisce sempre 0: non blocca mai l'avvio."""
    root = Path(argv[1]) if len(argv) > 1 else None
    if root is None:
        return 0
    try:
        outcome = check_and_update(root, _launcher_version(), http_json, http_bytes, _uv_sync,
                                   lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        message = _message(outcome)
        if message and os.environ.get("DECK_INVENTORY_NO_DIALOG") != "1":
            if ui is None:
                from deck_inventory import dialogs as ui
            ui.info(message)
    except Exception as e:
        log_error(root, f"aggiornamento: errore imprevisto: {e!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
