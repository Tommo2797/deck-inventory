"""Pubblica una nuova versione su GitHub (solo autore, Mac).

Uso: .app/src/tools/publish.sh <versione> [--skip-online] [--dry-run]

Controlla tutto prima di toccare qualcosa (ramo main allineato e pulito, account gh,
uv uguale a quello dei launcher, versione, voce nel CHANGELOG, test normali + privati
+ dal vivo), poi aggiorna VERSION, CHANGELOG e README, crea commit e tag, li carica e
crea la release con lo zip (prima verificato come lo installerebbe l'aggiornamento).
Il link del binder (da settings.txt) serve solo al test dal vivo: non viene mai
stampato né scritto da nessuna parte.
"""

import argparse
import os
import re
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from deck_inventory import UPDATE_REPO, changelog, update  # noqa: E402
from deck_inventory.errors import SettingsError  # noqa: E402
from deck_inventory.settings import read_link  # noqa: E402
from tools.make_share_zip import make_share_zip  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
ZIP_NAME = "deck-inventory.zip"
BINDER_ENV = "DECK_INVENTORY_TEST_BINDER"
MAC_LAUNCHER = "Start (Mac).command"
_VERSION_LINE = re.compile(r'^VERSION = "[^"]*"$', re.MULTILINE)
_UV_VERSION_LINE = re.compile(r'^UV_VERSION="([^"]+)"', re.MULTILINE)

Sh = Callable[[list[str]], str]


class Refused(Exception):
    """Un controllo non è passato: il messaggio spiega perché."""


def check_version(new: str, latest: str | None) -> None:
    if not re.fullmatch(r"\d+\.\d+\.\d+", new):
        raise ValueError(f"La versione {new!r} non è nel formato x.y.z (es. 1.2.0).")
    if latest is None:
        return
    old = changelog.parse_version(latest)
    if old is None:
        raise ValueError(f"L'ultima release ha un nome non riconosciuto: {latest!r}.")
    if changelog.parse_version(new) <= old:
        raise ValueError(f"La versione {new} non è più alta dell'ultima pubblicata ({latest}).")


def bump_version(init_text: str, new: str) -> str:
    out, n = _VERSION_LINE.subn(f'VERSION = "{new}"', init_text)
    if n != 1:
        raise ValueError("Riga VERSION non trovata in deck_inventory/__init__.py.")
    return out


def release_notes(changelog_text: str, version: str) -> str:
    target = changelog.parse_version(version)
    for entry in changelog.parse(changelog_text):
        if changelog.parse_version(entry.version) == target:
            if not entry.items:
                raise ValueError(f"Nel CHANGELOG la voce {version} non ha novità.")
            return changelog.format_entries([entry])
    raise ValueError(f"Nel CHANGELOG manca la voce == {version} ==.")


def launcher_uv_version(root: Path) -> str:
    """La versione di uv fissata nei launcher (letta dal launcher Mac, unica fonte)."""
    try:
        text = (root / MAC_LAUNCHER).read_text(encoding="utf-8")
    except OSError as e:
        raise Refused(f"Non riesco a leggere {MAC_LAUNCHER}: {e}")
    m = _UV_VERSION_LINE.search(text)
    if not m:
        raise Refused(f"In {MAC_LAUNCHER} manca la riga UV_VERSION=\"...\".")
    return m.group(1)


def check_zip(zip_path: Path, version: str | None) -> None:
    """Lo zip passa gli stessi controlli dell'aggiornamento automatico.

    `version` None (prova): solo struttura e MIN_LAUNCHER, la versione non è ancora alzata.
    """
    with tempfile.TemporaryDirectory() as tmp:
        try:
            rel_root = update.extract_release(Path(zip_path).read_bytes(), Path(tmp))
            got, min_launcher = update.read_meta(rel_root / ".app" / "src")
        except (update.UpdateError, OSError) as e:
            raise Refused(f"Lo zip della release non sarebbe installabile dall'aggiornamento: {e}")
    if version is not None and got != version:
        raise Refused(f"Lo zip contiene la versione {got}, non la {version}.")
    if not isinstance(min_launcher, int) or min_launcher < 1:
        raise Refused(f"Nello zip MIN_LAUNCHER vale {min_launcher!r}: deve essere un intero >= 1.")


def _today() -> str:
    return date.today().isoformat()


def _real_sh(root: Path) -> Sh:
    def sh(cmd: list[str]) -> str:
        return subprocess.run(cmd, cwd=root, capture_output=True, text=True, check=True).stdout
    return sh


def _redact(text: str, secret: str | None) -> str:
    return text.replace(secret, "<link del binder>") if secret else text


def _call(sh: Sh, cmd: list[str], what: str, secret: str | None = None) -> str:
    try:
        return sh(cmd)
    except subprocess.CalledProcessError as e:
        detail = "\n".join(s.strip() for s in (e.stdout or "", e.stderr or "") if s and s.strip())
        detail = _redact(detail[-3000:], secret)
        raise Refused(f"{what} non è riuscito." + (f"\n{detail}" if detail else ""))
    except OSError as e:
        raise Refused(f"{what} non è riuscito: {e}")


def _check_git(sh: Sh) -> None:
    branch = _call(sh, ["git", "rev-parse", "--abbrev-ref", "HEAD"], "Leggere il ramo git").strip()
    if branch != "main":
        raise Refused(f"Sei sul ramo {branch!r}: si pubblica solo dal ramo main.")
    if _call(sh, ["git", "status", "--porcelain"], "git status").strip():
        raise Refused("Ci sono modifiche non salvate in git: fai commit (o annullale) e riprova.")
    _call(sh, ["git", "fetch", "origin"], "git fetch (collegamento a GitHub)")
    head = _call(sh, ["git", "rev-parse", "HEAD"], "Leggere HEAD").strip()
    remote = _call(sh, ["git", "rev-parse", "origin/main"], "Leggere origin/main").strip()
    if head != remote:
        raise Refused("Il ramo main locale non è allineato con GitHub (origin/main): fai pull/push e riprova.")


def _check_gh(sh: Sh) -> None:
    owner = UPDATE_REPO.split("/")[0]
    login = _call(sh, ["gh", "api", "user", "-q", ".login"], "Leggere l'account gh (gh auth login?)").strip()
    if login != owner:
        raise Refused(f"gh è collegato all'account {login!r}, ma il repository {UPDATE_REPO} è di {owner!r}.")


def _check_uv(sh: Sh, root: Path) -> None:
    """uv.lock si scrive con l'uv in uso: deve essere quello dei launcher, che non cambia mai."""
    want = launcher_uv_version(root)
    uv = os.environ.get("UV", "").strip()  # impostata da `uv run` (publish.sh)
    if not uv:
        raise Refused("Non so quale uv è in uso: avvia con .app/src/tools/publish.sh.")
    words = _call(sh, [uv, "--version"], "Leggere la versione di uv").split()
    got = words[1] if len(words) > 1 else "?"
    if got != want:
        raise Refused(f"Stai usando uv {got}, ma i launcher usano uv {want} (UV_VERSION in {MAC_LAUNCHER}): "
                      f"uv.lock deve funzionare con quella. Usa uv {want}.")


def _latest_release(sh: Sh) -> str | None:
    cmd = ["gh", "release", "view", "--repo", UPDATE_REPO, "--json", "tagName", "-q", ".tagName"]
    try:
        return sh(cmd).strip() or None
    except subprocess.CalledProcessError as e:
        if "not found" in (e.stderr or "").lower():
            return None
        raise Refused(f"Leggere l'ultima release di {UPDATE_REPO} non è riuscito.\n{(e.stderr or '').strip()}")


def _run_tests(sh: Sh, root: Path, skip_online: bool) -> None:
    tests = root / ".app/src/tests"
    if not (tests / "private").is_dir():
        raise Refused("Manca .app/src/tests/private: senza i dati privati i test non sono completi.")
    pytest = [sys.executable, "-m", "pytest", str(tests), "-q"]
    print("Test normali e con dati privati...")
    out = _call(sh, pytest, "La suite di test")
    print("  " + (out.strip().splitlines() or ["ok"])[-1])
    if skip_online:
        print("\n!!! ATTENZIONE: test dal vivo su Piltover Archive SALTATO (--skip-online) !!!\n")
        return
    try:
        link = read_link(root)
    except SettingsError:
        link = None
    if not link:
        raise Refused("Per il test dal vivo serve un link valido in settings.txt (oppure usa --skip-online).")
    print("Test dal vivo su Piltover Archive...")
    previous = os.environ.get(BINDER_ENV)
    os.environ[BINDER_ENV] = link
    try:
        out = _call(sh, [*pytest, "-m", "online"], "Il test dal vivo", secret=link)
    finally:
        if previous is None:
            os.environ.pop(BINDER_ENV, None)
        else:
            os.environ[BINDER_ENV] = previous
    print("  " + _redact((out.strip().splitlines() or ["ok"])[-1], link))


def _release(sh: Sh, root: Path, version: str, notes_today: str) -> None:
    tag = f"v{version}"
    init = root / ".app/src/deck_inventory/__init__.py"
    log = root / ".app/src/CHANGELOG.txt"
    readme = root / "README.txt"
    done: list[str] = []
    todo = ["file aggiornati (VERSION, CHANGELOG, README)", "commit", f"tag {tag}",
            f"push di main e {tag} su GitHub", f"release {tag} con {ZIP_NAME}"]

    def step(what: str, action: Callable[[], object]) -> None:
        try:
            action()
        except Exception as e:
            msg = str(e) if isinstance(e, Refused) else f"{what}: {e}"
            raise Refused(
                f"{msg}\nGià fatto: {', '.join(done) or 'niente'}.\nNon fatto: {', '.join(todo)}."
            ) from e
        done.append(todo.pop(0))

    def write_files() -> None:
        init.write_text(bump_version(init.read_text(encoding="utf-8"), version), encoding="utf-8")
        text = changelog.set_release_date(log.read_text(encoding="utf-8"), version, notes_today)
        log.write_text(text, encoding="utf-8")
        section = changelog.readme_section(changelog.parse(text))
        readme.write_text(changelog.replace_readme_section(readme.read_text(encoding="utf-8"), section),
                          encoding="utf-8")

    step("Aggiornare i file", write_files)
    files = [str(p.relative_to(root)) for p in (init, log, readme)]
    step("git commit", lambda: (_call(sh, ["git", "add", "--", *files], "git add"),
                                _call(sh, ["git", "commit", "-m", f"release: {tag}"], "git commit")))
    step("git tag", lambda: _call(sh, ["git", "tag", tag], "git tag"))
    step("git push", lambda: _call(sh, ["git", "push", "origin", "main", tag], "git push"))

    def create_release() -> None:
        notes = release_notes(log.read_text(encoding="utf-8"), version)
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = Path(tmp) / ZIP_NAME
            make_share_zip(root, zip_path)
            check_zip(zip_path, version)
            _call(sh, ["gh", "release", "create", tag, str(zip_path), "--repo", UPDATE_REPO,
                       "--title", f"Deck Inventory {version}", "--notes", notes], "gh release create")

    step("Creare la release", create_release)


def run(argv: list[str], sh: Sh, root: Path = ROOT) -> int:
    parser = argparse.ArgumentParser(prog="publish.sh", description="Pubblica una nuova versione.")
    parser.add_argument("version", help="es. 1.2.0")
    parser.add_argument("--skip-online", action="store_true", help="salta solo il test dal vivo")
    parser.add_argument("--dry-run", action="store_true", help="controlla tutto senza pubblicare")
    args = parser.parse_args(argv)
    version, tag = args.version, f"v{args.version}"
    try:
        _check_git(sh)
        _check_gh(sh)
        _check_uv(sh, root)
        latest = _latest_release(sh)
        try:
            check_version(version, latest)
            release_notes((root / ".app/src/CHANGELOG.txt").read_text(encoding="utf-8"), version)
        except ValueError as e:
            raise Refused(str(e))
        _run_tests(sh, root, args.skip_online)

        # Prova dello zip prima di qualunque commit/tag/push; dopo l'aumento di
        # versione si ricrea e si ricontrolla (anche la versione) prima della release.
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = Path(tmp) / ZIP_NAME
            make_share_zip(root, zip_path)
            check_zip(zip_path, None)
            size = zip_path.stat().st_size

        if args.dry_run:
            print(f"\nProva (--dry-run): tutti i controlli sono passati. Ultima release: {latest or 'nessuna'}.")
            print(f"Pubblicando {tag} farebbe:")
            print(f"  1. VERSION = \"{version}\", data di oggi ({_today()}) nel CHANGELOG, sezione NOVITÀ del README")
            print(f"  2. commit \"release: {tag}\", tag {tag}, git push origin main {tag}")
            print(f"  3. release {tag} su {UPDATE_REPO} con {ZIP_NAME} ({size / 1_000_000:.1f} MB)")
            print("Nessuna modifica fatta.")
            return 0

        _release(sh, root, version, _today())
    except Refused as e:
        print(f"\nPubblicazione interrotta: {e}")
        return 1
    print(f"\nPubblicata {tag}: https://github.com/{UPDATE_REPO}/releases/tag/{tag}")
    return 0


if __name__ == "__main__":
    sys.exit(run(sys.argv[1:], _real_sh(ROOT)))
