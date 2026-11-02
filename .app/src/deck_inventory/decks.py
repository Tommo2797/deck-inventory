import re
from pathlib import Path

from .errors import NoDecksError
from .inventory import Deck
from .names import is_rune, normalize

_SECTIONS = {"legend", "champion", "maindeck", "battlefields", "runes", "sideboard"}
_CARD = re.compile(r"^\s*(\d+)\s+(.+?)\s*$")
_ORDER_HEADER = (
    "# Ordine dei mazzi: un mazzo per riga.\n"
    "# Il mazzo in alto ha la priorità più alta.\n"
    "# I nomi sono i nomi dei file senza .txt (maiuscole e apostrofi non contano).\n"
    "# Le righe vuote e quelle che iniziano con # vengono ignorate.\n"
)


def parse_deck(text: str, name: str) -> tuple[Deck, list[str]]:
    main: dict[str, int] = {}
    side: dict[str, int] = {}
    bad: list[str] = []
    section: str | None = None
    for raw in text.lstrip("﻿").splitlines():
        line = raw.strip()
        if not line:
            continue
        head = line.rstrip(":").strip().lower()
        if head in _SECTIONS:
            section = head
            continue
        m = _CARD.match(line)
        if not m or section is None:
            bad.append(line)
            continue
        card, qty = m.group(2), int(m.group(1))
        if section == "runes" or is_rune(card):
            continue
        target = side if section == "sideboard" else main
        target[card] = target.get(card, 0) + qty
    return Deck(name, main, side), bad


def display_name(filename: str) -> str:
    stem = filename[:-4] if filename.lower().endswith(".txt") else filename
    words = stem.replace("_", " ").split()
    return " ".join(re.sub(r"(^|['’])(\w)", lambda m: m.group(1) + m.group(2).upper(), w.lower()) for w in words)


def _order_lines(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    return [ln.strip() for ln in lines if ln.strip() and not ln.strip().startswith("#")]


def load_decks(decks_dir: Path) -> tuple[list[Deck], list[str]]:
    decks_dir = Path(decks_dir)
    if not decks_dir.is_dir():
        # Primo avvio senza cartella: la creo con un order.txt commentato.
        decks_dir.mkdir(parents=True)
        (decks_dir / "order.txt").write_text(_ORDER_HEADER, encoding="utf-8")
        raise NoDecksError(
            "Ho creato la cartella «decks» dentro la cartella di Deck Inventory: "
            "mettici i file .txt dei tuoi mazzi e fai di nuovo doppio clic su Start."
        )
    files = sorted(
        (p for p in decks_dir.glob("*.txt") if p.name.lower() != "order.txt"),
        key=lambda p: (display_name(p.name).lower(), p.name),
    )
    if not files:
        raise NoDecksError("Nessun mazzo trovato: metti i file .txt dei mazzi nella cartella dei mazzi.")

    by_key: dict[str, Deck] = {}
    names: dict[str, str] = {}
    sources: dict[str, str] = {}
    warnings: list[str] = []
    for p in files:
        name = display_name(p.name)
        key = normalize(name)
        deck, bad = parse_deck(p.read_text(encoding="utf-8-sig"), name)
        if key in sources:
            warnings.append(
                f"I file «{sources[key]}» e «{p.name}» hanno lo stesso nome di mazzo: uso solo «{p.name}»"
            )
        by_key[key] = deck
        names[key] = name
        sources[key] = p.name
        for line in bad:
            warnings.append(f"Mazzo «{name}»: riga non riconosciuta: «{line}»")

    order_path = decks_dir / "order.txt"
    order_lines = _order_lines(order_path) if order_path.exists() else []
    if not order_lines:
        # File mancante o solo commenti/righe vuote: lo riempio in ordine alfabetico.
        text = order_path.read_text(encoding="utf-8-sig") if order_path.exists() else _ORDER_HEADER
        if text and not text.endswith("\n"):
            text += "\n"
        order_path.write_text(text + "".join(names[k] + "\n" for k in by_key), encoding="utf-8")
        return list(by_key.values()), warnings

    ordered: list[Deck] = []
    seen: set[str] = set()
    for line in order_lines:
        key = normalize(line)
        if key in by_key and key not in seen:
            ordered.append(by_key[key])
            seen.add(key)
        elif key not in by_key:
            warnings.append(f"«{line}» in order.txt non corrisponde a nessun file")
    missing = [k for k in by_key if k not in seen]
    if missing:
        text = order_path.read_text(encoding="utf-8-sig")
        if text and not text.endswith("\n"):
            text += "\n"
        for k in missing:
            ordered.append(by_key[k])
            warnings.append(f"Mazzo «{names[k]}» non era in order.txt: aggiunto in fondo")
            text += names[k] + "\n"
        order_path.write_text(text, encoding="utf-8")
    return ordered, warnings
