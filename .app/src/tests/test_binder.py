import json
from pathlib import Path

import pytest

from deck_inventory import VERSION, browsers
from deck_inventory import binder
from deck_inventory.binder import _flight_text, fetch_collection, parse_payloads
from deck_inventory.errors import (
    BinderPrivateError,
    EmptyBinderError,
    SiteChangedError,
)
from conftest import FIXTURES, owned_from_csv, online_binder, private_path
from make_dummy_binder import build as build_dummy_pages

MISSING = "https://piltoverarchive.com/users/esempio/collection/00000000-1111-4222-8333-444444444444"


def load_json(path: Path) -> list[str]:
    return json.loads(path.read_text(encoding="utf-8"))


def dummy_payloads() -> list[str]:
    # Pagine HTML d'esempio -> testo RSC, come fa fetch_payloads.
    pages = load_json(FIXTURES / "binder_pages_dummy.json")
    return [_flight_text(html) for html in pages]


def test_dummy_fixture_is_up_to_date():
    # Se fallisce: python tests/make_dummy_binder.py
    assert load_json(FIXTURES / "binder_pages_dummy.json") == build_dummy_pages()


def test_dummy_pages_are_rsc_pushes():
    # I dati stanno solo dentro stringhe JSON escapate, spezzate in più push.
    for html in load_json(FIXTURES / "binder_pages_dummy.json"):
        assert '"initialOwnership":' not in html
        assert '\\"initialOwnership\\":' in html
        assert html.count("self.__next_f.push([1,") > 1


def test_dummy_fixture_matches_csv():
    owned = parse_payloads(dummy_payloads())
    assert owned == owned_from_csv(FIXTURES / "collection_dummy.csv")
    # 11 nomi, 26 copie; Arc Bolt = 3 normali + 1 foil; Ember Fox = 2 varianti padre;
    # apostrofo tipografico nel payload normalizzato come nel CSV.
    assert len(owned) == 11
    assert sum(owned.values()) == 26
    assert owned["arc bolt"] == 4
    assert owned["ember fox"] == 2
    assert owned["tidecaller's charm"] == 2
    assert owned["sparks, the lantern"] == 1


def test_dummy_missing_page_is_site_changed():
    with pytest.raises(SiteChangedError):
        parse_payloads(dummy_payloads()[:-1])


def test_fixture_matches_csv_same_day():
    # Dati reali (solo in locale, tests/private).
    owned = parse_payloads(load_json(private_path("binder_payloads_2026-10-31.json")))
    csv_owned = owned_from_csv(private_path("collection_2026-10-31.csv"))
    assert owned == csv_owned  # 248 nomi, 541 copie; Defy == 8
    assert len(owned) == 248
    assert sum(owned.values()) == 541
    assert owned["defy"] == 8


def test_garbage_is_site_changed():
    with pytest.raises(SiteChangedError):
        parse_payloads(["<html>nope</html>"])


def test_site_changed_message_has_version():
    with pytest.raises(SiteChangedError) as exc:
        parse_payloads(["<html>nope</html>"])
    assert VERSION in exc.value.message


def test_empty_is_site_changed():
    with pytest.raises(SiteChangedError):
        parse_payloads([])


def test_missing_page_is_site_changed():
    # Senza l'ultima pagina alcune varianti possedute non hanno nome (dati reali).
    with pytest.raises(SiteChangedError):
        parse_payloads(load_json(private_path("binder_payloads_2026-10-31.json"))[:-1])


def test_empty_binder():
    # Pagina valida (struttura riconosciuta) ma nessuna carta posseduta.
    payload = (
        '{"initialOwnership":{},"pagination":{"total":0,"page":1,"limit":100,'
        '"totalPages":0,"hasNext":false,"hasPrevious":false}}'
    )
    with pytest.raises(EmptyBinderError):
        parse_payloads([payload])


def test_all_zero_quantities_is_empty_binder():
    payload = (
        '{"data":[{"id":"5124c1a4-1e3c-4781-b698-c55ac26b7c0a","variantNumber":"OGN-013",'
        '"childVariants":[],"card":{"name":"Pouty Poro"}}],'
        '"initialOwnership":{"5124c1a4-1e3c-4781-b698-c55ac26b7c0a":0}}'
    )
    with pytest.raises(EmptyBinderError):
        parse_payloads([payload])


# --- binder inesistente ------------------------------------------------------

_MISSING_HTML = "<html><head><title>User Not Found | Piltover Archive</title></head></html>"


def test_not_found_title_in_html_is_private_without_waiting():
    def never(ms):
        raise AssertionError("niente attesa: il <title> basta")
    with pytest.raises(BinderPrivateError):
        binder._raise_not_found(_MISSING_HTML, never, 90_000)


@pytest.mark.parametrize("visible, error", [(True, BinderPrivateError), (False, SiteChangedError)])
def test_not_found_waits_for_heading(visible, error):
    waits = []
    with pytest.raises(error):
        binder._raise_not_found("<html><title>Altro</title></html>",
                                lambda ms: waits.append(ms) or visible, 90_000)
    assert waits == [binder._NOT_FOUND_WAIT_MS]


def test_not_found_wait_bounded_by_deadline():
    waits = []
    with pytest.raises(SiteChangedError):
        binder._raise_not_found("", lambda ms: waits.append(ms) or False, 1200)
    with pytest.raises(SiteChangedError):
        binder._raise_not_found("", lambda ms: waits.append(ms) or False, -5)
    assert waits == [1200, 1]


class _FakeLocator:
    def __init__(self, exc=None):
        self.exc, self.calls = exc, []

    @property
    def first(self):
        return self

    def wait_for(self, **kw):
        self.calls.append(kw)
        if self.exc:
            raise self.exc


class _FakePage:
    def __init__(self, locator):
        self.locator = locator

    def get_by_role(self, role, name):
        assert (role, name) == ("heading", "User Not Found")
        return self.locator


def test_heading_visible_waits_and_maps_timeout():
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

    loc = _FakeLocator()
    assert binder._heading_visible(_FakePage(loc), 5000) is True
    assert loc.calls == [{"state": "visible", "timeout": 5000}]
    # Il timeout dell'attesa non diventa un errore di rete (è un sottotipo di Error).
    assert binder._heading_visible(_FakePage(_FakeLocator(PlaywrightTimeoutError("t"))), 5000) is False
    with pytest.raises(PlaywrightError):
        binder._heading_visible(_FakePage(_FakeLocator(PlaywrightError("chiuso"))), 5000)


def _launch():
    if browsers.choose(browsers.default_browser_id(), browsers.find_installed()) is None:
        pytest.skip("nessun browser Chromium installato")
    return lambda p: browsers.launch(p, Path("unused"), print)


@pytest.mark.online
def test_online_good_link():
    owned = fetch_collection(online_binder(), _launch())
    assert sum(owned.values()) > 0


@pytest.mark.online
def test_online_missing_binder_is_private():
    with pytest.raises(BinderPrivateError):
        fetch_collection(MISSING, _launch())
