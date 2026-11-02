"""Genera tests/fixtures/binder_pages_dummy.json: un binder di ESEMPIO (dati finti).

Uso (dalla cartella .app/src):  python tests/make_dummy_binder.py

Il file contiene una lista di documenti HTML, uno per pagina del binder, nella
stessa forma delle pagine vere di Piltover Archive (vedi docstring di
deck_inventory/binder.py): lo stream RSC è spezzato in più script
`self.__next_f.push([1, "<testo>"])` con il testo come stringa JSON escapata;
concatenando i pezzi si ottiene il testo RSC con `initialOwnership` (tutto il
binder, già sommato per variante "padre"), gli oggetti variante della pagina
(con `childVariants` e `card.name`) e `pagination`.

Il contenuto corrisponde a tests/fixtures/collection_dummy.csv (stesse carte,
stesse quantità), così il test "payload == CSV" gira anche sui dati finti.
Un test verifica che il file salvato coincida con `build()`.
"""

import json
from pathlib import Path

OUT = Path(__file__).parent / "fixtures" / "binder_pages_dummy.json"
BINDER_ID = "00000000-0000-4000-8000-000000000000"
LIMIT = 6


def _uuid(n: int) -> str:
    return f"00000000-0000-4000-8000-{n:012d}"


# (numero variante, nome carta, quantità sommata sulla variante padre, figli)
# "Tidecaller’s Charm" usa l'apostrofo tipografico: il CSV usa quello dritto,
# quindi il confronto esercita anche names.normalize.
VARIANTS = [
    ("EX-002", "Tidecaller’s Charm", 2, []),
    ("EX-003", "Sparks, the Lantern", 1, []),
    ("EX-004", "Stone Sentry", 2, []),
    ("EX-005", "Ember Fox", 1, []),
    ("EX-005a", "Ember Fox", 1, []),
    ("EX-006", "Iron Ballista", 3, []),
    # pagina 2
    ("EX-001", "Arc Bolt", 4, ["Foil"]),  # 3 normali + 1 foil
    ("EX-007", "Ashen Warden", 1, []),
    ("EX-008", "Silent Harbor", 1, []),
    ("EX-009", "Blaze Captain", 1, []),
    ("EX-010", "Fury Rune", 7, []),
    ("EX-011", "Lone Wanderer", 2, []),
]
# Variante a quantità 0 senza oggetto in nessuna pagina: va ignorata.
ZERO_VARIANT = _uuid(999)


def _variant(index: int, number: str, name: str, children: list[str]) -> dict:
    vid = _uuid(index + 1)
    return {
        "id": vid,
        "variantNumber": number,
        "rarity": "Common",
        "variantType": "Standard",
        "imageUrl": f"https://cdn.example.invalid/cards/{number}.webp",
        "variantLabel": "Standard",
        "parentVariantId": None,
        "childVariants": [
            {
                "id": _uuid(100 + index * 10 + k),
                "variantNumber": f"{number}-{label}",
                "variantType": "Standard",
                "variantLabel": label,
                "parentVariantId": vid,
            }
            for k, label in enumerate(children)
        ],
        "set": {"id": _uuid(500), "name": "Example Set", "prefix": "EX"},
        "card": {"id": _uuid(600 + index), "name": name, "tags": [], "colors": []},
    }


def _flight(page: int, total_pages: int, ownership: dict, variants: list[dict]) -> str:
    props = {
        "userId": "user_example",
        "binderId": BINDER_ID,
        "initialData": "$b:props:initialData",
        "initialOwnership": ownership,
    }
    data = {
        "data": variants,
        "pagination": {
            "total": len(VARIANTS),
            "page": page,
            "limit": LIMIT,
            "totalPages": total_pages,
            "hasNext": page < total_pages,
            "hasPrevious": page > 1,
        },
    }
    lines = [
        '1:"$Sreact.fragment"',
        '2:I[339756,["/_next/static/chunks/example.js"],"default"]',
        'a:["$","div",null,{"className":"px-4 pb-8 pt-3","children":[["$","$L2",null,'
        + json.dumps(props, ensure_ascii=False, separators=(",", ":"))
        + "]]}]",
        "b:" + json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        '0:{"P":null,"b":"example","p":"","c":["","users","esempio","collection"]}',
    ]
    return "\n".join(lines) + "\n"


def _html(flight: str) -> str:
    # Pezzi da 700 caratteri: i tagli cadono anche dentro le stringhe JSON,
    # come succede nelle pagine vere.
    chunks = [flight[i : i + 700] for i in range(0, len(flight), 700)]
    scripts = ["<script>(self.__next_f=self.__next_f||[]).push([0])</script>"]
    scripts += [f"<script>self.__next_f.push([1,{json.dumps(c)}])</script>" for c in chunks]
    return (
        '<!DOCTYPE html><html lang="en"><head><title>Collection</title></head>'
        '<body><div id="grid"></div>' + "".join(scripts) + "</body></html>"
    )


def build() -> list[str]:
    ownership = {_uuid(i + 1): qty for i, (_, _, qty, _) in enumerate(VARIANTS)}
    ownership[ZERO_VARIANT] = 0
    objects = [_variant(i, num, name, ch) for i, (num, name, _, ch) in enumerate(VARIANTS)]
    pages = [objects[i : i + LIMIT] for i in range(0, len(objects), LIMIT)]
    return [_html(_flight(n, len(pages), ownership, p)) for n, p in enumerate(pages, start=1)]


def main() -> None:
    OUT.write_text(json.dumps(build(), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"scritto {OUT}")


if __name__ == "__main__":
    main()
