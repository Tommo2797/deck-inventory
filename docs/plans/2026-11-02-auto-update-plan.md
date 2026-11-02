# Auto-update e storico versioni — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** All'avvio Deck Inventory si aggiorna da solo all'ultima release pubblicata su GitHub (senza mai bloccarsi), mostra le novità, e l'autore pubblica le versioni con un comando unico; il README contiene lo storico delle versioni.

**Architecture:** Un modulo Python solo-stdlib `deck_inventory/update.py`, lanciato dai launcher come passo separato (`python -m deck_inventory.update ROOT`) prima del programma principale; tutta la logica (controllo, download, verifica, scambio atomico di `.app/src`, `uv sync`, rollback, messaggi) sta lì ed è quindi aggiornabile. Le funzioni di rete e di sync sono iniettate per i test. Lo storico vive in `.app/src/CHANGELOG.txt` (unica fonte) da cui derivano la sezione NOVITÀ del README, le note della release e il messaggio post-aggiornamento. Il comando `tools/publish.sh` fa controlli, bump, commit, tag, push e `gh release create` con lo zip di `make_share_zip.py`.

**Tech Stack:** Python 3.12 stdlib (urllib.request, json, zipfile, shutil, subprocess), tkinter (dialoghi esistenti), pytest, bash/batch, GitHub REST API pubblica, `gh` CLI (solo pubblicazione).

**Spec:** `docs/2026-11-02-auto-update-design.md` (vincolante). Contesto: `docs/2026-10-31-deck-inventory-design.md`.

## Global Constraints

- Repository degli aggiornamenti: `Tommo2797/deck-inventory`, scritto in un solo punto: `UPDATE_REPO = "Tommo2797/deck-inventory"` in `deck_inventory/__init__.py`.
- Versione: `VERSION` in `deck_inventory/__init__.py`, formato `x.y.z`, tag GitHub `v<x.y.z>`. Questa consegna porta `VERSION = "1.1.0"` **solo al momento della pubblicazione** (lo fa `publish`); nel codice resta `1.0.0` fino ad allora.
- Versione dei launcher: `MIN_LAUNCHER = 1` in `deck_inventory/__init__.py`; i launcher nuovi passano `DECK_INVENTORY_LAUNCHER=1` e `DECK_INVENTORY_UV=<percorso assoluto di uv>` nell'ambiente.
- Allegato della release: nome fisso `deck-inventory.zip`, creato da `make_share_zip.py` (radice `Deck Inventory/`).
- Si aggiornano solo `.app/src/` e `README.txt`. Mai: launcher, `settings.txt`, `decks/`, `Inventory *.html`, `.app/runtime/` (tranne `.app/runtime/update/`).
- Cartella con `.git` → nessun aggiornamento.
- Il passo di aggiornamento non blocca mai: esce sempre con codice 0; il launcher ignora comunque il suo codice di uscita.
- Timeout rete: 3 s per la chiamata API, 30 s per il download dello zip.
- Errori dell'aggiornamento → riga in `.app/runtime/last-error.log` (append, con versione e data), nessun dialogo d'errore.
- Testi utente in italiano. `DECK_INVENTORY_NO_DIALOG=1` → nessun dialogo (test automatici).
- Comandi uv sempre con le variabili di isolamento del progetto (vedi spec 1.0.0); test: `uv run --project .app/src pytest .app/src/tests -q` dalla radice.
- Firma dei commit: quella configurata nel repository (`Tommo2797`); messaggi che terminano con riga vuota + `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **GitHub risponde ma in modo inatteso** (403 rate limit, 404 nessuna release, JSON senza l'allegato, tag non `vX.Y.Z`): nessun aggiornamento, nessun dialogo, avvio normale. → Test in Task 2.
2. **Zip scaricato corrotto o malevolo** (troncato, percorsi `../`, manca `deck_inventory/__init__.py`): versione installata intatta. → Test in Task 2.
3. **`uv sync` fallisce dopo lo scambio**: rollback ai file vecchi, `uv sync` di nuovo, avvio con la versione vecchia. → Test in Task 2.
4. **Release che richiede un launcher più nuovo**: niente installazione, messaggio una sola volta per quella versione. → Test in Task 2.
5. **Avvio senza internet**: il controllo dura al massimo ~3 s e poi si prosegue. → Verifica manuale in Task 3 (rete finta irraggiungibile).

---

## Struttura dei file

```
.app/src/
├── CHANGELOG.txt                 Task 1 — unica fonte dello storico
├── deck_inventory/
│   ├── __init__.py               Task 1 — + MIN_LAUNCHER, UPDATE_REPO
│   ├── changelog.py              Task 1 — parsing e rendering dello storico
│   ├── update.py                 Task 2 — logica aggiornamento (stdlib)
│   └── __main__ update entry     Task 3 — `python -m deck_inventory.update`
├── tools/publish.py, publish.sh  Task 4
└── tests/test_changelog.py, test_update.py, test_publish.py
README.txt                        Task 1 (NOVITÀ), Task 4 (AGGIORNAMENTI)
Start (Mac).command, Start (Windows).bat   Task 3
```

---

### Task 1: Storico versioni (CHANGELOG + README NOVITÀ)

**Files:**
- Create: `.app/src/CHANGELOG.txt`, `.app/src/deck_inventory/changelog.py`
- Modify: `.app/src/deck_inventory/__init__.py`, `README.txt`
- Test: `.app/src/tests/test_changelog.py`

**Interfaces:**
- Produces:
  - `__init__.py`: `VERSION = "1.0.0"` (invariato), `MIN_LAUNCHER = 1`, `UPDATE_REPO = "Tommo2797/deck-inventory"`.
  - `changelog.Entry` dataclass: `version: str`, `date: str` (`YYYY-MM-DD` o `""` se non ancora pubblicata), `items: list[str]`.
  - `changelog.parse_version(s: str) -> tuple[int, int, int] | None` — accetta `1.2.3` e `v1.2.3`; altrimenti `None`.
  - `changelog.parse(text: str) -> list[Entry]` — ordine del file (più recente in alto). Formato del file:
    ```
    # Deck Inventory — novità. Una sezione per versione, la più recente in alto.
    # Righe che iniziano con # = commenti. Una novità per riga, con "- ".

    == 1.1.0 ==
    - Il programma si aggiorna da solo quando esce una versione nuova.
    - Il README contiene lo storico delle versioni (questa sezione).

    == 1.0.0 (2026-10-31) ==
    - Prima versione.
    ```
    Intestazione: `== <versione> ==` oppure `== <versione> (<data>) ==`. Voci senza versione valida o duplicate → `ValueError` con messaggio chiaro.
  - `changelog.between(entries: list[Entry], old: str, new: str) -> list[Entry]` — voci con `old < versione <= new`, dalla più recente.
  - `changelog.format_entries(entries: list[Entry]) -> str` — testo per dialogo/note: `Versione 1.1.0 (2026-11-02)` + righe `• voce`; data omessa se vuota.
  - `changelog.readme_section(entries: list[Entry]) -> str` — blocco che inizia con `NOVITÀ\n------\n` seguito da `format_entries`.
  - `changelog.replace_readme_section(readme: str, section: str) -> str` — sostituisce dalla riga `NOVITÀ` fino a fine file (la sezione è sempre l'ultima); se manca la appende dopo una riga vuota.
  - `changelog.set_release_date(text: str, version: str, date: str) -> str` — trasforma `== 1.1.0 ==` in `== 1.1.0 (date) ==` (usato da publish).

- [ ] **Step 1: Test che falliscono** — `test_parse_and_between` (file d'esempio sopra: `between(e, "1.0.0", "1.1.0")` → solo 1.1.0; `between(e, "0.9.0", "1.1.0")` → 1.1.0 poi 1.0.0); `test_parse_version` (`"v1.10.0"` → `(1,10,0)`; `"1.2"`, `"x"` → `None`; confronto `parse_version("1.10.0") > parse_version("1.9.9")`); `test_duplicate_version_raises`; `test_readme_section_replace` (README con sezioni + vecchia NOVITÀ → sostituita, il resto identico; README senza NOVITÀ → appesa); `test_set_release_date`; `test_repo_readme_in_sync` — `replace_readme_section(README.txt reale, readme_section(parse(CHANGELOG.txt reale)))` è identico al README reale (blocca README e storico disallineati).
- [ ] **Step 2: Verificare che falliscano.**
- [ ] **Step 3: Implementare** `changelog.py`, aggiornare `__init__.py`, creare `CHANGELOG.txt` con le due voci dell'esempio (1.1.0 senza data), aggiungere a `README.txt` la sezione NOVITÀ generata, come ultima sezione.
- [ ] **Step 4: Test verdi** (suite completa).
- [ ] **Step 5: Commit** — `feat: changelog as single source and README NOVITÀ section`

---

### Task 2: Logica di aggiornamento

**Files:**
- Create: `.app/src/deck_inventory/update.py` (solo standard library + `deck_inventory.changelog` e `deck_inventory.__init__`; NON importare dialogs/tkinter/playwright a livello di modulo)
- Test: `.app/src/tests/test_update.py`

**Interfaces:**
- Consumes: Task 1 (`parse_version`, `parse`, `between`, `format_entries`, `VERSION`, `MIN_LAUNCHER`, `UPDATE_REPO`).
- Produces:
  - `update.Release` dataclass: `version: str`, `zip_url: str`.
  - `update.API_URL = "https://api.github.com/repos/{repo}/releases/latest"`; env `DECK_INVENTORY_UPDATE_API` (solo per i test manuali) sostituisce l'URL completo.
  - `update.latest_release(fetch_json: Callable[[str], dict]) -> Release | None` — `None` se tag non valido o manca l'asset `deck-inventory.zip` o `fetch_json` solleva qualsiasi eccezione.
  - `update.http_json(url: str) -> dict` / `update.http_bytes(url: str) -> bytes` — urllib con header `User-Agent: deck-inventory/<VERSION>` e `Accept: application/vnd.github+json`, timeout 3 s / 30 s.
  - `update.extract_release(data: bytes, staging: Path) -> Path` — estrae in `staging` e restituisce la cartella che contiene `.app/src` e `README.txt` (la radice `Deck Inventory/` dello zip); `UpdateError` se zip non valido, percorso assoluto o con `..`, o mancano `.app/src/deck_inventory/__init__.py`, `.app/src/pyproject.toml`, `README.txt`.
  - `update.read_meta(src_dir: Path) -> tuple[str, int]` — `(VERSION, MIN_LAUNCHER)` letti dal testo di `deck_inventory/__init__.py` con regex (senza importarlo); `MIN_LAUNCHER` assente → `1`.
  - `update.Outcome` dataclass: `status: Literal["skipped","current","updated","needs_launcher","failed"]`, `old: str`, `new: str | None`, `notes: str` (testo `format_entries` delle versioni comprese, solo per `updated`/`needs_launcher`).
  - `update.check_and_update(root: Path, launcher: int, fetch_json, fetch_bytes, run_sync: Callable[[Path], bool], now: Callable[[], str]) -> Outcome` — algoritmo:
    1. `root/".git"` esiste → `skipped`. `launcher < 1` (env assente) → `skipped`.
    2. `latest_release` → `None` → `skipped`. Versione `<=` installata (`read_meta(root/".app/src")`) → `current`.
    3. Se esiste `root/.app/runtime/update/notified-<new>` → `current` (già avvisato che serve un launcher nuovo).
    4. Scarica, `extract_release` in `root/.app/runtime/update/staging` (svuotata prima). `read_meta` della release: versione diversa dal tag → `failed`. `min_launcher > launcher` → crea il file `notified-<new>`, `needs_launcher`.
    5. Scambio: `root/.app/src` → `root/.app/runtime/update/previous` (eliminata prima se esiste), staging `.app/src` → `root/.app/src`; rinomine con 5 tentativi a 0,5 s; se la rinomina continua a fallire, ripiego con `shutil.copytree` + rimozione. Poi `README.txt` sostituito con `os.replace` da quello della release.
    6. `run_sync(root/".app/src")` falso → rollback (rimette `previous` al posto di `.app/src` e il README vecchio, conservato prima come `previous/README.txt.bak`), `run_sync` di nuovo, `failed`.
    7. Successo → `updated`, `notes = format_entries(between(parse(nuovo CHANGELOG), old, new))`; pulizia di staging/previous.
    Qualsiasi eccezione nei passi 4–7 → rollback se lo scambio era iniziato, riga nel log, `failed`. La funzione non solleva mai.
  - `update.log_error(root: Path, message: str) -> None` — append a `root/.app/runtime/last-error.log`.

Fixture di test: un progetto finto in `tmp_path` (`.app/src/deck_inventory/__init__.py` con `VERSION = "1.0.0"`, `CHANGELOG.txt`, `pyproject.toml`, `README.txt`) e uno zip di release costruito con `tools/make_share_zip.make_share_zip` a partire da una seconda copia con `VERSION = "1.1.0"`; `fetch_json`/`fetch_bytes`/`run_sync` finti.

- [ ] **Step 1: Test che falliscono**
  - `test_git_folder_skips`, `test_no_launcher_env_skips`
  - `test_api_errors_skip` — `fetch_json` che solleva / restituisce `{}` / tag `"latest"` / senza asset → `skipped`, file intatti
  - `test_same_or_older_is_current`
  - `test_update_success` — `updated`, `.app/src/deck_inventory/__init__.py` contiene `1.1.0`, README nuovo, `settings.txt`, `decks/x.txt`, `Inventory a.html`, `Start (Mac).command` del progetto finto **identici**, `notes` contiene `"1.1.0"`, staging/previous rimossi
  - `test_skipped_versions_notes` — da 1.0.0 a 1.2.0 → note con 1.2.0 e 1.1.0
  - `test_bad_zip_keeps_old` — bytes troncati; zip con voce `../evil.txt`; zip senza `__init__.py` → `failed`, file intatti, `last-error.log` scritto, `evil.txt` non creato fuori
  - `test_sync_failure_rolls_back` — `run_sync` falso la prima volta → `failed`, `.app/src` e README tornano alla 1.0.0, `run_sync` chiamato due volte
  - `test_needs_launcher_once` — release con `MIN_LAUNCHER = 2`, launcher 1 → `needs_launcher` la prima volta, `current` la seconda, file intatti
  - `test_version_mismatch_fails` — tag `v1.1.0` ma `__init__` dice `1.2.0` → `failed`
- [ ] **Step 2: Verificare che falliscano.** **Step 3: Implementare.** **Step 4: Test verdi.**
- [ ] **Step 5: Commit** — `feat: self-update from latest GitHub release with atomic swap and rollback`

---

### Task 3: Punto di ingresso, messaggi e launcher

**Files:**
- Create: entry point `python -m deck_inventory.update` (blocco `if __name__ == "__main__":` in `update.py`, oppure `deck_inventory/update_cli.py` richiamato da lì — a scelta, purché il comando sia `python -m deck_inventory.update <ROOT>`)
- Modify: `Start (Mac).command`, `Start (Windows).bat`, `README.txt` (nessuna sezione nuova qui)
- Test: `.app/src/tests/test_update.py` (aggiunte)

**Interfaces:**
- Consumes: `check_and_update`, `http_json`, `http_bytes`, `dialogs.info` (import ritardato dentro la funzione che mostra il messaggio).
- Produces:
  - `update.main(argv: list[str], ui=None) -> int` — legge `DECK_INVENTORY_LAUNCHER` (int, default 0) e `DECK_INVENTORY_UV`; `run_sync` = `subprocess.run([uv, "sync", "--project", str(src), "--frozen", "--no-dev"])` con returncode 0 (uv mancante → `False`); chiama `check_and_update`; messaggi (se `DECK_INVENTORY_NO_DIALOG != "1"`):
    - `updated`: `"Deck Inventory è stato aggiornato dalla versione {old} alla versione {new}.\n\nNovità:\n{notes}"`
    - `needs_launcher`: `"È disponibile la versione {new} di Deck Inventory, ma per installarla serve scaricarla di nuovo a mano da:\nhttps://github.com/{UPDATE_REPO}/releases/latest\n\nPer ora continui a usare la versione {old}."`
    - altri esiti: nessun messaggio.
    Restituisce sempre 0.
- Launcher (entrambi), dopo la `uv sync` riuscita e la scrittura dello stato, prima dell'avvio del programma:
  - esportano `DECK_INVENTORY_LAUNCHER=1` e `DECK_INVENTORY_UV=<percorso assoluto di uv>`;
  - eseguono `"$UV" run --project "$SRC" --frozen --no-dev python -m deck_inventory.update "$ROOT"` ignorando il codice d'uscita (Windows: `call` equivalente, nessun `if errorlevel`);
  - poi l'avvio del programma come oggi. Nient'altro cambia nei launcher.

- [ ] **Step 1: Test che falliscono** — `test_main_messages` (ui finta: `updated` → un `info` con `"dalla versione 1.0.0 alla versione 1.1.0"` e `"Novità"`; `needs_launcher` → `info` con l'URL delle release; `current`/`skipped`/`failed` → nessun messaggio; sempre return 0); `test_main_no_dialog_env`; `test_main_missing_uv_means_sync_false` (monkeypatch di `check_and_update` per catturare `run_sync` e verificare che con `DECK_INVENTORY_UV` assente restituisca `False`).
- [ ] **Step 2–4:** fallire → implementare (codice + launcher) → verdi.
- [ ] **Step 5: Verifica manuale Mac su una copia** (mai nella cartella reale; la copia NON deve contenere `.git`): copia in `~/Desktop/prova-update/Deck Inventory` con `decks/` dai fixture finti e `settings.txt` con il link reale preso dal `settings.txt` della cartella di sviluppo; un server locale (`python -m http.server` in una cartella con `latest.json` + `deck-inventory.zip` costruito da una copia con `VERSION = "1.1.0"` e voce CHANGELOG 1.1.0) e `DECK_INVENTORY_UPDATE_API=http://127.0.0.1:<porta>/latest.json`. Controllare: (a) primo avvio → messaggio di aggiornamento, `.app/src` alla 1.1.0, pagina generata; (b) secondo avvio → nessun messaggio; (c) server spento → l'avvio non ritarda più di ~3 s e genera la pagina; (d) zip corrotto servito → nessun messaggio, versione invariata, riga in `last-error.log`; (e) release con `MIN_LAUNCHER = 2` → messaggio una sola volta. Usare `DECK_INVENTORY_NO_DIALOG=1` dove serve automazione e verificare i messaggi con la ui finta nei test. Cancellare la copia alla fine.
- [ ] **Step 6: Commit** — `feat: launchers run the update step before starting`

---

### Task 4: Comando di pubblicazione e README

**Files:**
- Create: `.app/src/tools/publish.py`, `.app/src/tools/publish.sh` (eseguibile; imposta le variabili di isolamento e lancia `uv run --project .app/src python .app/src/tools/publish.py "$@"` dalla radice del repository)
- Modify: `README.txt` (nuova sezione AGGIORNAMENTI prima di NOVITÀ), `.app/src/tools/make_share_zip.py` solo se serve escludere `publish.*` (gli strumenti dell'autore non vanno nello zip: escludere `tools/publish.py` e `tools/publish.sh`)
- Test: `.app/src/tests/test_publish.py`

**Interfaces:**
- Consumes: `changelog.*`, `make_share_zip.make_share_zip`, `UPDATE_REPO`, `settings.read_link`.
- Produces: `publish.py <versione> [--skip-online] [--dry-run]`. Funzioni testabili:
  - `publish.check_version(new: str, latest: str | None) -> None` — `ValueError` se formato non `x.y.z` o non maggiore di `latest`.
  - `publish.bump_version(init_text: str, new: str) -> str` — sostituisce la riga `VERSION = "..."`.
  - `publish.release_notes(changelog_text: str, version: str) -> str` — `format_entries` della sola voce; `ValueError` se manca o non ha voci.
  - `publish.run(argv, sh: Callable[[list[str]], str]) -> int` — `sh` esegue comandi e restituisce stdout (iniettato per i test). Passi e controlli, in quest'ordine, ognuno con messaggio italiano chiaro e uscita 1 se fallisce:
    1. ramo `main`, `git status --porcelain` vuoto, `git fetch` e `HEAD == origin/main`;
    2. `gh api user -q .login` == proprietario di `UPDATE_REPO`;
    3. ultima release: `gh release view --repo UPDATE_REPO --json tagName -q .tagName` (nessuna release → `None`); `check_version`;
    4. voce CHANGELOG presente e non vuota (`release_notes`);
    5. `tests/private/` presente; suite completa; se non `--skip-online`: link da `settings.txt` della radice → test `-m online` con `DECK_INVENTORY_TEST_BINDER`; con `--skip-online` stampa un avviso evidente;
    6. `--dry-run`: crea lo zip in una cartella temporanea, stampa cosa farebbe, esce 0 senza modificare nulla;
    7. scrive `VERSION`, data di oggi nell'intestazione CHANGELOG (`set_release_date`), README rigenerato (`replace_readme_section`), commit `release: v<versione>`, tag `v<versione>`, `git push origin main v<versione>`;
    8. zip `deck-inventory.zip` in cartella temporanea; `gh release create v<versione> <zip> --repo UPDATE_REPO --title "Deck Inventory <versione>" --notes <note>`.
    Se un passo da 7 in poi fallisce, il messaggio elenca cosa è già stato fatto (commit/tag/push/release) e cosa no.
- README: sezione **AGGIORNAMENTI** (italiano semplice): il programma si aggiorna da solo all'avvio quando esce una versione nuova e mostra le novità; i tuoi mazzi, il link e le pagine non vengono toccati; senza internet usa la versione che ha; chi ha la 1.0.0 deve passare alla 1.1.0 a mano una volta (scaricare `deck-inventory.zip` da `https://github.com/Tommo2797/deck-inventory/releases/latest`, estrarlo in una cartella nuova, copiarci `settings.txt` e la cartella `decks`); se compare "serve scaricarla di nuovo a mano" stessa procedura.

- [ ] **Step 1: Test che falliscono** — `test_check_version` (`"1.1.0"` vs `"v1.0.0"` ok; `"1.0.0"` vs `"v1.0.0"` errore; `"1.1"` errore; `latest=None` ok); `test_bump_version`; `test_release_notes_missing`; `test_run_refuses_dirty_tree` (sh finto: porcelain non vuoto → 1, nessun commit); `test_run_dry_run_changes_nothing` (sh finto che registra i comandi: nessun `git commit`/`push`/`gh release create`); `test_run_full_sequence` (ordine dei comandi: commit → tag → push → gh release create con `deck-inventory.zip`); `test_share_zip_excludes_publish_tools`.
- [ ] **Step 2–4:** fallire → implementare → verdi; aggiornare README (e `test_repo_readme_in_sync` di Task 1 deve restare verde).
- [ ] **Step 5: Verifica** — `.app/src/tools/publish.sh 1.1.0 --dry-run` nella cartella di sviluppo reale: tutti i controlli passano (incluso il test online), stampa il piano, `git status` resta pulito. **Non** eseguire la pubblicazione vera: la fa il controller dopo conferma dell'utente.
- [ ] **Step 6: Commit** — `feat: publish command and README update instructions`
