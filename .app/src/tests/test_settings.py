import pytest

from deck_inventory.errors import SettingsError
from deck_inventory.settings import clean_link, read_link, write_link

GOOD = "https://piltoverarchive.com/users/esempio/collection/00000000-0000-4000-8000-000000000000"


def test_clean_variants():
    for raw in [GOOD, GOOD + "/", f"  {GOOD}?tab=x ", GOOD + "#top"]:
        assert clean_link(raw) == GOOD


def test_private_format_explained():
    with pytest.raises(SettingsError, match="Share"):
        clean_link("https://piltoverarchive.com/collection/00000000-0000-4000-8000-000000000000")


def test_other_site():
    with pytest.raises(SettingsError):
        clean_link("https://example.com/x")


def test_roundtrip(tmp_path):
    assert read_link(tmp_path) is None
    write_link(tmp_path, GOOD)
    assert read_link(tmp_path) == GOOD


def test_hand_edited(tmp_path):
    (tmp_path / "settings.txt").write_text("# x\nbinder=" + GOOD + "\n", encoding="utf-8")
    assert read_link(tmp_path) == GOOD


def test_empty_key_is_none(tmp_path):
    (tmp_path / "settings.txt").write_text("binder = \n", encoding="utf-8")
    assert read_link(tmp_path) is None
