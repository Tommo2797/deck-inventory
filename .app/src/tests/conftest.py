import csv
import os
from pathlib import Path

import pytest

from deck_inventory.names import normalize

FIXTURES = Path(__file__).parent / "fixtures"
# Dati reali dell'autore: solo in locale, ignorati da git (vedi .gitignore).
PRIVATE = Path(__file__).parent / "private"
# Link d'esempio (formato valido, binder inesistente).
DUMMY_BINDER = "https://piltoverarchive.com/users/esempio/collection/00000000-0000-4000-8000-000000000000"


def private_path(name: str) -> Path:
    """Percorso di un file in tests/private; salta il test se manca."""
    path = PRIVATE / name
    if not path.exists():
        pytest.skip(f"dati privati assenti: tests/private/{name}")
    return path


def online_binder() -> str:
    """Link di un binder pubblico reale per i test online (variabile d'ambiente)."""
    link = os.environ.get("DECK_INVENTORY_TEST_BINDER", "").strip()
    if not link:
        pytest.skip("DECK_INVENTORY_TEST_BINDER non impostata")
    return link


def owned_from_csv(path) -> dict[str, int]:
    owned: dict[str, int] = {}
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            key = normalize(row["Card Name"])
            owned[key] = owned.get(key, 0) + int(row["Quantity"])
    return owned
