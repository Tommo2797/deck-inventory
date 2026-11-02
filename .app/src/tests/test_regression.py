import shutil

from conftest import FIXTURES, PRIVATE, owned_from_csv, private_path
from deck_inventory.decks import load_decks
from deck_inventory.inventory import compute


# Dati d'esempio (tests/fixtures). Numeri calcolati a mano, rune escluse.
# Collezione (CSV): Arc Bolt 4 (3+1 foil), Tidecaller's Charm 2, Sparks 1,
# Stone Sentry 2, Ember Fox 2 (due varianti), Iron Ballista 3, Ashen Warden 1,
# Silent Harbor 1, Blaze Captain 1; Mist Walker e Old Lighthouse 0.
# Ordine (order.txt): Control, Aggro, Tempo.
#
# Control (need 13): Ashen 1/1, Sparks 1/1, Arc Bolt 3/3 (resta 1),
#   Tidecaller's 3 -> 2 (manca 1), Stone 2/2, Harbor 1/1, Mist (side) 2 -> 0 (mancano 2)
#   => have 10, missing 3, incomplete 2
# Aggro (need 14): Blaze 1/1, Ember 4 (1 champion + 3) -> 2 (mancano 2),
#   Arc Bolt 4 (3 main + 1 side) -> 1 (mancano 3), Iron 3/3, Harbor 1 -> 0,
#   Stone (side) 1 -> 0  => have 7, missing 7, incomplete 4
# Tempo (need 13): tutto già usato -> have 0, missing 13
#   (Ashen 1, Mist 1, Tidecaller's 3, Iron 3, Sparks 2, Lighthouse 1, Arc Bolt 2)
#
# Totale, per carta need/have: Ashen 2/1, Sparks 3/1, Arc Bolt 9/4, Tidecaller's 6/2,
#   Stone 3/2, Harbor 2/1, Mist 3/0, Blaze 1/1, Ember 4/2, Iron 6/3, Lighthouse 1/0
#   => 11 righe, need 40, have 17, missing 23, incomplete 10 (tutte tranne Blaze)
def test_dummy_data(tmp_path):
    work = tmp_path / "decks"
    shutil.copytree(FIXTURES / "decks", work)
    decks, warns = load_decks(work)
    total, per = compute(decks, owned_from_csv(FIXTURES / "collection_dummy.csv"))
    assert warns == [] and len(total.rows) == 11
    assert (total.need, total.have, total.missing, total.incomplete) == (40, 17, 23, 10)
    assert [(s.title, s.need, s.have, s.missing, s.incomplete) for s in per] == [
        ("Control", 13, 10, 3, 2), ("Aggro", 14, 7, 7, 4), ("Tempo", 13, 0, 13, 7)]
    arc = next(r for r in total.rows if r.name == "Arc Bolt")
    assert (arc.need, arc.have, arc.missing, arc.main, arc.side, arc.n_decks) == (9, 4, 5, 6, 3, 3)
    ember = next(r for r in total.rows if r.name == "Ember Fox")
    assert (ember.need, ember.have, ember.main) == (4, 2, 4)
    assert not any(r.name.endswith("Rune") for r in total.rows)


# numeri validati dall'utente il 2026-10-31 (dati reali, solo in locale: tests/private)
def test_real_data(tmp_path):
    collection = private_path("collection_2026-10-31.csv")
    private_path("decks/order.txt")
    work = tmp_path / "decks"
    shutil.copytree(PRIVATE / "decks", work)
    decks, warns = load_decks(work)
    total, per = compute(decks, owned_from_csv(collection))
    assert warns == [] and len(total.rows) == 124
    assert (total.need, total.have, total.missing, total.incomplete) == (378, 225, 153, 70)
    assert [(s.title, s.have, s.missing) for s in per] == [
        ("Ornn Aggro", 54, 0), ("Yasuo Move", 37, 17), ("Lillia", 44, 10), ("Kai'Sa", 48, 6),
        ("Yasuo Untap", 23, 31), ("Ziggs", 4, 50), ("Ornn", 15, 39)]
    defy = next(r for r in total.rows if r.name == "Defy")
    assert (defy.need, defy.have) == (15, 8)
