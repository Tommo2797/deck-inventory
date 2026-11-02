import pytest

from deck_inventory.decks import display_name, load_decks, parse_deck
from deck_inventory.errors import NoDecksError


def test_parse_sections_and_runes():
    deck, bad = parse_deck("Legend:\n1 Ornn, Fire Below the Mountain\n\nRunes:\n8 Calm Rune\n\nSideboard:\n3 Disarming Rake\n", "Ornn")
    assert deck.main == {"Ornn, Fire Below the Mountain": 1} and deck.side == {"Disarming Rake": 3} and bad == []


def test_crlf_bom_and_garbage():
    deck, bad = parse_deck("﻿MainDeck:\r\n3 Defy\r\n\r\nciao\r\n", "X")
    assert deck.main == {"Defy": 3} and bad == ["ciao"]


def test_line_outside_section_is_unrecognized():
    _, bad = parse_deck("3 Defy\n", "X")
    assert bad == ["3 Defy"]


def test_display_name():
    assert display_name("kai'sa.txt") == "Kai'Sa" and display_name("ornn_aggro.txt") == "Ornn Aggro"


def test_order_file(tmp_path):  # file b non in order -> in fondo + avviso; riga fantasma -> avviso
    (tmp_path / "a.txt").write_text("MainDeck:\n1 X\n")
    (tmp_path / "b.txt").write_text("MainDeck:\n1 Y\n")
    (tmp_path / "order.txt").write_text("A\nFantasma\n")
    decks, warns = load_decks(tmp_path)
    assert [d.name for d in decks] == ["A", "B"] and len(warns) == 2
    assert "B" in (tmp_path / "order.txt").read_text()


def test_order_file_created(tmp_path):
    (tmp_path / "z.txt").write_text("MainDeck:\n1 X\n")
    (tmp_path / "a.txt").write_text("MainDeck:\n1 Y\n")
    decks, _ = load_decks(tmp_path)
    assert [d.name for d in decks] == ["A", "Z"]
    assert (tmp_path / "order.txt").read_text().startswith("#")


def test_no_decks(tmp_path):
    with pytest.raises(NoDecksError):
        load_decks(tmp_path)


def test_missing_decks_folder_is_created(tmp_path):
    decks_dir = tmp_path / "decks"
    with pytest.raises(NoDecksError, match="Ho creato la cartella"):
        load_decks(decks_dir)
    assert decks_dir.is_dir()
    assert (decks_dir / "order.txt").read_text(encoding="utf-8").startswith("#")


def test_same_deck_name_warns_and_keeps_later(tmp_path):
    (tmp_path / "ornn aggro.txt").write_text("MainDeck:\n1 X\n")
    (tmp_path / "ornn_aggro.txt").write_text("MainDeck:\n2 Y\n")
    decks, warns = load_decks(tmp_path)
    assert len(decks) == 1 and decks[0].main == {"Y": 2}
    assert warns == [
        "I file «ornn aggro.txt» e «ornn_aggro.txt» hanno lo stesso nome di mazzo: uso solo «ornn_aggro.txt»"
    ]


def test_comments_only_order_file_is_filled(tmp_path):
    (tmp_path / "z.txt").write_text("MainDeck:\n1 X\n")
    (tmp_path / "a.txt").write_text("MainDeck:\n1 Y\n")
    (tmp_path / "order.txt").write_text("# solo commenti\n\n# altro")
    decks, warns = load_decks(tmp_path)
    assert [d.name for d in decks] == ["A", "Z"] and warns == []
    assert (tmp_path / "order.txt").read_text() == "# solo commenti\n\n# altro\nA\nZ\n"
