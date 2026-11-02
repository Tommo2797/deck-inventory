"""Lettura di un binder pubblico di Piltover Archive con un browser invisibile.

Come carica i dati la pagina (verificato il 2026-10-31, da sloggati)
-------------------------------------------------------------------
- La pagina `https://piltoverarchive.com/users/<utente>/collection/<binderId>`
  è renderizzata lato server (Next.js App Router). Le carte NON arrivano da
  una POST "server action": l'unica POST alla URL del binder è
  `getUserPricingPrefs` (valuta/provider prezzi) e non contiene carte.
- I dati stanno nell'HTML del documento, nello stream RSC
  ("flight data") scritto da script `self.__next_f.push([1, "<testo>"])`.
  Concatenando i `<testo>` (stringhe JSON) si ottiene il testo RSC, che contiene:
    * `"initialOwnership":{"<parentVariantId>": <quantità>, ...}` — TUTTO il
      binder in una mappa, già sommata per variante "padre" (es. Defy
      7 normali + 1 foil = 8 sulla variante OGN-045; Pouty Poro promo Nexus
      conta sulla variante padre OGN-013). Non dipende dalla pagina.
    * gli oggetti variante della pagina corrente, nella forma
      `{"id":"<parentVariantId>","variantNumber":"OGN-045",...,
        "childVariants":[{"id":...,"variantNumber":"OGN-045-Foil",...}],
        "set":{...},"card":{"id":...,"name":"Defy",...}}`
    * `"pagination":{"total":250,"page":1,"limit":100,"totalPages":3,...}`.
- La griglia mostra di default tutto il catalogo (1.434 varianti, anche
  quelle con quantità 0) paginato a 48 per pagina con `?page=N` (link
  "Next" → `?page=2`). I parametri della URL diventano filtri della ricerca:
  `qtyMin=1` = solo carte possedute ("Owned only"), `limit` è limitato a 100
  dal server, `page` = pagina.
- Per avere i nomi di tutte le varianti possedute si caricano quindi le pagine
  `<link>?qtyMin=1&limit=100&page=N` per N = 1..totalPages (3 pagine per il
  binder di prova da 250 varianti / 541 copie) e si prende il testo RSC di
  ciascun documento. Non si usa il DOM (la griglia è virtualizzata).
- La pagina, lato client, chiama anche l'API pubblica
  `/api/external/v1/collection/users/<userId>/search?...&collectionId=<binderId>`
  (JSON senza quantità). Non la usiamo: tutto ciò che serve è nell'HTML.
- Binder/utente inesistente: risposta 200, senza `initialOwnership`, con
  `<title>User Not Found | Piltover Archive</title>` nell'HTML del server
  (verificato il 2026-11-02) e il titolo visibile "User Not Found". L'h1
  "User Not Found" compare anche nello stream RSC delle pagine buone, quindi non
  si cerca quel testo nello stream: prima il <title> dell'HTML, poi (se manca)
  si aspetta qualche secondo il titolo renderizzato.

Payload = testo RSC (già decodificato) di una pagina del binder.
`parse_payloads` unisce `initialOwnership` con i nomi delle varianti trovate
in tutti i payload; se una variante posseduta non ha nome, il caricamento è
incompleto e solleva `SiteChangedError`. Binder valido ma senza carte
possedute (`initialOwnership` vuota o tutta a 0) → `EmptyBinderError`.

Se il sito cambia: aprire il link in un browser, cercare nell'HTML
"initialOwnership" e "pagination", e aggiornare `_OWNERSHIP_KEY`,
`_VARIANT_START`, `_page_url` di conseguenza.
"""

import json
import re
import time
from typing import Callable
from urllib.parse import urlsplit, urlunsplit

from deck_inventory import VERSION
from deck_inventory.errors import (
    BinderNetworkError,
    BinderPrivateError,
    EmptyBinderError,
    SiteChangedError,
)
from deck_inventory.names import normalize

_PUSH = re.compile(r'self\.__next_f\.push\(\[1,("(?:[^"\\]|\\.)*")\]\)')
_OWNERSHIP_KEY = '"initialOwnership":'
_PAGINATION_KEY = '"pagination":'
_VARIANT_START = re.compile(r'\{"id":"[0-9a-f-]{36}","variantNumber":')
_NOT_FOUND_TEXT = "User Not Found"
_NOT_FOUND_TITLE = re.compile(r"<title>\s*User Not Found\b")
_NOT_FOUND_WAIT_MS = 5000
_PAGE_SIZE = 100
_MAX_PAGES = 100

_SITE_CHANGED = (
    "Non riesco a leggere il binder: Piltover Archive è cambiato, serve una "
    f"versione aggiornata di Deck Inventory (versione attuale {VERSION})."
)
_EMPTY = (
    "Il binder è vuoto: non contiene carte. Controlla di aver condiviso il "
    "binder giusto."
)
_PRIVATE = (
    "Il binder non è pubblico o il link non è corretto. Su Piltover Archive apri "
    'il binder, usa "Make Public" e poi "Share", e copia di nuovo il link.'
)
_NETWORK = (
    "Non riesco a raggiungere Piltover Archive. Controlla la connessione a "
    "internet e riprova."
)
_decoder = json.JSONDecoder()


def parse_payloads(payloads: list[str]) -> dict[str, int]:
    ownership: dict | None = None
    names: dict[str, str] = {}
    for payload in payloads:
        if ownership is None:
            ownership = _ownership(payload)
        names.update(_variant_names(payload))
    if ownership is None:
        raise SiteChangedError(_SITE_CHANGED)
    owned: dict[str, int] = {}
    for variant_id, quantity in ownership.items():
        if not isinstance(quantity, int) or quantity <= 0:
            continue
        if variant_id not in names:
            raise SiteChangedError(_SITE_CHANGED)
        key = normalize(names[variant_id])
        owned[key] = owned.get(key, 0) + quantity
    if not owned:
        raise EmptyBinderError(_EMPTY)
    return owned


def _ownership(flight: str) -> dict | None:
    pos = flight.find(_OWNERSHIP_KEY)
    if pos < 0:
        return None
    try:
        value, _ = _decoder.raw_decode(flight, pos + len(_OWNERSHIP_KEY))
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


def _variant_names(flight: str) -> dict[str, str]:
    names: dict[str, str] = {}
    for match in _VARIANT_START.finditer(flight):
        try:
            variant, _ = _decoder.raw_decode(flight, match.start())
            name = variant["card"]["name"]
        except (ValueError, KeyError, TypeError):
            continue
        if not isinstance(name, str):
            continue
        names[variant["id"]] = name
        for child in variant.get("childVariants") or []:
            if isinstance(child, dict) and "id" in child:
                names[child["id"]] = name
    return names


def _flight_text(html: str) -> str:
    try:
        return "".join(json.loads(chunk) for chunk in _PUSH.findall(html))
    except ValueError:
        raise SiteChangedError(_SITE_CHANGED)


def _total_pages(flight: str) -> int:
    pos = flight.find(_PAGINATION_KEY)
    if pos < 0:
        raise SiteChangedError(_SITE_CHANGED)
    try:
        pagination, _ = _decoder.raw_decode(flight, pos + len(_PAGINATION_KEY))
        total = int(pagination["totalPages"])
    except (ValueError, KeyError, TypeError):
        raise SiteChangedError(_SITE_CHANGED)
    return max(1, min(total, _MAX_PAGES))


def _page_url(link: str, page: int) -> str:
    parts = urlsplit(link.strip())
    query = f"qtyMin=1&limit={_PAGE_SIZE}&page={page}"
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, ""))


def _heading_visible(page, timeout_ms: float) -> bool:
    """Aspetta (al massimo `timeout_ms`) il titolo "User Not Found" renderizzato."""
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

    heading = page.get_by_role("heading", name=_NOT_FOUND_TEXT)
    try:
        heading.first.wait_for(state="visible", timeout=timeout_ms)
    except PlaywrightTimeoutError:
        return False
    return True


def _raise_not_found(html: str, heading_visible: Callable[[float], bool], remaining_ms: float) -> None:
    """Pagina senza `initialOwnership`: binder inesistente (→ privato) o sito cambiato."""
    if _NOT_FOUND_TITLE.search(html):
        raise BinderPrivateError(_PRIVATE)
    # Playwright: timeout 0 = nessun limite, quindi almeno 1 ms.
    if heading_visible(max(1, min(_NOT_FOUND_WAIT_MS, remaining_ms))):
        raise BinderPrivateError(_PRIVATE)
    raise SiteChangedError(_SITE_CHANGED)


def fetch_payloads(link: str, launcher: Callable, timeout_s: int = 90) -> list[str]:
    """`launcher(playwright)` restituisce un Browser avviato (vedi browsers.launch).

    Il tempo massimo vale per le pagine, non per l'avvio (che può includere il
    download del browser).
    """
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright

    payloads: list[str] = []
    try:
        with sync_playwright() as p:
            browser = launcher(p)
            deadline = time.monotonic() + timeout_s
            try:
                page = browser.new_context().new_page()
                total = 1
                number = 1
                while number <= total:
                    remaining_ms = (deadline - time.monotonic()) * 1000
                    if remaining_ms <= 0:
                        raise BinderNetworkError(_NETWORK)
                    response = page.goto(
                        _page_url(link, number),
                        wait_until="domcontentloaded",
                        timeout=remaining_ms,
                    )
                    if urlsplit(page.url).path.startswith("/sign-in"):
                        raise BinderPrivateError(_PRIVATE)
                    if response is None:
                        raise SiteChangedError(_SITE_CHANGED)
                    if response.status == 404:
                        raise BinderPrivateError(_PRIVATE)
                    if response.status >= 400:
                        raise BinderNetworkError(_NETWORK)
                    html = response.text()
                    flight = _flight_text(html)
                    if _OWNERSHIP_KEY not in flight:
                        _raise_not_found(html, lambda ms: _heading_visible(page, ms),
                                         (deadline - time.monotonic()) * 1000)
                    if number == 1:
                        total = _total_pages(flight)
                    payloads.append(flight)
                    number += 1
            finally:
                browser.close()
    except PlaywrightError as exc:
        raise BinderNetworkError(_NETWORK) from exc
    return payloads


def fetch_collection(link: str, launcher: Callable) -> dict[str, int]:
    return parse_payloads(fetch_payloads(link, launcher))
