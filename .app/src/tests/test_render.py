from datetime import datetime

from deck_inventory.inventory import Deck, compute
from deck_inventory.render import page_filename, render_page

GOOD = "https://piltoverarchive.com/users/esempio/collection/00000000-0000-4000-8000-000000000000"
NOW = datetime(2026, 10, 31, 18, 40)


def synthetic():
    names = ["Ornn Aggro", "Yasuo Move", "Lillia", "Ziggs"]
    decks = [Deck(n, {"Defy": 3}, {}) for n in names]
    return compute(decks, {"defy": 8})


def test_page_contains_expected_bits():
    total, per = synthetic()
    html = render_page(total, per, ["avviso «x»"], GOOD, NOW, "1.0.0")
    assert "12/8" in html and "Ornn Aggro" in html and "4x Defy (12/8)" in html
    assert "avviso «x»" in html and "1.0.0" in html
    assert "<script src" not in html and "<link" not in html
    assert "Servono 12 copie, ne hai 8, ne mancano 4 (1 carte diverse incomplete)." in html
    assert f'href="{GOOD}"' in html and "31/10/2026 18:40" in html
    assert "prefers-color-scheme: dark" in html


def test_sections_in_spec_order():
    total, per = synthetic()
    html = render_page(total, per, ["avviso"], GOOD, NOW, "1.0.0")
    positions = [html.index(s) for s in (
        "avviso", "Tutti i mazzi insieme", "Solo le carte mancanti", "Split per mazzo",
        "Ornn Aggro", "Yasuo Move", "Lillia", "Ziggs")]
    assert positions == sorted(positions)


def test_no_warnings_box_when_empty():
    total, per = synthetic()
    assert 'class="warnings"' not in render_page(total, per, [], GOOD, NOW, "1.0.0")


def test_complete_card_shows_check():
    total, per = compute([Deck("A", {"Defy": 2}, {})], {"defy": 5})
    html = render_page(total, per, [], GOOD, NOW, "1.0.0")
    assert "✓" in html and "2/5" in html


def test_escaping():
    total, per = compute([Deck("<b>", {"<b>": 1}, {})], {})
    html = render_page(total, per, ["<b>"], GOOD, NOW, "1.0.0")
    assert "<b>" not in html and "&lt;b&gt;" in html


def test_filename():
    assert page_filename(datetime(2026, 10, 31, 18, 40)) == "Inventory 2026-10-31 18.40.html"
