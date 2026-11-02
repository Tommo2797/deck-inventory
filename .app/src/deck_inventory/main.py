"""Flusso principale: link → mazzi → browser → collezione → pagina."""

import traceback
import webbrowser
from datetime import datetime
from pathlib import Path

from deck_inventory import VERSION, binder, browsers
from deck_inventory.decks import load_decks
from deck_inventory.errors import SettingsError, UserFacingError
from deck_inventory.inventory import compute
from deck_inventory.render import page_filename, render_page
from deck_inventory.settings import clean_link, read_link, write_link

READING = "Leggo la collezione da Piltover Archive…"
UNEXPECTED_MESSAGE = (
    "Si è verificato un errore imprevisto (Deck Inventory {version}). "
    "I dettagli sono stati salvati in {log}. La pagina precedente non è stata toccata."
)


def _get_link(project_dir: Path, ui) -> str | None:
    """Link dal file impostazioni; se manca o non è valido lo chiede finché valido o annullato."""
    error: str | None = None
    try:
        link = read_link(project_dir)
    except SettingsError as e:
        link, error = None, e.message
    if link is not None:
        return link
    while link is None:
        typed = ui.ask_link(error=error)
        if typed is None:
            return None
        try:
            link = clean_link(typed)
        except SettingsError as e:
            error = e.message
    write_link(project_dir, link)
    return link


def _generate(project_dir: Path, ui, link: str) -> Path:
    runtime_dir = project_dir / ".app" / "runtime"
    with ui.Progress() as progress:
        progress.set("Leggo i mazzi…")
        decks, warnings = load_decks(project_dir / "decks")
        progress.set(READING)

        def launcher(playwright):
            browser = browsers.launch(playwright, runtime_dir, progress.set)
            progress.set(READING)  # dopo un eventuale download del browser
            return browser

        # Lavoro lungo (rete, eventuale download): in un thread, la finestra resta viva.
        owned = progress.run(binder.fetch_collection, link, launcher)
        progress.set("Creo la pagina…")
        total, per_deck = compute(decks, owned)
        now = datetime.now()
        html = render_page(total, per_deck, warnings, link, now, VERSION)
        out = project_dir / page_filename(now)
        out.write_text(html, encoding="utf-8")
        for old in project_dir.glob("Inventory *.html"):
            if old != out:
                old.unlink()
    return out


def run(project_dir: Path, ui) -> Path | None:
    project_dir = Path(project_dir)
    try:
        link = _get_link(project_dir, ui)
        if link is None:
            return None
        out = _generate(project_dir, ui, link)
        webbrowser.open(out.as_uri())
        return out
    except UserFacingError as e:
        ui.error(e.message)
    except Exception:
        log = project_dir / ".app" / "runtime" / "last-error.log"
        try:
            log.parent.mkdir(parents=True, exist_ok=True)
            log.write_text(f"Deck Inventory {VERSION}\n{traceback.format_exc()}", encoding="utf-8")
        except OSError:
            pass
        ui.error(UNEXPECTED_MESSAGE.format(version=VERSION, log=log))
    return None
