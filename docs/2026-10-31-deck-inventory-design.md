# Deck Inventory — documento di progetto

Data: 2026-10-31 · Stato: bozza da approvare

## Perché esiste

L'utente gioca a Riftbound e tiene la propria collezione di carte su Piltover Archive (piltoverarchive.com). Ha diverse liste di mazzi (formato testo esportato dal deckbuilder) e vuole sapere, senza conti a mano, quante copie di ogni carta servono e quante ne possiede: per tutti i mazzi insieme e per ciascun mazzo, con le copie possedute assegnate ai mazzi in ordine di priorità.

Oggi lo fa a mano (export CSV dal sito + script lanciato da un agente AI). L'obiettivo è un tool locale, **senza AI**, che faccia tutto con un doppio clic e che si possa **passare ad altri giocatori**: ognuno lo usa con il proprio binder.

## Obiettivi

- Doppio clic su un file di avvio → si apre una pagina con il confronto mazzi/collezione aggiornato.
- Funziona su **Mac e Windows**, anche su un **computer appena acquistato** senza nulla preinstallato (niente Python, niente Node).
- La collezione si legge **automaticamente** dal binder pubblico su Piltover Archive: niente export manuale, niente login, niente token.
- Il progetto è **una cartella autosufficiente**: si può spostare o copiare ovunque e continua a funzionare; cancellarla rimuove tutto.
- Per condividerlo basta passare la cartella (senza la parte installata) e cambiare il link del binder.
- L'utente standard vede solo quello che gli serve; il resto è nascosto.

## Non obiettivi

- Nessuna modifica della collezione su Piltover Archive (solo lettura).
- Nessun server sempre acceso, nessun account, nessun servizio cloud.
- Nessun riordino dei mazzi dalla pagina (deciso: l'ordine si cambia solo in `order.txt`).
- Nessun conteggio delle rune.

## Anti-obiettivi (sarebbe un fallimento anche se "funziona")

- Riscaricare i ~150 MB a ogni avvio.
- Dipendere da percorsi fuori dalla cartella del progetto (rompersi se la si sposta).
- Richiedere all'utente di installare cose a mano, scrivere nel terminale o copiare token.
- Mostrare una pagina vuota o numeri sbagliati in silenzio quando qualcosa non va (binder privato, link errato, nessuna rete, carta non riconosciuta): l'errore va detto in chiaro.

## Struttura della cartella

```
Deck Inventory/
├── Start (Mac).command          ← doppio clic su Mac
├── Start (Windows).bat          ← doppio clic su Windows
├── settings.txt                 ← link del binder pubblico (unica cosa personale)
├── README.txt                   ← istruzioni brevi (come ottenere il link, come aggiungere mazzi)
├── decks/
│   ├── order.txt                ← ordine/priorità dei mazzi, uno per riga
│   ├── ornn aggro.txt
│   ├── yasuo move.txt
│   └── ...
├── Inventory 2026-10-31 18.40.html   ← generato a ogni avvio (il precedente viene cancellato)
└── .app/                        ← nascosta: script, runtime Python (uv), dipendenze, browser, log
```

- `.app/` è nascosta: su Mac per via del punto iniziale; su Windows il primo avvio le imposta l'attributo "nascosto".
- Tutto ciò che viene installato (uv, Python, librerie, eventuale browser, cache) sta dentro `.app/`.
- Questo documento (`docs/`) è materiale di sviluppo: a fine lavoro va spostato dentro `.app/` o rimosso dalla versione da condividere.

## Flusso d'uso

1. L'utente ha la cartella.
2. Mette almeno una lista in `decks/`.
3. Doppio clic su "Start".
   - Primo avvio: se `settings.txt` non ha un link, una finestra di dialogo chiede di incollarlo e lo salva; poi installa ciò che serve, mostrando l'avanzamento in una finestra di dialogo.
   - Avvii successivi: il guard vede che è tutto installato e passa subito all'aggiornamento (pochi secondi).
4. Si apre nel **browser predefinito** la pagina `Inventory <data ora>.html`.
   - Per rivedere l'ultimo risultato: aprire quel file.
   - Dopo aver cambiato mazzi o collezione: tornare al punto 3.

## Installazione e guard

- Lo script di avvio usa **uv** (scaricato dentro `.app/`) per ottenere Python e le librerie, sempre dentro `.app/` (cache, Python e ambiente compresi: niente nella cartella utente).
- **Guard**: prima di installare controlla cosa c'è già. Si installa solo ciò che manca; i ~150 MB del browser si scaricano al massimo una volta.
- **Cartella spostata**: se l'ambiente Python ha percorsi assoluti non più validi, il guard lo rileva e lo ricrea dalla cache locale, senza riscaricare il browser né Python.
- Se l'installazione si interrompe a metà (rete persa), l'avvio successivo riprende o rifà solo la parte incompleta.

## Lettura della collezione

- Fonte: il **link di condivisione del binder pubblico**, formato `https://piltoverarchive.com/users/<utente>/collection/<id>` (si ottiene su Piltover Archive con "Make Public" → "Share").
- Il binder deve essere pubblico; da sloggati la pagina è visibile.
- Fatti verificati il 2026-10-31:
  - L'API `/api/external/v1/collection…` richiede un token di login (401 senza) e non permette chiamate da altre origini → non usabile.
  - La pagina pubblica del binder carica le carte tramite **Next.js server action** (POST alla stessa URL), non tramite un'API pubblica; l'identificativo dell'azione cambia a ogni deploy del sito → non chiamarla direttamente.
  - L'HTML iniziale della pagina pubblica non contiene le carte (caricate dopo, lato client).
- Metodo deciso: aprire il link in un **browser invisibile** (Playwright) e leggere i dati come li carica la pagina. Come estrarli (risposte di rete intercettate, DOM, eventuale funzione di export presente nella pagina) è lasciato al builder, con il requisito di ottenere **tutte** le carte (il binder di prova ha 1.434 carte; la pagina pagina/carica a blocchi).
- Browser: usare un browser già installato della famiglia Chromium (Chrome, Edge, Brave…), preferendo il predefinito se è di quella famiglia; se il predefinito è Safari/Firefox usare Chrome/Edge se presenti; solo se non c'è nessuno scaricare Chromium (~150 MB) dentro `.app/`.
- Dati necessari per carta: nome e quantità. Più righe con lo stesso nome (varianti: foil, alt art, promo, lingue) **si sommano**. Esempio: Defy 7 normali + 1 foil = 8.
- Campi presenti nell'export CSV del sito, utili come riferimento sul modello dati: `Variant Number, Card Name, Set, Set Prefix, Rarity, Variant Type, Variant Label, Foil, Quantity, Language, Condition, …`.

## Liste dei mazzi

Formato (testo esportato dal deckbuilder), sezioni separate da righe vuote; più mazzi in un file non sono previsti (un file = un mazzo):

```
Legend:
1 Ornn, Fire Below the Mountain

Champion:
1 Ornn, Blacksmith

MainDeck:
3 Defy
...

Battlefields:
1 Ornn's Forge
...

Runes:
8 Calm Rune
4 Mind Rune

Sideboard:
3 Disarming Rake
...
```

- Riga carta: `<quantità> <nome>`; i nomi possono contenere virgole e apostrofi.
- **Rune escluse** da tutti i conteggi (nomi che finiscono con " Rune", es. Calm Rune, Chaos Rune, Mind Rune, Fury Rune). Attenzione: "Runeblade Anvil" non è una rune.
- **Mazzo** = Legend + Champion + MainDeck + Battlefields. **Side** = Sideboard. Entrambi contano nel totale.
- Nome visualizzato del mazzo = nome del file senza `.txt` (es. `ornn aggro.txt` → "Ornn Aggro").
- Righe non riconosciute: segnalarle nella pagina, non ignorarle in silenzio.

## Ordine dei mazzi: `decks/order.txt`

- Un nome di mazzo per riga; l'ordine delle righe è la priorità.
- I file dei mazzi hanno nomi liberi, senza numeri.
- Mazzo presente in `decks/` ma non in `order.txt` → aggiunto in fondo automaticamente e segnalato.
- Riga di `order.txt` senza file corrispondente → ignorata e segnalata.
- Se `order.txt` non esiste → creato con i mazzi in ordine alfabetico.

## Calcoli

Per ogni carta (rune escluse):
- **Servono** = somma delle copie in tutti i mazzi (mazzo + side).
- **Hai** = copie nella collezione (varianti sommate).
- **Mancano** = max(Servono − Hai, 0).

**Assegnazione per mazzo**: le copie possedute si consumano mazzo dopo mazzo nell'ordine di `order.txt`. Ogni mazzo riceve min(copie rimaste, copie richieste dal mazzo). Esempio: servono 9 in 3 mazzi da 3, ne hai 7 → 3/3, 3/3, 3/1. La somma delle mancanti per mazzo coincide con le mancanti totali.

## Pagina dei risultati

Contenuto (già validato dall'utente in versione Markdown):

1. Intestazione: data/ora aggiornamento, link del binder, numero mazzi.
2. **Tutti i mazzi insieme**: riepilogo (copie che servono, che hai, che mancano, carte diverse incomplete) e tabella con colonne `Servono/Hai` (formato `12/8`), `Carta`, `Mancano` (✓ se completa), `Mazzo`, `Side`, `N. mazzi`; ordinata per Servono decrescente, poi nome.
3. **Solo le carte mancanti** (lista della spesa): `4x Defy (12/8)`, ordinata per mancanti decrescente.
4. **Split per mazzo** nell'ordine di `order.txt`: per ogni mazzo riepilogo + tabella con `Servono/Hai` assegnati, `Carta`, `Mancano`, `Mazzo`, `Side`.
5. Avvisi: righe non riconosciute, mazzi aggiunti in fondo, righe di `order.txt` senza file.

Requisiti: un unico file HTML autosufficiente (dati inclusi, nessuna risorsa esterna necessaria), leggibile anche offline. Lingua dell'interfaccia: italiano.

Riferimento: l'output attuale è un riepilogo unificato in Markdown, generato dal file originale delle liste dei mazzi; i 7 mazzi lì presenti sono il materiale di prova (da separare in file singoli).

## Errori da gestire con messaggio chiaro

- `settings.txt` vuoto o link non valido (non del formato binder di Piltover Archive).
- Binder privato o inesistente.
- Nessuna connessione / sito irraggiungibile: mostrare l'errore; se c'è una pagina precedente, non cancellarla.
- Nessun mazzo in `decks/`.
- Nessun browser compatibile e download fallito.

## Decisioni dell'utente

- **Manutenzione quando il sito cambia: a mano, per ora.** Il tool ha un numero di versione visibile (nella pagina e nei messaggi). Se la lettura del binder fallisce perché la pagina non ha più la forma attesa, il messaggio lo dice chiaramente ("Piltover Archive è cambiato, serve una versione aggiornata di Deck Inventory", con la versione attuale). L'utente sistema la propria copia e ripassa la cartella. In futuro: aggiornamento via git (fuori da questo lavoro, ma tenere gli script in `.app/src/` in modo che sia facile metterli sotto git).
- **Interfaccia: niente terminale come interfaccia.** La finestra del terminale aperta dal doppio clic va ridotta al minimo/nascosta quanto la piattaforma permette. Le interazioni avvengono con finestre di dialogo native: richiesta del link al primo avvio (campo di testo), avanzamento ("Installazione in corso…", "Aggiornamento collezione…"), errori. Gli errori compaiono anche nella pagina quando c'è una pagina da mostrare. Il builder sceglie la tecnica (dialoghi nativi del sistema, tkinter se disponibile nel Python di uv, ecc.), purché funzioni su un computer nuovo senza altre installazioni.

## Scelte prese da me (Claude), da controllare

- Nomi dei file in inglese per coerenza con "Deck Inventory" e con `order.txt`: `settings.txt`, `README.txt`, `Start (Mac).command`, `Start (Windows).bat`, `Inventory <data ora>.html`. Interfaccia e README in italiano.
- Linguaggio: Python gestito da uv, tutto dentro `.app/`.
- Se l'aggiornamento fallisce, la pagina precedente non viene cancellata.
- **Abbinamento nomi**: deck e collezione si confrontano per nome normalizzato (maiuscole/minuscole, apostrofi tipografici ' vs ', spazi multipli). Nessuna verifica contro il catalogo completo delle carte: le liste vengono dal deckbuilder, quindi i nomi sono corretti per costruzione; una carta non posseduta mostra semplicemente "Hai = 0". "Riga non riconosciuta" significa solo una riga del file mazzo che non rispetta il formato `<quantità> <nome>` o sta fuori da una sezione nota. Si assume che il binder usi i nomi inglesi delle carte per tutte le lingue (verificato sul CSV: `Card Name` è in inglese).
- **Piattaforme**: macOS 12+ su Apple Silicon e Intel; Windows 10/11 x64 (Windows ARM tramite emulazione x64, senza build dedicata).
- **`.app/` divisa in due**: `.app/src/` (script, versionati, da condividere) e `.app/runtime/` (uv, Python, ambiente, eventuale browser: si ricrea da solo). Il guard registra piattaforma/architettura e percorso dell'installazione: se la cartella è stata spostata o copiata su un'altra macchina/sistema, ricrea solo ciò che non è più valido. Quindi per condividere si può passare la cartella così com'è; il README suggerisce di togliere `.app/runtime/` (o di zippare senza) per alleggerirla.

## Lasciato al builder

- Tecnica esatta di estrazione dei dati dal binder pubblico (vedi sopra).
- Rilevamento del browser predefinito su Mac e Windows.
- Generazione della pagina (template, stile), purché rispetti contenuto e requisiti.
- Formato interno di `settings.txt` (deve restare modificabile a mano da un utente non tecnico).
- Gestione del permesso di esecuzione su Mac (`.command` scaricato da internet → Gatekeeper/quarantena) e relative istruzioni nel README.
