# Deck Inventory — handoff

Ultimo aggiornamento: 2026-11-04 · Versione pubblicata: **1.1.0** · Repo pubblico: https://github.com/Tommo2797/deck-inventory

Questo documento serve per riprendere il lavoro senza la conversazione in cui è stato costruito. Leggerlo prima di toccare il codice.

## Cos'è

Tool locale (Mac e Windows) avviato con doppio clic su `Start (Mac).command` / `Start (Windows).bat`. Legge le liste dei mazzi Riftbound in `decks/` (priorità in `decks/order.txt`), legge la collezione da un **binder pubblico** di Piltover Archive con un browser invisibile (Playwright + Chrome/Edge/Brave installato, altrimenti Chromium scaricato) e genera `Inventory <data ora>.html` con Servono/Hai, carte mancanti e split per mazzo (copie assegnate ai mazzi in ordine di priorità). Dalla 1.1.0 si aggiorna da solo dall'ultima release GitHub.

Documenti di riferimento (l'intento è lì; il codice è la verità sui dettagli):
- `docs/2026-10-31-deck-inventory-design.md` — tool base (1.0.0)
- `docs/2026-11-02-auto-update-design.md` — aggiornamento automatico e storico (1.1.0)
- `docs/plans/*` — piani di implementazione **storici**: in alcuni punti superati (vedi "Differenze rispetto ai piani").

## Mappa del codice

| Percorso | Cosa fa |
|---|---|
| `Start (Mac).command`, `Start (Windows).bat` | Installano uv 0.13.1 → Python e dipendenze dentro `.app/runtime/` (guard su `install-state.txt`), lanciano il passo di aggiornamento, poi il programma. **Mai aggiornati automaticamente** (vedi contratto). |
| `.app/src/deck_inventory/main.py` | Flusso: link → mazzi → browser → binder → calcoli → pagina; errori in dialoghi, imprevisti in `.app/runtime/last-error.log`. |
| `decks.py`, `inventory.py`, `names.py` | Parsing liste/order.txt, calcoli e assegnazione per mazzo, normalizzazione nomi; rune escluse. |
| `binder.py` | Legge le carte dai dati RSC server-rendered (`self.__next_f.push`) delle pagine `?qtyMin=1&limit=100&page=N`. Docstring = come ripararlo se il sito cambia. |
| `browsers.py` | Sceglie il browser (predefinito se Chromium-like, poi Chrome/Edge/…; Arc non usato), fallback Chromium Playwright. |
| `settings.py` | `settings.txt` (`binder = <link>`), validazione del link pubblico. |
| `render.py`, `dialogs.py` | Pagina HTML autosufficiente; dialoghi tkinter. |
| `update.py` | Aggiornamento automatico (solo stdlib). Docstring = contratto con i launcher. |
| `changelog.py`, `.app/src/CHANGELOG.txt` | Unica fonte dello storico → README "NOVITÀ", note della release, messaggio post-aggiornamento. |
| `tools/publish.py`, `tools/publish.sh` | Pubblicazione (solo autore). Esclusi dallo zip. |
| `tools/make_share_zip.py` | Zip della release: in un repo git include **solo file tracciati**, esclude test/docs/publish/venv. |
| `tools/capture_binder.py` | Cattura pagine reali del binder (per ricreare fixture quando il sito cambia). |

## Lavorare sul progetto

**Regola d'oro: uv sempre con le variabili di isolamento**, altrimenti scarica Python/cache nella home (successo più volte). Dalla radice del progetto:

```bash
R="$PWD/.app/runtime"
export UV_CACHE_DIR=$R/uv-cache UV_PYTHON_INSTALL_DIR=$R/python UV_PROJECT_ENVIRONMENT=$R/venv \
       PLAYWRIGHT_BROWSERS_PATH=$R/browsers UV_PYTHON_PREFERENCE=only-managed
uv run --frozen --project .app/src pytest .app/src/tests -q          # suite normale (offline)
```

- **Test con dati reali**: `.app/src/tests/private/` (git-ignored: CSV della collezione, liste reali, cattura del binder del 2026-10-31). Se manca, 3 test vengono saltati. Non spostarli mai in file tracciati.
- **Test dal vivo** (marker `online`, esclusi di default): `DECK_INVENTORY_TEST_BINDER=<link binder> uv run … pytest … -m online`. Aprono Chrome: **nei terminali/agent sandboxati Chrome si blocca** → lanciarli da un Terminale normale.
- Dopo aver spostato la cartella, `.app/runtime/venv` ha percorsi assoluti vecchi: cancellarlo (`rm -rf .app/runtime/venv`) e rilanciare; si ricrea dalla cache senza download.
- La cartella di sviluppo contiene `.git` → **non si auto-aggiorna mai** (voluto).
- Variabili utili: `DECK_INVENTORY_NO_DIALOG=1` (nessun dialogo, per test automatici), `DECK_INVENTORY_UPDATE_API=<url>` (finto GitHub per testare l'aggiornamento; rilassa il controllo https), `BROWSER=true` (non apre la pagina a fine giro).

## Pubblicare una versione

1. Aggiungere in cima a `.app/src/CHANGELOG.txt` una sezione `== x.y.z ==` (senza data) con le novità in italiano semplice, una per riga `- …`. Rigenerare il README (`test_repo_readme_in_sync` fallisce se non coincidono: usare `changelog.replace_readme_section`).
2. Commit su `main`, push, tree pulito.
3. Da un Terminale normale: `.app/src/tools/publish.sh x.y.z --dry-run`, poi senza `--dry-run`.

Il comando rifiuta se: non su `main` allineato, modifiche non salvate, `gh` non è l'account **Tommo2797** (sul Mac dell'autore è collegato anche un secondo account: `gh auth switch`), versione non maggiore dell'ultima release, voce changelog mancante, `tests/private/` assente, test rossi, uv ≠ 0.13.1, zip non valido per l'updater. Poi: versione + data nel changelog + README → commit `release: vX` → tag → push → `gh release create` con `deck-inventory.zip`. `--skip-online` salta i test dal vivo (solo se Piltover Archive non risponde). Se fallisce a metà, il messaggio dice cosa è già stato fatto.

Condividere il tool: link a https://github.com/Tommo2797/deck-inventory/releases/latest → file **`deck-inventory.zip`** negli Assets (non "Source code").

## Contratto da non rompere (launcher congelati)

I launcher distribuiti non si aggiornano mai. Ogni versione futura deve:
- restare avviabile come `python -m deck_inventory.update <ROOT>` e `python -m deck_inventory <ROOT>` con `PYTHONPATH=.app/src`, leggendo `DECK_INVENTORY_LAUNCHER` e `DECK_INVENTORY_UV`;
- funzionare con `uv sync --frozen` di **uv 0.13.1** (pyproject/uv.lock compatibili);
- mantenere `deck_inventory.dialogs.info(str)` (dopo lo scambio l'updater importa i dialoghi della versione nuova), importando solo stdlib/moduli stabili;
- tenere `update.py` solo-stdlib e senza import di tkinter/playwright a livello di modulo.

Se un launcher deve cambiare: aumentare `MIN_LAUNCHER` in `deck_inventory/__init__.py` (oggi 1) e il numero che i launcher esportano; chi ha launcher vecchi riceverà il messaggio "serve scaricarla di nuovo a mano" (una volta per versione). Gli utenti 1.0.0 non hanno l'updater: passano a mano alla 1.1.0 una volta (istruzioni in README → AGGIORNAMENTI).

## Privacy (repo pubblico)

- Nessun dato personale nei file tracciati: niente link/ID del binder dell'autore, percorsi `/Users/...`, email. Test con dati finti (`tests/fixtures/`, link finto `…/users/esempio/collection/00000000-0000-4000-8000-000000000000`).
- Identità git del repo: `Tommo2797 <46868658+Tommo2797@users.noreply.github.com>` (configurata localmente nel repo).
- Ramo locale **`backup/pre-public`**: storia vecchia **con dati personali**. Solo copia di sicurezza, scollegato da GitHub: **non fare mai push**.

## Stato e cose aperte

Verificato: Mac end-to-end (installazione da zero, spostamento cartella, fallback Chromium, aggiornamento con finto GitHub in 5 scenari, download reale da GitHub in sola lettura, release 1.1.0 scaricata e validata con il codice dell'updater).

Da verificare:
- **Windows mai provato** (launcher, lock `msvcrt`, scambio cartelle con file bloccati, `uv sync` annidato mentre python.exe gira).
- **Finestra "aggiornato dalla X alla Y"** mai vista a schermo (testata solo con UI finta): guardarla alla prossima release su un'installazione non-git.
- **Blocco al primo avvio** visto due volte in run di agent: quasi certamente Chrome nel sandbox; confermare con un doppio clic reale su una copia nuova.
- **Binder privato**: rilevato come "privato/inesistente" (con attesa sull'intestazione "User Not Found" e controllo del `<title>`), testato su binder inesistente ma mai su un binder reso privato.

Migliorie rimandate (si possono consegnare con l'auto-update):
- finestra di avanzamento durante download/sync dell'aggiornamento;
- pausa dopo aggiornamenti falliti ripetuti (oggi riprova a ogni avvio);
- timeout DNS (i 3 s non coprono `getaddrinfo`);
- `publish` non rifiuta se un launcher è cambiato senza aumentare `MIN_LAUNCHER`;
- avvio concorrente: il secondo launcher salta l'update (lock) ma può partire mentre il primo scambia i file (non distruttivo, richiede modifica ai launcher);
- piccole: host dello zip non limitato a GitHub, nessun limite di dimensione dello zip, redazione del link in `publish` solo sulla stringa esatta, `set_release_date` con CRLF, nomi di mazzo duplicati in `order.txt` ignorati in silenzio, messaggio "pagina precedente non toccata" impreciso se fallisce l'apertura del browser.

## Differenze rispetto ai piani

- Piano 1.0.0, lettura binder: i dati **non** arrivano da "server action" POST, ma dall'HTML server-rendered (RSC) paginato con `?qtyMin=1&limit=100&page=N`.
- Piano 1.0.0, browser: Opera rimosso; c'è fallback su più candidati e Chromium solo se nessuno parte; il download di Chromium è ~580 MB (non 150).
- Piano 1.0.0, test: i dati reali sono stati spostati in `tests/private/`; i fixture tracciati sono finti.
- Piano 1.1.0: aggiunti lock di aggiornamento, marker `swap-in-progress`, copia via `.partial`, ripristino di ultima istanza; zip da file tracciati git; `publish` valida lo zip e la versione di uv.
