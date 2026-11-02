from dataclasses import dataclass, field

from .names import normalize


@dataclass
class Deck:
    name: str
    main: dict[str, int]
    side: dict[str, int]


@dataclass
class Row:
    name: str
    need: int
    have: int
    missing: int
    main: int
    side: int
    n_decks: int | None = None


@dataclass
class Section:
    title: str
    rows: list[Row] = field(default_factory=list)
    need: int = 0
    have: int = 0
    missing: int = 0
    incomplete: int = 0


def _section(title: str, rows: list[Row]) -> Section:
    rows.sort(key=lambda r: (-r.need, r.name.lower()))
    return Section(
        title=title,
        rows=rows,
        need=sum(r.need for r in rows),
        have=sum(min(r.have, r.need) for r in rows),
        missing=sum(r.missing for r in rows),
        incomplete=sum(1 for r in rows if r.missing > 0),
    )


def _counts(deck: Deck) -> dict[str, list]:
    """Per nome normalizzato: [nome visualizzato, main, side]."""
    out: dict[str, list] = {}
    for part, cards in ((1, deck.main), (2, deck.side)):
        for name, qty in cards.items():
            entry = out.setdefault(normalize(name), [name, 0, 0])
            entry[part] += qty
    return out


def compute(decks: list[Deck], owned: dict[str, int]) -> tuple[Section, list[Section]]:
    totals: dict[str, list] = {}  # key -> [name, main, side, n_decks]
    remaining = dict(owned)
    per_deck: list[Section] = []

    for deck in decks:
        rows = []
        for key, (name, main, side) in _counts(deck).items():
            need = main + side
            have = min(need, remaining.get(key, 0))
            remaining[key] = remaining.get(key, 0) - have
            rows.append(Row(name, need, have, need - have, main, side))
            t = totals.setdefault(key, [name, 0, 0, 0])
            t[1] += main
            t[2] += side
            t[3] += 1
        per_deck.append(_section(deck.name, rows))

    total_rows = []
    for key, (name, main, side, n_decks) in totals.items():
        need = main + side
        have = owned.get(key, 0)
        total_rows.append(Row(name, need, have, max(0, need - have), main, side, n_decks))
    return _section("Totale", total_rows), per_deck
