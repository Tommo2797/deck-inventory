# Deck Inventory — backlog

Idee per nuove implementazioni, fix e verifiche ancora da fare. Quando una voce viene fatta, toglierla da qui (lo storico sta in `.app/src/CHANGELOG.txt` e nella storia git).

Contesto del progetto e come lavorarci: `docs/HANDOFF.md`.

## Da verificare

- **Windows mai provato**: launcher, lock `msvcrt`, scambio cartelle con file bloccati, `uv sync` annidato mentre python.exe gira.
- **Finestra "aggiornato dalla X alla Y"** mai vista a schermo (testata solo con UI finta): guardarla alla prossima release su un'installazione non-git.
- **Blocco al primo avvio** visto due volte in run di agent: quasi certamente Chrome nel sandbox; confermare con un doppio clic reale su una copia nuova.
- **Binder privato**: rilevato come "privato/inesistente" (con attesa sull'intestazione "User Not Found" e controllo del `<title>`), testato su binder inesistente ma mai su un binder reso privato.

## Migliorie rimandate

Si possono consegnare con l'aggiornamento automatico.

### Aggiornamento automatico

- Finestra di avanzamento durante download/sync dell'aggiornamento.
- Pausa dopo aggiornamenti falliti ripetuti (oggi riprova a ogni avvio).
- Timeout DNS: i 3 s non coprono `getaddrinfo`.
- Avvio concorrente: il secondo launcher salta l'update (lock) ma può partire mentre il primo scambia i file. Non distruttivo; la correzione richiede una modifica ai launcher (vedi "Contratto da non rompere" in `HANDOFF.md`).
- Host dello zip non limitato a GitHub.
- Nessun limite di dimensione dello zip.

### Pubblicazione (`tools/publish.py`)

- Non rifiuta se un launcher è cambiato senza aumentare `MIN_LAUNCHER`.
- Redazione del link solo sulla stringa esatta.
- `set_release_date` non gestisce il CRLF.

### Programma

- Nomi di mazzo duplicati in `order.txt` ignorati in silenzio.
- Messaggio "pagina precedente non toccata" impreciso se fallisce l'apertura del browser.

## Idee

- **Collezione da lista personale invece che da Piltover Archive.** Togliere la lettura del binder (browser invisibile, Playwright, dipendenza dalla forma del sito) a favore di una lista personale della collezione. Riferimento: il progetto Bulk Scanner (progetto separato dell'autore, cartella accanto a questa), che costruisce la collezione leggendo il codice stampato sulle carte ed esporta `collection.csv`.
- **Da app locale a webapp.** Oggi è un tool locale avviato dai launcher con Python/uv. Valutare cosa cambia per aggiornamento automatico, launcher congelati e lettura della collezione (un browser non può usare Playwright).
- **Anteprima della carta all'hover o al tap.** Mostrare l'immagine della carta passando il mouse o toccando il nome nella pagina generata, usando i dati della gallery ufficiale: https://playriftbound.com/en-us/card-gallery/ (Bulk Scanner già legge il JSON in `__NEXT_DATA__` per costruire `cards.json`).
- **Prezzo medio delle carte.** Mostrare il prezzo medio da Cardmarket (https://www.cardmarket.com/it/Riftbound), ad esempio per le carte mancanti o per il valore dei mazzi. Da capire come ottenere i dati (API, pagina pubblica, limiti d'uso).
- **Fusione con Bulk Scanner.** Da capire in che termini: un solo progetto, oppure uno che produce la collezione e l'altro che la usa. Collegata alle idee sulla lista personale e sulla webapp.
