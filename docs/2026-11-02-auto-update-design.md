# Deck Inventory — aggiornamento automatico e storico delle versioni

Data: 2026-11-02 · Stato: bozza da approvare · Progetto di partenza: `docs/2026-10-31-deck-inventory-design.md` (versione 1.0.0)

## Perché

Oggi, per far arrivare una modifica a chi usa il tool, l'autore deve creare uno zip nuovo e ripassarlo a mano. L'obiettivo è che chi ha il tool riceva **da solo** le versioni nuove al doppio clic su Start, e che l'autore decida **quando** una versione è pronta. Chi riceve un aggiornamento deve poter vedere cosa è cambiato.

## Obiettivi

- All'avvio il tool controlla se su GitHub c'è una **versione pubblicata** più nuova della sua. Se sì, la scarica, la installa, avvisa con un messaggio e poi prosegue con il flusso normale. Se no, prosegue subito.
- Solo le versioni **pubblicate di proposito** dall'autore arrivano agli utenti: i normali commit/push su `main` non arrivano a nessuno.
- Un **comando unico** sul Mac dell'autore pubblica una versione.
- Il README contiene uno **storico delle versioni** ("NOVITÀ") con cosa è cambiato in ognuna.

## Non obiettivi

- Nessuna richiesta di permesso prima di aggiornare (deciso dall'utente: si aggiorna da solo e avvisa).
- Nessun ritorno a una versione precedente su richiesta dell'utente.
- Pubblicazione solo dall'autore, dal suo Mac (deciso dall'utente). Niente CI, niente altri pubblicatori.
- Nessun aggiornamento automatico dei file `Start (Mac).command` / `Start (Windows).bat` (vedi "Cosa si aggiorna").

## Anti-obiettivi (fallimento anche se "funziona")

- Un controllo aggiornamenti che **blocca o rallenta** il tool: senza internet, GitHub lento o irraggiungibile, limite di richieste superato → si salta il controllo in silenzio e si usa la versione installata.
- Un aggiornamento interrotto a metà che lascia il tool **rotto o a metà tra due versioni**.
- Un aggiornamento che tocca i **dati dell'utente**: `settings.txt`, `decks/`, le pagine `Inventory …html`, `.app/runtime/` (salvo quanto serve a reinstallare le dipendenze).
- Un aggiornamento che sovrascrive la **copia di sviluppo** dell'autore.
- Pubblicare per sbaglio: versione non più alta dell'ultima, note mancanti, test rossi, modifiche non salvate.

## Contesto tecnico attuale (1.0.0)

- Repository pubblico: `https://github.com/Tommo2797/deck-inventory`, ramo `main`. La CLI `gh` sul Mac dell'autore è collegata all'account `Tommo2797`.
- Versione in `.app/src/deck_inventory/__init__.py` (`VERSION = "1.0.0"`), mostrata nella pagina e nei messaggi di errore.
- I launcher, dopo il guard e `uv sync --frozen --no-dev`, eseguono `uv run --project .app/src --frozen --no-dev python -m deck_inventory "<ROOT>"` con `PYTHONPATH` = `.app/src` e tutte le variabili di isolamento (vedi spec 1.0.0).
- `.app/src/tools/make_share_zip.py` crea lo zip pulito da condividere (esclude runtime, dati utente, docs, .git, tests).
- Le copie 1.0.0 già distribuite **non hanno** l'aggiornamento automatico: chi le ha dovrà ricevere a mano, una volta sola, la prima versione che lo contiene. Da lì in poi si aggiornano da sole.

## Cosa decide l'utente (già deciso)

- Aggiornamento solo quando l'autore **pubblica** una versione.
- Aggiornamento **automatico** con messaggio, senza chiedere.
- **Storico delle versioni** nel README.
- Pubblicazione solo dall'autore, dal suo Mac.

## Comportamento all'avvio

Ordine nuovo del launcher: guard e installazione come oggi → **controllo aggiornamenti** → se c'è stato un aggiornamento, di nuovo `uv sync` (le dipendenze potrebbero essere cambiate) → avvio del programma come oggi.

Controllo aggiornamenti:
1. Se nella cartella del progetto esiste `.git` → **salta** (è la copia di sviluppo dell'autore).
2. Chiede a GitHub l'ultima release pubblicata del repository configurato (API pubblica, senza login, timeout breve: pochi secondi in tutto).
3. Se la versione dell'ultima release non è **più alta** della versione installata (confronto numerico `x.y.z`) → prosegue.
4. Altrimenti scarica l'allegato della release (lo zip pulito), lo verifica e installa la nuova versione **in modo atomico**: o tutto o niente. Se qualcosa va storto la versione installata resta quella di prima, funzionante; il dettaglio va in `.app/runtime/last-error.log` e il tool prosegue con la versione vecchia senza mostrare errori (al prossimo avvio riprova).
5. Se l'aggiornamento è riuscito: messaggio "Deck Inventory è stato aggiornato dalla versione X alla versione Y", con sotto le novità di **tutte** le versioni comprese tra X (esclusa) e Y (inclusa), dalla più recente. Il messaggio si chiude con OK e il flusso prosegue.

Qualsiasi errore di rete, risposta inattesa, limite di richieste di GitHub o assenza di release → si salta il controllo in silenzio (al massimo una riga nel log).

## Cosa si aggiorna

- **Sì**: tutto `.app/src/` e `README.txt`.
- **No**: `Start (Mac).command`, `Start (Windows).bat` (sostituire un file mentre è in esecuzione è rischioso, soprattutto su Windows), `settings.txt`, `decks/`, `Inventory …html`, `.app/runtime/` (tranne lo spazio di lavoro temporaneo dell'aggiornamento e quanto ricrea `uv sync`).
- Conseguenza: la logica nei launcher deve restare minima e stabile. Se in futuro un launcher dovrà cambiare, servirà un meccanismo dedicato (fuori da questo lavoro).

## Storico delle versioni

- **Unica fonte**: un file di novità versionato dentro `.app/src/` (così arriva con l'aggiornamento), scritto dall'autore. Per ogni versione: numero, data, elenco di cambiamenti in italiano semplice.
- Da questa fonte derivano: la sezione "NOVITÀ" del README (dalla più recente), il testo della release su GitHub, il messaggio mostrato dopo l'aggiornamento.
- La prima voce dello storico è **1.0.0** (prima versione) e la prima pubblicata con questo lavoro è **1.1.0** (aggiornamento automatico + storico).

## Comando di pubblicazione (solo autore, Mac)

Un comando unico con la versione come argomento (es. "pubblica 1.1.0"). Controlla e rifiuta di procedere, con messaggio chiaro, se:
- ci sono modifiche non salvate in git o non si è su `main` allineato con GitHub;
- la versione non è nel formato `x.y.z` o non è più alta dell'ultima release pubblicata;
- nel file delle novità manca la voce per quella versione;
- i test non passano;
- `gh` non è collegato all'account che possiede il repository.

Poi, in ordine: aggiorna il numero di versione nel codice, rigenera la sezione "NOVITÀ" del README, crea il commit e il tag `v<versione>`, carica su GitHub, crea lo zip pulito con `make_share_zip.py` e crea la release con lo zip allegato e le note della versione. Se un passo fallisce dopo il commit, il messaggio dice esattamente cosa è stato fatto e cosa no.

## Dove si legge il repository da cui aggiornarsi

L'indirizzo del repository (`Tommo2797/deck-inventory`) è scritto in **un solo punto** del codice, così chi copia il progetto per farne una sua versione lo cambia in un posto solo. (Scelta mia.)

## Sicurezza minima

- Download solo via HTTPS da GitHub, solo l'allegato della release del repository configurato, con nome fisso.
- Lo zip viene estratto in una cartella temporanea dentro `.app/runtime/` e controllato prima dell'installazione: deve avere la struttura attesa e nessun percorso che esca dalla cartella.

## Vincoli emersi dalla revisione (scelte mie)

- **Contratto dei launcher.** I launcher non si aggiornano mai, quindi ogni versione futura deve funzionare con quelli esistenti. Dalla 1.1.0 i launcher passano al programma un proprio **numero di versione del launcher** (parte da 1). Ogni versione del programma dichiara il numero minimo di launcher che le serve. Se una release richiede un launcher più nuovo di quello installato, l'aggiornamento **non** viene installato e compare un messaggio: "È disponibile la versione X, ma per installarla serve scaricare di nuovo Deck Inventory a mano" (con il link alla pagina delle release). Il tool prosegue con la versione attuale. Questo controllo va incluso già nella 1.1.0, perché dopo non si potrebbe più aggiungere.
- **Dipendenze dopo l'aggiornamento.** Tutta la logica dell'aggiornamento sta nel programma Python, che si può aggiornare, e non nei launcher. Dopo aver sostituito i file è il programma stesso a lanciare `uv sync` (il launcher gli passa il percorso di uv). Se `uv sync` fallisce, rimette i file della versione precedente, li risincronizza e prosegue con la vecchia versione, scrivendo il dettaglio nel log. Per i launcher cambia solo questo: prima di avviare il programma eseguono il passo di aggiornamento.
- **Windows non verificato.** Non c'è una macchina Windows su cui provare, quindi lo scambio delle cartelle si fa in modo prudente: più tentativi in caso di file bloccati e copia come ripiego se la rinomina non riesce. Lo scambio avviene prima che il programma principale importi i file nuovi. Il lato Windows resta dichiarato "non verificato".
- **Chi ha la 1.0.0.** Passa alla 1.1.0 a mano una volta sola: scarica lo zip della release, lo estrae in una cartella nuova e ci copia dentro il proprio `settings.txt` e la propria cartella `decks/`. Il README e le note della 1.1.0 lo spiegano. Non è previsto di estrarre lo zip sopra la cartella vecchia.
- **Test prima di pubblicare.** Sono obbligatori i test normali, quelli con i dati privati dell'autore (presenti sul suo Mac) e il test dal vivo su Piltover Archive, che usa il binder dell'autore preso dal `settings.txt` della sua copia di sviluppo. Se il sito è irraggiungibile, l'autore può saltare solo il test dal vivo con un'opzione esplicita, e il comando lo segnala.

## Scelte prese da me (Claude), da controllare

- Se si saltano più versioni, il messaggio mostra le novità di tutte quelle saltate.
- Unico file di novità come fonte per README, release e messaggio.
- I launcher non si aggiornano da soli.
- La copia di sviluppo (con `.git`) non si aggiorna mai da sola.
- Aggiornamento fallito → si resta sulla versione vecchia senza messaggi d'errore, solo log; si riprova al prossimo avvio.
- Indirizzo del repository in un solo punto del codice.
- Prima versione con aggiornamento automatico: 1.1.0.

## Lasciato al builder

- In che punto del launcher e in che modulo Python vive il controllo (purché l'ordine sia quello descritto e il secondo `uv sync` avvenga solo dopo un aggiornamento).
- Formato del file delle novità (purché leggibile e modificabile a mano dall'autore).
- Tecnica di installazione atomica (es. estrazione in cartella temporanea + scambio di cartelle).
- Nome e posizione del comando di pubblicazione e come si lancia (deve usare l'ambiente isolato del progetto).
- Come mostrare il messaggio con le novità (finestra tkinter come gli altri dialoghi).
