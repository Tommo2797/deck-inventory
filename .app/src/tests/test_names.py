from deck_inventory.names import is_rune, normalize


def test_normalize():
    assert normalize("An Offer You Can’t Refuse") == normalize("an offer you can't  refuse ")


def test_is_rune():
    assert is_rune("Calm Rune") and is_rune("Fury Rune")
    assert not is_rune("Runeblade Anvil")
