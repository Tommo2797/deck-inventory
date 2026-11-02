from deck_inventory.inventory import Deck, compute


def test_allocation_in_deck_order():
    decks = [Deck("A", {"Defy": 3}, {}), Deck("B", {"Defy": 3}, {}), Deck("C", {"Defy": 3}, {})]
    total, per = compute(decks, {"defy": 7})
    assert [(r.need, r.have) for s in per for r in s.rows] == [(3, 3), (3, 3), (3, 1)]
    assert total.rows[0].need == 9 and total.rows[0].have == 7 and total.rows[0].missing == 2


def test_main_and_side_both_count():
    total, _ = compute([Deck("A", {"Star-Crossed": 1}, {"Star-Crossed": 1})], {})
    r = total.rows[0]
    assert (r.need, r.main, r.side, r.missing) == (2, 1, 1, 2)


def test_have_can_exceed_need_in_total():
    total, per = compute([Deck("A", {"Cloth Armor": 1}, {})], {"cloth armor": 2})
    assert (total.rows[0].need, total.rows[0].have, total.rows[0].missing) == (1, 2, 0)
    assert per[0].rows[0].have == 1


def test_sort_need_desc_then_name():
    total, _ = compute([Deck("A", {"b": 1, "a": 1, "c": 3}, {})], {})
    assert [r.name for r in total.rows] == ["c", "a", "b"]


def test_section_summary():
    total, _ = compute([Deck("A", {"x": 3, "y": 2}, {})], {"x": 3, "y": 1})
    assert (total.need, total.have, total.missing, total.incomplete) == (5, 4, 1, 1)


def test_spellings_merge_by_normalized_name_first_seen_wins():
    decks = [Deck("A", {"Can’t Stop": 1}, {}), Deck("B", {"can't  stop": 2}, {})]
    total, _ = compute(decks, {})
    assert len(total.rows) == 1
    assert total.rows[0].name == "Can’t Stop" and total.rows[0].need == 3
    assert total.rows[0].n_decks == 2
