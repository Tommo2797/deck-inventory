import re
from pathlib import Path

from deck_inventory.errors import SettingsError

SETTINGS_FILE = "settings.txt"

BINDER_RE = r"^https://(www\.)?piltoverarchive\.com/users/[^/\s]+/collection/[0-9a-fA-F-]{36}$"
PRIVATE_RE = r"^https://(www\.)?piltoverarchive\.com/collection/[0-9a-fA-F-]{36}$"

PRIVATE_MESSAGE = (
    "Questo è un link privato. Apri il binder su Piltover Archive, clicca \"Make Public\", "
    "poi \"Share\", e incolla qui il link che ti viene copiato."
)
INVALID_MESSAGE = (
    "Link non valido. Incolla il link pubblico del tuo binder, nel formato "
    "https://piltoverarchive.com/users/NOME/collection/ID"
)

TEMPLATE = """# Deck Inventory — impostazioni
# Link del tuo binder PUBBLICO su Piltover Archive
# (sul sito: apri il binder → "Make Public" → "Share", poi incolla qui sotto)
binder = {link}
"""


def clean_link(raw: str) -> str:
    link = raw.strip()
    link = re.split(r"[?#]", link, maxsplit=1)[0].rstrip("/")
    if re.fullmatch(BINDER_RE, link):
        return link
    if re.fullmatch(PRIVATE_RE, link):
        raise SettingsError(PRIVATE_MESSAGE)
    raise SettingsError(INVALID_MESSAGE)


def read_link(project_dir: Path) -> str | None:
    path = project_dir / SETTINGS_FILE
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r"binder\s*=\s*(.*)$", line)
        if match:
            value = match.group(1).strip()
            return clean_link(value) if value else None
    return None


def write_link(project_dir: Path, link: str) -> None:
    cleaned = clean_link(link)
    (project_dir / SETTINGS_FILE).write_text(TEMPLATE.format(link=cleaned), encoding="utf-8")
