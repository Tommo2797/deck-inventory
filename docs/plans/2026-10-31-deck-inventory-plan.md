# Deck Inventory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Un tool locale, avviato con doppio clic su Mac e Windows, che legge le liste dei mazzi in `decks/` e la collezione dal binder pubblico Piltover Archive e genera una pagina HTML con il confronto Servono/Hai (totale e per mazzo, con assegnazione delle copie in ordine di priorità).

**Architecture:** Due launcher nativi (`.command`, `.bat`) scaricano uv dentro `.app/runtime/`, che a sua volta installa Python e Playwright sempre lì dentro (guard con file di stato). Il pacchetto Python `deck_inventory` in `.app/src/` fa il lavoro: parsing mazzi, lettura binder con browser invisibile, calcoli, rendering di un singolo HTML autosufficiente, dialoghi tkinter. Le funzioni pure (parsing, calcoli, rendering) sono testate con pytest su dati reali; la parte browser con una fixture catturata dal sito.

**Tech Stack:** Python 3.12 (gestito da uv 0.13.1), Playwright per Python, tkinter (incluso nel Python di uv), pytest; bash (Mac), batch + PowerShell (Windows); curl e tar (presenti di serie su macOS e Windows 10 1803+).

**Spec:** `docs/2026-10-31-deck-inventory-design.md` (stessa cartella del progetto). Gli implementatori leggono spec e piano.

**Nota successiva:** le fixture con dati reali (collezione, mazzi, cattura del binder) citate sotto non sono più nel repository: stanno in `.app/src/tests/private/` (ignorata da git) e i test relativi vengono saltati se mancano. I test pubblici usano dati d'esempio in `.app/src/tests/fixtures/` (`collection_dummy.csv`, `decks/`, `binder_pages_dummy.json` generato da `tests/make_dummy_binder.py`).

## Global Constraints

- Tutto ciò che viene installato o scaricato sta in `.app/runtime/`; nessun file fuori dalla cartella del progetto (niente `~/.cache`, `~/.local`, `%APPDATA%`). Variabili sempre impostate dai launcher: `UV_CACHE_DIR=.app/runtime/uv-cache`, `UV_PYTHON_INSTALL_DIR=.app/runtime/python`, `UV_PROJECT_ENVIRONMENT=.app/runtime/venv`, `PLAYWRIGHT_BROWSERS_PATH=.app/runtime/browsers`, `UV_PYTHON_PREFERENCE=only-managed`.
- Nessun percorso assoluto salvato nei file del progetto, tranne il file di stato del guard (che serve proprio a rilevare lo spostamento).
- Piattaforme: macOS 12+ (arm64 e x86_64), Windows 10/11 x64.
- File utente: `settings.txt`, `README.txt`, `Start (Mac).command`, `Start (Windows).bat`, `decks/`, `decks/order.txt`, `Inventory YYYY-MM-DD HH.MM.html`.
- Testo dell'interfaccia (pagina, dialoghi, README) in italiano.
- Rune escluse: nomi che finiscono con `" Rune"` (es. `Calm Rune`); `Runeblade Anvil` NON è una rune.
- Mazzo = Legend + Champion + MainDeck + Battlefields; Side = Sideboard.
- Formato cella: `Servono/Hai` → `12/8`; colonna Mancano: `**4**` evidenziato oppure `✓`.
- Versione: `VERSION = "1.0.0"` in `deck_inventory/__init__.py`, mostrata nella pagina e nei messaggi di errore.
- Se un aggiornamento fallisce, la pagina `Inventory *.html` precedente non viene toccata.
- Il terminale non è l'interfaccia: richieste e messaggi passano da finestre di dialogo.

## Review Focus

1. **Binder modificato dopo la fixture / binder di un'altra persona**: la lettura deve restituire tutte le carte possedute (non solo quelle visibili nella prima schermata della griglia virtualizzata). → Test in Task 5 che confronta il parsing della fixture con il CSV dello stesso giorno (248 nomi, 541 copie).
2. **Link incollato sbagliato** (link privato `/collection/<id>` senza `/users/`, spazi, slash finale, query `?x=`): messaggio chiaro, non crash. → Test in Task 3.
3. **File mazzo con fine riga Windows (`\r\n`), BOM UTF-8, righe vuote extra, nomi con virgole/apostrofi tipografici**: parsing identico. → Test in Task 2.
4. **Cartella spostata o copiata su un altro computer** dopo l'installazione: il guard reinstalla solo venv/ciò che non è valido, senza riscaricare il browser. → Verifica manuale in Task 7 (spostare la cartella e rilanciare, controllare che non scarichi).
5. **Percorso della cartella con spazi o caratteri accentati** (`Deck Inventory`, `Università`): launcher e Python funzionano. → Il progetto stesso ha uno spazio nel nome; Task 7 lo prova anche in una cartella con `à`.

---

## Struttura dei file

```
Deck Inventory/
├── Start (Mac).command              Task 7
├── Start (Windows).bat              Task 7
├── settings.txt                     creato da Task 3 al primo avvio (non versionato)
├── README.txt                       Task 8
├── decks/order.txt + *.txt          dati utente (non versionati)
├── docs/                            spec + piano
├── .gitignore                       Task 1
└── .app/
    ├── src/
    │   ├── pyproject.toml           Task 1
    │   ├── deck_inventory/
    │   │   ├── __init__.py          VERSION
    │   │   ├── names.py             normalizzazione nomi (Task 1)
    │   │   ├── decks.py             parsing mazzi + order.txt (Task 2)
    │   │   ├── settings.py          settings.txt + validazione link (Task 3)
    │   │   ├── binder.py            lettura binder con Playwright + parsing payload (Task 5)
    │   │   ├── browsers.py          scelta del browser (Task 4)
    │   │   ├── inventory.py         calcoli e assegnazione (Task 1)
    │   │   ├── render.py            HTML (Task 6)
    │   │   ├── dialogs.py           finestre tkinter (Task 6)
    │   │   ├── errors.py            eccezioni con messaggio per l'utente (Task 1)
    │   │   └── main.py              orchestrazione (Task 6)
    │   ├── tools/capture_binder.py  cattura fixture (Task 5)
    │   └── tests/                   pytest + fixtures
    └── runtime/                     installato (non versionato)
```

Repository git con radice in `Deck Inventory/` (preparazione all'aggiornamento via git deciso per il futuro).

---

### Task 1: Progetto, nomi, calcoli

**Files:**
- Create: `.gitignore`, `.app/src/pyproject.toml`, `.app/src/deck_inventory/__init__.py`, `names.py`, `errors.py`, `inventory.py`
- Create: `.app/src/tests/fixtures/collection_2026-10-31.csv` (copia del CSV della collezione esportato da Piltover Archive)
- Test: `.app/src/tests/test_names.py`, `.app/src/tests/test_inventory.py`

**Interfaces:**
- Produces:
  - `names.normalize(name: str) -> str` — minuscolo, `’`/`‘` → `'`, spazi multipli → uno, strip.
  - `names.is_rune(name: str) -> bool`
  - `errors.UserFacingError(Exception)` con attributo `message: str` (italiano); sottoclassi `SettingsError`, `NoDecksError`, `BinderPrivateError`, `BinderNetworkError`, `SiteChangedError`, `BrowserUnavailableError`.
  - `inventory.Deck` dataclass: `name: str`, `main: dict[str, int]`, `side: dict[str, int]` (chiavi = nome visualizzato, rune già escluse).
  - `inventory.Row` dataclass: `name, need, have, missing, main, side, n_decks: int|None`.
  - `inventory.Section` dataclass: `title: str`, `rows: list[Row]`, `need: int`, `have: int`, `missing: int`, `incomplete: int`.
  - `inventory.compute(decks: list[Deck], owned: dict[str, int]) -> tuple[Section, list[Section]]` — `owned` ha chiavi normalizzate; restituisce (totale, sezioni per mazzo nell'ordine di `decks`).

- [ ] **Step 1: Setup**
  `git init` in `Deck Inventory/`. `.gitignore`: `.app/runtime/`, `settings.txt`, `decks/`, `Inventory *.html`, `__pycache__/`, `.pytest_cache/`. `pyproject.toml`: nome `deck-inventory`, `requires-python = ">=3.12,<3.13"`, dipendenza `playwright`, gruppo dev `pytest`. Per lo sviluppo esportare le stesse variabili dei Global Constraints puntando a `.app/runtime/`.

- [ ] **Step 2: Test che falliscono**

```python
# test_names.py
def test_normalize():
    assert normalize("An Offer You Can’t Refuse") == normalize("an offer you can't  refuse ")
def test_is_rune():
    assert is_rune("Calm Rune") and is_rune("Fury Rune")
    assert not is_rune("Runeblade Anvil")

# test_inventory.py
def test_allocation_in_deck_order():
    decks = [Deck("A", {"Defy": 3}, {}), Deck("B", {"Defy": 3}, {}), Deck("C", {"Defy": 3}, {})]
    total, per = compute(decks, {"defy": 7})
    assert [(r.need, r.have) for s in per for r in s.rows] == [(3, 3), (3, 3), (3, 1)]
    assert total.rows[0].need == 9 and total.rows[0].have == 7 and total.rows[0].missing == 2
def test_main_and_side_both_count():
    total, _ = compute([Deck("A", {"Star-Crossed": 1}, {"Star-Crossed": 1})], {})
    r = total.rows[0]; assert (r.need, r.main, r.side, r.missing) == (2, 1, 1, 2)
def test_have_can_exceed_need_in_total():
    total, per = compute([Deck("A", {"Cloth Armor": 1}, {})], {"cloth armor": 2})
    assert (total.rows[0].need, total.rows[0].have, total.rows[0].missing) == (1, 2, 0)
    assert (per[0].rows[0].have) == 1
def test_sort_need_desc_then_name():
    total, _ = compute([Deck("A", {"b": 1, "a": 1, "c": 3}, {})], {})
    assert [r.name for r in total.rows] == ["c", "a", "b"]
def test_section_summary():
    total, _ = compute([Deck("A", {"x": 3, "y": 2}, {})], {"x": 3, "y": 1})
    assert (total.need, total.have, total.missing, total.incomplete) == (5, 4, 1, 1)
```

- [ ] **Step 3: Verificare che falliscano** — `uv run --project .app/src pytest .app/src/tests -q` → errori di import.

- [ ] **Step 4: Implementare** `names.py`, `errors.py`, `inventory.py` secondo le interfacce. Nella sezione totale `have` = possedute (non limitate); `Section.have` del totale = somma di `min(have, need)`; nelle sezioni per mazzo l'assegnazione consuma una copia locale di `owned`. `n_decks` valorizzato solo nel totale.

- [ ] **Step 5: Test verdi** — stesso comando → PASS.

- [ ] **Step 6: Commit** — `git commit -m "feat: core inventory computation"`

---

### Task 2: Liste dei mazzi e `order.txt`

**Files:**
- Create: `.app/src/deck_inventory/decks.py`
- Create: `.app/src/tests/fixtures/decks/` con i 7 mazzi presi dal file originale delle liste dei mazzi (separatore `___`), un file ciascuno: `ornn aggro.txt` (quello con Pit Crew), `yasuo move.txt` (Kayn), `lillia.txt`, `kai'sa.txt`, `yasuo untap.txt` (Baron Nashor), `ziggs.txt`, `ornn.txt` (Plaza Guardian), più `order.txt` con quell'ordine.
- Test: `.app/src/tests/test_decks.py`, `.app/src/tests/test_regression.py`

**Interfaces:**
- Consumes: `inventory.Deck`, `names.normalize`, `names.is_rune`.
- Produces:
  - `decks.parse_deck(text: str, name: str) -> tuple[Deck, list[str]]` — seconda voce = righe non riconosciute (testo originale).
  - `decks.display_name(filename: str) -> str` — `"kai'sa.txt"` → `"Kai'Sa"`, `"ornn_aggro.txt"` → `"Ornn Aggro"`.
  - `decks.load_decks(decks_dir: Path) -> tuple[list[Deck], list[str]]` — seconda voce = avvisi in italiano per la pagina. Legge/crea/aggiorna `order.txt`. Solleva `NoDecksError` se non c'è nessun `.txt` oltre a `order.txt`.

Regole: sezioni note `Legend, Champion, MainDeck, Battlefields, Runes, Sideboard` (match case-insensitive, `:` finale); riga carta `^\s*(\d+)\s+(.+?)\s*$`; righe vuote ignorate; leggere con `encoding="utf-8-sig"`; rune scartate. `order.txt`: una riga per mazzo, righe vuote e righe che iniziano con `#` ignorate, match con `normalize` applicato al nome visualizzato; mazzi mancanti appesi in fondo al file + avviso "Mazzo «X» non era in order.txt: aggiunto in fondo"; righe senza file → avviso "«X» in order.txt non corrisponde a nessun file"; file assente → creato in ordine alfabetico con un commento in testa che spiega l'uso.

- [ ] **Step 1: Test che falliscono**

```python
def test_parse_sections_and_runes():
    deck, bad = parse_deck("Legend:\n1 Ornn, Fire Below the Mountain\n\nRunes:\n8 Calm Rune\n\nSideboard:\n3 Disarming Rake\n", "Ornn")
    assert deck.main == {"Ornn, Fire Below the Mountain": 1} and deck.side == {"Disarming Rake": 3} and bad == []
def test_crlf_bom_and_garbage():
    deck, bad = parse_deck("﻿MainDeck:\r\n3 Defy\r\n\r\nciao\r\n", "X")
    assert deck.main == {"Defy": 3} and bad == ["ciao"]
def test_line_outside_section_is_unrecognized():
    _, bad = parse_deck("3 Defy\n", "X"); assert bad == ["3 Defy"]
def test_display_name():
    assert display_name("kai'sa.txt") == "Kai'Sa" and display_name("ornn_aggro.txt") == "Ornn Aggro"
def test_order_file(tmp_path):  # file b non in order -> in fondo + avviso; riga fantasma -> avviso
    (tmp_path/"a.txt").write_text("MainDeck:\n1 X\n"); (tmp_path/"b.txt").write_text("MainDeck:\n1 Y\n")
    (tmp_path/"order.txt").write_text("A\nFantasma\n")
    decks, warns = load_decks(tmp_path)
    assert [d.name for d in decks] == ["A", "B"] and len(warns) == 2
    assert "B" in (tmp_path/"order.txt").read_text()
def test_order_file_created(tmp_path):
    (tmp_path/"z.txt").write_text("MainDeck:\n1 X\n"); (tmp_path/"a.txt").write_text("MainDeck:\n1 Y\n")
    decks, _ = load_decks(tmp_path); assert [d.name for d in decks] == ["A", "Z"]
def test_no_decks(tmp_path):
    with pytest.raises(NoDecksError): load_decks(tmp_path)

# test_regression.py — numeri validati dall'utente il 2026-10-31
def test_real_data():
    decks, warns = load_decks(FIXTURES/"decks")
    total, per = compute(decks, owned_from_csv(FIXTURES/"collection_2026-10-31.csv"))
    assert warns == [] and len(total.rows) == 124
    assert (total.need, total.have, total.missing, total.incomplete) == (378, 225, 153, 70)
    assert [(s.title, s.have, s.missing) for s in per] == [
        ("Ornn Aggro", 54, 0), ("Yasuo Move", 37, 17), ("Lillia", 44, 10), ("Kai'Sa", 48, 6),
        ("Yasuo Untap", 23, 31), ("Ziggs", 4, 50), ("Ornn", 15, 39)]
    defy = next(r for r in total.rows if r.name == "Defy"); assert (defy.need, defy.have) == (15, 8)
```
`owned_from_csv` è un helper di test (somma `Quantity` per `normalize(Card Name)`). La regressione usa `load_decks` su una copia in `tmp_path` per non riscrivere la fixture.

- [ ] **Step 2: Verificare che falliscano**, **Step 3: implementare `decks.py`**, **Step 4: test verdi** (`uv run --project .app/src pytest .app/src/tests -q`).
- [ ] **Step 5: Commit** — `git commit -m "feat: deck lists and order.txt"`

---

### Task 3: `settings.txt` e validazione del link

**Files:**
- Create: `.app/src/deck_inventory/settings.py`
- Test: `.app/src/tests/test_settings.py`

**Interfaces:**
- Produces:
  - `settings.BINDER_RE = r"^https://(www\.)?piltoverarchive\.com/users/[^/\s]+/collection/[0-9a-fA-F-]{36}$"`
  - `settings.clean_link(raw: str) -> str` — strip, rimuove query/fragment e `/` finale; solleva `SettingsError` con messaggio esplicativo. Per un link `https://piltoverarchive.com/collection/<id>` (formato privato) il messaggio dice di usare "Make Public" → "Share".
  - `settings.read_link(project_dir: Path) -> str | None` — `None` se file assente o chiave vuota.
  - `settings.write_link(project_dir: Path, link: str) -> None`

Formato del file (creato da `write_link`, modificabile a mano):
```
# Deck Inventory — impostazioni
# Link del tuo binder PUBBLICO su Piltover Archive
# (sul sito: apri il binder → "Make Public" → "Share", poi incolla qui sotto)
binder = https://piltoverarchive.com/users/NOME/collection/ID
```
Parsing: prima riga non commento con `binder =`; spazi intorno a `=` opzionali.

- [ ] **Step 1: Test che falliscono**

```python
GOOD = "https://piltoverarchive.com/users/esempio/collection/00000000-0000-4000-8000-000000000000"
def test_clean_variants():
    for raw in [GOOD, GOOD + "/", f"  {GOOD}?tab=x ", GOOD + "#top"]:
        assert clean_link(raw) == GOOD
def test_private_format_explained():
    with pytest.raises(SettingsError, match="Share"):
        clean_link("https://piltoverarchive.com/collection/00000000-0000-4000-8000-000000000000")
def test_other_site():
    with pytest.raises(SettingsError): clean_link("https://example.com/x")
def test_roundtrip(tmp_path):
    assert read_link(tmp_path) is None
    write_link(tmp_path, GOOD); assert read_link(tmp_path) == GOOD
def test_hand_edited(tmp_path):
    (tmp_path/"settings.txt").write_text("# x\nbinder=" + GOOD + "\n"); assert read_link(tmp_path) == GOOD
```

- [ ] **Step 2–4:** fallire → implementare → verdi.
- [ ] **Step 5: Commit** — `git commit -m "feat: settings and binder link validation"`

---

### Task 4: Scelta del browser

**Files:**
- Create: `.app/src/deck_inventory/browsers.py`
- Test: `.app/src/tests/test_browsers.py`

**Interfaces:**
- Produces:
  - `browsers.LaunchSpec` dataclass: `channel: str | None`, `executable_path: str | None` (uno dei due, o entrambi `None` = Chromium scaricato da Playwright).
  - `browsers.default_browser_id() -> str | None` — Mac: bundle id per lo schema `https` da `~/Library/Preferences/com.apple.LaunchServices/com.apple.launchservices.secure.plist` (plistlib, chiave `LSHandlers`, `LSHandlerURLScheme == "https"`, `LSHandlerRoleAll`). Windows: `ProgId` da `HKCU\Software\Microsoft\Windows\Shell\Associations\UrlAssociations\https\UserChoice` (winreg). `None` se non determinabile.
  - `browsers.choose(default_id: str | None, installed: dict[str, str]) -> LaunchSpec | None` — pura, testabile. `installed` = mappa famiglia → percorso eseguibile trovato (`chrome`, `msedge`, `brave`, `vivaldi`, `opera`, `chromium`). Ordine: famiglia del predefinito se Chromium-based → `chrome` → `msedge` → altri trovati → `None`.
  - `browsers.find_installed() -> dict[str, str]` — percorsi standard: Mac `/Applications/<App>.app/Contents/MacOS/<bin>` e la stessa sotto `~/Applications`; Windows `%ProgramFiles%`, `%ProgramFiles(x86)%`, `%LocalAppData%`.
  - `browsers.resolve(runtime_dir: Path, progress: Callable[[str], None]) -> LaunchSpec` — usa i precedenti; se `None`, esegue `python -m playwright install chromium` (con `PLAYWRIGHT_BROWSERS_PATH` già impostato) mostrando "Scarico il browser (circa 150 MB, solo la prima volta)…" e restituisce `LaunchSpec(None, None)`. Il guard sta nel fatto che Playwright non riscarica se il browser è già in `PLAYWRIGHT_BROWSERS_PATH`. Se il download fallisce → `BrowserUnavailableError`.
  - Mappa id predefinito → famiglia: `com.google.chrome`→chrome, `com.microsoft.edgemac`→msedge, `com.brave.browser`→brave, `com.vivaldi.vivaldi`→vivaldi, `com.operasoftware.opera`→opera; Windows `ChromeHTML`→chrome, `MSEdgeHTM`→msedge, `BraveHTML`→brave, `VivaldiHTM`→vivaldi, `OperaStable`→opera (confronto case-insensitive, prefisso).

- [ ] **Step 1: Test che falliscono** (solo `choose`, la parte pura)

```python
def test_default_chromium_wins():
    assert choose("com.brave.Browser", {"chrome": "/c", "brave": "/b"}) == LaunchSpec(None, "/b")
def test_safari_default_falls_back_to_chrome():
    assert choose("com.apple.Safari", {"chrome": "/c", "msedge": "/e"}).executable_path == "/c"
def test_edge_when_no_chrome():
    assert choose("FirefoxURL-308046B0AF4A39CB", {"msedge": "/e"}).executable_path == "/e"
def test_nothing_installed():
    assert choose(None, {}) is None
```
- [ ] **Step 2–4:** fallire → implementare (tutte le funzioni; lanciare sempre con `executable_path`, è il modo uniforme per tutte le famiglie) → verdi.
- [ ] **Step 5: Commit** — `git commit -m "feat: pick installed chromium-based browser, download as fallback"`

---

### Task 5: Lettura del binder pubblico

Questo task include uno spike: il formato dei dati va scoperto dal sito reale (vedi spec, "Lettura della collezione"). Ricognizione già fatta: da sloggati la pagina pubblica è accessibile; le carte arrivano con POST "server action" alla stessa URL della pagina (header `Next-Action`), non dall'API `/api/external/v1/...` (401). La griglia è virtualizzata: il DOM contiene solo le carte visibili, quindi **non** usare il DOM come fonte primaria. La pagina mostra anche un filtro "Ownership" e il conteggio "Show N cards": verificare se da sloggati compaiono solo le carte possedute o tutto il catalogo con quantità 0.

**Files:**
- Create: `.app/src/tools/capture_binder.py`, `.app/src/deck_inventory/binder.py`
- Create: `.app/src/tests/fixtures/binder_payloads_2026-10-31.json` (output della cattura)
- Test: `.app/src/tests/test_binder.py`

**Interfaces:**
- Consumes: `names.normalize`, `errors.*`, `browsers.LaunchSpec`, `browsers.resolve` (Task 4); lanciare con `executable_path=launch.executable_path` (o Chromium di Playwright se `None`).
- Produces:
  - `binder.parse_payloads(payloads: list[str]) -> dict[str, int]` — chiavi normalizzate, varianti sommate, solo quantità > 0. Solleva `SiteChangedError` se non trova la struttura attesa o il risultato è vuoto.
  - `binder.fetch_payloads(link: str, launch: LaunchSpec, timeout_s: int = 90) -> list[str]` — apre la pagina headless senza cookie, raccoglie i body delle risposte POST alla URL del binder finché il caricamento è completo, solleva `BinderPrivateError` se la navigazione finisce su `/sign-in` o la pagina dice che il binder non esiste/non è pubblico, `BinderNetworkError` per errori di rete/timeout.
  - `binder.fetch_collection(link: str, launch: LaunchSpec) -> dict[str, int]` = `parse_payloads(fetch_payloads(...))`.

- [ ] **Step 1: Cattura.** `capture_binder.py <link> <out.json>`: Playwright headless, contesto pulito, registra ogni risposta (URL, metodo, status, header `content-type`, body testo) di POST verso la URL del binder; se necessario forza il caricamento completo (scroll del contenitore della griglia, o meglio un parametro della richiesta che porti tutte le pagine — documentare cosa si è trovato in un commento in testa al file). Eseguire sul binder dell'utente (link in GOOD, Task 3) e salvare la fixture. Annotare in testa a `binder.py` la forma del payload trovata.
- [ ] **Step 2: Test che falliscono**

```python
def test_fixture_matches_csv_same_day():
    owned = parse_payloads(load_fixture("binder_payloads_2026-10-31.json"))
    csv_owned = owned_from_csv(FIXTURES/"collection_2026-10-31.csv")
    assert owned == csv_owned          # 248 nomi, 541 copie; Defy == 8
def test_garbage_is_site_changed():
    with pytest.raises(SiteChangedError): parse_payloads(["<html>nope</html>"])
def test_empty_is_site_changed():
    with pytest.raises(SiteChangedError): parse_payloads([])
```
Se `test_fixture_matches_csv_same_day` fallisce solo perché l'utente ha modificato il binder dopo l'export del CSV, chiedere all'utente un CSV nuovo e ricatturare: il confronto esatto con lo stesso stato è il test di completezza (Review Focus 1).

- [ ] **Step 3: Implementare** `parse_payloads` e `fetch_payloads`.
- [ ] **Step 4: Test verdi** + test manuale marcato `@pytest.mark.online` che chiama `fetch_collection(GOOD, ...)` e controlla `sum(values) > 0` e che un link inventato (UUID valido ma inesistente) dia `BinderPrivateError`. Escluso di default (`-m "not online"` in `pyproject.toml`).
- [ ] **Step 5: Commit** — `git commit -m "feat: read public binder via headless browser"`

---

### Task 6: Pagina, dialoghi, orchestrazione

**Files:**
- Create: `.app/src/deck_inventory/render.py`, `dialogs.py`, `main.py`
- Test: `.app/src/tests/test_render.py`, `.app/src/tests/test_main.py`

**Interfaces:**
- Consumes: tutto quanto sopra.
- Produces:
  - `render.render_page(total: Section, per_deck: list[Section], warnings: list[str], link: str, generated_at: datetime, version: str) -> str` — HTML completo, CSS inline, nessuna risorsa esterna, tutti i testi passati da `html.escape`. Sezioni nell'ordine della spec ("Pagina dei risultati", punti 1–5): intestazione; "Tutti i mazzi insieme" (riepilogo + tabella con `N. mazzi`); "Solo le carte mancanti" (`4x Defy (12/8)`); "Split per mazzo"; avvisi in un riquadro in alto se presenti. Riepilogo: "Servono N copie, ne hai N, ne mancano N (N carte diverse incomplete)."
  - `render.page_filename(dt: datetime) -> str` → `"Inventory 2026-10-31 18.40.html"`.
  - `dialogs.ask_link(error: str | None) -> str | None` (tkinter, campo testo + OK/Annulla; `None` se annullato), `dialogs.Progress` (context manager con `.set(text)`, finestra piccola non modale con barra indeterminata), `dialogs.error(message: str)`, `dialogs.info(message: str)`.
  - `main.run(project_dir: Path, ui) -> Path | None` — `ui` è l'oggetto `dialogs` (iniettato per i test). Passi: link (`read_link`; se manca → `ask_link` finché valido o annullato → `write_link`) → `load_decks` → `browsers.resolve` → `fetch_collection` → `compute` → `render_page` → scrive il nuovo file, **poi** cancella gli altri `Inventory *.html` → apre con `webbrowser.open(path.as_uri())` → restituisce il percorso. Ogni `UserFacingError` → `ui.error(e.message)` e return `None` senza toccare i file HTML. `SiteChangedError.message` include `VERSION`. Eccezioni inattese → `ui.error` con testo generico + traccia salvata in `.app/runtime/last-error.log`.
  - Entry point: `python -m deck_inventory <project_dir>`.

- [ ] **Step 1: Test che falliscono**

```python
def test_page_contains_expected_bits():
    html = render_page(total, per, ["avviso «x»"], GOOD, datetime(2026,10,31,18,40), "1.0.0")
    assert "12/8" in html and "Ornn Aggro" in html and "4x Defy (12/8)" in html
    assert "avviso «x»" in html and "1.0.0" in html and "<script src" not in html and "<link" not in html
def test_escaping():
    assert "<b>" not in render_page(section_with_name("<b>"), [], [], GOOD, NOW, "1.0.0")
def test_filename():
    assert page_filename(datetime(2026,10,31,18,40)) == "Inventory 2026-10-31 18.40.html"
def test_failure_keeps_previous_page(tmp_path, fake_ui, monkeypatch):
    (tmp_path/"Inventory old.html").write_text("x"); setup_project(tmp_path)
    monkeypatch.setattr(binder, "fetch_collection", raise_(BinderNetworkError("rete")))
    assert run(tmp_path, fake_ui) is None
    assert (tmp_path/"Inventory old.html").exists() and fake_ui.errors == ["rete"]
def test_success_replaces_previous_page(tmp_path, fake_ui, monkeypatch):
    (tmp_path/"Inventory old.html").write_text("x"); setup_project(tmp_path)
    monkeypatch.setattr(binder, "fetch_collection", lambda *a: {"defy": 8})
    monkeypatch.setattr(browsers, "resolve", lambda *a: LaunchSpec(None, None))
    monkeypatch.setattr(webbrowser, "open", lambda *a: True)
    out = run(tmp_path, fake_ui)
    assert out.exists() and not (tmp_path/"Inventory old.html").exists()
def test_missing_link_asks_and_saves(tmp_path, fake_ui, ...):  # fake_ui.ask_link restituisce GOOD
    ...; assert read_link(tmp_path) == GOOD
def test_cancel_link_stops(tmp_path, fake_ui):  # ask_link -> None
    assert run(tmp_path, fake_ui) is None
```
- [ ] **Step 2–4:** fallire → implementare → verdi.
- [ ] **Step 5: Verifica manuale end-to-end sul Mac di sviluppo**: copiare i deck fixture in `decks/`, `uv run --project .app/src python -m deck_inventory "$PWD"` → si apre la pagina; confrontarla con il riepilogo unificato originale (stessi numeri se il binder non è cambiato).
- [ ] **Step 6: Commit** — `git commit -m "feat: results page, dialogs and main flow"`

---

### Task 7: Launcher e guard di installazione

**Files:**
- Create: `Start (Mac).command` (eseguibile, `chmod +x`), `Start (Windows).bat` (fine riga CRLF)
- Create: `.app/src/uv.lock` (versionato; `uv lock`)

**Interfaces:**
- Produces: file di stato del guard `.app/runtime/install-state.txt`, una riga: `<ROOT assoluto>|<os>-<arch>` (es. `/Users/x/Desktop/Deck Inventory|darwin-arm64`, `C:\Users\x\Desktop\Deck Inventory|windows-x64`). Letto e scritto direttamente dal launcher, senza Python.

Il guard ha due livelli:
- **uv** (`uv sync --frozen`) non riscarica Python né librerie se sono già presenti e coerenti con `uv.lock`; **Playwright** non riscarica il browser se è già in `PLAYWRIGHT_BROWSERS_PATH`. Gli aggiornamenti degli script (nuovo `uv.lock`) sono quindi gestiti da uv.
- **`install-state.txt`** rileva ciò che uv non vede: se il ROOT è diverso (cartella spostata/copiata) → cancella `runtime/venv` (contiene percorsi assoluti); se `<os>-<arch>` è diverso (copiata su un'altra macchina) → cancella anche `runtime/python`, `runtime/uv` e `runtime/browsers`. Poi sync e riscrive il file.

Comportamento comune dei launcher (stessi passi su entrambi i sistemi):
1. Calcola `ROOT` dalla posizione del launcher stesso (mai percorsi fissi); imposta le variabili dei Global Constraints.
2. Nasconde/riduce la propria finestra: Mac `osascript -e 'tell application "Terminal" to set miniaturized of front window to true'`; Windows: se non già avviato minimizzato, si rilancia con `start "" /min cmd /c "%~f0" min` ed esce.
3. Se `.app/runtime/uv/uv[.exe]` manca: dialog nativo una sola volta ("Prima installazione: Deck Inventory scaricherà i componenti necessari dentro la sua cartella. Può richiedere qualche minuto. Al termine si aprirà la pagina.") — Mac `osascript display dialog`, Windows PowerShell `[System.Windows.Forms.MessageBox]` — poi scarica uv **0.13.1** da `https://github.com/astral-sh/uv/releases/download/0.13.1/uv-<target>.tar.gz|.zip` con `curl -fL` e lo estrae con `tar` (target: `aarch64-apple-darwin`, `x86_64-apple-darwin` da `uname -m`; `x86_64-pc-windows-msvc`). Errore di rete → dialog nativo con messaggio e uscita.
4. Windows: `attrib +h "%ROOT%\.app"` (idempotente).
5. Guard: confronta `install-state.txt` con `ROOT|os-arch` corrente e cancella come descritto sopra (prima del passo 3 se cambia `os-arch`, così uv viene riscaricato per la piattaforma giusta); poi `uv sync --project .app/src --frozen --no-dev`; se riesce, scrive `install-state.txt`. Errore della sync → dialog nativo "Installazione non riuscita, controlla la connessione e riprova" e uscita (al prossimo avvio uv riprende).
6. `uv run --project .app/src --frozen --no-dev python -m deck_inventory "ROOT"`.
7. Mac: a fine esecuzione chiude la propria finestra del Terminale (`osascript ... close (every window whose name contains "Start (Mac)")` in background dopo `exit`).

- [ ] **Step 1:** `uv lock` in `.app/src/`; scrivere i due launcher.
- [ ] **Step 2: Verifica Mac (manuale)**: copia pulita della cartella senza `.app/runtime` in una cartella con spazi e accenti nel nome (es. `prova à/`); doppio clic → dialog prima installazione → richiesta link → pagina. Secondo doppio clic: nessun download (controllare che la dimensione di `.app/runtime` non cambi e che il tempo sia < 15 s). Spostare la cartella altrove e rilanciare: funziona, `runtime/browsers` (se usato) non viene riscaricato.
  Verificare anche il caso del cambio piattaforma simulando `install-state.txt` con un `os-arch` diverso: deve cancellare e reinstallare tutto.
- [ ] **Step 3: Verifica Windows (manuale, su una macchina o VM Windows 10/11 pulita)**: stessi passi; `.app` risulta nascosta in Esplora risorse; nessuna finestra nera resta aperta in primo piano. Se non c'è una macchina Windows disponibile, segnalarlo all'utente: il launcher Windows resta non verificato.
- [ ] **Step 4: Commit** — `git commit -m "feat: double-click launchers with install guard"`

---

### Task 8: README e pacchetto da condividere

**Files:**
- Create: `README.txt`, `decks/order.txt` di esempio (solo commento), `.app/src/tools/make_share_zip.py`

**Interfaces:**
- Produces: `make_share_zip.py <project_dir> <out.zip>` — zip della cartella escludendo `.app/runtime/`, `settings.txt`, `Inventory *.html`, `docs/`, `.git/`, `decks/*` tranne un `order.txt` vuoto commentato; preserva il bit eseguibile di `Start (Mac).command`.

README (italiano, breve): cosa fa; primo avvio (doppio clic su Start; su Mac, se compare "impossibile aprire perché proviene da uno sviluppatore non identificato": tasto destro → Apri); come ottenere il link (binder → "Make Public" → "Share"; cambiarlo in `settings.txt`); come aggiungere un mazzo (file `.txt` in `decks/`, formato del deckbuilder) e cambiare l'ordine (`decks/order.txt`); dove trovare l'ultima pagina; versione e "se compare 'Piltover Archive è cambiato' chiedi una versione aggiornata".

- [ ] **Step 1:** Scrivere README e `make_share_zip.py`.
- [ ] **Step 2: Verifica**: creare lo zip, estrarlo in una cartella nuova, controllare l'assenza di `runtime/`, `settings.txt`, deck personali; doppio clic su Start dalla copia estratta → chiede il link → funziona.
- [ ] **Step 3:** Spostare `docs/` del progetto fuori dal pacchetto condivisibile è già gestito dallo zip; nessuna azione sulla cartella di sviluppo.
- [ ] **Step 4: Commit** — `git commit -m "docs: README and share package"`
