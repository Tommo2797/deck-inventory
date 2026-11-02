"""Scelta del browser Chromium da usare con Playwright."""

import os
import plistlib
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from deck_inventory.errors import BrowserUnavailableError


@dataclass(frozen=True)
class LaunchSpec:
    channel: str | None
    executable_path: str | None


_MAC_IDS = {
    "com.google.chrome": "chrome",
    "com.microsoft.edgemac": "msedge",
    "com.brave.browser": "brave",
    "com.vivaldi.vivaldi": "vivaldi",
}
_WIN_IDS = {
    "chromehtml": "chrome",
    "msedgehtm": "msedge",
    "bravehtml": "brave",
    "vivaldihtm": "vivaldi",
}
# Ordine dopo chrome e msedge: "altri trovati".
# Opera è escluso: su Windows launcher.exe è solo un avviatore e Playwright non
# riesce a pilotarlo.
_OTHERS = ("brave", "vivaldi", "chromium")

_MAC_APPS = {
    "chrome": "Google Chrome",
    "msedge": "Microsoft Edge",
    "brave": "Brave Browser",
    "vivaldi": "Vivaldi",
    "chromium": "Chromium",
}
_WIN_PATHS = {
    "chrome": r"Google\Chrome\Application\chrome.exe",
    "msedge": r"Microsoft\Edge\Application\msedge.exe",
    "brave": r"BraveSoftware\Brave-Browser\Application\brave.exe",
    "vivaldi": r"Vivaldi\Application\vivaldi.exe",
}


def _family(default_id: str | None) -> str | None:
    if not default_id:
        return None
    low = default_id.lower()
    for table in (_MAC_IDS, _WIN_IDS):
        for prefix, family in table.items():
            if low.startswith(prefix):
                return family
    return None


def default_browser_id() -> str | None:
    try:
        if sys.platform == "darwin":
            path = (
                Path.home()
                / "Library/Preferences/com.apple.LaunchServices"
                / "com.apple.launchservices.secure.plist"
            )
            with open(path, "rb") as f:
                data = plistlib.load(f)
            for handler in data.get("LSHandlers", []):
                if handler.get("LSHandlerURLScheme") == "https":
                    value = handler.get("LSHandlerRoleAll")
                    return value if isinstance(value, str) else None
            return None
        if sys.platform == "win32":
            import winreg

            key_path = (
                r"Software\Microsoft\Windows\Shell\Associations"
                r"\UrlAssociations\https\UserChoice"
            )
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                value, _ = winreg.QueryValueEx(key, "ProgId")
            return value
    except Exception:
        return None
    return None


def candidates(default_id: str | None, installed: dict[str, str]) -> list[LaunchSpec]:
    """Browser installati, in ordine di preferenza (prima quello predefinito)."""
    family = _family(default_id)
    order = [family] if family else []
    order += ["chrome", "msedge", *_OTHERS]
    specs: list[LaunchSpec] = []
    for fam in dict.fromkeys(order):
        if fam in installed:
            specs.append(LaunchSpec(None, installed[fam]))
    return specs


def choose(default_id: str | None, installed: dict[str, str]) -> LaunchSpec | None:
    specs = candidates(default_id, installed)
    return specs[0] if specs else None


def find_installed() -> dict[str, str]:
    found: dict[str, str] = {}
    if sys.platform == "darwin":
        roots = [Path("/Applications"), Path.home() / "Applications"]
        for family, app in _MAC_APPS.items():
            for root in roots:
                exe = root / f"{app}.app" / "Contents" / "MacOS" / app
                if exe.is_file():
                    found[family] = str(exe)
                    break
    elif sys.platform == "win32":
        roots = [
            os.environ.get(var)
            for var in ("ProgramFiles", "ProgramFiles(x86)", "LocalAppData")
        ]
        for family, rel in _WIN_PATHS.items():
            for root in filter(None, roots):
                exe = Path(root) / rel
                if exe.is_file():
                    found[family] = str(exe)
                    break
    return found


DOWNLOAD_MESSAGE = "Scarico il browser (alcune centinaia di MB, solo la prima volta)…"
INSTALL_TIMEOUT_S = 30 * 60
_LOG_LINES = 40
_FAILED = (
    "Download del browser non riuscito. Controlla la connessione a internet e riprova. "
    "I dettagli sono in {log}."
)
_NO_BROWSER = "Non riesco ad avviare nessun browser: {detail}"


def install_bundled(runtime_dir: Path, progress: Callable[[str], None]) -> None:
    """Scarica il Chromium di Playwright in PLAYWRIGHT_BROWSERS_PATH (minuti, ~600 MB)."""
    progress(DOWNLOAD_MESSAGE)
    log = Path(runtime_dir) / "last-error.log"
    try:
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
            timeout=INSTALL_TIMEOUT_S,
            check=False,
        )
        output, code = result.stdout or "", result.returncode
    except subprocess.TimeoutExpired as exc:
        out = exc.output or ""
        output = out.decode(errors="replace") if isinstance(out, bytes) else out
        output += f"\n(interrotto dopo {INSTALL_TIMEOUT_S} secondi)"
        code = None
    except OSError as exc:
        output, code = f"{type(exc).__name__}: {exc}", None
    if code == 0:
        return
    tail = "\n".join(output.splitlines()[-_LOG_LINES:])
    try:
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(f"playwright install chromium (codice {code})\n{tail}\n", encoding="utf-8")
    except OSError:
        pass
    raise BrowserUnavailableError(_FAILED.format(log=log))


def _first_line(exc: Exception) -> str:
    text = getattr(exc, "message", None) or str(exc)
    return (text.splitlines() or [type(exc).__name__])[0]


def launch(
    playwright,
    runtime_dir: Path,
    progress: Callable[[str], None],
    default_id: str | None = None,
    installed: dict[str, str] | None = None,
):
    """Avvia un Chromium headless e restituisce il Browser di Playwright.

    Prova i browser installati in ordine di preferenza; se nessuno parte usa il
    Chromium di Playwright, scaricandolo solo se non è già in
    PLAYWRIGHT_BROWSERS_PATH (o se c'è ma non parte).
    """
    from playwright.sync_api import Error as PlaywrightError

    if installed is None:
        default_id, installed = default_browser_id(), find_installed()
    chromium = playwright.chromium
    last: Exception | None = None
    for spec in candidates(default_id, installed):
        try:
            return chromium.launch(headless=True, executable_path=spec.executable_path)
        except PlaywrightError as exc:
            last = exc
    if Path(chromium.executable_path).exists():
        try:
            return chromium.launch(headless=True)
        except PlaywrightError as exc:
            last = exc
    install_bundled(runtime_dir, progress)
    try:
        return chromium.launch(headless=True)
    except PlaywrightError as exc:
        last = exc
    raise BrowserUnavailableError(_NO_BROWSER.format(detail=_first_line(last))) from last
