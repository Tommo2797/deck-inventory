DECK INVENTORY
==============

Confronta le tue liste di mazzi Riftbound con la tua collezione su Piltover
Archive e ti dice quali carte hai già e quali ti mancano.

PRIMO AVVIO
-----------
1. Metti almeno una lista di mazzo (file .txt) nella cartella "decks".
   Se la cartella non c'è, la crea il programma al primo avvio e ti avvisa:
   aggiungi i mazzi e fai di nuovo doppio clic su Start.
2. Doppio clic su "Start (Mac).command" (Mac) oppure "Start (Windows).bat"
   (Windows).
   - Mac: se macOS blocca il file, apri Impostazioni di Sistema → Privacy e
     sicurezza, scorri in basso e clicca "Apri comunque"; poi rifai doppio
     clic sul file.
   - Windows: se compare "Windows ha protetto il PC", clicca "Ulteriori
     informazioni" e poi "Esegui comunque".
3. Prima scarica i componenti necessari dentro la cartella: ci vogliono
   alcuni minuti, serve internet.
4. Poi ti chiede il link del tuo binder (vedi sotto).
5. Se sul computer non c'è un browser tipo Chrome, Edge o Brave, scarica
   anche un browser di alcune centinaia di MB (solo la prima volta).
6. Al termine si apre la pagina con i risultati.

Dai avvii successivi bastano pochi secondi.
Nota: il file per Windows non è ancora stato provato. Il percorso della
cartella non deve contenere i caratteri & o %.

IL LINK DEL BINDER
------------------
Su Piltover Archive apri il tuo binder, clicca "Make Public" e poi "Share":
il link viene copiato. Incollalo quando richiesto. Per cambiarlo in seguito
apri "settings.txt" con un editor di testo e modifica la riga "binder = ...".

AGGIUNGERE UN MAZZO
-------------------
Salva la lista, nel formato esportato dal deckbuilder (sezioni Legend,
Champion, MainDeck, Battlefields, Sideboard, con righe tipo "3 Nome carta"),
come file .txt dentro "decks". Il nome del file è il nome del mazzo.

CAMBIARE L'ORDINE
-----------------
Apri "decks/order.txt": un mazzo per riga, quello in alto ha la priorità più
alta. I mazzi nuovi vengono aggiunti in fondo.

DOVE TROVO L'ULTIMA PAGINA
--------------------------
Nella cartella principale c'è un file "Inventory ....html" con data e ora:
aprilo con un doppio clic. Dopo aver cambiato mazzi o collezione, rifai
doppio clic su Start per aggiornarlo.

SE QUALCOSA NON VA
------------------
Se compare "Piltover Archive è cambiato", il sito è stato modificato:
chiedi una versione aggiornata di Deck Inventory. Nel messaggio e in fondo
alla pagina trovi il numero di versione.

CONDIVIDERE
-----------
Per dare Deck Inventory a qualcun altro copia la cartella TOGLIENDO:
- la cartella ".app/runtime" (i componenti scaricati, molto pesanti);
- il file "settings.txt" (contiene il link al TUO binder);
- le pagine "Inventory ....html" (mostrano la TUA collezione);
- se vuoi, i tuoi mazzi nella cartella "decks".
La cartella ".app" è nascosta: su Mac premi Cmd+Maiusc+. nel Finder per
vederla; su Windows attiva "Elementi nascosti" nel menu Visualizza.
(Per chi usa il terminale: lo script .app/src/tools/make_share_zip.py crea
già uno zip pulito.)

DISINSTALLARE
-------------
Tutto resta dentro questa cartella: per rimuovere ogni cosa basta eliminarla.
